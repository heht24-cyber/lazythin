"""把 REST JSON 翻译成一帧快照(Snapshot)。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def _num(v, default: int = 0) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return default


@dataclass
class SystemInfo:
    my_id: str = ""
    uptime: int = 0
    version: str = ""
    codename: str = ""
    cpu_percent: float | None = None
    errors: list = field(default_factory=list)

    @classmethod
    def from_json(cls, status: dict, version: dict, sys_error: dict | None) -> "SystemInfo":
        cpu = status.get("cpuPercent")
        return cls(
            my_id=str(status.get("myID") or ""),
            uptime=_num(status.get("uptime")),
            version=str(version.get("version") or "") if isinstance(version, dict) else "",
            codename=str(version.get("codename") or "") if isinstance(version, dict) else "",
            cpu_percent=float(cpu) if isinstance(cpu, (int, float)) else None,
            errors=list(sys_error.get("errors") or []) if isinstance(sys_error, dict) else [],
        )


@dataclass
class FolderInfo:
    id: str = ""
    label: str = ""
    path: str = ""
    paused: bool = False
    ftype: str = ""
    # 运行态
    state: str = ""
    need_bytes: int = 0
    global_bytes: int = 0
    insync_bytes: int = 0
    global_files: int = 0
    db_errors: int = 0
    last_error: str = ""

    @classmethod
    def from_config(cls, d: dict) -> "FolderInfo":
        return cls(
            id=str(d.get("id") or ""),
            label=str(d.get("label") or d.get("id") or ""),
            path=str(d.get("path") or ""),
            paused=bool(d.get("paused")),
            ftype=str(d.get("type") or ""),
        )

    def apply_db(self, db: dict | None) -> None:
        if not isinstance(db, dict):
            return
        self.state = str(db.get("state") or "")
        self.need_bytes = _num(db.get("needBytes"))
        self.global_bytes = _num(db.get("globalBytes"))
        self.insync_bytes = _num(db.get("inSyncBytes"))
        self.global_files = _num(db.get("globalFiles"))
        self.db_errors = _num(db.get("errors"))
        self.last_error = str(db.get("error") or "")

    @property
    def progress(self) -> float:
        if self.global_bytes <= 0:
            return 1.0
        return min(1.0, self.insync_bytes / self.global_bytes)


@dataclass
class DeviceInfo:
    id: str = ""
    name: str = ""
    connected: bool = False
    address: str = ""
    ctype: str = ""
    client_version: str = ""
    paused: bool = False
    is_local: bool = False
    in_bytes: int = 0
    out_bytes: int = 0

    @classmethod
    def from_config(cls, d: dict) -> "DeviceInfo":
        return cls(
            # v2 用 deviceID,v1 用 id
            id=str(d.get("deviceID") or d.get("id") or ""),
            name=str(d.get("name") or ""),
        )

    def apply_conn(self, c: dict | None) -> None:
        if not isinstance(c, dict):
            return
        self.connected = bool(c.get("connected"))
        self.address = str(c.get("address") or "")
        self.ctype = str(c.get("type") or "")
        self.client_version = str(c.get("clientVersion") or "")
        self.paused = bool(c.get("paused"))
        self.is_local = bool(c.get("isLocal"))
        self.in_bytes = _num(c.get("inBytesTotal"))
        self.out_bytes = _num(c.get("outBytesTotal"))


@dataclass
class Snapshot:
    system: SystemInfo
    folders: list[FolderInfo] = field(default_factory=list)
    devices: list[DeviceInfo] = field(default_factory=list)
    timestamp: float = 0.0


def build_snapshot(client) -> Snapshot:
    status = client.system_status()
    version = client.system_version()
    sys_error = client.system_errors()
    cfg = client.config()
    if not isinstance(cfg, dict):
        cfg = {}

    folders = [FolderInfo.from_config(f) for f in (cfg.get("folders") or []) if isinstance(f, dict)]
    for f in folders:
        try:
            f.apply_db(client.db_status(f.id))
        except Exception:
            pass  # 单个文件夹状态失败不影响整体

    my_id = str(status.get("myID") or "") if isinstance(status, dict) else ""
    devices = []
    for d in (cfg.get("devices") or []):
        if not isinstance(d, dict):
            continue
        dev = DeviceInfo.from_config(d)
        if not dev.id or dev.id == my_id:
            continue  # 跳过空 id 与本机自身
        devices.append(dev)

    conns = client.connections()
    cmap = conns.get("connections") or {} if isinstance(conns, dict) else {}
    for dev in devices:
        dev.apply_conn(cmap.get(dev.id))
    known = {d.id for d in devices}
    for did, c in (cmap.items() if isinstance(cmap, dict) else []):
        if did not in known and isinstance(c, dict) and c.get("connected"):
            extra = DeviceInfo(id=str(did), name="")
            extra.apply_conn(c)
            devices.append(extra)

    return Snapshot(
        system=SystemInfo.from_json(status, version, sys_error),
        folders=folders,
        devices=devices,
        timestamp=time.time(),
    )


def snapshot_json(s: Snapshot) -> dict:
    return {
        "system": {
            "myID": s.system.my_id,
            "version": s.system.version,
            "codename": s.system.codename,
            "uptime": s.system.uptime,
            "errors": len(s.system.errors),
        },
        "folders": [
            {
                "id": f.id, "label": f.label, "path": f.path, "state": f.state,
                "paused": f.paused, "type": f.ftype,
                "needBytes": f.need_bytes, "globalBytes": f.global_bytes,
                "inSyncBytes": f.insync_bytes, "progress": round(f.progress, 6),
                "errors": f.db_errors,
            }
            for f in s.folders
        ],
        "devices": [
            {
                "id": d.id, "name": d.name, "connected": d.connected,
                "address": d.address, "clientVersion": d.client_version,
                "paused": d.paused,
            }
            for d in s.devices
        ],
    }
