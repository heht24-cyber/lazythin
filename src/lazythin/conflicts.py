"""扫描并解决 *.sync-conflict-* 冲突文件。

Syncthing 的冲突副本命名形如:
    file.sync-conflict-20260101-101010-ABC1234.txt   (原文件 file.txt)
也兼容把标记放在最后的旧风格:
    file.txt.sync-conflict-20260101-101010-ABC1234

解决策略(默认全部先出计划,--yes 才执行):
    keep-orig      保留原文件,冲突副本改名 .lazythin-bak(或删除)
    keep-conflict  冲突副本顶替原文件,原文件改名 .lazythin-bak
    keep-both      冲突副本改名为「file (conflict 20260101-101010).txt」
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

CONFLICT_MARKER = ".sync-conflict-"
RE_REST = re.compile(r"^(\d{8}-\d{6})-([^.]*?)(\..*)?$")
SKIP_DIRS = {".stfolder", ".stversions", ".lazythin"}

MODES = ("keep-orig", "keep-conflict", "keep-both")


@dataclass
class Conflict:
    path: Path
    original: Path | None
    stamp: str = ""
    device: str = ""
    size: int = 0
    mtime: float = 0.0


def parse_conflict(path: Path) -> Conflict:
    name = path.name
    i = name.find(CONFLICT_MARKER)
    original: Path | None = None
    stamp = ""
    device = ""
    if i >= 0:
        head = name[:i]
        rest = name[i + len(CONFLICT_MARKER):]
        m = RE_REST.match(rest)
        if m:
            stamp, device, ext = m.group(1), m.group(2), m.group(3) or ""
            if head + ext != name:
                original = path.with_name(head + ext)
    try:
        stat = path.stat()
        size, mtime = stat.st_size, stat.st_mtime
    except OSError:
        size, mtime = 0, 0.0
    return Conflict(path=path, original=original, stamp=stamp, device=device,
                    size=size, mtime=mtime)


def scan(root: Path) -> list[Conflict]:
    out: list[Conflict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if CONFLICT_MARKER in fn:
                out.append(parse_conflict(Path(dirpath) / fn))
    out.sort(key=lambda c: c.mtime, reverse=True)
    return out


def renamed_both(c: Conflict) -> Path:
    assert c.original is not None
    stem = c.original.stem or "file"
    suffix = c.original.suffix
    tag = f" (conflict {c.stamp})" if c.stamp else " (conflict copy)"
    target = c.original.with_name(stem + tag + suffix)
    n = 2
    while target.exists():
        target = c.original.with_name(f"{stem}{tag} {n}{suffix}")
        n += 1
    return target


def plan_resolve(c: Conflict, mode: str, backup: bool = True) -> list[str]:
    if mode not in MODES:
        raise ValueError(f"未知解决方式:{mode}(可选:{'/'.join(MODES)})")
    if c.original is None:
        return [f"跳过 {c.path.name}:无法解析出对应的原文件"]
    if mode == "keep-orig":
        if backup:
            return [f"改名 {c.path.name} -> {c.path.name}.lazythin-bak"]
        return [f"删除 {c.path.name}"]
    if mode == "keep-conflict":
        acts = []
        if backup and c.original.exists():
            acts.append(f"改名 {c.original.name} -> {c.original.name}.lazythin-bak")
        acts.append(f"{c.original.name} 的内容替换为冲突副本 {c.path.name}")
        return acts
    target = renamed_both(c)
    return [f"改名 {c.path.name} -> {target.name}"]


def resolve(c: Conflict, mode: str, backup: bool = True) -> list[str]:
    """执行解决动作,返回实际执行的动作描述(失败抛 OSError)。"""
    if c.original is None:
        return [f"跳过 {c.path.name}:无法解析出对应的原文件"]
    acts: list[str] = []
    if mode == "keep-orig":
        if backup:
            c.path.rename(c.path.with_name(c.path.name + ".lazythin-bak"))
            acts.append(f"改名 {c.path.name} -> {c.path.name}.lazythin-bak")
        else:
            c.path.unlink()
            acts.append(f"删除 {c.path.name}")
    elif mode == "keep-conflict":
        if backup and c.original.exists():
            c.original.rename(c.original.with_name(c.original.name + ".lazythin-bak"))
            acts.append(f"改名 {c.original.name} -> {c.original.name}.lazythin-bak")
        c.path.rename(c.original)
        acts.append(f"{c.original.name} 的内容替换为冲突副本")
    else:
        target = renamed_both(c)
        c.path.rename(target)
        acts.append(f"改名 {c.path.name} -> {target.name}")
    return acts


def unified_diff(c: Conflict) -> str:
    import difflib

    if c.original is None or not c.original.exists():
        return f"(找不到原文件,无法对比:{c.original})"
    try:
        head = c.original.read_bytes()[:1024]
        binary = b"\x00" in head or b"\x00" in c.path.read_bytes()[:1024]
    except OSError as exc:
        return f"(读取失败:{exc})"
    if binary:
        return (f"{c.original.name} 与 {c.path.name} 是二进制文件,不逐行 diff;"
                f"大小 {c.original.stat().st_size} vs {c.size} 字节")
    a = c.original.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    b = c.path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = list(difflib.unified_diff(a, b, fromfile=c.original.name, tofile=c.path.name))
    return "".join(diff) if diff else "(两个文件内容完全一致)"
