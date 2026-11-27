"""命令行入口:默认进 TUI;status / conflicts 子命令。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .api import ApiError, Client
from .conflicts import MODES, parse_conflict, plan_resolve, resolve, scan, unified_diff
from .model import build_snapshot, snapshot_json
from .tui import _enable_vt_windows, fmt_bytes, render_dashboard, run_tui


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lazythin",
        description="Syncthing 终端管家:状态一眼可见,冲突一键收拾。",
        epilog="示例:\n"
               "  lazythin                      # TUI 实时面板\n"
               "  lazythin --once               # 渲染一帧退出(截图/脚本)\n"
               "  lazythin status --json        # 状态快照 JSON\n"
               "  lazythin conflicts            # 扫描冲突文件\n"
               "  lazythin conflicts --diff 'D:\\Share\\a.sync-conflict-….txt'\n"
               "  lazythin conflicts --resolve keep-orig --yes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--config", help="Syncthing config.xml path / 路径(默认自动查找)")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color / 禁用颜色")
    p.add_argument("--lang", choices=["zh", "en"], default=None,
                   help="UI language: en or zh (or set LAZYTHIN_LANG)")
    p.add_argument("--once", action="store_true", help="Render one frame and exit / 渲染一帧后退出")
    p.add_argument("--interval", type=float, default=2.0, help="TUI refresh interval in seconds (default 2)")
    p.add_argument("--timeout", type=float, default=5.0, help="API timeout in seconds (default 5)")
    p.add_argument("--version", action="version", version=f"lazythin {__version__}")
    sub = p.add_subparsers(dest="cmd")

    ps = sub.add_parser("status", help="打印一次状态快照")
    ps.add_argument("--json", action="store_true", help="输出 JSON")

    pc = sub.add_parser("conflicts", help="扫描/对比/解决冲突文件")
    pc.add_argument("--folder", help="只扫描该目录(默认全部已配置文件夹)")
    pc.add_argument("--diff", metavar="FILE", help="打印冲突副本与原文件的 unified diff")
    pc.add_argument("--resolve", choices=list(MODES), help="解决方式")
    pc.add_argument("--yes", action="store_true", help="真正执行(默认只打印计划)")
    pc.add_argument("--no-backup", action="store_true",
                    help="败方直接删除(默认保留为 .lazythin-bak)")
    pc.add_argument("files", nargs="*", help="只处理这些冲突文件(默认全部)")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    if args.cmd is None:
        return _cmd_tui(args)
    if args.cmd == "status":
        return _cmd_status(args)
    return _cmd_conflicts(args)


def _make_client(args) -> Client:
    return Client.from_config(args.config, timeout=args.timeout)


def _use_color(args) -> bool:
    return (not args.no_color) and sys.stdout.isatty() and _enable_vt_windows()


def _lang(args) -> str:
    val = getattr(args, "lang", None) or os.environ.get("LAZYTHIN_LANG", "")
    return "en" if val.lower().startswith("en") else "zh"


def _cmd_tui(args, client=None) -> int:
    lang = _lang(args)
    if client is None:
        try:
            client = _make_client(args)
        except Exception as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
    if args.once:
        try:
            snap = build_snapshot(client)
        except Exception as exc:
            msg = f"Failed to fetch status: {exc}\n" if lang == "en" else f"获取状态失败:{exc}\n"
            sys.stderr.write(msg)
            return 2
        print(render_dashboard(snap, None, _use_color(args), lang=lang))
        return 0
    if not sys.stdin.isatty():
        msg = (
            "TUI requires an interactive terminal; use --once or status --json for scripts.\n"
            if lang == "en"
            else "TUI 需要交互终端;脚本/管道场景请用 --once 或 status --json\n"
        )
        sys.stderr.write(msg)
        return 2
    return run_tui(client, interval=args.interval, use_color=_use_color(args), lang=lang)


def _cmd_status(args, client=None) -> int:
    lang = _lang(args)
    try:
        if client is None:
            client = _make_client(args)
        snap = build_snapshot(client)
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        print(json.dumps(snapshot_json(snap), ensure_ascii=False, indent=2))
    else:
        print(render_dashboard(snap, None, _use_color(args), lang=lang))
        print()
        print("Tip: run `lazythin` to launch the live TUI." if lang == "en" else "提示:直接运行 lazythin 进入实时面板。")
    return 0


def _cmd_conflicts(args, client=None) -> int:
    lang = _lang(args)
    en = lang == "en"
    if args.diff:
        p = Path(args.diff).expanduser()
        if not p.is_file():
            sys.stderr.write(f"File not found: {p}\n" if en else f"文件不存在:{p}\n")
            return 2
        print(unified_diff(parse_conflict(p)))
        return 0

    if args.files:
        conflicts = []
        for f in args.files:
            p = Path(f).expanduser()
            if not p.is_file():
                sys.stderr.write(f"File not found: {p}\n" if en else f"文件不存在:{p}\n")
                return 2
            conflicts.append(parse_conflict(p))
    else:
        roots: list[Path] = []
        if args.folder:
            roots = [Path(args.folder).expanduser()]
        else:
            try:
                if client is None:
                    client = _make_client(args)
                cfg = client.config()
                roots = [Path(f.get("path")) for f in (cfg.get("folders") or []) if f.get("path")]
            except Exception as exc:
                msg = (
                    f"Cannot read folder list: {exc}; pass --folder to scan a directory directly.\n"
                    if en
                    else f"拿不到文件夹列表:{exc};可用 --folder 直接指定目录\n"
                )
                sys.stderr.write(msg)
                return 2
        conflicts = []
        for r in roots:
            if r.exists():
                conflicts.extend(scan(r))

    if not conflicts:
        print("No conflict files found ✅" if en else "没有发现冲突文件 ✅")
        return 0

    for c in conflicts:
        orig = c.original.name if c.original else ("(no original file)" if en else "(无原文件)")
        info = [x for x in (c.stamp, c.device) if x] or ["?"]
        print(f"⚠ {c.path}")
        label = "original" if en else "原文件"
        print(f"   {label} {orig} · {' · '.join(info)} · {fmt_bytes(c.size)}")

    if not args.resolve:
        if en:
            print(f"\nFound {len(conflicts)} conflict(s). Resolve with: --resolve keep-orig|keep-conflict|keep-both "
                  "(dry-run by default; pass --yes to apply)")
        else:
            print(f"\n共 {len(conflicts)} 个冲突。解决:--resolve keep-orig|keep-conflict|keep-both"
                  "(默认只打印计划,加 --yes 执行)")
        return 1

    backup = not args.no_backup
    done = 0
    for c in conflicts:
        if not args.yes:
            for act in plan_resolve(c, args.resolve, backup):
                tag = "[plan]" if en else "[计划]"
                print(f"  {tag} {act}")
        else:
            try:
                for act in resolve(c, args.resolve, backup):
                    tag = "[done]" if en else "[完成]"
                    print(f"  {tag} {act}")
                done += 1
            except OSError as exc:
                tag = "[failed]" if en else "[失败]"
                print(f"  {tag} {c.path.name}:{exc}")
    if args.yes:
        print(f"\nResolved {done}/{len(conflicts)} conflict(s)." if en else f"\n已处理 {done}/{len(conflicts)} 个。")
        return 0 if done == len(conflicts) else 1
    print("\nDry-run plan above. Pass --yes to apply." if en else "\n以上为执行计划,确认无误后加 --yes 执行。")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
