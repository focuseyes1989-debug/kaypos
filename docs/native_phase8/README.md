# KAY POS Native — Phase 8

Date: 2026-09-05  
Status: Release preflight started; local packaged build and smoke test passed

Phase 8 turns the completed Phase 7 source into a separately identifiable Windows distribution and records the remaining deployment acceptance work. The original KAY POS, POS Lite, and Service Job Client entry points remain available.

## Completed in this increment

- Added the separate `KAY POS Native` version identity `0.8.0` and Windows executable metadata.
- Updated the launcher card so Native is no longer described as a Phase 2 preview.
- Added a deterministic `--smoke-test` that opens the Native login UI with a temporary configuration and performs no database, server, or network operation.
- Added a build manifest with version, release channel, minimum display, API identity, source revision/dirty state, executable size, SHA-256, and smoke result.
- Pinned the Native Qt build dependencies and included the required Qt runtime DLLs in the application loading directory. This prevents a packaged `QtWidgets` startup failure caused by mixed or nested Qt runtime resolution.
- Built the isolated onedir distribution at `dist/KAY_POS_Native` and passed its packaged smoke test.

## Verified artifact

- Product: `KAY POS Native`
- Version: `0.8.0`
- Channel: `phase8-preview`
- Minimum display: `1366x768`
- Executable: `KAY_POS_Native.exe`
- Executable size: `7,996,367` bytes
- SHA-256: `01f3379b3c4ce2a94e9bcc39e466159a4230d0f01553584271122ba5e5729028`
- Source revision: `372fdcdb05510b5b79a10bc4ee23d6c97c68c346` with uncommitted Phase 7/8 work
- Packaged smoke test: passed

Build from a clean environment with:

```powershell
python -m venv .venv-native-build
.\.venv-native-build\Scripts\python.exe -m pip install -r requirements-pos-native.txt
.\.venv-native-build\Scripts\python.exe build_native_pos.py
```

The generated `build-manifest.json` is release evidence and belongs beside the executable. Build output is not source-controlled.

The combined Native regression suite passed 199 tests after the packaged build verification.

## Remaining Phase 8 acceptance

The remaining rows in `acceptance.csv` require a deployment or physical device. They must use a backup and a controlled test target where stated. No production restore, server restart, cloud transfer, Telegram send, printer/drawer action, or ZKTeco operation was performed during this local preflight.
