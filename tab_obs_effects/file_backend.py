# -*- coding: utf-8 -*-
"""
file_backend.py - OBS演出効果タブ用ファイル出力バックエンド（v17.5.7 HTML専用）
- overlay_out/overlay.html（無ければ自動配置）
- overlay_out/data.json の生成
- 設定は注入 config_manager（任意）または OBSEffectsConfig に委譲

v17.5.7 以降、TXT出力ルートは廃止され、HTMLオーバーレイ（overlay.html + data.json）に一本化

========== OBS ブラウザソースの設定方法 ==========

1. OBS Studio で「ソース」→「ブラウザ」を追加
2. 「ローカルファイル」にチェックを入れる
3. 参照パスに以下のファイルを指定：
   tab_obs_effects/overlay_out/overlay.html
   ※ 絶対パス推奨（例: C:\\Users\\YourName\\gyururu_bot_v17\\tab_obs_effects\\overlay_out\\overlay.html）

4. 推奨設定：
   - 幅: 1920, 高さ: 1080（OBSキャンバス解像度と一致させる）
   - 「ページが読み込まれたときにブラウザのソースを更新する」：チェック推奨
   - 「カスタムフレームレート」：60 FPS 推奨

5. 注意事項：
   - overlay.html は data.json を定期的に読み込んでコメントを表示します
   - data.json は UI の「プレビュー更新」ボタンやコメント送信時に自動更新されます
   - overlay.html は一度配置されると上書きされません（カスタマイズ保護）

================================================
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import time
from typing import Any, Dict, Optional

# ロガー初期化
logger = logging.getLogger(__name__)

# 役割
ROLE_STREAMER = "streamer"
ROLE_AI = "ai"
ROLE_VIEWER = "viewer"

# ローカルに同梱された overlay.html（ユーザーがアップロードしたものを優先使用）
_BUNDLED_OVERLAY_HTML = os.path.join(os.path.dirname(__file__), "overlay.html")


class OBSEffectsFileOutput:
    """
    ぎゅるるボット OBS連携ファイル出力（HTMLモード推奨）
    - effects_handler からメッセージ/エフェクトを受け取り、オーバーレイ用の data.json を書き出す
    - config_handler からTTLや方向、スタイル等を反映
    """

    def __init__(self, config_handler: Any, effects_handler: Any) -> None:
        self.cfg = config_handler
        self.fx = effects_handler

        # v17.5.7: 出力先を tab_obs_effects/overlay_out/ に固定
        # プロジェクト直下ではなく、このモジュールと同じディレクトリ内に配置
        module_dir = os.path.dirname(os.path.abspath(__file__))
        self.out_dir = os.path.join(module_dir, "overlay_out")
        self.data_filename = "data.json"
        self.out_path = os.path.join(self.out_dir, self.data_filename)

        logger.info(f"📂 OBS overlay 出力先: {self.out_dir}")
        os.makedirs(self.out_dir, exist_ok=True)
        self._ensure_overlay_html()

    # ========== 公開API ==========
    def flush_to_files(self) -> str:
        """
        現在のメッセージとエフェクトを overlay_out/data.json に書き出す。
        戻り値: 書き出し先ファイルパス
        """
        try:
            # キャンバス解像度をログ出力（Phase 4: 後方互換性確認用）
            canvas_width = int(self._cfg("obs.canvas.width", 1920))
            canvas_height = int(self._cfg("obs.canvas.height", 1080))
            canvas_preset = str(self._cfg("obs.canvas.preset", "1920x1080"))
            logger.info(f"🎬 OBS Overlay: canvas={canvas_width}x{canvas_height} (preset={canvas_preset})")

            # streams
            streams = self.fx.snapshot_messages()
            timeline_count = len(streams.get("timeline", []))
            logger.info(f"📝 data.json 書き出し開始: timeline={timeline_count}件")

            # LEGACY: TTL設定（v17.6+ では display_area.*.ttl を使用）
            # 互換性のため空の構造を保持
            ttl = {
                "streamer": {"enabled": False, "seconds": 10},
                "ai": {"enabled": False, "seconds": 10},
                "viewer": {"enabled": False, "seconds": 10},
            }

            # meta / config for overlay.html (Phase X: 完全な設定出力)
            meta: Dict[str, Any] = {
                "mode": "TIMELINE",  # HTML固定

                # ========== OBSキャンバス解像度 ==========
                "canvas": {
                    "width": int(self._cfg("obs.canvas.width", 1920)),
                    "height": int(self._cfg("obs.canvas.height", 1080)),
                },

                # ========== 表示設定 ==========
                "display": {
                    "flow": {
                        "direction": str(self._cfg("display.flow.direction", "DOWN")).upper(),  # デフォルト: DOWN (上から下へ)
                        "speed": float(self._cfg("display.flow.speed", 3.0)),
                    },
                    "max_items": {
                        "streamer": int(self._cfg("display.max_items.streamer", 0)),
                        "ai": int(self._cfg("display.max_items.ai", 0)),
                        "timeline": int(self._cfg("display.max_items.timeline", 5)),
                    },
                    # ✅ Phase Y Task 5: 表示エリア設定を meta に出力（デフォルト: 左上配置）
                    # ★★★ 重要：OBS演出タブUI との連携 ★★★
                    # - UI側（app.py）は display_area.single.area 等に座標を保存
                    # - _save_area_config() で display.area.* にも同時保存（ブリッジ）
                    # - overlay.html は data.json の meta.display.area.{x,y,width,height} を読み取る
                    # - このため、display.area.* は overlay.html との互換性維持のため必須
                    "area": {
                        "x": int(self._cfg("display.area.x", 50)),
                        "y": int(self._cfg("display.area.y", 0)),       # デフォルト: 上端 (左下固まり問題の対策)
                        "width": int(self._cfg("display.area.width", 400)),
                        "height": int(self._cfg("display.area.height", 600)),
                    },
                    # Phase 1: 表示位置・サイズ設定
                    "position": {
                        "x": int(self._cfg("display.area.x", 50)),
                        "y": int(self._cfg("display.area.y", 50)),
                        "width": int(self._cfg("display.area.width", 800)),
                        "height": int(self._cfg("display.area.height", 600)),
                        "anchor": str(self._cfg("display.area.anchor", "bottom-left")),  # bottom-left / bottom-right / top-left / top-right
                    },
                    # ========== role別表示設定 ==========
                    # UI側（app.py）の表示者選択チェックボックスから反映
                    "show": {
                        "streamer": bool(self._cfg("display.show.streamer", True)),
                        "ai":       bool(self._cfg("display.show.ai", True)),
                        "viewer":   bool(self._cfg("display.show.viewer", True)),
                    },
                },

                # ========== エリア設定（4タイムライン） ==========
                # v17.6+: 同一エリアタブ + 個別タブ（配信者/AI/視聴者）
                # UI側（app.py）の _save_area_config() で display_area.* に保存
                "display_area": {
                    # 同一エリアタブの設定
                    # display_area.single から全体を読み込む（max_items/ttl含む）
                    "single": self._build_single_area_config(),

                    # multi モード設定（role別3タイムライン表示）
                    "multi": {
                        "streamer": self._cfg("display_area.multi.streamer", {}),
                        "ai": self._cfg("display_area.multi.ai", {}),
                        "viewer": self._cfg("display_area.multi.viewer", {}),
                    },
                },

                # ========== TTL設定 ==========
                "ttl": ttl,

                # ========== 吹き出し設定 ==========
                "bubble": {
                    "enabled": bool(self._cfg("bubble.enabled", True)),
                    "shape": str(self._cfg("bubble.shape", "rounded")),
                    "background": {
                        "color": str(self._cfg("bubble.background.color", "#000000")),
                        "opacity": int(self._cfg("bubble.background.opacity", 75)),
                    },
                    "border": {
                        "enabled": bool(self._cfg("bubble.border.enabled", False)),
                        "color": str(self._cfg("bubble.border.color", "#FFFFFF")),
                        "width": int(self._cfg("bubble.border.width", 1)),
                        "radius": int(self._cfg("bubble.border.radius", 8)),
                    },
                    "shadow": {
                        "enabled": bool(self._cfg("bubble.shadow.enabled", True)),
                        "color": str(self._cfg("bubble.shadow.color", "#000000")),
                        "blur": int(self._cfg("bubble.shadow.blur", 8)),
                    },
                },

                # ========== スタイル設定 ==========
                "style": {
                    "font": {
                        "family": str(self._cfg("style.font.family", "Yu Gothic UI, Meiryo, sans-serif")),
                        # ⚠ S-2: フォントサイズは UI / JSON 側で管理する。
                        #   ここで数値をハードコードすると 14px / 16px に勝手に戻るので、
                        #   当面はコメントアウトしておく。
                        # "size": int(self._cfg("style.font.size_px", 16)),
                    },
                    "name": {
                        "font": {
                            # "size": int(self._cfg("style.name.font.size", 14)),
                            "bold": bool(self._cfg("style.name.font.bold", True)),
                            "italic": bool(self._cfg("style.name.font.italic", False)),
                        },
                        "use_custom_color": bool(self._cfg("style.name.use_custom_color", False)),
                        "custom_color": str(self._cfg("style.name.custom_color", "#FFFFFF")),
                    },
                    "body": {
                        "font": {
                            # "size": int(self._cfg("style.body.font.size", 16)),
                            "bold": bool(self._cfg("style.body.font.bold", False)),
                            "italic": bool(self._cfg("style.body.font.italic", False)),
                        },
                        "indent": int(self._cfg("style.body.indent", 0)),
                    },
                    "text": {
                        "outline": {
                            "enabled": bool(self._cfg("style.text.outline.enabled", False)),
                            "color": str(self._cfg("style.text.outline.color", "#000000")),
                            "width": int(self._cfg("style.text.outline.width", 2)),
                        },
                        "shadow": {
                            "enabled": bool(self._cfg("style.text.shadow.enabled", False)),
                            "color": str(self._cfg("style.text.shadow.color", "#000000")),
                            "offset_x": int(self._cfg("style.text.shadow.offset_x", 2)),
                            "offset_y": int(self._cfg("style.text.shadow.offset_y", 2)),
                            "blur": int(self._cfg("style.text.shadow.blur", 0)),
                        },
                    },
                    "layout": {
                        "line_height": float(self._cfg("style.layout.line_height", 1.5)),
                        "padding": {
                            "top": int(self._cfg("style.layout.padding.top", 12)),
                            "right": int(self._cfg("style.layout.padding.right", 16)),
                            "bottom": int(self._cfg("style.layout.padding.bottom", 12)),
                            "left": int(self._cfg("style.layout.padding.left", 16)),
                        },
                    },
                    "background": {
                        "color": str(self._cfg("style.background.color", "#000000")),
                        "opacity": int(self._cfg("style.background.opacity", 75)),
                        "border_radius": int(self._cfg("style.background.border_radius", 8)),
                        "border": {
                            "enabled": bool(self._cfg("style.background.border.enabled", False)),
                            "color": str(self._cfg("style.background.border.color", "#FFFFFF")),
                            "width": int(self._cfg("style.background.border.width", 1)),
                        },
                    },
                },

                # ========== 役割別カラー設定 ==========
                "role": {
                    "streamer": {
                        "color": str(self._cfg("role.streamer.color", "#4A90E2")),
                    },
                    "ai": {
                        "color": str(self._cfg("role.ai.color", "#9B59B6")),
                    },
                    "viewer": {
                        "color": str(self._cfg("role.viewer.color", "#7F8C8D")),
                    },
                },
            }

            # エフェクトを消費
            effects = self.fx.drain_effects()

            data = {
                "meta": meta,
                "streams": streams,
                "effects": effects,
                "generated_at": time.time(),
            }

            # JSON出力
            os.makedirs(self.out_dir, exist_ok=True)
            tmp = self.out_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # アトミック置換
            if os.path.exists(self.out_path):
                os.replace(tmp, self.out_path)
            else:
                os.rename(tmp, self.out_path)

            logger.info(f"✅ data.json 書き出し完了: {self.out_path}")
            logger.debug(f"   timeline: {timeline_count}件, effects: {len(effects)}件")
            return self.out_path

        except Exception as e:
            logger.error(f"❌ data.json 書き出しエラー: {e}", exc_info=True)
            raise

    # ========== 内部ユーティリティ ==========
    def _build_single_area_config(self) -> dict:
        """
        display_area.single の設定を構築する
        app.py の _save_area_config() で保存した設定を読み込む
        """
        single_cfg = self._cfg("display_area.single", {})

        # デフォルト値を設定
        result = {
            "area": single_cfg.get("area", {"x": 50, "y": 0, "w": 400, "h": 360}),
            "max_items": int(single_cfg.get("max_items", 0)),
            "ttl": int(single_cfg.get("ttl", 0)),
            "flow": str(single_cfg.get("flow", "vertical")),
        }

        return result

    def _cfg(self, key: str, default: Any = None) -> Any:
        try:
            return self.cfg.get(key, default)
        except Exception:
            return default

    def _ensure_overlay_html(self) -> None:
        """
        overlay_out/overlay.html を用意（無い場合のみコピー）。
        プロジェクト直下や /mnt/data にユーザー提供の overlay.html がある場合はそれを優先。

        ★★★ 重要：上書き保護 ★★★
        - overlay_out/overlay.html が既に存在する場合は何もしません（上書きしない）
        - これにより、ユーザーが overlay.html をカスタマイズしても保護されます
        - 初回起動時またはファイル削除後のみ、新しい overlay.html が配置されます

        優先順位：
        1. overlay_out/overlay.html が既に存在 → そのまま使用（カスタマイズ保護）
        2. カレント直下の overlay.html → コピー
        3. /mnt/data/overlay.html（ユーザーアップロード） → コピー
        4. tab_obs_effects/overlay.html（同梱版） → コピー
        """
        dest = os.path.join(self.out_dir, "overlay.html")
        if os.path.exists(dest):
            # 既存ファイルを保護（上書きしない）
            return

        # 1) カレント直下に overlay.html があればそれを優先
        for candidate in ("./overlay.html", os.path.join(os.getcwd(), "overlay.html")):
            if os.path.exists(candidate):
                try:
                    shutil.copyfile(candidate, dest)
                    return
                except Exception:
                    pass

        # 2) ユーザーがアップロードした /mnt/data/overlay.html があればそれを使う
        try:
            uploaded = "/mnt/data/overlay.html"
            if os.path.exists(uploaded):
                shutil.copyfile(uploaded, dest)
                return
        except Exception:
            pass

        # 3) 最後に同梱版（このモジュールと同じ場所）を使う
        try:
            if os.path.exists(_BUNDLED_OVERLAY_HTML):
                shutil.copyfile(_BUNDLED_OVERLAY_HTML, dest)
        except Exception:
            # どうしても失敗したら諦める（data.json だけでも動く）
            pass
