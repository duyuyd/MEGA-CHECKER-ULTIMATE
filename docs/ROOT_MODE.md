# Android Dual Access Mode 10.1.1

MEGA CHECKER is **No-Root first**. ROOT is an optional capability, never a prerequisite.

## Access modes

- `auto` (default): opens the selected file as the Termux app UID first. Only if the OS returns `PermissionError` does it attempt the same explicitly selected file through `su -c cat`.
- `noroot`: never invokes `su`. This is the strict mode for unrooted devices and privacy-conscious runs.
- `root`: requires a usable ROOT grant and streams exactly one explicitly selected absolute file through `su`.

The existing `--root-input` switch remains as a compatibility alias for `--access-mode root`.

## Commands

```bash
# Works on ordinary Android/Termux; never asks for ROOT if the file is readable.
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode auto --format auto

# Strict No-Root mode.
python mega_checker.py audit-dataset -i ~/storage/shared/list.txt --access-mode noroot --format auto

# Optional ROOT route for a specific protected file.
python mega_checker.py audit-dataset -i /data/local/tmp/list.txt --access-mode root --format auto

# Device/access diagnostics; a No-Root result is a successful diagnostic, not a command failure.
python mega_checker.py root-audit
```

## Safety and fallback

- Ordinary parser, HMAC deduplication, SQLite aggregation and reports work unchanged in No-Root mode.
- Automatic fallback occurs only for an OS `PermissionError`; missing files and malformed paths are not silently retried as ROOT.
- ROOT is restricted to read-only diagnostics and one caller-selected file. No arbitrary shell command, recursive crawl, app-private data extraction, system mutation, or account access is provided.
- Reports include `access_mode` (`noroot` or `root`) so results are auditable.
