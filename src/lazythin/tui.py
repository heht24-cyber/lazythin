"""TUI:实时面板渲染 + 按键循环(零依赖,Windows/Unix 通用)。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from .conflicts import Conflict, scan as scan_conflicts
from .model import Snapshot, build_snapshot

try:
    from .api import ApiError
except ImportError:  # pragma: no cover
    class ApiError(RuntimeError):  # type: ignore
        pass

SPIN = "|/-\\"
_CODE = {
    "red": "31", "green": "32", "yellow": "33", "cyan": "36",
    "dim": "90", "bold": "1", "white": "97",
}


class _C:
    def __init__(self, on: bool):
        self.on = on

    def __call__(self, name: str, s: str) -> str:
        code = _CODE.get(name)
        if not self.on or not code:
            return s
        return f"\x1b[{code}m{s}\x1b[0m"

    def bold(self, s): return self("bold", s)
    def dim(self, s): return self("dim", s)
    def red(self, s): return self("red", s)
    def green(self, s): return self("green", s)
    def yellow(self, s): return self("yellow", s)


def fmt_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TiB"


def fmt_uptime(sec: int) -> str:
    d, r = divmod(int(sec), 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def bar(frac: float, width: int = 10) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    return "▓" * filled + "░" * (width - filled)


def _short_addr(addr: str, limit: int = 34) -> str:
    if len(addr) <= limit:
        return addr
    return addr[:12] + "…" + addr[-(limit - 15):]


def _folder_mark(f, spin: str):
    if f.paused:
        return "‖", "dim"
    state = (f.state or "").lower()
    if "error" in state:
        return "●", "red"
    if "sync" in state:
        return spin, "yellow"
    if "scan" in state:
        return spin, "cyan"
    if state == "idle":
        return "●", "green"
    return "●", "yellow"


def _rate(prev: Snapshot | None, cur: Snapshot, dev) -> str:
    if prev is None:
        return ""
    pd = next((d for d in prev.devices if d.id == dev.id), None)
    if pd is None or not dev.connected or not pd.connected:
        return ""
    dt = cur.timestamp - prev.timestamp
    if dt <= 0.2:
        return ""
    in_rate = max(0.0, (dev.in_bytes - pd.in_bytes) / dt)
    out_rate = max(0.0, (dev.out_bytes - pd.out_bytes) / dt)
    if in_rate < 1 and out_rate < 1:
        return ""
    return f"↓ {fmt_bytes(in_rate)}/s ↑ {fmt_bytes(out_rate)}/s"


def render_dashboard(s: Snapshot, prev: Snapshot | None = None,
                     use_color: bool = True, spin: str = "-") -> str:
    C = _C(use_color)
    info = s.system
    head = [C.bold("lazythin")]
    if info.version:
        ver = f"syncthing {info.version}"
        if info.codename:
            ver += f" \"{info.codename}\""
        head.append(ver)
    if info.my_id:
        head.append(f"本机 {info.my_id[:7]}…")
    head.append(f"已运行 {fmt_uptime(info.uptime)}")
    if info.cpu_percent is not None:
        head.append(f"CPU {info.cpu_percent:.1f}%")

    lines = ["  " + "  ·  ".join(head)]
    if info.errors:
        last = info.errors[0]
        msg = str(last.get("message", ""))[:60] if isinstance(last, dict) else ""
        lines.append(C.red(f"  ✖ 系统错误 {len(info.errors)} 条 {msg}"))
    lines.append("  " + "─" * 58)

    lines.append(C.bold(f"  文件夹 {len(s.folders)}"))
    if not s.folders:
        lines.append(C.dim("  (没有配置共享文件夹)"))
    for f in s.folders:
        mark, color = _folder_mark(f, spin)
        name = (f.label or f.id or "?")[:16]
        state = "已暂停" if f.paused else (f.state or "未知")
        name_col = f"{name:<16}"
        state_col = f"{state[:10]:<10}"
        if f.need_bytes > 0 or f.state == "syncing":
            row = (f"  {mark} {C(color, name_col)} {C(color, state_col)} "
                   f"{bar(f.progress)} {f.progress * 100:5.1f}%  需 {fmt_bytes(f.need_bytes)}")
        else:
            row = (f"  {mark} {C(color, name_col)} {C(color, state_col)} "
                   f"{fmt_bytes(f.insync_bytes)} / {fmt_bytes(f.global_bytes)}"
                   f"  {f.global_files} 项")
        lines.append(row)
        sub = f.path or "(路径未知)"
        if f.ftype:
            sub += f" · {f.ftype}"
        if f.db_errors:
            sub += C.red(f" · 错误 {f.db_errors}")
        lines.append(C.dim(f"     {sub}"))

    lines.append("")
    lines.append(C.bold(f"  设备 {len(s.devices)}"))
    if not s.devices:
        lines.append(C.dim("  (没有其他设备)"))
    for d in s.devices:
        name = (d.name or d.id[:7] or "?")[:16]
        if d.paused:
            lines.append(f"  ‖ {C('dim', f'{name:<16}')} 已暂停")
        elif d.connected:
            extra = _short_addr(d.address)
            if d.client_version:
                extra += f"  {d.client_version}"
            rate = _rate(prev, s, d)
            if rate:
                extra += f"  {rate}"
            lines.append(f"  ● {C('green', f'{name:<16}')} {extra}")
        else:
            lines.append(f"  ○ {C('dim', f'{name:<16}')} 离线")

    lines.append("  " + "─" * 58)
    return "\n".join(lines)


def render_conflicts(conflicts: list[Conflict], roots: list[Path],
                     use_color: bool = True) -> str:
    C = _C(use_color)
    lines = [C.bold(f"  冲突文件 {len(conflicts)} 个")]
    if roots:
        scope = " ; ".join(str(r) for r in roots)
        lines.append(C.dim(f"  扫描范围:{scope}"))
    lines.append("")
    if not conflicts:
        lines.append(C.green("  ✅ 没有冲突文件,干净"))
    for c in conflicts:
        orig = c.original.name if c.original else "(无原文件)"
        info = [x for x in (c.stamp, c.device) if x]
        info.append(fmt_bytes(c.size))
        lines.append(f"  ⚠ {C('yellow', c.path.name)}")
        lines.append(C.dim(f"     原文件 {orig} · {' · '.join(info)}"))
    lines.append("")
    lines.append(C.dim("  差异与解决用命令行:lazythin conflicts --diff <文件>"))
    lines.append(C.dim("                 lazythin conflicts --resolve keep-orig|keep-conflict|keep-both --yes"))
    lines.append("  c / 回车 返回状态面板 · q 退出")
    return "\n".join(lines)


def _enable_vt_windows() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return True
        mode.value |= 0x0004
        return bool(k.SetConsoleMode(h, mode))
    except Exception:
        return False


class _TermGuard:
    """隐藏光标;Unix 上进入 cbreak 原始终端模式。"""

    def __init__(self, ansi: bool):
        self.ansi = ansi
        self._saved = None

    def __enter__(self):
        if self.ansi:
            sys.stdout.write("\x1b[?25l")
            sys.stdout.flush()
        if os.name != "nt":
            import termios
            import tty
            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc):
        if self._saved is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSAFLUSH, self._saved)
        if self.ansi:
            sys.stdout.write("\x1b[?25h\n")
        else:
            sys.stdout.write("\n")
        sys.stdout.flush()
        return False


def _wait_key(seconds: float) -> str | None:
    """等一个按键;超时返回 None。"""
    if os.name == "nt":
        import msvcrt
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    msvcrt.getwch()  # 功能/方向键第二段,忽略
                    return None
                if ch in ("\x03", "\x1b"):
                    return "q"
                return ch.lower() if ch.isalpha() else ch
            time.sleep(0.05)
        return None
    import select
    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if not ready:
        return None
    ch = sys.stdin.read(1)
    if ch in ("\x03", "\x1b"):
        return "q"
    return ch.lower() if ch.isalpha() else ch


def run_tui(client, interval: float = 2.0, use_color: bool = True) -> int:
    prev: Snapshot | None = None
    show_conflicts = False
    conflicts: list[Conflict] = []
    roots: list[Path] = []
    spin_i = 0
    C = _C(use_color)

    with _TermGuard(use_color):
        while True:
            snap: Snapshot | None = None
            error = None
            try:
                snap = build_snapshot(client)
            except ApiError as exc:
                error = str(exc)
            except Exception as exc:  # config/网络等
                error = f"{type(exc).__name__}: {exc}"

            clear = "\x1b[2J\x1b[H" if use_color else ""
            if error is not None:
                body = ["  " + C.red(f"连不上 Syncthing:{error}"),
                        "  r 重试 · q 退出"]
            elif show_conflicts:
                body = render_conflicts(conflicts, roots, use_color).splitlines()
            else:
                body = render_dashboard(snap, prev, use_color, SPIN[spin_i % 4]).splitlines()
                prev = snap
            sys.stdout.write(clear + "\n".join(body) + "\n")
            sys.stdout.flush()
            spin_i += 1

            key = _wait_key(interval)
            if key == "q":
                return 0
            if key == "r":
                continue
            if key == "c":
                show_conflicts = not show_conflicts
                if show_conflicts and snap is not None:
                    roots = [Path(f.path) for f in snap.folders if f.path]
                    conflicts = []
                    for r in roots:
                        if r.exists():
                            conflicts.extend(scan_conflicts(r))
            elif key in ("\r", "\n", " ") and show_conflicts:
                show_conflicts = False
