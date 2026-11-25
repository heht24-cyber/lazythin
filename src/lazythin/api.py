"""Syncthing REST API 客户端(只读;兼容 v1/v2 端点形状)。"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request

from .config import find_config, parse_gui


class ApiError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        if base_url.startswith("https://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE  # Syncthing GUI 常用自签名证书
            self._ctx = ctx
        else:
            self._ctx = None

    @classmethod
    def from_config(cls, explicit_config: str | None = None, **kw) -> "Client":
        gui = parse_gui(find_config(explicit_config))
        return cls(gui.base_url, gui.api_key, **kw)

    def get(self, path: str, params: dict | None = None):
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-API-Key": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:
            raise ApiError(f"请求 {path} 失败:{type(exc).__name__}: {exc}") from exc

    # ---- 只读端点 ----
    def system_status(self):
        return self.get("/rest/system/status")

    def system_version(self):
        return self.get("/rest/system/version")

    def system_errors(self):
        return self.get("/rest/system/error")

    def config(self):
        return self.get("/rest/config")

    def db_status(self, folder_id: str):
        return self.get("/rest/db/status", {"folder": folder_id})

    def connections(self):
        return self.get("/rest/system/connections")
