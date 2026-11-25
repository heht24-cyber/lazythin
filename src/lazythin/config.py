"""定位并解析 Syncthing 的 config.xml(GUI 地址 + API key)。"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass
class GuiInfo:
    base_url: str
    api_key: str


def candidate_paths() -> list[Path]:
    out: list[Path] = []
    for env in ("LAZYTHIN_CONFIG", "SYNCTHING_CONFIG"):
        v = os.environ.get(env)
        if v:
            out.append(Path(v))
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(Path(local) / "Syncthing" / "config.xml")
    out.extend([
        home / ".config" / "syncthing" / "config.xml",
        home / ".local" / "state" / "syncthing" / "config.xml",
        home / "Library" / "Application Support" / "Syncthing" / "config.xml",
    ])
    return out


def find_config(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p.resolve()
        raise ConfigError(f"指定的 config 不存在:{p}")
    for p in candidate_paths():
        if p.is_file():
            return p
    tried = "; ".join(str(p) for p in candidate_paths())
    raise ConfigError(f"找不到 Syncthing 的 config.xml(试过:{tried})。可用 --config 显式指定。")


def parse_gui(config_path: Path) -> GuiInfo:
    try:
        root = ET.parse(str(config_path)).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ConfigError(f"config.xml 无法解析:{exc}") from exc
    gui = root.find("gui")
    if gui is None:
        raise ConfigError("config.xml 中没有 <gui> 节点")
    address = (gui.findtext("address") or "127.0.0.1:8384").strip()
    api_key = (gui.findtext("apikey") or "").strip()
    if not api_key:
        raise ConfigError("<gui> 里没有 <apikey>,无法调用本地 API")
    scheme = "https" if (gui.get("tls") or "false").lower() == "true" else "http"
    return GuiInfo(base_url=f"{scheme}://{address}", api_key=api_key)
