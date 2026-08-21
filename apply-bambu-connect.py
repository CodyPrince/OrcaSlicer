#!/usr/bin/env python3
"""
Safely apply Cody's saved Bambu Connect unified patch to the latest Orca source.

Why this exists:
Git's normal patch application can reject a patch when Orca moves code to new
line numbers or changes patch metadata, even when the actual surrounding source
text is still compatible. This script ignores patch line numbers and applies
each hunk by matching the real old source text.

Safety behavior:
- If a hunk's old text is found exactly, it is replaced.
- If the new text is already present, that hunk is treated as already applied.
- If neither old nor new text can be found, the script stops with an error.
It never guesses or silently forces a questionable change.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hunk:
    old_lines: list[str]
    new_lines: list[str]
    header: str


@dataclass
class FilePatch:
    path: str
    hunks: list[Hunk]


def parse_patch(patch_text: str) -> list[FilePatch]:
    lines = patch_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    files: list[FilePatch] = []
    current: FilePatch | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if not m:
                raise RuntimeError(f"Could not parse patch file header: {line}")
            current = FilePatch(path=m.group(2), hunks=[])
            files.append(current)
            i += 1
            continue

        if line.startswith("@@ "):
            if current is None:
                raise RuntimeError(f"Found hunk before file header: {line}")

            header = line
            old_lines: list[str] = []
            new_lines: list[str] = []
            i += 1

            while i < len(lines):
                hline = lines[i]
                if hline.startswith("diff --git ") or hline.startswith("@@ "):
                    break
                if hline.startswith("\\ No newline at end of file"):
                    i += 1
                    continue
                if hline.startswith(" "):
                    text = hline[1:]
                    old_lines.append(text)
                    new_lines.append(text)
                elif hline.startswith("-") and not hline.startswith("---"):
                    old_lines.append(hline[1:])
                elif hline.startswith("+") and not hline.startswith("+++"):
                    new_lines.append(hline[1:])
                elif hline.startswith(("index ", "--- ", "+++ ")):
                    pass
                elif hline == "":
                    # A truly empty patch-control line can occur at EOF.
                    pass
                else:
                    raise RuntimeError(f"Unexpected patch line in {current.path}: {hline!r}")
                i += 1

            current.hunks.append(Hunk(old_lines=old_lines, new_lines=new_lines, header=header))
            continue

        i += 1

    if not files:
        raise RuntimeError("No file patches were found.")

    return files


def find_subsequence(haystack: list[str], needle: list[str], *, trailing_ws_insensitive: bool = False) -> list[int]:
    if not needle:
        return []

    if trailing_ws_insensitive:
        h = [x.rstrip() for x in haystack]
        n = [x.rstrip() for x in needle]
    else:
        h = haystack
        n = needle

    last = len(h) - len(n)
    return [i for i in range(last + 1) if h[i:i + len(n)] == n]


def apply_file_patch(root: Path, fp: FilePatch) -> tuple[int, int]:
    target = root / fp.path
    if not target.exists():
        raise RuntimeError(f"Required Orca file does not exist: {fp.path}")

    raw = target.read_bytes()
    newline = "\r\n" if raw.count(b"\r\n") > raw.count(b"\n") / 2 else "\n"
    text = raw.decode("utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    had_final_newline = normalized.endswith("\n")
    lines = normalized.split("\n")
    if had_final_newline:
        lines = lines[:-1]

    applied = 0
    already = 0

    for hunk_index, hunk in enumerate(fp.hunks, start=1):
        old_matches = find_subsequence(lines, hunk.old_lines)
        if not old_matches:
            old_matches = find_subsequence(lines, hunk.old_lines, trailing_ws_insensitive=True)

        if len(old_matches) == 1:
            start = old_matches[0]
            lines[start:start + len(hunk.old_lines)] = hunk.new_lines
            applied += 1
            print(f"APPLIED  {fp.path} hunk {hunk_index}")
            continue

        if len(old_matches) > 1:
            raise RuntimeError(
                f"Unsafe: {fp.path} hunk {hunk_index} matched {len(old_matches)} places. "
                "Refusing to guess."
            )

        new_matches = find_subsequence(lines, hunk.new_lines)
        if not new_matches:
            new_matches = find_subsequence(lines, hunk.new_lines, trailing_ws_insensitive=True)

        if new_matches:
            already += 1
            print(f"ALREADY  {fp.path} hunk {hunk_index}")
            continue

        raise RuntimeError(
            f"Our saved Bambu Connect change no longer has a safe match in {fp.path} "
            f"(hunk {hunk_index}: {hunk.header}). "
            "Orca changed this area enough that the saved feature needs a deliberate refresh."
        )

    output = "\n".join(lines)
    if had_final_newline:
        output += "\n"
    if newline == "\r\n":
        output = output.replace("\n", "\r\n")
    target.write_bytes(output.encode("utf-8"))

    return applied, already


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("patch", type=Path)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()

    patch_text = args.patch.read_text(encoding="utf-8")
    file_patches = parse_patch(patch_text)

    total_applied = 0
    total_already = 0

    for fp in file_patches:
        a, b = apply_file_patch(args.source_root, fp)
        total_applied += a
        total_already += b

    print()
    print(f"Bambu Connect patch complete: {total_applied} hunks applied, {total_already} already present.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
