# Orca + OBN Managed Package

This folder controls Cody's managed Windows x64 Orca/OBN package.

## What the managed build does

- Uses the untouched official OrcaSlicer `nightly-builds` Windows x64 installer.
- Builds Open Bamboo Networking from the current upstream `master`.
- Layers `CodyPrince/open-bamboo-networking:fix/issue-78-printer-selection` onto that upstream source.
- Applies the Windows DirectShow H2C camera fix only when equivalent `lv=rtsps` handling is not already upstream.
- Builds and tests OBN in GitHub Actions.
- Packages the official Orca installer, managed OBN plugin files, and a manifest containing source SHAs and SHA256 hashes.
- Updates the rolling prerelease tag `orca-obn-managed-latest`.

## Safety choices

The first managed build stays pinned to OBN ABI `02.03.00.99`, matching the proven working setup. It intentionally does **not** switch the installed system to a newer OBN ABI or automatically replace the current working Orca/OBN installation.

The existing local `Update-Orca.cmd` / verification setup remains the recovery path until the managed package has passed hardware testing.

## Camera fix

OBN can return a local camera URL carrying `lv=rtsps` for H.264 printers. On Windows, Orca's DirectShow path receives that URL through `BambuSource.dll`. The saved patch makes the DirectShow URL parser honor that hint and use RTSPS/H.264 on port 322 instead of treating it as MJPEG on port 6000.

Once upstream OBN contains equivalent logic, the workflow detects it and stops applying the saved patch.