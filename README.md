# lazythin

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0_(stdlib_only)-2da44e.svg)](pyproject.toml)

English | [简体中文](README.zh-CN.md)

> **Syncthing in your terminal: live status at a glance, `.sync-conflict` files cleaned up in one command.**

*`lazythin` = `lazy` (like lazygit) + `syncthing`.* A lightweight daily driver for Syncthing users who don't want to open a browser just to check sync progress or untangle conflict files. **Zero third-party dependencies — pure Python standard library.**

## Why lazythin?

Syncthing is rock-solid, except for two recurring paper cuts:

1. **Checking status means opening a browser.** Want to know if a folder is stuck, whether a peer is online, or how much is left to transfer? You have to open `127.0.0.1:8384`.
2. **Conflict files pile up silently.** When two devices edit the same file, Syncthing creates `report.sync-conflict-20261125-193000-WKFLOR2.txt` with no easy built-in way to diff and clean them up safely. This is one of Syncthing's longest-running user pain points (see upstream issues [#2584](https://github.com/syncthing/syncthing/issues/2584), [#2282](https://github.com/syncthing/syncthing/issues/2282), [#8604](https://github.com/syncthing/syncthing/issues/8604)).

Existing terminal tools — Go's [syncthingtui](https://github.com/Evidlo/syncthingtui) and [stc](https://github.com/tenox7/stc), Rust's [stui](https://github.com/corcoran/stui) — focus mainly on monitoring or config and require platform-specific binaries. `lazythin` focuses on:

- **Zero dependencies, cross-platform**: runs anywhere Python 3.9+ is installed (Windows, Linux, macOS) — no compiler or platform binary needed.
- **End-to-end conflict workflow**: scan → unified diff → safe resolution (dry-run by default + losing file moved to `.lazythin-bak`, never silently deleted).
- **Scriptable**: `--once` and `status --json` for dashboards, monitoring, or shell pipelines.

## Quick Start

Install in one line with `pipx`, `uv`, or `pip`:

```console
# Recommended (isolated CLI)
$ pipx install git+https://github.com/heht24-cyber/lazythin.git

# Or run directly without installing via uv
$ uvx --from git+https://github.com/heht24-cyber/lazythin.git lazythin

# Or with pip
$ pip install git+https://github.com/heht24-cyber/lazythin.git
```

Then just run:

```console
$ lazythin
```

`lazythin` automatically locates your local Syncthing `config.xml`, reads the GUI address and API key, and connects immediately.

**TUI keybindings**: `r` refresh now · `c` switch to conflicts view · `q` quit (auto-refreshes every 2s by default; adjust with `--interval`).

Sample output (real Syncthing v2.1.7 instance):

```console
$ lazythin --once
  lazythin  ·  syncthing v2.1.7 "Hafnium Hornet"  ·  local B3B6IYX…  ·  uptime 10h 11m  ·  CPU 0.0%
  ──────────────────────────────────────────────────────────
  Folders (1)
  ● Shared           idle       ▓▓▓▓▓▓▓▓▓▓ 100.0%  need 21.7 KiB
     D:\Share · sendreceive · errors 4

  Devices (1)
  ● NixSurface       [fd7a:115c:a1e0::c836:3f27]:35774  v2.1.3
  ──────────────────────────────────────────────────────────
```

*(Actively syncing folders display a progress bar and live transfer rate, e.g. `↓ 12.3 MiB/s ↑ 1.1 MiB/s`, computed across refresh ticks. Note: current TUI labels are in Chinese; English UI localization is welcome via PR.)*

## Resolve Conflict Files in 3 Steps

```console
# 1. Scan all Syncthing folders for .sync-conflict-* files
$ lazythin conflicts
⚠ D:\Share\docs\report.sync-conflict-20261125-193000-WKFLOR2.txt
   original: report.txt · 20261125-193000 · WKFLOR2 · 20 B

# 2. Inspect a unified diff against the original file
$ lazythin conflicts --diff 'D:\Share\docs\report.sync-conflict-20261125-193000-WKFLOR2.txt'
--- report.txt
+++ report.sync-conflict-20261125-193000-WKFLOR2.txt
@@ -1,2 +1,2 @@
 Line 1
-old content
+new content

# 3. Preview (dry-run by default), then execute with --yes
$ lazythin conflicts --resolve keep-conflict --yes
  [done] rename report.txt -> report.txt.lazythin-bak
  [done] replace report.txt with conflict copy
```

### Resolution Modes

| Strategy | Behavior |
| :--- | :--- |
| `keep-orig` | Keep the original file; move the conflict copy to `.lazythin-bak` |
| `keep-conflict` | Replace original with the conflict copy; move original to `.lazythin-bak` |
| `keep-both` | Rename conflict copy to `report (conflict 20261125-193000).txt` and keep both |

**Safety by design**: dry-run is the default — nothing changes on disk until you pass `--yes`. By default, the discarded version is moved to `.lazythin-bak` instead of deleted (pass `--no-backup` to delete permanently). Binary files automatically skip line-by-line diff.

Conflict filename parsing matches Syncthing's official `conflictName()` in `lib/model/folder_sendrecv.go` (`<stem>.sync-conflict-YYYYMMDD-HHMMSS-<deviceID><ext>`) and also supports legacy suffix-style conflict names.

## Scripting & Automation

```console
$ lazythin status --json      # Machine-readable status snapshot
$ lazythin --once             # Render one frame and exit (monitoring / CI)
```

Exit codes: `conflicts` returns `1` when unresolved conflicts are found (`0` when clean), and `2` when the Syncthing API is unreachable.

## Compatibility & Security

- Tested against **Syncthing v2.1.7**; all 5 REST endpoints used are non-deprecated official APIs, compatible with both v2 (`deviceID`) and v1 (`id`) schemas.
- **Read-only API calls only** (`/rest/system/status`, `/rest/config`, `/rest/db/status`, `/rest/system/connections`, etc.) — `lazythin` never mutates your Syncthing configuration.
- Auto-discovers `config.xml` on Windows (`%LOCALAPPDATA%\Syncthing`), Linux (`~/.config/syncthing`, `~/.local/state/syncthing`), and macOS (`~/Library/Application Support/Syncthing`), or accepts `--config <path>`. API key stays local.
- Handles self-signed HTTPS GUI endpoints automatically.

## Limitations (v0.1)

- Uses lightweight local polling (2s default) rather than SSE/event streaming.
- Skips `.stversions` archive folders during conflict scans by design.

## Development & Tests

```console
$ git clone https://github.com/heht24-cyber/lazythin
$ cd lazythin
$ pip install -e .
$ python -m unittest discover -s tests -v
```

40 unit tests using offline fixtures captured from real Syncthing v2.1.7 API responses.

## License

MIT
