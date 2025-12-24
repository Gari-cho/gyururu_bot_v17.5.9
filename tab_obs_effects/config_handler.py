# -*- coding: utf-8 -*-
"""
config_handler.py - OBS演出タブ用 設定ハンドラ（軽量版）
- 外部の UnifiedConfigManager / ConfigManager が注入されればそれを使用
- 未注入時は内部辞書で get/set/save を成立させる
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, List, Optional

# 絵文字プリセットをインポート
from .emoji_presets import EMOJI_EFFECT_PRESETS

# ロガー初期化
logger = logging.getLogger(__name__)


class OBSEffectsConfig:
    """設定ハンドラ（最小構成）。上位から config_manager を注入できる。"""

    # 組み込みプリセット一覧（削除禁止）
    BUILTIN_PRESETS: List[str] = [
        "default", "minimal", "pop", "clean", "comic", "neon",
        "kawaii_pastel", "kawaii_bubble", "kawaii_neon_pink",
        "cool_dark", "cool_gradient_feel"
    ]

    DEFAULTS: Dict[str, Any] = {
        # ========== OBSキャンバス解像度設定 ==========
        # OBSの基本（キャンバス）解像度と同じ考え方
        "obs.canvas.preset": "1920x1080",  # 1920x1080 / 2560x1440 / 1280x720 / 1280x1024 / custom
        "obs.canvas.width": 1920,          # キャンバス幅（px）
        "obs.canvas.height": 1080,         # キャンバス高さ（px）

        # ========== コメント表示プリセット設定 ==========
        "obs.comment.active_preset": "default",  # 現在選択中のプリセット
        "obs.comment.presets": {
            # デフォルトプリセット（現在の見た目）
            "default": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#000000",
                "bubble.background.opacity": 75,
                "bubble.border.enabled": False,
                "bubble.border.color": "#FFFFFF",
                "bubble.border.width": 1,
                "bubble.border.radius": 8,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#000000",
                "bubble.shadow.blur": 8,
                "style.font.family": "Yu Gothic UI, Meiryo, sans-serif",
                # ⚠ S-2: フォントサイズの初期値は JSON / UI で管理する。
                #   ここで数値をハードコードすると、ユーザーが変更しても
                #   14px / 16px などに勝手に戻ってしまうため、
                #   当面はコメントアウトして変更禁止とする。
                # "style.font.size_px": 16,
                # "style.name.font.size": 14,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 16,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 2,
                "style.text.shadow.enabled": False,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 2,
                "style.text.shadow.offset_y": 2,
                "style.text.shadow.blur": 0,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 12,
                "style.layout.padding.right": 16,
                "style.layout.padding.bottom": 12,
                "style.layout.padding.left": 16,
                "role.streamer.color": "#4A90E2",
                "role.ai.color": "#9B59B6",
                "role.viewer.color": "#7F8C8D",
                "effect.type.streamer": "fadeUp",
                "effect.type.ai": "pop",
                "effect.type.viewer": "fadeUp",
            },
            # ミニマルプリセット（シンプル・洗練）
            "minimal": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "square",
                "bubble.background.color": "#FFFFFF",
                "bubble.background.opacity": 95,
                "bubble.border.enabled": True,
                "bubble.border.color": "#E0E0E0",
                "bubble.border.width": 1,
                "bubble.border.radius": 4,
                "bubble.shadow.enabled": False,
                "bubble.shadow.color": "#000000",
                "bubble.shadow.blur": 0,
                "style.font.family": "Yu Gothic UI, Helvetica, sans-serif",
                # ⚠ S-2: フォントサイズはコメントアウト（理由は上記参照）
                # "style.font.size_px": 14,
                # "style.name.font.size": 12,
                "style.name.font.bold": False,
                "style.name.font.italic": False,
                # "style.body.font.size": 14,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 0,
                "style.text.shadow.enabled": False,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 0,
                "style.layout.line_height": 1.4,
                "style.layout.padding.top": 8,
                "style.layout.padding.right": 12,
                "style.layout.padding.bottom": 8,
                "style.layout.padding.left": 12,
                "role.streamer.color": "#333333",
                "role.ai.color": "#666666",
                "role.viewer.color": "#999999",
                "effect.type.streamer": "fadeUp",
                "effect.type.ai": "fadeUp",
                "effect.type.viewer": "fadeUp",
            },
            # ポッププリセット（明るい・カラフル）
            "pop": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#FF69B4",
                "bubble.background.opacity": 90,
                "bubble.border.enabled": True,
                "bubble.border.color": "#FFFFFF",
                "bubble.border.width": 3,
                "bubble.border.radius": 16,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#FF1493",
                "bubble.shadow.blur": 12,
                "style.font.family": "Yu Gothic UI, Comic Sans MS, sans-serif",
                # "style.font.size_px": 18,
                # "style.name.font.size": 16,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 18,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": True,
                "style.text.outline.color": "#FFFFFF",
                "style.text.outline.width": 2,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 2,
                "style.text.shadow.offset_y": 2,
                "style.text.shadow.blur": 4,
                "style.layout.line_height": 1.6,
                "style.layout.padding.top": 16,
                "style.layout.padding.right": 20,
                "style.layout.padding.bottom": 16,
                "style.layout.padding.left": 20,
                "role.streamer.color": "#FFD700",
                "role.ai.color": "#00FFFF",
                "role.viewer.color": "#FF69B4",
                "effect.type.streamer": "pop",
                "effect.type.ai": "pop",
                "effect.type.viewer": "pop",
            },
            # クリーンプリセット（モダン・すっきり）
            "clean": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#FFFFFF",
                "bubble.background.opacity": 90,
                "bubble.border.enabled": False,
                "bubble.border.color": "#CCCCCC",
                "bubble.border.width": 0,
                "bubble.border.radius": 12,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#000000",
                "bubble.shadow.blur": 16,
                "style.font.family": "Yu Gothic UI, Segoe UI, sans-serif",
                # "style.font.size_px": 15,
                # "style.name.font.size": 13,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 15,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 0,
                "style.text.shadow.enabled": False,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 0,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 14,
                "style.layout.padding.right": 18,
                "style.layout.padding.bottom": 14,
                "style.layout.padding.left": 18,
                "role.streamer.color": "#2196F3",
                "role.ai.color": "#9C27B0",
                "role.viewer.color": "#607D8B",
                "effect.type.streamer": "fadeUp",
                "effect.type.ai": "slide",
                "effect.type.viewer": "fadeUp",
            },
            # コミックプリセット（漫画風）
            "comic": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "comic",
                "bubble.background.color": "#FFFFFF",
                "bubble.background.opacity": 100,
                "bubble.border.enabled": True,
                "bubble.border.color": "#000000",
                "bubble.border.width": 3,
                "bubble.border.radius": 20,
                "bubble.shadow.enabled": False,
                "bubble.shadow.color": "#000000",
                "bubble.shadow.blur": 0,
                "style.font.family": "Yu Gothic UI, Comic Sans MS, cursive",
                # "style.font.size_px": 16,
                # "style.name.font.size": 14,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 16,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": True,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 2,
                "style.text.shadow.enabled": False,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 0,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 14,
                "style.layout.padding.right": 18,
                "style.layout.padding.bottom": 14,
                "style.layout.padding.left": 18,
                "role.streamer.color": "#FF5722",
                "role.ai.color": "#4CAF50",
                "role.viewer.color": "#3F51B5",
                "effect.type.streamer": "pop",
                "effect.type.ai": "drop",
                "effect.type.viewer": "pop",
            },
            # ネオンプリセット（光る・派手）
            "neon": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#0A0A0A",
                "bubble.background.opacity": 85,
                "bubble.border.enabled": True,
                "bubble.border.color": "#00FFFF",
                "bubble.border.width": 2,
                "bubble.border.radius": 10,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#00FFFF",
                "bubble.shadow.blur": 20,
                "style.font.family": "Yu Gothic UI, Arial, sans-serif",
                # "style.font.size_px": 17,
                # "style.name.font.size": 15,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 17,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 0,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#00FFFF",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 8,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 14,
                "style.layout.padding.right": 18,
                "style.layout.padding.bottom": 14,
                "style.layout.padding.left": 18,
                "role.streamer.color": "#FF00FF",
                "role.ai.color": "#00FFFF",
                "role.viewer.color": "#FFFF00",
                "effect.type.streamer": "glow",
                "effect.type.ai": "glow",
                "effect.type.viewer": "glow",
            },
            # 可愛いパステルプリセット（ふんわり・優しい）
            "kawaii_pastel": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#FFE5F0",
                "bubble.background.opacity": 92,
                "bubble.border.enabled": True,
                "bubble.border.color": "#FFB3D9",
                "bubble.border.width": 2,
                "bubble.border.radius": 18,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#FFB3D9",
                "bubble.shadow.blur": 10,
                "style.font.family": "Yu Gothic UI, Meiryo, sans-serif",
                # "style.font.size_px": 16,
                # "style.name.font.size": 15,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 16,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#FFFFFF",
                "style.text.outline.width": 1,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#FFB3D9",
                "style.text.shadow.offset_x": 1,
                "style.text.shadow.offset_y": 1,
                "style.text.shadow.blur": 3,
                "style.layout.line_height": 1.6,
                "style.layout.padding.top": 14,
                "style.layout.padding.right": 18,
                "style.layout.padding.bottom": 14,
                "style.layout.padding.left": 18,
                "role.streamer.color": "#FF69B4",
                "role.ai.color": "#DDA0DD",
                "role.viewer.color": "#98D8C8",
                "effect.type.streamer": "pop",
                "effect.type.ai": "pop",
                "effect.type.viewer": "pop",
            },
            # 可愛い吹き出しプリセット（漫画風・カラフル）
            "kawaii_bubble": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "comic",
                "bubble.background.color": "#FFFFFF",
                "bubble.background.opacity": 100,
                "bubble.border.enabled": True,
                "bubble.border.color": "#FF69B4",
                "bubble.border.width": 4,
                "bubble.border.radius": 20,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#FFB3D9",
                "bubble.shadow.blur": 8,
                "style.font.family": "Yu Gothic UI, Comic Sans MS, sans-serif",
                # "style.font.size_px": 17,
                # "style.name.font.size": 16,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 17,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 0,
                "style.text.shadow.enabled": False,
                "style.text.shadow.color": "#000000",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 0,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 16,
                "style.layout.padding.right": 20,
                "style.layout.padding.bottom": 16,
                "style.layout.padding.left": 20,
                "role.streamer.color": "#FF1493",
                "role.ai.color": "#FF69B4",
                "role.viewer.color": "#FFB347",
                "effect.type.streamer": "pop",
                "effect.type.ai": "pop",
                "effect.type.viewer": "pop",
            },
            # 可愛いネオンピンクプリセット（目立つ・キラキラ）
            "kawaii_neon_pink": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#FF1493",
                "bubble.background.opacity": 88,
                "bubble.border.enabled": True,
                "bubble.border.color": "#FF69B4",
                "bubble.border.width": 3,
                "bubble.border.radius": 16,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#FF69B4",
                "bubble.shadow.blur": 18,
                "style.font.family": "Yu Gothic UI, Arial, sans-serif",
                # "style.font.size_px": 17,
                # "style.name.font.size": 16,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 17,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": True,
                "style.text.outline.color": "#FFFFFF",
                "style.text.outline.width": 2,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#00FFFF",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 6,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 15,
                "style.layout.padding.right": 20,
                "style.layout.padding.bottom": 15,
                "style.layout.padding.left": 20,
                "role.streamer.color": "#FFFF00",
                "role.ai.color": "#00FFFF",
                "role.viewer.color": "#FFB3D9",
                "effect.type.streamer": "glow",
                "effect.type.ai": "glow",
                "effect.type.viewer": "glow",
            },
            # 格好いいダークプリセット（クール・シャープ）
            "cool_dark": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#0D0D0D",
                "bubble.background.opacity": 92,
                "bubble.border.enabled": True,
                "bubble.border.color": "#00BFFF",
                "bubble.border.width": 2,
                "bubble.border.radius": 6,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#00BFFF",
                "bubble.shadow.blur": 12,
                "style.font.family": "Yu Gothic UI, Arial, sans-serif",
                # "style.font.size_px": 16,
                # "style.name.font.size": 15,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 16,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": False,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 0,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#00BFFF",
                "style.text.shadow.offset_x": 0,
                "style.text.shadow.offset_y": 0,
                "style.text.shadow.blur": 4,
                "style.layout.line_height": 1.4,
                "style.layout.padding.top": 12,
                "style.layout.padding.right": 16,
                "style.layout.padding.bottom": 12,
                "style.layout.padding.left": 16,
                "role.streamer.color": "#00BFFF",
                "role.ai.color": "#1E90FF",
                "role.viewer.color": "#4169E1",
                "effect.type.streamer": "slide",
                "effect.type.ai": "slide",
                "effect.type.viewer": "slide",
            },
            # 格好いいグラデ風プリセット（高級感・ゴージャス）
            "cool_gradient_feel": {
                "display.flow.direction": "DOWN",
                "bubble.enabled": True,
                "bubble.shape": "rounded",
                "bubble.background.color": "#1A0A2E",
                "bubble.background.opacity": 90,
                "bubble.border.enabled": True,
                "bubble.border.color": "#FFD700",
                "bubble.border.width": 2,
                "bubble.border.radius": 10,
                "bubble.shadow.enabled": True,
                "bubble.shadow.color": "#8B00FF",
                "bubble.shadow.blur": 16,
                "style.font.family": "Yu Gothic UI, Georgia, serif",
                # "style.font.size_px": 16,
                # "style.name.font.size": 15,
                "style.name.font.bold": True,
                "style.name.font.italic": False,
                # "style.body.font.size": 16,
                "style.body.font.bold": False,
                "style.body.font.italic": False,
                "style.text.outline.enabled": True,
                "style.text.outline.color": "#000000",
                "style.text.outline.width": 1,
                "style.text.shadow.enabled": True,
                "style.text.shadow.color": "#FFD700",
                "style.text.shadow.offset_x": 1,
                "style.text.shadow.offset_y": 1,
                "style.text.shadow.blur": 4,
                "style.layout.line_height": 1.5,
                "style.layout.padding.top": 14,
                "style.layout.padding.right": 18,
                "style.layout.padding.bottom": 14,
                "style.layout.padding.left": 18,
                "role.streamer.color": "#FFD700",
                "role.ai.color": "#C0C0C0",
                "role.viewer.color": "#DAA520",
                "effect.type.streamer": "drop",
                "effect.type.ai": "drop",
                "effect.type.viewer": "drop",
            },
        },

        # ========== 絵文字エフェクト プリセット設定 ==========
        # 絵文字エフェクトプリセット（emoji_presets.py から読み込み）
        "obs.effects.presets": EMOJI_EFFECT_PRESETS,

        # ========== 出力設定 ==========
        # 出力モード: "HTML" or "TEXT"
        "display.output.mode": "HTML",

        # ========== タイムライン設定 ==========
        # タイムラインに視聴者コメントを含めるか
        "display.timeline.include_viewer": False,
        # タイムライン方向: "UP" or "DOWN" or "SIDE_SCROLL"
        "display.timeline.direction": "UP",

        # 表示件数設定（0で制限なし）
        "display.max_items.streamer": 0,
        "display.max_items.ai": 0,
        "display.max_items.timeline": 5,
        "display.max_items.viewer": 0,

        # ========== コメントの流れ設定 (Phase X) ==========
        "display.flow.direction": "DOWN",  # UP / DOWN / SIDE_SCROLL / LEFT / RIGHT (デフォルト: DOWN = 上から下へ)
        "display.flow.speed": 3.0,  # 横スクロール速度（秒）
        "display.flow.pad_bottom": True,  # UP時に下端揃え

        # ========== 表示モード設定 ==========
        "display.area.mode": "SEPARATE",  # TIMELINE or SEPARATE (旧仕様・互換性のため残す)

        # ========== 表示エリア設定 v17.5.x 新構造 ==========
        "display_area": {
            "mode": "single",  # "single" または "multi"

            "single": {
                "area": {"x": 50, "y": 0, "w": 400, "h": 360},
                "max_items": 10,
                "ttl": 8,
                "flow": "vertical"
            },

            "multi": {
                "streamer": {
                    "enabled": True,
                    "area": {"x": 50, "y": 0, "w": 400, "h": 360},
                    "max_items": 10,
                    "ttl": 8,
                    "flow": "vertical"
                },
                "ai": {
                    "enabled": True,
                    "area": {"x": 50, "y": 0, "w": 400, "h": 360},
                    "max_items": 10,
                    "ttl": 8,
                    "flow": "vertical"
                },
                "viewer": {
                    "enabled": True,
                    "area": {"x": 50, "y": 0, "w": 400, "h": 360},
                    "max_items": 10,
                    "ttl": 8,
                    "flow": "vertical"
                }
            }
        },

        # ========== 表示エリア設定 (旧仕様・互換性のため残す) ==========
        "display.area.preset": "custom",
        "display.area.x": 50,      # 左端からの距離（px）
        "display.area.y": 0,       # 上端からの距離（px）※左下固まり問題の対策
        "display.area.width": 400,
        "display.area.height": 600,

        # ========== 表示者選択 ==========
        "display.show.streamer": True,
        "display.show.ai": True,
        "display.show.viewer": True,

        # ========== TTL（自動消去）設定 (Phase X) ==========
        # file_backend.py が読み込むキー (ttl.*.enabled/seconds)
        "ttl.streamer.enabled": False,
        "ttl.streamer.seconds": 10,
        "ttl.ai.enabled": False,
        "ttl.ai.seconds": 10,
        "ttl.viewer.enabled": False,
        "ttl.viewer.seconds": 10,

        # app.py の UI が使うキー (expire.*.enabled/seconds) - 互換性のため残す
        "expire.streamer.enabled": False,
        "expire.streamer.seconds": 10,
        "expire.ai.enabled": False,
        "expire.ai.seconds": 10,
        "expire.viewer.enabled": False,
        "expire.viewer.seconds": 10,

        # ========== 吹き出し設定 (Phase X) ==========
        "bubble.enabled": True,
        "bubble.shape": "rounded",  # rounded / square / comic
        "bubble.background.color": "#000000",
        "bubble.background.opacity": 75,  # 0-100
        "bubble.border.enabled": False,
        "bubble.border.color": "#FFFFFF",
        "bubble.border.width": 1,
        "bubble.border.radius": 8,
        "bubble.shadow.enabled": True,
        "bubble.shadow.color": "#000000",
        "bubble.shadow.blur": 8,

        # ========== フォント・スタイル設定 (Phase X) ==========
        "style.font.family": "Yu Gothic UI, Meiryo, sans-serif",
        # "style.font.size_px": 16,

        # 配信者名のスタイル
        # "style.name.font.size": 14,
        "style.name.font.bold": True,
        "style.name.font.italic": False,
        "style.name.use_custom_color": False,
        "style.name.custom_color": "#FFFFFF",

        # 本文のスタイル
        # "style.body.font.size": 16,
        "style.body.font.bold": False,
        "style.body.font.italic": False,
        "style.body.indent": 0,

        # テキスト装飾
        "style.text.outline.enabled": False,
        "style.text.outline.color": "#000000",
        "style.text.outline.width": 2,
        "style.text.shadow.enabled": False,
        "style.text.shadow.color": "#000000",
        "style.text.shadow.offset_x": 2,
        "style.text.shadow.offset_y": 2,

        # レイアウト
        "style.layout.name_position": "TOP_LEFT",  # 名前の位置プリセット
        "style.layout.name_offset_x": 0,  # 名前のX座標オフセット
        "style.layout.name_offset_y": 0,  # 名前のY座標オフセット
        "style.layout.name_body_spacing": 4,  # 名前と本文の間隔
        "style.layout.line_height": 1.5,
        "style.layout.padding.top": 12,
        "style.layout.padding.right": 16,
        "style.layout.padding.bottom": 12,
        "style.layout.padding.left": 16,

        # 背景
        "style.background.color": "#000000",
        "style.background.opacity": 75,
        "style.background.border_radius": 8,
        "style.background.border.enabled": False,
        "style.background.border.color": "#FFFFFF",
        "style.background.border.width": 1,

        # ========== 役割別カラー設定 (Phase X) ==========
        "role.streamer.color": "#4A90E2",
        "role.ai.color": "#9B59B6",
        "role.viewer.color": "#7F8C8D",

        # ========== エフェクト設定 (Phase X) ==========
        "effect.type.streamer": "fadeUp",
        "effect.type.ai": "pop",
        "effect.type.viewer": "fadeUp",

        # ========== 出力先設定 ==========
        # 出力先ディレクトリ
        "output.dir": "./overlay_out",
        # data.json のファイル名（overlay.html は固定生成）
        "output.data_filename": "data.json",
    }

    def __init__(self, config_manager: Optional[Any] = None, persist_path: Optional[str] = None) -> None:
        self._external = config_manager
        self._defaults = dict(self.DEFAULTS)
        # 内部辞書（外部が無い場合のみ使用）
        self._store: Dict[str, Any] = dict(self.DEFAULTS)
        # フォールバックの保存先（外部マネージャ無しのときだけ使う）
        self._persist_path = persist_path or os.path.join(".","overlay_out",".obs_effects_config.json")

        if self._external is None:
            # 可能なら前回保存を読み込み
            try:
                if os.path.exists(self._persist_path):
                    with open(self._persist_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self._store.update(data)
            except Exception:
                pass

        # 後方互換性: 古い設定をdefaultプリセットに統合
        self._migrate_to_presets()

        # 新しいプリセットを自動的にマージ
        self._merge_new_presets()

    def _migrate_to_presets(self) -> None:
        """古い設定ファイル（プリセットキーなし）を自動的にdefaultプリセットに統合"""
        # プリセットキーが存在しない場合のみマイグレーション
        if self.get("obs.comment.active_preset") is None:
            # 既存の各種設定値を読み取ってdefaultプリセットに統合
            preset_keys = [
                "display.flow.direction",
                "bubble.enabled", "bubble.shape", "bubble.background.color", "bubble.background.opacity",
                "bubble.border.enabled", "bubble.border.color", "bubble.border.width", "bubble.border.radius",
                "bubble.shadow.enabled", "bubble.shadow.color", "bubble.shadow.blur",
                "style.font.family", "style.font.size_px",
                "style.name.font.size", "style.name.font.bold", "style.name.font.italic",
                "style.body.font.size", "style.body.font.bold", "style.body.font.italic",
                "style.text.outline.enabled", "style.text.outline.color", "style.text.outline.width",
                "style.text.shadow.enabled", "style.text.shadow.color",
                "style.text.shadow.offset_x", "style.text.shadow.offset_y", "style.text.shadow.blur",
                "style.layout.line_height",
                "style.layout.padding.top", "style.layout.padding.right",
                "style.layout.padding.bottom", "style.layout.padding.left",
                "role.streamer.color", "role.ai.color", "role.viewer.color",
                "effect.type.streamer", "effect.type.ai", "effect.type.viewer",
            ]

            # 既存値を読み取り
            default_preset = {}
            for key in preset_keys:
                value = self.get(key)
                if value is not None:
                    default_preset[key] = value

            # defaultプリセットとして保存
            if default_preset:
                presets = self.get("obs.comment.presets", {})
                if not isinstance(presets, dict):
                    presets = {}
                presets["default"] = default_preset
                self.set("obs.comment.presets", presets)
                self.set("obs.comment.active_preset", "default")
                self.save()
                print("[Config] 古い設定をdefaultプリセットに統合しました")

    def _merge_new_presets(self) -> None:
        """DEFAULTSに定義されている新しいプリセットを既存の設定にマージ"""
        # DEFAULTSからプリセット定義を取得
        default_presets = self.DEFAULTS.get("obs.comment.presets", {})
        if not isinstance(default_presets, dict):
            return

        # 現在の設定からプリセットを取得
        current_presets = self.get("obs.comment.presets", {})
        if not isinstance(current_presets, dict):
            current_presets = {}

        # 新しいプリセットがあればマージ
        updated = False
        for preset_name, preset_data in default_presets.items():
            if preset_name not in current_presets:
                current_presets[preset_name] = preset_data
                updated = True
                logger.info(f"新しいプリセット '{preset_name}' を追加しました")

        # 更新があれば保存
        if updated:
            self.set("obs.comment.presets", current_presets)
            self.save()

    # ========== 基本操作 ==========
    def get(self, key: str, default: Any = None) -> Any:
        if self._external and hasattr(self._external, "get"):
            try:
                value = self._external.get(key, default)
                return self._defaults.get(key, value) if value is None else value
            except Exception:
                # 外部が壊れても止めない
                return self._defaults.get(key, default)
        # 内部辞書
        return self._store.get(key, self._defaults.get(key, default))

    def set(self, key: str, value: Any) -> None:
        if self._external and hasattr(self._external, "set"):
            try:
                self._external.set(key, value)
                return
            except Exception:
                # 外部が壊れても内部に逃がす
                pass
        self._store[key] = value

    def save(self) -> None:
        if self._external and hasattr(self._external, "save"):
            try:
                self._external.save()
                return
            except Exception:
                # 外部保存に失敗しても内部保存へ
                pass
        # 内部保存
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ========== プリセット操作 ==========
    def get_preset_names(self) -> List[str]:
        """利用可能なプリセット名のリストを返す"""
        presets = self.get("obs.comment.presets", {})
        if isinstance(presets, dict):
            return list(presets.keys())
        return ["default"]

    def get_active_preset_name(self) -> str:
        """現在選択中のプリセット名を返す"""
        return self.get("obs.comment.active_preset", "default")

    def get_preset(self, preset_name: str) -> Dict[str, Any]:
        """指定されたプリセットの内容を返す"""
        presets = self.get("obs.comment.presets", {})
        if isinstance(presets, dict) and preset_name in presets:
            return dict(presets[preset_name])
        return {}

    def apply_preset(self, preset_name: str) -> bool:
        """指定されたプリセットを適用（active_presetを変更し、各値を設定に反映）"""
        preset = self.get_preset(preset_name)
        if not preset:
            return False

        # プリセットの各値を設定に反映
        for key, value in preset.items():
            self.set(key, value)

        # アクティブプリセットを更新
        self.set("obs.comment.active_preset", preset_name)
        return True

    def save_preset(self, preset_name: str, preset_data: Dict[str, Any]) -> bool:
        """
        新しいプリセットを保存、または既存のプリセットを上書き

        Args:
            preset_name: プリセット名
            preset_data: プリセットの内容（dict）

        Returns:
            bool: 成功時 True、失敗時 False

        Note:
            Phase 5: 将来の拡張用プレースホルダー
            現在のGUIでは「現在の設定を新規プリセットとして保存」機能は未実装
        """
        if not preset_name or not isinstance(preset_data, dict):
            return False

        # プリセット辞書を取得
        presets = self.get("obs.comment.presets", {})
        if not isinstance(presets, dict):
            presets = {}

        # 新規プリセットを追加または上書き
        presets[preset_name] = dict(preset_data)
        self.set("obs.comment.presets", presets)
        self.save()

        return True

    def is_builtin_preset(self, preset_name: str) -> bool:
        """組み込みプリセットかどうかを判定（削除不可判定に使用）"""
        return preset_name in self.BUILTIN_PRESETS

    def delete_preset(self, preset_name: str) -> bool:
        """
        ユーザー作成プリセットを削除

        Args:
            preset_name: 削除するプリセット名

        Returns:
            bool: 成功時 True、失敗時 False

        Note:
            Phase 5: 将来の拡張用プレースホルダー
            組み込みプリセットは削除不可
        """
        # 組み込みプリセットは削除不可
        if self.is_builtin_preset(preset_name):
            print(f"[Config] 組み込みプリセット '{preset_name}' は削除できません")
            return False

        # プリセット辞書を取得
        presets = self.get("obs.comment.presets", {})
        if not isinstance(presets, dict) or preset_name not in presets:
            return False

        # プリセットを削除
        del presets[preset_name]
        self.set("obs.comment.presets", presets)
        self.save()

        # 削除したプリセットがアクティブだった場合は default に戻す
        if self.get_active_preset_name() == preset_name:
            self.set("obs.comment.active_preset", "default")
            self.apply_preset("default")

        return True
