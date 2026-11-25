""" canned REST 数据,形状取自真实 Syncthing v2.1.7 探测结果。"""

from __future__ import annotations


def fake_api_data() -> dict:
    return {
        "status": {"myID": "B3B6IYX-DEMO-DEVICE-ID01", "uptime": 36166, "cpuPercent": 0.7},
        "version": {"version": "v2.1.7", "codename": "Hafnium Hornet"},
        "error": {"errors": []},
        "config": {
            "folders": [{
                "id": "shared", "label": "Shared", "path": "D:\\Share",
                "paused": False, "type": "sendreceive",
            }],
            "devices": [
                {"deviceID": "WKFLOR2-DEMO1-DEVICE", "name": "PC_HE"},
                {"deviceID": "NIXSURF-DEMO2-DEVICE", "name": "NixSurface"},
                {"deviceID": "", "name": "坏条目"},
            ],
        },
        "db": {
            "shared": {
                "state": "idle", "needBytes": 22268, "globalBytes": 13677899567,
                "inSyncBytes": 13677877299, "globalFiles": 4069, "errors": 4, "error": "",
            },
        },
        "connections": {
            "connections": {
                "WKFLOR2-DEMO1-DEVICE": {
                    "connected": True,
                    "address": "[fd7a:115c:a1e0::c836:3f27]:35774",
                    "type": "tcp-server", "clientVersion": "v2.1.3",
                    "paused": False, "isLocal": False,
                    "inBytesTotal": 1000, "outBytesTotal": 2000,
                },
                "NIXSURF-DEMO2-DEVICE": {
                    "connected": False, "address": "", "type": "",
                    "clientVersion": "", "paused": False, "isLocal": False,
                    "inBytesTotal": 0, "outBytesTotal": 0,
                },
            },
        },
    }


class FakeClient:
    """测试用 Client 替身,接口与 lazythin.api.Client 一致。"""

    def __init__(self, data: dict | None = None):
        self.data = data or fake_api_data()

    def system_status(self):
        return self.data["status"]

    def system_version(self):
        return self.data["version"]

    def system_errors(self):
        return self.data["error"]

    def config(self):
        return self.data["config"]

    def db_status(self, folder_id: str):
        return self.data["db"].get(folder_id, {})

    def connections(self):
        return self.data["connections"]
