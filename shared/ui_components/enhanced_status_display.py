# -*- coding: utf-8 -*-
"""
enhanced_status_display.py
強化スチE�Eタス表示�E�E16.5 準拠�E�E
- 斁E���Eイベント購読を廁E��し、STATUS_UPDATE を単一イベントとして購読
- payload の "source" と "kind" で細刁E���E�Eystem / voicevox / queue / health など�E�E
- 可能なら他�E標準イベント！ES_CONNECTED / WS_DISCONNECTED など�E�も購読して表示
"""

from typing import Any, Dict, Optional
import tkinter as tk
from tkinter import ttk

try:
    from shared.message_bus import get_message_bus
    from shared.event_types import Events
except Exception:
    # フォールバック�E�メイン側の安�E化により、ここ�E通常通らなぁE��定！E
    from enum import Enum
    def _upper(x): 
        return x.upper() if isinstance(x, str) else getattr(x, "name", str(x)).upper()
    class Events(Enum):
        STATUS_UPDATE = "STATUS_UPDATE"
        WS_CONNECTED = "WS_CONNECTED"
        WS_DISCONNECTED = "WS_DISCONNECTED"
    class _FB:
        def __init__(self): self._s = {}
        def publish(self, ev, data=None, **kw): 
            for cb in self._s.get(_upper(ev), []): cb(data, **kw)
        def subscribe(self, ev, cb, **kw):
            self._s.setdefault(_upper(ev), []).append(cb)
    def get_message_bus(): return _FB()

SOURCE_LABELS = {
    "system": "🖥�E�ESystem",
    "voicevox": "🎤 VoiceVox",
    "queue": "🧺 Queue",
    "health": "🩺 Health",
    "obs_effects": "📺 OBS",
    "unknown": "❁EUnknown"
}

class EnhancedStatusDisplay(ttk.Frame):
    """
    単一 STATUS_UPDATE イベントを起点に、ソース別の状態を表示
    侁Epayload:
      {
        "source": "system" | "voicevox" | "queue" | "health" | "obs_effects",
        "kind": "status" | "effect_preview" | "metric" | ...,
        "message": "...",
        "preset": "...",
        "level": "info" | "warn" | "error",
        "extra": { ... }
      }
    """
    def __init__(self, parent: tk.Misc, message_bus=None, config_manager=None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.bus = message_bus or get_message_bus()
        self.config_manager = config_manager

        self.state_vars: Dict[str, tk.StringVar] = {}
        self._build_ui()
        self._subscribe()

    # ===== UI =====
    def _build_ui(self) -> None:
        self.pack(fill=tk.BOTH, expand=True)

        root = ttk.Frame(self)
        root.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Label(root, text="📊 スチE�Eタス・ダチE��ュボ�EチE, font=("", 12, "bold")).pack(anchor="w")

        grid = ttk.Frame(root)
        grid.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self._add_row(grid, "system")
        self._add_row(grid, "voicevox")
        self._add_row(grid, "queue")
        self._add_row(grid, "health")
        self._add_row(grid, "obs_effects")

    def _add_row(self, parent: tk.Misc, source_key: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=3)

        lbl = ttk.Label(row, text=SOURCE_LABELS.get(source_key, SOURCE_LABELS["unknown"]), width=14)
        lbl.pack(side=tk.LEFT)

        var = tk.StringVar(value=" E)
        self.state_vars[source_key] = var
        val = ttk.Label(row, textvariable=var)
        val.pack(side=tk.LEFT, padx=(6, 0))

    # ===== 購読 =====
    def _subscribe(self) -> None:
        # 旧: 斁E���Eイベント購読は廁E���E�E
        # ("system_status_update", ...), ("voicevox_status_update", ...), ...
        # 新: STATUS_UPDATE ひとつに雁E��E
        self.bus.subscribe(Events.STATUS_UPDATE, self._on_status_update)

        # 任愁E WebSocket接続系をあわせて表示
        if hasattr(Events, "WS_CONNECTED"):
            self.bus.subscribe(Events.WS_CONNECTED, lambda _d, **k: self._set("system", "WS: Connected"))
        if hasattr(Events, "WS_DISCONNECTED"):
            self.bus.subscribe(Events.WS_DISCONNECTED, lambda _d, **k: self._set("system", "WS: Disconnected"))

    # ===== ハンドラ =====
    def _on_status_update(self, data: Optional[Dict[str, Any]], **kwargs) -> None:
        try:
            source = str((data or {}).get("source") or "unknown").lower()
            kind = (data or {}).get("kind") or "status"
            level = (data or {}).get("level") or "info"

            # メチE��ージの整形
            msg = (data or {}).get("message")
            preset = (data or {}).get("preset")
            if kind == "effect_preview" and preset:
                text = f"Effect: {preset}"
            elif msg:
                text = str(msg)
            else:
                text = f"{kind}"

            # レベルに応じた付加
            if level == "warn":
                text = f"⚠�E�E{text}"
            elif level == "error":
                text = f"❁E{text}"

            self._set(source, text)

        except Exception as e:
            self._set("system", f"❁ESTATUS_UPDATE error: {e}")

    # ===== 状態更新 =====
    def _set(self, source: str, text: str) -> None:
        key = source if source in self.state_vars else "unknown"
        self.state_vars[key].set(text)

# Factory�E�他タブから利用�E�E
def create_status_display(parent, message_bus=None, config_manager=None):
    return EnhancedStatusDisplay(parent, message_bus=message_bus, config_manager=config_manager)
