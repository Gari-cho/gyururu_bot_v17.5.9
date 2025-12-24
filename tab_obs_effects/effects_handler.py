# -*- coding: utf-8 -*-
"""
effects_handler.py - OBS演出タブ: メッセージとエフェクトの管理（最小導線）
- 役割別のメッセージキュー
- エフェクトの簡易キュー
"""

from __future__ import annotations
import time
from typing import Dict, List, Tuple, Any

# ロール定数を constants.py から取得
from .constants import ROLE_STREAMER, ROLE_AI, ROLE_VIEWER


class EffectsHandler:
    """配信者/AI/視聴者メッセージの蓄積と、オーバーレイ用エフェクトのキュー管理。"""

    def __init__(self) -> None:
        # Phase X: (name, text, effect_type, ts) に拡張
        self._q_streamer: List[Tuple[str, str, str, float]] = []
        self._q_ai: List[Tuple[str, str, str, float]] = []
        self._q_viewer: List[Tuple[str, str, str, float]] = []
        # effects: list of {"id": "confetti", "params": {...}, "ts": ...}
        self._effects: List[Dict[str, Any]] = []

    # ========== メッセージ ==========
    def push_message(
        self,
        role: str,
        name: str,
        text: str,
        effect_type: str = "fadeUp",
        ts: float | None = None
    ) -> None:
        """
        メッセージをキューに追加（Phase X: effectType対応）

        Args:
            role: ROLE_STREAMER / ROLE_AI / ROLE_VIEWER
            name: 配信者名 or AI名 or 視聴者名
            text: メッセージ本文
            effect_type: エフェクトタイプ (fadeUp, pop, drop, glow, slide)
            ts: タイムスタンプ（未指定時は現在時刻）
        """
        ts = float(ts or time.time())
        item = (name or "", text or "", effect_type or "fadeUp", ts)
        if role == ROLE_STREAMER:
            self._q_streamer.append(item)
        elif role == ROLE_AI:
            self._q_ai.append(item)
        else:
            self._q_viewer.append(item)

    def clear_messages(self) -> None:
        self._q_streamer.clear()
        self._q_ai.clear()
        self._q_viewer.clear()

    def snapshot_messages(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        オーバーレイJSON用の整形済みスナップショットを返す（Phase X: effectType対応）

        timeline は ts 昇順にソートされる（視聴者コメント表示安定化のため）
        """
        def to_items(role: str, q: List[Tuple[str, str, str, float]]) -> List[Dict[str, Any]]:
            return [
                {
                    "role": role,
                    "name": n,
                    "body": t,
                    "effectType": et,
                    "ts": ts
                }
                for (n, t, et, ts) in q
            ]

        # 全ロールのメッセージを連結
        timeline = (
            to_items(ROLE_STREAMER, self._q_streamer)
            + to_items(ROLE_AI, self._q_ai)
            + to_items(ROLE_VIEWER, self._q_viewer)
        )

        # ★ timeline を ts 昇順にソート（視聴者コメント表示バグ修正）
        timeline = sorted(timeline, key=lambda item: item.get("ts", 0.0))

        return {
            "timeline": timeline,
            "streamer": to_items(ROLE_STREAMER, self._q_streamer),
            "ai": to_items(ROLE_AI, self._q_ai),
            "viewer": to_items(ROLE_VIEWER, self._q_viewer),
        }

    # ========== エフェクト ==========
    def enqueue_effect(self, effect_id: str, params: Dict[str, Any] | None = None) -> None:
        self._effects.append({
            "id": effect_id,
            "params": params or {},
            "ts": time.time(),
        })

    def drain_effects(self) -> List[Dict[str, Any]]:
        """キューの中身を返して空にする。"""
        out = list(self._effects)
        self._effects.clear()
        return out
