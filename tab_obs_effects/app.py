# -*- coding: utf-8 -*-
"""
tab_obs_effects/app.py
OBS演出効果タブ（v17.3統合版）
- メインファイル (main_v_17_3.py) 対応
- スタンドアロンモード対応
- 既存モジュール統合 (config_handler, effects_handler, file_backend)
- 実用的なエフェクト管理UI
- リアルタイムプレビュー機能
- チャット連動エフェクト
- 設定保存・復元機能

更新履歴:
- v17.3: メインファイル統合、既存モジュール使用、スタンドアロン対応
- v16.6: 拡張版（オリジナル）
"""

from typing import Any, Dict, Optional, List
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import tkinter.font as tkfont  # フォント計測用
import os, json, logging, threading, time
from datetime import datetime
from pathlib import Path
import http.server
import socketserver

# ロガー初期化
logger = logging.getLogger(__name__)

# v17.3: 既存モジュールのインポートを試行
try:
    from .config_handler import OBSEffectsConfig
    from .effects_handler import EffectsHandler
    from .file_backend import OBSEffectsFileOutput
    from .obs_manager import OBSManager
    from .constants import ROLE_STREAMER, ROLE_AI, ROLE_VIEWER
    _USE_INTEGRATED_MODULES = True
except ImportError:
    # スタンドアロンモード時のフォールバック
    _USE_INTEGRATED_MODULES = False
    # constants.py からロール定数をインポート（フォールバック）
    try:
        from constants import ROLE_STREAMER, ROLE_AI, ROLE_VIEWER
    except ImportError:
        # 最終フォールバック: ハードコード
        ROLE_STREAMER = "streamer"
        ROLE_AI = "ai"
        ROLE_VIEWER = "viewer"

# v17.5.7: overlay_out の出力先を tab_obs_effects/ 配下に固定
BASE_DIR = Path(__file__).resolve().parent
OVERLAY_OUT_DIR = BASE_DIR / "overlay_out"

# v16.6互換: 独自OverlayFileBackendクラス（フォールバック用）
class OverlayFileBackend:
    """overlay.html + data.json を管理する最小バックエンド"""
    def __init__(self, out_dir: Path | str = None):
        # デフォルトは tab_obs_effects/overlay_out を使用
        if out_dir is None:
            out_dir = OVERLAY_OUT_DIR
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.html_path = self.out_dir / "overlay.html"
        self.data_path = self.out_dir / "data.json"
        self._lock = threading.Lock()
        self._ensure_html_exists()
        self._ensure_data_exists()

    def _ensure_html_exists(self):
        if self.html_path.exists():
            return
        # 最小テンプレ（スタイルは data.json のキーをJSで反映）
        html = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Overlay</title>
<style>
  :root{
    --maxw: 960px; --bg:#ffffff; --op:1; --radius:0px; --border:0px solid #000;
    --pad: 8px 12px; --align:left; --lineh:1.5; --indent:0px;
    /* ⚠ S-2: フォントサイズは config (style.name.font.size, style.body.font.size) からのみ設定する。
       ★ 勝手にここで固定値にしないこと！applyStyle(cfg) 内で cfg から設定される。 */
    /* --name-size:12px; --body-size:14px; */
    --name-weight:bold; --name-style:normal;
    --body-weight:normal; --body-style:normal;
    --name-color:inherit;
    --text-shadow:none;
    --streamer:#4A90E2; --ai:#9B59B6; --viewer:#7F8C8D;
  }
  body{margin:0;background:transparent;overflow:hidden;font-family: "Yu Gothic UI", Meiryo, Arial, sans-serif;}
  .wrap{max-width: var(--maxw); padding: 0.5rem;}
  .item{display:block; margin:10px 0; background: var(--bg);
        border-radius: var(--radius); border: var(--border);
        padding: var(--pad);}
  .role-streamer{color: var(--streamer)}
  .role-ai{color: var(--ai)}
  .role-viewer{color: var(--viewer)}
  .name{font-weight:var(--name-weight); font-style:var(--name-style); 
        font-size:var(--name-size); color:var(--name-color); 
        margin-bottom:4px; text-shadow:var(--text-shadow);}
  .body{line-height: var(--lineh); text-align: var(--align); white-space: pre-wrap;
        font-weight:var(--body-weight); font-style:var(--body-style);
        font-size:var(--body-size); text-shadow:var(--text-shadow);}
  .indent{padding-left: var(--indent);}
</style>
</head>
<body>
  <div class="wrap" id="wrap"></div>
<script>
 const wrap = document.getElementById('wrap');
 let last = "";

 function applyStyle(cfg){
   const r = document.documentElement;
   const maxw = cfg?.ui?.style_panel?.max_width_px ?? 960;
   r.style.setProperty('--maxw', maxw + 'px');

   const bg = cfg?.style?.background?.color ?? '#ffffff';
   const op = (cfg?.style?.background?.opacity ?? 100)/100.0;
   r.style.setProperty('--bg', bg);
   r.style.setProperty('--op', op.toString());

   const radius = (cfg?.style?.background?.border_radius ?? 0) + 'px';
   const bw = (cfg?.style?.background?.border?.width ?? 0) + 'px';
   const bc = cfg?.style?.background?.border?.color ?? '#000000';
   const ben = cfg?.style?.background?.border?.enabled ?? false;
   r.style.setProperty('--radius', radius);
   r.style.setProperty('--border', (ben? (bw+' solid '+bc) : '0px solid transparent'));

   const padT = cfg?.style?.layout?.padding?.top ?? 8;
   const padR = cfg?.style?.layout?.padding?.right ?? 12;
   const padB = cfg?.style?.layout?.padding?.bottom ?? 8;
   const padL = cfg?.style?.layout?.padding?.left ?? 12;
   r.style.setProperty('--pad', padT+'px '+padR+'px '+padB+'px '+padL+'px');

   const align = (cfg?.display?.text?.alignment ?? 'LEFT').toLowerCase();  // ← キー名を修正
   r.style.setProperty('--align', align);

   const lh = cfg?.style?.layout?.line_height ?? 1.5;
   r.style.setProperty('--lineh', lh);

   const indent = (cfg?.style?.body?.indent ?? 0) + 'px';
   r.style.setProperty('--indent', indent);

   // フォントサイズ
   const nameSize = (cfg?.style?.name?.font?.size ?? 24) + 'px';
   const bodySize = (cfg?.style?.body?.font?.size ?? 26) + 'px';
   r.style.setProperty('--name-size', nameSize);
   r.style.setProperty('--body-size', bodySize);

   // フォント装飾
   const nameBold = cfg?.style?.name?.font?.bold ?? true;
   const nameItalic = cfg?.style?.name?.font?.italic ?? false;
   const bodyBold = cfg?.style?.body?.font?.bold ?? false;
   const bodyItalic = cfg?.style?.body?.font?.italic ?? false;
   r.style.setProperty('--name-weight', nameBold ? 'bold' : 'normal');
   r.style.setProperty('--name-style', nameItalic ? 'italic' : 'normal');
   r.style.setProperty('--body-weight', bodyBold ? 'bold' : 'normal');
   r.style.setProperty('--body-style', bodyItalic ? 'italic' : 'normal');

   // 名前のカラー（カスタムカラーが有効な場合）
   const useCustomColor = cfg?.style?.name?.use_custom_color ?? false;
   const customColor = cfg?.style?.name?.custom_color ?? '#FFFFFF';
   r.style.setProperty('--name-color', useCustomColor ? customColor : 'inherit');

   // テキスト縁取り
   const outlineEnabled = cfg?.style?.text?.outline?.enabled ?? false;
   const outlineColor = cfg?.style?.text?.outline?.color ?? '#000000';
   const outlineWidth = cfg?.style?.text?.outline?.width ?? 2;
   if (outlineEnabled) {
     const outline = `${outlineWidth}px ${outlineWidth}px 0 ${outlineColor}, -${outlineWidth}px -${outlineWidth}px 0 ${outlineColor}, ${outlineWidth}px -${outlineWidth}px 0 ${outlineColor}, -${outlineWidth}px ${outlineWidth}px 0 ${outlineColor}`;
     r.style.setProperty('--text-shadow', outline);
   } else {
     const shadowEnabled = cfg?.style?.text?.shadow?.enabled ?? false;
     if (shadowEnabled) {
       const shadowColor = cfg?.style?.text?.shadow?.color ?? '#000000';
       const shadowX = cfg?.style?.text?.shadow?.offset_x ?? 2;
       const shadowY = cfg?.style?.text?.shadow?.offset_y ?? 2;
       r.style.setProperty('--text-shadow', `${shadowX}px ${shadowY}px 3px ${shadowColor}`);
     } else {
       r.style.setProperty('--text-shadow', 'none');
     }
   }

   // 役割別カラー
   r.style.setProperty('--streamer', cfg?.style?.role?.streamer?.color ?? '#4A90E2');
   r.style.setProperty('--ai', cfg?.style?.role?.ai?.color ?? '#9B59B6');
   r.style.setProperty('--viewer', cfg?.style?.role?.viewer?.color ?? '#7F8C8D');
 }

 function render(data){
   if(!data) return;
   const key = JSON.stringify(data);
   if(key===last) return; last = key;

   applyStyle(data.config || {});
   wrap.innerHTML = "";

   const items = data.items || []; // [{role,name,text,ts}]
   for(const it of items){
     const roleClass = it.role==='streamer'?'role-streamer':(it.role==='ai'?'role-ai':'role-viewer');
     const box = document.createElement('div');
     box.className = 'item '+roleClass;

     if((data.config?.display?.name_visibility ?? 'SHOW') === 'SHOW' && it.name){
       const n = document.createElement('div');
       n.className = 'name';
       n.textContent = it.name;
       box.appendChild(n);
     }
     const b = document.createElement('div');
     b.className = 'body indent';
     b.textContent = it.text ?? '';
     box.appendChild(b);

     wrap.appendChild(box);
   }
 }

 async function tick(){
   try{
     const res = await fetch('data.json?ts='+(Date.now()));
     const json = await res.json();
     render(json);
   }catch(e){ /* first run may 404 */ }
   setTimeout(tick, 500);
 }
 tick();
</script>
</body></html>"""
        self.html_path.write_text(html, encoding="utf-8")

    def _ensure_data_exists(self):
        if not self.data_path.exists():
            self.data_path.write_text(json.dumps({"config":{}, "items":[]}, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_snapshot(self, config: dict, items: list):
        with self._lock:
            payload = {"config": config or {}, "items": items or []}
            self.data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# 共有シングルトン
try:
    from shared.message_bus import get_message_bus
    from shared.event_types import Events
    from shared.unified_config_manager import UnifiedConfigManager
    SHARED_AVAILABLE = True
except Exception:
    # フォールバック
    from enum import Enum
    def _upper(x):
        return x.upper() if isinstance(x, str) else getattr(x, "name", str(x)).upper()
    class Events(Enum):
        CHAT_MESSAGE = "CHAT_MESSAGE"
        AI_RESPONSE = "AI_RESPONSE"
        STATUS_UPDATE = "STATUS_UPDATE"
    class _FB:
        def __init__(self): self._s = {}
        def publish(self, ev, data=None, **kw):
            for cb in self._s.get(_upper(ev), []): cb(data, **kw)
        def subscribe(self, ev, cb, **kw):
            self._s.setdefault(_upper(ev), []).append(cb)
    def get_message_bus(): return _FB()
    class UnifiedConfigManager:
        def __init__(self): self._cfg = {}
        def get(self, key, default=None): return default
        def set(self, key, value): pass
        def save(self): pass
    SHARED_AVAILABLE = False

class EffectPreset:
    """
    エフェクトプリセット定義（v17.5.7+ 絵文字エフェクト対応）

    必須フィールド:
    - name: プリセットID (例: "confetti")
    - description: 表示名 (例: "🎉 紙吹雪")
    - duration: 継続時間（秒）
    - emoji: 使用する絵文字リスト
    - animation: アニメーションタイプ (fall/rise/scatter/burst/flow/pop)
    - count: 生成する絵文字の数
    - area: 表示エリア (top/bottom/center/full)

    オプションフィールド:
    - color: プレビュー用カラーコード（旧UI用、将来削除可能）
    - trigger_words: 自動発火用トリガーワード
    - obs_scene: OBS連携用シーン名（将来拡張用）
    - obs_source: OBS連携用ソース名（将来拡張用）
    - size_min: 絵文字の最小サイズ（px、デフォルト32）
    - size_max: 絵文字の最大サイズ（px、デフォルト32）
      ※ size_min == size_max なら固定サイズ、異なればランダムサイズ
    """
    def __init__(self, name: str, description: str, duration: float,
                 emoji: List[str], animation: str, count: int, area: str,
                 color: str = "#FF6B6B", trigger_words: List[str] = None,
                 obs_scene: str = "", obs_source: str = "",
                 size_min: int = 32,
                 size_max: int = 32):
        # 必須フィールド
        self.name = name
        self.description = description
        self.duration = duration
        self.emoji = emoji
        self.animation = animation
        self.count = count
        self.area = area

        # オプションフィールド
        self.color = color
        self.trigger_words = trigger_words or []
        self.obs_scene = obs_scene
        self.obs_source = obs_source

        # サイズ関連フィールド
        self.size_min = size_min
        self.size_max = size_max

        # 内部管理用
        self.enabled = True
        self.last_used = None

class OBSEffectsTabUI(ttk.Frame):
    """
    OBS演出効果タブ（拡張版）
    - 豊富なプリセット管理
    - ビジュアルプレビュー
    - チャット連動設定
    - 統計情報表示

    v17.5.7 以降の仕様:

    - 演出エフェクトのプレビューは HTML オーバーレイ (overlay.html) のみで行う。
    - このクラス内に、演出専用の Canvas や
      「プレビューと実行」枠（ミニプレビューUI）を再実装しないこと。
    - コメント表示エリアのプレビューは、コメント系タブ
      （コメント表示エリア設定 / コメントの装飾設定）側の責務とする。

    NOTE:
    - 演出効果の視覚プレビューは overlay.html (ブラウザ / OBS ブラウザソース) のみで行う。
    - コメント表示エリアキャンバスへのエフェクト描画や、
      ここから overlay.html を二重に埋め込む実装は行わない。
    """
    
    def __init__(self, parent: tk.Misc, message_bus=None, config_manager=None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.bus = message_bus or get_message_bus()
        self.config_manager = config_manager or UnifiedConfigManager()
        
        # v17.3: 統合モジュールの初期化
        if _USE_INTEGRATED_MODULES:
            # 既存モジュールを使用
            self.obs_config = OBSEffectsConfig(config_manager=self.config_manager)
            self.effects = EffectsHandler()
            self.file_output = OBSEffectsFileOutput(self.obs_config, self.effects)
            self.obs_manager = OBSManager()
        else:
            # フォールバック: 独自実装を使用
            self.obs_config = None
            self.effects = None
            self.file_output = None
            self.obs_manager = None
        
        # データ管理
        self.effects_presets: Dict[str, EffectPreset] = {}
        self.effect_history: List[Dict[str, Any]] = []
        self.obs_connected = False
        self.auto_effects_enabled = True
        
        # UI状態
        self.selected_preset = None
        # エフェクト密度（プリセット count に掛ける倍率）
        self.effect_density_var = tk.DoubleVar(value=1.0)

        # 二重表示禁止フラグ（config から初期値を取得）
        initial_prevent_double = True
        try:
            if hasattr(self.config_manager, "get"):
                initial_prevent_double = bool(
                    self.config_manager.get("display.prevent_double", True)
                )
        except Exception:
            initial_prevent_double = True

        self.prevent_double_var = tk.BooleanVar(value=initial_prevent_double)

        # v17.5.7+: HTTP プレビューサーバー
        self._preview_server_thread = None
        self._preview_server_port = None
        self._preview_httpd = None

        # 統計
        self.stats = {
            'total_effects': 0,
            'chat_triggered': 0,
            'ai_triggered': 0,
            'manual_triggered': 0,
            'session_start': datetime.now()
        }

        self._load_default_presets()
        self._build_ui()
        self._subscribe_events()
        self._load_settings()
        
        # v16.6互換: 独自バックエンド（統合モジュールが無い場合のみ）
        if not _USE_INTEGRATED_MODULES:
            # v17.5.7: デフォルトで tab_obs_effects/overlay_out を使用
            self._overlay_backend = OverlayFileBackend()
            self._overlay_items = []  # 表示キュー（配信者/AI/視聴者の時系列）

        
    def _inject_unified_area_controls(self, parent):
        """
        v17.6 新仕様：コメント表示エリア設定タブ（並列タブ構造）
        - 同一エリア / 配信者 / AIキャラ / 視聴者 をタブで並列配置
        - 各タブ内に表示者選択チェックボックスと座標入力フィールドを配置
        - 「コメントの流れ」は一番下に共通配置
        """
        import tkinter as tk
        from tkinter import ttk

        # ルート：全体を包むフレーム
        root_frame = ttk.Frame(parent, padding=(8, 6))
        root_frame.pack(fill="both", expand=True, padx=8, pady=6)

        # ──────────────────────────
        # 1. コメントの流れ（最上部に配置）
        # ──────────────────────────
        flow_frame = ttk.LabelFrame(root_frame, text="🔄 コメントの流れ")
        flow_frame.pack(fill="x", expand=False, padx=4, pady=(4, 4))

        ttk.Label(flow_frame, text="方向:").pack(side="left", padx=(8, 4), pady=4)

        # display.flow.direction（UP/DOWN/LEFT/RIGHT）と
        # 旧 single_cfg["flow"] から初期値を決定
        cfg = getattr(self, "config_manager", None)
        if cfg is None:
            return

        # ========== 設定を読み込む ==========
        display_area_config = cfg.get("display_area", {})

        # single設定
        single_cfg = display_area_config.get("single", {})
        single_area = single_cfg.get("area", {"x": 50, "y": 0, "w": 400, "h": 360})

        # multi設定
        multi_cfg = display_area_config.get("multi", {})
        streamer_cfg = multi_cfg.get("streamer", {})
        ai_cfg = multi_cfg.get("ai", {})
        viewer_cfg = multi_cfg.get("viewer", {})

        flow_direction = cfg.get("display.flow.direction", "UP")
        legacy_flow = single_cfg.get("flow", "")

        # 旧形式（vertical / horizontal-left / horizontal-right）→ 新形式に変換
        if legacy_flow in ("vertical", "horizontal-left", "horizontal-right"):
            if legacy_flow == "horizontal-left":
                initial_flow = "LEFT"
            elif legacy_flow == "horizontal-right":
                initial_flow = "RIGHT"
            else:
                initial_flow = "UP"
        elif legacy_flow in ("UP", "DOWN", "LEFT", "RIGHT"):
            initial_flow = legacy_flow
        else:
            initial_flow = flow_direction or "UP"

        # GUI では UP / DOWN / LEFT / RIGHT をそのまま持たせる
        self.single_flow = tk.StringVar(value=initial_flow)

        ttk.Radiobutton(
            flow_frame,
            text="下から上",
            value="UP",
            variable=self.single_flow,
        ).pack(side="left", padx=4, pady=4)

        ttk.Radiobutton(
            flow_frame,
            text="上から下",
            value="DOWN",
            variable=self.single_flow,
        ).pack(side="left", padx=4, pady=4)

        ttk.Radiobutton(
            flow_frame,
            text="右から左",
            value="LEFT",
            variable=self.single_flow,
        ).pack(side="left", padx=4, pady=4)

        ttk.Radiobutton(
            flow_frame,
            text="左から右",
            value="RIGHT",
            variable=self.single_flow,
        ).pack(side="left", padx=4, pady=4)

        # ──────────────────────────
        # 2. 表示制御（二重表示禁止）
        # ──────────────────────────
        double_frame = ttk.LabelFrame(root_frame, text="⚠️ 表示制御")
        double_frame.pack(fill="x", expand=False, padx=4, pady=(0, 4))

        ttk.Checkbutton(
            double_frame,
            text="二重表示を禁止する（統一エリアと個別エリアを同時に表示しない）",
            variable=self.prevent_double_var,
            command=self._on_toggle_prevent_double
        ).pack(side="left", padx=8, pady=4)

        # ──────────────────────────
        # 3. タブ構造（同一エリア / 配信者 / AIキャラ / 視聴者を並列配置）
        # ──────────────────────────
        self.area_tabs_notebook = ttk.Notebook(root_frame)
        self.area_tabs_notebook.pack(fill="both", expand=True, padx=4, pady=(4, 8))

        # 各タブ用フレーム
        single_tab = ttk.Frame(self.area_tabs_notebook)
        streamer_tab = ttk.Frame(self.area_tabs_notebook)
        ai_tab = ttk.Frame(self.area_tabs_notebook)
        viewer_tab = ttk.Frame(self.area_tabs_notebook)

        self.area_tabs_notebook.add(single_tab, text="同一エリア")
        self.area_tabs_notebook.add(streamer_tab, text="配信者")
        self.area_tabs_notebook.add(ai_tab, text="AIキャラ")
        self.area_tabs_notebook.add(viewer_tab, text="視聴者")

        # タブ切り替え時のイベント
        self.area_tabs_notebook.bind("<<NotebookTabChanged>>", self._on_area_tab_changed)

        # ──────────────────────────
        # 1-1. 同一エリアタブの中身
        # ──────────────────────────
        self._build_single_area_tab(single_tab, single_cfg, single_area)

        # ──────────────────────────
        # 1-2. 配信者タブの中身
        # ──────────────────────────
        self._build_role_area_tab(streamer_tab, "streamer", "配信者", streamer_cfg)

        # ──────────────────────────
        # 1-3. AIキャラタブの中身
        # ──────────────────────────
        self._build_role_area_tab(ai_tab, "ai", "AIキャラ", ai_cfg)

        # ──────────────────────────
        # 1-4. 視聴者タブの中身
        # ──────────────────────────
        self._build_role_area_tab(viewer_tab, "viewer", "視聴者", viewer_cfg)

        # ========== 互換性のため旧変数も保持 ==========
        self.mode_var = tk.StringVar(value="TIMELINE")
        self.inc_viewer = tk.BooleanVar(value=True)
        self.flow_direction_area = tk.StringVar(value="UP")
        self.flow_pad_bottom_area = tk.BooleanVar(value=True)

        # 現在編集中のロール
        self.current_editing_role = tk.StringVar(value="single")

        # プレビュー更新
        self._update_area_preview()

    # ------------------------------------------------------------------
    # 同一エリア用タブ
    # ------------------------------------------------------------------
    def _build_single_area_tab(self, parent, single_cfg, single_area):
        import tkinter as tk
        from tkinter import ttk

        # スクロール可能にする
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # グリッドを2列構成に
        scrollable.columnconfigure(1, weight=1)

        row = 0

        # 表示者選択
        ttk.Label(scrollable, text="表示者選択:", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        chk_frame = ttk.Frame(scrollable)
        chk_frame.grid(row=row, column=1, sticky="w", padx=4, pady=4)

        # config から初期値を読み込む
        cfg = self.config_manager
        self.single_show_streamer = tk.BooleanVar(value=bool(cfg.get("display.show.streamer", True)))
        self.single_show_ai = tk.BooleanVar(value=bool(cfg.get("display.show.ai", True)))
        self.single_show_viewer = tk.BooleanVar(value=bool(cfg.get("display.show.viewer", True)))

        # 保存処理・リセット処理との互換性のためエイリアスを張る
        self.show_streamer = self.single_show_streamer
        self.show_ai = self.single_show_ai
        self.show_viewer = self.single_show_viewer

        def _on_single_toggle():
            self._enforce_double_display_rules(source="single")
            self._update_area_preview()

        ttk.Checkbutton(chk_frame, text="配信者", variable=self.single_show_streamer,
                       command=_on_single_toggle).pack(side="left", padx=4)
        ttk.Checkbutton(chk_frame, text="AIキャラ", variable=self.single_show_ai,
                       command=_on_single_toggle).pack(side="left", padx=4)
        ttk.Checkbutton(chk_frame, text="視聴者", variable=self.single_show_viewer,
                       command=_on_single_toggle).pack(side="left", padx=4)

        # 表示件数
        row += 1
        ttk.Label(scrollable, text="表示件数 (0=自動):", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        self.single_max_items = tk.IntVar(value=single_cfg.get("max_items", 10))
        ttk.Entry(scrollable, textvariable=self.single_max_items, width=8).grid(
            row=row, column=1, sticky="w", padx=4, pady=4)

        # TTL
        row += 1
        ttk.Label(scrollable, text="自動消去 (TTL秒):", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        self.single_ttl = tk.IntVar(value=single_cfg.get("ttl", 8))
        ttk.Entry(scrollable, textvariable=self.single_ttl, width=8).grid(
            row=row, column=1, sticky="w", padx=4, pady=4)

        # ========== 表示エリア設定（座標入力） ==========
        row += 1
        ttk.Separator(scrollable, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=12)

        row += 1
        ttk.Label(scrollable, text="📐 表示エリア設定", font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # 座標変数の初期化
        self.single_area_x = tk.IntVar(value=single_area.get("x", 50))
        self.single_area_y = tk.IntVar(value=single_area.get("y", 0))
        self.single_area_w = tk.IntVar(value=single_area.get("w", 400))
        self.single_area_h = tk.IntVar(value=single_area.get("h", 600))

        # X座標
        row += 1
        ttk.Label(scrollable, text="X座標:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        x_frame = ttk.Frame(scrollable)
        x_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(x_frame, from_=0, to=1920, textvariable=self.single_area_x, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(x_frame, text="px").pack(side="left", padx=(4, 0))

        # Y座標
        row += 1
        ttk.Label(scrollable, text="Y座標:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        y_frame = ttk.Frame(scrollable)
        y_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(y_frame, from_=0, to=1080, textvariable=self.single_area_y, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(y_frame, text="px").pack(side="left", padx=(4, 0))

        # 幅
        row += 1
        ttk.Label(scrollable, text="幅:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        w_frame = ttk.Frame(scrollable)
        w_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(w_frame, from_=100, to=1920, textvariable=self.single_area_w, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(w_frame, text="px").pack(side="left", padx=(4, 0))

        # 高さ
        row += 1
        ttk.Label(scrollable, text="高さ:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        h_frame = ttk.Frame(scrollable)
        h_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(h_frame, from_=100, to=1080, textvariable=self.single_area_h, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(h_frame, text="px").pack(side="left", padx=(4, 0))

        # 位置編集ボタン
        row += 1
        ttk.Button(scrollable, text="🖱 プレビューで位置を編集",
                  command=lambda: self._edit_area_position("single")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=20, pady=8)

    # ------------------------------------------------------------------
    # 個別ロール用タブ（配信者 / AIキャラ / 視聴者）
    # ------------------------------------------------------------------
    def _build_role_area_tab(self, parent, role, label, role_cfg):
        """
        個別ロール（配信者/AIキャラ/視聴者）のタブを構築
        - 表示者選択チェックボックス（デフォルトOFF）
        - 表示件数・TTL設定
        - 座標設定
        """
        import tkinter as tk
        from tkinter import ttk

        # スクロール可能にする
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        scrollable.columnconfigure(1, weight=1)

        row = 0

        # 表示者選択チェックボックス
        ttk.Label(scrollable, text="表示者選択:", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)

        # デフォルトはOFF（False）
        enabled_var = tk.BooleanVar(value=role_cfg.get("enabled", False))
        setattr(self, f"role_{role}_enabled", enabled_var)

        def _on_multi_toggle():
            self._enforce_double_display_rules(source="multi")
            self._update_area_preview()

        ttk.Checkbutton(scrollable, text=f"{label}を表示", variable=enabled_var,
                       command=_on_multi_toggle).grid(
            row=row, column=1, sticky="w", padx=4, pady=4)

        # 表示件数
        row += 1
        ttk.Label(scrollable, text="表示件数 (0=自動):", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        max_items_var = tk.IntVar(value=role_cfg.get("max_items", 10))
        setattr(self, f"role_{role}_max", max_items_var)
        ttk.Entry(scrollable, textvariable=max_items_var, width=8).grid(
            row=row, column=1, sticky="w", padx=4, pady=4)

        # TTL
        row += 1
        ttk.Label(scrollable, text="自動消去 (TTL秒):", font=("", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8, pady=4)
        ttl_var = tk.IntVar(value=role_cfg.get("ttl", 8))
        setattr(self, f"role_{role}_ttl", ttl_var)
        ttk.Entry(scrollable, textvariable=ttl_var, width=8).grid(
            row=row, column=1, sticky="w", padx=4, pady=4)

        # ========== 表示エリア設定（座標入力） ==========
        row += 1
        ttk.Separator(scrollable, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=12)

        row += 1
        ttk.Label(scrollable, text="📐 表示エリア設定", font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # 座標変数の初期化（配信者・AIキャラ・視聴者でデフォルト位置を横並びに）
        default_positions = {
            "streamer": {"x": 50, "y": 0, "w": 400, "h": 360},
            "ai": {"x": 500, "y": 0, "w": 400, "h": 360},
            "viewer": {"x": 950, "y": 0, "w": 400, "h": 360}
        }
        area = role_cfg.get("area", default_positions.get(role, {"x": 50, "y": 0, "w": 400, "h": 360}))
        x_var = tk.IntVar(value=area.get("x", default_positions[role]["x"]))
        y_var = tk.IntVar(value=area.get("y", default_positions[role]["y"]))
        w_var = tk.IntVar(value=area.get("w", default_positions[role]["w"]))
        h_var = tk.IntVar(value=area.get("h", default_positions[role]["h"]))

        setattr(self, f"role_{role}_x", x_var)
        setattr(self, f"role_{role}_y", y_var)
        setattr(self, f"role_{role}_w", w_var)
        setattr(self, f"role_{role}_h", h_var)

        # X座標
        row += 1
        ttk.Label(scrollable, text="X座標:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        x_frame = ttk.Frame(scrollable)
        x_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(x_frame, from_=0, to=1920, textvariable=x_var, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(x_frame, text="px").pack(side="left", padx=(4, 0))

        # Y座標
        row += 1
        ttk.Label(scrollable, text="Y座標:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        y_frame = ttk.Frame(scrollable)
        y_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(y_frame, from_=0, to=1080, textvariable=y_var, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(y_frame, text="px").pack(side="left", padx=(4, 0))

        # 幅
        row += 1
        ttk.Label(scrollable, text="幅:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        w_frame = ttk.Frame(scrollable)
        w_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(w_frame, from_=100, to=1920, textvariable=w_var, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(w_frame, text="px").pack(side="left", padx=(4, 0))

        # 高さ
        row += 1
        ttk.Label(scrollable, text="高さ:").grid(row=row, column=0, sticky="w", padx=(20, 0), pady=2)
        h_frame = ttk.Frame(scrollable)
        h_frame.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        tk.Spinbox(h_frame, from_=100, to=1080, textvariable=h_var, width=10,
                  command=self._update_area_preview).pack(side="left")
        ttk.Label(h_frame, text="px").pack(side="left", padx=(4, 0))

        # 位置編集ボタン
        row += 1
        ttk.Button(scrollable, text="🖱 プレビューで位置を編集",
                  command=lambda: self._edit_area_position(role)).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=20, pady=8)

    def _on_area_tab_changed(self, event):
        """エリアタブ切り替え時の処理（編集中のロールを変更）"""
        if not hasattr(self, 'area_tabs_notebook'):
            return

        current_tab_index = self.area_tabs_notebook.index(self.area_tabs_notebook.select())

        # タブインデックスに応じて編集中のロールを変更
        role_map = {
            0: "single",      # 同一エリア
            1: "streamer",    # 配信者
            2: "ai",          # AIキャラ
            3: "viewer"       # 視聴者
        }

        role = role_map.get(current_tab_index, "single")

        # 共通ヘルパーを使ってロール＋プレビューを同期
        self._select_area_tab_for_role(role)

    def _select_area_tab_for_role(self, role: str):
        """
        プレビューキャンバス側からタブを同期させるヘルパー。
        role: "single" / "streamer" / "ai" / "viewer"
        """
        if not hasattr(self, "area_tabs_notebook"):
            return

        index_map = {
            "single": 0,      # 同一エリア
            "streamer": 1,    # 配信者
            "ai": 2,          # AIキャラ
            "viewer": 3,      # 視聴者
        }
        idx = index_map.get(role)
        if idx is None:
            return

        try:
            self.area_tabs_notebook.select(idx)
        except Exception:
            # Notebook 未構築などの場合は無視
            return

        # 編集対象ロールも合わせて変更
        if hasattr(self, "current_editing_role"):
            self.current_editing_role.set(role)

        # プレビュー再描画
        self._update_area_preview()

    # E-8: 役割タブ切り替え時の処理

    # E-8.5: 二重表示禁止の排他制御
    def _on_toggle_prevent_double(self):
        """二重表示禁止 ON/OFF 時に一度状態を正規化"""
        if not self.prevent_double_var.get():
            # OFF のときは何もしない（自由に二重表示OK）
            return
        self._enforce_double_display_rules()

    def _enforce_double_display_rules(self, source: str | None = None) -> None:
        """
        二重表示禁止が ON のとき、
        「同じロールが合同エリアと個別エリアの両方で ON になっている」場合だけ片方をOFFにする。

        - source == "single": 合同エリア側の操作 → 対応する個別エリア側だけOFF
        - source == "multi":  個別エリア側の操作 → 対応する合同エリア側だけOFF
        - source is None:     二重表示禁止をONにした直後など → 全ロールを一括チェック
        """
        # 二重表示禁止が OFF のときは一切何もしない
        if not self.prevent_double_var.get():
            return

        # ロール → (single側のフラグ, multi側のフラグ) の対応表
        role_map = {
            "streamer": (self.single_show_streamer, self.role_streamer_enabled),
            "ai":       (self.single_show_ai,       self.role_ai_enabled),
            "viewer":   (self.single_show_viewer,   self.role_viewer_enabled),
        }

        # ※ A案なので「特定ロールのみ」ではなく、全ロールを毎回チェックする
        for role_name, (single_var, multi_var) in role_map.items():
            single_on = bool(single_var.get())
            multi_on  = bool(multi_var.get())

            # 両方 ON になっているロールだけ調整する
            if single_on and multi_on:
                if source == "single":
                    # 合同エリア側を操作 → 個別エリア側をOFF
                    multi_var.set(False)
                elif source == "multi":
                    # 個別エリア側を操作 → 合同エリア側をOFF
                    single_var.set(False)
                else:
                    # source 不明（prevent_double を ON にした直後など）
                    # どちら優先かはお好みで。ここでは「合同エリア優先」として個別をOFFにする。
                    multi_var.set(False)

    # E-9: 設定の保存
    def _save_area_config(self):
        """コメント表示エリアの設定を保存（v17.6対応 + HTMLブリッジ）"""
        if not hasattr(self, "config_manager") or not self.config_manager:
            return

        cfg = self.config_manager

        # 1) 同一エリアの設定（新フォーマット）
        if hasattr(self, "single_area_x"):
            single_cfg = {
                "area": {
                    "x": int(self.single_area_x.get()),
                    "y": int(self.single_area_y.get()),
                    "w": int(self.single_area_w.get()),
                    "h": int(self.single_area_h.get()),
                }
            }

            # 表示件数（max_items）の保存
            if hasattr(self, "single_max_items"):
                try:
                    single_cfg["max_items"] = int(self.single_max_items.get() or 0)
                except Exception:
                    single_cfg["max_items"] = 0

            # 自動消去（TTL秒）の保存
            if hasattr(self, "single_ttl"):
                try:
                    single_cfg["ttl"] = int(self.single_ttl.get() or 0)
                except Exception:
                    single_cfg["ttl"] = 0

            # flow設定の保存（UP / DOWN / LEFT / RIGHT で保持）
            if hasattr(self, "single_flow"):
                flow_value = self.single_flow.get() or "UP"

                # 旧形式が残っている場合はここで正規化
                if flow_value == "vertical":
                    flow_value = "UP"
                elif flow_value == "horizontal-left":
                    flow_value = "LEFT"
                elif flow_value == "horizontal-right":
                    flow_value = "RIGHT"

                single_cfg["flow"] = flow_value

            cfg.set("display_area.single", single_cfg)

            # ★ HTML overlay 用: 旧フォーマット display.area.* にも反映
            single_area = single_cfg["area"]
            cfg.set("display.area.x", single_area["x"])
            cfg.set("display.area.y", single_area["y"])
            cfg.set("display.area.width", single_area["w"])
            cfg.set("display.area.height", single_area["h"])

        # 2) 各ロールの設定（新フォーマット）
        for role in ["streamer", "ai", "viewer"]:
            x_name = f"role_{role}_x"
            if not hasattr(self, x_name):
                continue

            # 座標
            area_cfg = {
                "area": {
                    "x": int(getattr(self, f"role_{role}_x").get()),
                    "y": int(getattr(self, f"role_{role}_y").get()),
                    "w": int(getattr(self, f"role_{role}_w").get()),
                    "h": int(getattr(self, f"role_{role}_h").get()),
                },
                # 表示のON/OFF
                "enabled": bool(getattr(self, f"role_{role}_enabled").get()),
            }

            # 表示件数（0 = 自動）の保存（あれば）
            max_name = f"role_{role}_max"
            if hasattr(self, max_name):
                try:
                    area_cfg["max_items"] = int(getattr(self, max_name).get() or 0)
                except Exception:
                    area_cfg["max_items"] = 0

            # 自動消去（TTL秒）の保存（あれば）
            ttl_name = f"role_{role}_ttl"
            if hasattr(self, ttl_name):
                try:
                    area_cfg["ttl"] = int(getattr(self, ttl_name).get() or 0)
                except Exception:
                    area_cfg["ttl"] = 0

            cfg.set(f"display_area.multi.{role}", area_cfg)

        # 3) コメントの流れ（single_flow → display.flow.direction）
        if hasattr(self, "single_flow"):
            flow_ui = self.single_flow.get() or "UP"

            # 旧形式も受け入れつつ、最終的には UP/DOWN/LEFT/RIGHT に揃える
            if flow_ui == "vertical":
                direction = "UP"
            elif flow_ui == "horizontal-left":
                direction = "LEFT"
            elif flow_ui == "horizontal-right":
                direction = "RIGHT"
            elif flow_ui in ("UP", "DOWN", "LEFT", "RIGHT"):
                direction = flow_ui
            else:
                direction = "UP"

            cfg.set("display.flow.direction", direction)

        # 3-1) 二重表示禁止フラグ → display.prevent_double
        if hasattr(self, "prevent_double_var"):
            try:
                cfg.set("display.prevent_double", bool(self.prevent_double_var.get()))
            except Exception as e:
                logger.warning(f"[AreaConfig] display.prevent_double の保存に失敗: {e}")

        # 4) 同一エリアタブの表示者選択チェックボックス → display.show.*
        # (overlay.html の showSettings に反映される)
        if hasattr(self, "single_show_streamer"):
            try:
                cfg.set("display.show.streamer", bool(self.single_show_streamer.get()))
            except Exception as e:
                logger.warning(f"[AreaConfig] display.show.streamer の保存に失敗: {e}")

        if hasattr(self, "single_show_ai"):
            try:
                cfg.set("display.show.ai", bool(self.single_show_ai.get()))
            except Exception as e:
                logger.warning(f"[AreaConfig] display.show.ai の保存に失敗: {e}")

        if hasattr(self, "single_show_viewer"):
            try:
                cfg.set("display.show.viewer", bool(self.single_show_viewer.get()))
            except Exception as e:
                logger.warning(f"[AreaConfig] display.show.viewer の保存に失敗: {e}")

        # 設定を保存
        cfg.save()

        # data.jsonを更新
        if hasattr(self, 'file_output') and self.file_output:
            try:
                self.file_output.flush_to_files()
                logger.debug(f"[AreaConfig] 座標設定を保存し、data.jsonを更新しました")
            except Exception as e:
                logger.error(f"[AreaConfig] data.json更新エラー: {e}")


    def _edit_area_position(self, role):
        """
        指定されたロールのエリア編集モードに切り替える
        role: "single", "streamer", "ai", "viewer"
        """
        self.current_editing_role.set(role)

        # プレビュー更新（編集中のロールをハイライト）
        self._update_area_preview()

    def _on_preview_resize(self, event):
        """プレビューコンテナのリサイズイベント"""
        # リサイズイベントが頻繁に発生するため、100ms後に再描画
        if hasattr(self, '_resize_timer'):
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(100, self._update_area_preview)

    def _update_area_preview(self):
        """プレビュー更新（v17.5.x 新仕様：single/multi 完全分離）"""
        if not hasattr(self, 'area_preview_canvas'):
            return

        canvas = self.area_preview_canvas

        # Canvasの実際のサイズを取得（リサイズ対応）
        canvas.update_idletasks()
        preview_display_width = canvas.winfo_width()
        preview_display_height = canvas.winfo_height()

        # 初期化時はサイズが取れないことがあるのでデフォルト値を使用
        if preview_display_width <= 1:
            preview_display_width = 400
        if preview_display_height <= 1:
            preview_display_height = 400

        canvas.delete("all")

        # OBSキャンバス解像度を取得
        canvas_w = self.canvas_width.get() if hasattr(self, 'canvas_width') else 1920
        canvas_h = self.canvas_height.get() if hasattr(self, 'canvas_height') else 1080

        # スケール計算（アスペクト比を保ったまま縮小）
        scale = min(preview_display_width / canvas_w, preview_display_height / canvas_h)

        # 実際の表示サイズ（中央に配置）
        display_w = int(canvas_w * scale)
        display_h = int(canvas_h * scale)
        offset_x = (preview_display_width - display_w) // 2
        offset_y = (preview_display_height - display_h) // 2

        # OBS画面全体を薄いグレーの枠で表示
        canvas.create_rectangle(offset_x, offset_y, offset_x + display_w, offset_y + display_h,
                               outline='#444', width=1, fill='#0a0a0a')

        # スケール情報を保存（マウスイベントで使用）
        self.preview_scale = scale
        self.preview_offset_x = offset_x
        self.preview_offset_y = offset_y

        # === v17.6 新仕様：すべての枠を並列表示 ===
        editing_role = self.current_editing_role.get() if hasattr(self, 'current_editing_role') else "single"

        drawn_any = False

        # ========== 1. 同一エリア（緑枠） ==========
        # 同一エリアの表示者選択チェックボックスのいずれかがONなら表示
        show_single = False
        if hasattr(self, 'single_show_streamer') and hasattr(self, 'single_show_ai') and hasattr(self, 'single_show_viewer'):
            if self.single_show_streamer.get() or self.single_show_ai.get() or self.single_show_viewer.get():
                show_single = True

        if show_single and hasattr(self, 'single_area_x'):
            x = int(self.single_area_x.get() * scale) + offset_x
            y = int(self.single_area_y.get() * scale) + offset_y
            w = int(self.single_area_w.get() * scale)
            h = int(self.single_area_h.get() * scale)

            # 編集中かどうかで見た目を変える
            is_editing = (editing_role == "single")
            line_width = 3 if is_editing else 2

            # 緑枠を描画（常にfillを設定して枠内全体をドラッグ可能に）
            canvas.create_rectangle(
                x, y, x + w, y + h,
                fill='#2a2a2a',
                outline='#00ff00',
                width=line_width,
                tags="area_single"
            )

            # チェックボックスで選択された表示者のサンプルコメントを表示
            sample_lines = []
            if self.single_show_streamer.get():
                sample_lines.append("配信者: これはサンプルメッセージです。")
            if self.single_show_ai.get():
                sample_lines.append("AIキャラ: サンプル応答です。")
            if self.single_show_viewer.get():
                sample_lines.append("視聴者: コメントの例です。")

            if sample_lines:
                label_text = "【編集中: 同一エリア】\n" if is_editing else ""
                canvas.create_text(
                    x + w // 2, y + h // 2,
                    text=label_text + "\n".join(sample_lines),
                    fill='#00ff00',
                    font=("Yu Gothic UI", 9),
                    justify="center",
                    tags="sample_text"
                )

            # リサイズハンドル（編集中のみ表示）
            if is_editing:
                handle_size = 8
                handles = [
                    (x, y, "nw"), (x + w, y, "ne"),
                    (x, y + h, "sw"), (x + w, y + h, "se")
                ]
                for hx, hy, tag in handles:
                    canvas.create_rectangle(
                        hx - handle_size//2, hy - handle_size//2,
                        hx + handle_size//2, hy + handle_size//2,
                        fill='#00ff00', outline='white', width=1, tags=f"handle_{tag}"
                    )

            drawn_any = True

        # ========== 2. 個別ロール（配信者・AIキャラ・視聴者） ==========
        # ロール定義 (role_key, enabled_var, x_var, y_var, w_var, h_var, color, label)
        role_defs = []

        if hasattr(self, 'role_streamer_enabled'):
            role_defs.append(("streamer", self.role_streamer_enabled, self.role_streamer_x, self.role_streamer_y,
                             self.role_streamer_w, self.role_streamer_h, '#FFD700', '配信者'))

        if hasattr(self, 'role_ai_enabled'):
            role_defs.append(("ai", self.role_ai_enabled, self.role_ai_x, self.role_ai_y,
                             self.role_ai_w, self.role_ai_h, '#FF69B4', 'AIキャラ'))

        if hasattr(self, 'role_viewer_enabled'):
            role_defs.append(("viewer", self.role_viewer_enabled, self.role_viewer_x, self.role_viewer_y,
                             self.role_viewer_w, self.role_viewer_h, '#00E5FF', '視聴者'))

        for role_key, enabled_var, x_var, y_var, w_var, h_var, color, label in role_defs:
            # enabled=True のロールのみ描画
            if not enabled_var.get():
                continue

            x = int(x_var.get() * scale) + offset_x
            y = int(y_var.get() * scale) + offset_y
            w = int(w_var.get() * scale)
            h = int(h_var.get() * scale)

            # 編集中のロールは太枠で強調
            is_editing = (role_key == editing_role)
            line_width = 3 if is_editing else 2

            # 枠を描画（常にfillを設定して枠内全体をドラッグ可能に）
            canvas.create_rectangle(
                x, y, x + w, y + h,
                fill='#2a2a2a',
                outline=color,
                width=line_width,
                tags=f"area_{role_key}"
            )

            # ラベルを表示（編集中は強調）
            label_text = f"【編集中: {label}】" if is_editing else label
            canvas.create_text(
                x + 5, y + 5,
                text=label_text,
                anchor="nw",
                fill=color,
                font=("", 10, "bold" if is_editing else "normal"),
                tags=f"label_{role_key}"
            )

            # リサイズハンドル（編集中のみ表示）
            if is_editing:
                handle_size = 8
                handles = [
                    (x, y, "nw"), (x + w, y, "ne"),
                    (x, y + h, "sw"), (x + w, y + h, "se")
                ]
                for hx, hy, tag in handles:
                    canvas.create_rectangle(
                        hx - handle_size//2, hy - handle_size//2,
                        hx + handle_size//2, hy + handle_size//2,
                        fill=color, outline='white', width=1,
                        tags=f"handle_{tag}_{role_key}"
                    )

            drawn_any = True

        # 何も有効な枠がない場合
        if not drawn_any:
            canvas.create_text(
                offset_x + display_w // 2,
                offset_y + display_h // 2,
                text="表示者が選択されていません\nいずれかのタブで表示者選択をONにしてください",
                fill="gray",
                font=("", 12),
                justify="center",
                tags="no_area_message"
            )

    def _get_editing_area_vars(self):
        """
        現在編集中のロールのエリア座標変数を取得
        Returns: (x_var, y_var, w_var, h_var) または None
        """
        if not hasattr(self, 'current_editing_role'):
            return None

        role = self.current_editing_role.get()

        if role == "single":
            if hasattr(self, 'single_area_x'):
                return (self.single_area_x, self.single_area_y, self.single_area_w, self.single_area_h)
        elif role == "streamer":
            if hasattr(self, 'role_streamer_x'):
                return (self.role_streamer_x, self.role_streamer_y, self.role_streamer_w, self.role_streamer_h)
        elif role == "ai":
            if hasattr(self, 'role_ai_x'):
                return (self.role_ai_x, self.role_ai_y, self.role_ai_w, self.role_ai_h)
        elif role == "viewer":
            if hasattr(self, 'role_viewer_x'):
                return (self.role_viewer_x, self.role_viewer_y, self.role_viewer_w, self.role_viewer_h)

        return None
    
    def _on_preview_press(self, event):
        """マウスプレス（すべてのエリアをドラッグ可能）"""
        items = self.area_preview_canvas.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)

        clicked_role = None

        # ハンドルをクリックしているか確認（role付きハンドル対応）
        for item in items:
            tags = self.area_preview_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("handle_"):
                    # handle_nw_streamer のような形式からロールを抽出
                    parts = tag.replace("handle_", "").split("_")
                    if len(parts) >= 2:
                        handle_dir = parts[0]
                        clicked_role = parts[1]
                        self.preview_drag_data["resize_handle"] = handle_dir
                    else:
                        # handle_nw のような形式（singleの場合）
                        clicked_role = "single"
                        self.preview_drag_data["resize_handle"] = tag.replace("handle_", "")
                    self.preview_drag_data["x"] = event.x
                    self.preview_drag_data["y"] = event.y

                    # タブ側も同期（single / streamer / ai / viewer）
                    self._select_area_tab_for_role(clicked_role)
                    return

        # エリア全体をドラッグ（すべてのロール対応）
        for item in items:
            tags = self.area_preview_canvas.gettags(item)
            # area_streamer, area_ai, area_viewer, area_single のいずれかをチェック
            for tag in tags:
                if tag.startswith("area_"):
                    clicked_role = tag.replace("area_", "")
                    self.preview_drag_data["dragging"] = True
                    self.preview_drag_data["x"] = event.x
                    self.preview_drag_data["y"] = event.y

                    # タブ側も同期（single / streamer / ai / viewer）
                    self._select_area_tab_for_role(clicked_role)
                    return

    def _on_preview_drag(self, event):
        """ドラッグ中（v17.5.x: 編集中のロールの座標を更新）"""
        # 編集中のロールの座標変数を取得
        area_vars = self._get_editing_area_vars()
        if not area_vars:
            return

        x_var, y_var, w_var, h_var = area_vars

        dx = event.x - self.preview_drag_data["x"]
        dy = event.y - self.preview_drag_data["y"]

        # 現在のスケールとキャンバス解像度を取得
        scale = getattr(self, 'preview_scale', 0.3)
        canvas_w = self.canvas_width.get() if hasattr(self, 'canvas_width') else 1920
        canvas_h = self.canvas_height.get() if hasattr(self, 'canvas_height') else 1080

        if self.preview_drag_data.get("resize_handle"):
            # リサイズ
            handle = self.preview_drag_data["resize_handle"]

            if "e" in handle:  # 右
                new_w = w_var.get() + int(dx / scale)
                w_var.set(max(100, min(canvas_w - x_var.get(), new_w)))
            if "w" in handle:  # 左
                new_x = x_var.get() + int(dx / scale)
                new_w = w_var.get() - int(dx / scale)
                if new_w >= 100:
                    x_var.set(max(0, new_x))
                    w_var.set(new_w)

            if "s" in handle:  # 下
                new_h = h_var.get() + int(dy / scale)
                h_var.set(max(100, min(canvas_h - y_var.get(), new_h)))
            if "n" in handle:  # 上
                new_y = y_var.get() + int(dy / scale)
                new_h = h_var.get() - int(dy / scale)
                if new_h >= 100:
                    y_var.set(max(0, new_y))
                    h_var.set(new_h)

            self.preview_drag_data["x"] = event.x
            self.preview_drag_data["y"] = event.y
            self._update_area_preview()

        elif self.preview_drag_data.get("dragging"):
            # 移動
            new_x = x_var.get() + int(dx / scale)
            new_y = y_var.get() + int(dy / scale)

            # 画面外に出ないように制限
            new_x = max(0, min(canvas_w - w_var.get(), new_x))
            new_y = max(0, min(canvas_h - h_var.get(), new_y))

            x_var.set(new_x)
            y_var.set(new_y)

            self.preview_drag_data["x"] = event.x
            self.preview_drag_data["y"] = event.y
            self._update_area_preview()
    
    def _on_preview_release(self, event):
        """マウスリリース（ドラッグ終了時に設定を保存）"""
        # ドラッグ中だった場合のみ保存
        was_dragging = self.preview_drag_data.get("dragging") or self.preview_drag_data.get("resize_handle")

        self.preview_drag_data["dragging"] = False
        self.preview_drag_data["resize_handle"] = None

        # 設定を保存して data.json を更新
        if was_dragging:
            if hasattr(self, "_save_area_config"):
                self._save_area_config()
            # HTML overlay へ即時反映（file_backend 統合版があれば flush_to_files が呼ばれる）
            if hasattr(self, "_export_overlay_snapshot"):
                self._export_overlay_snapshot()
    
    def _on_preview_motion(self, event):
        """マウス移動（カーソル変更）"""
        items = self.area_preview_canvas.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)
        cursor = "arrow"
        
        for item in items:
            tags = self.area_preview_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("handle_"):
                    handle = tag.replace("handle_", "")
                    if handle in ["nw", "se"]:
                        cursor = "size_nw_se"
                    elif handle in ["ne", "sw"]:
                        cursor = "size_ne_sw"
                    break
            if cursor != "arrow":
                break
        
        if cursor == "arrow" and self.preview_rect and self.preview_rect in items:
            cursor = "fleur"  # 移動カーソル
        
        self.area_preview_canvas.config(cursor=cursor)
    
    def _reset_area_settings(self):
        """設定リセット（安全性向上：hasattrチェック付き）"""
        # エリアプリセット
        if hasattr(self, "area_preset"):
            self.area_preset.set("custom")

        # 座標とサイズ
        if hasattr(self, "area_x"):
            self.area_x.set(100)
        if hasattr(self, "area_y"):
            self.area_y.set(100)
        if hasattr(self, "area_width"):
            self.area_width.set(400)
        if hasattr(self, "area_height"):
            self.area_height.set(600)

        # フロー方向
        if hasattr(self, "flow_direction_area"):
            self.flow_direction_area.set("UP")
        if hasattr(self, "flow_pad_bottom_area"):
            self.flow_pad_bottom_area.set(True)

        # 表示者選択（同一エリア）
        # show_* は single_show_* のエイリアスなので、どちらかが存在すればOK
        if hasattr(self, "show_streamer"):
            self.show_streamer.set(True)
        if hasattr(self, "show_ai"):
            self.show_ai.set(True)
        if hasattr(self, "show_viewer"):
            self.show_viewer.set(True)

        # プレビュー更新
        if hasattr(self, "_update_area_preview"):
            self._update_area_preview()

    def _inject_comment_style_controls(self, parent):
        """
        コメントスタイル設定（スクロール可能な拡張版 + プレビュー）
        - フォント・テキスト関連
        - レイアウト関連
        - 背景関連
        - 役割別カラー
        """
        import tkinter as tk
        from tkinter import ttk, colorchooser
        
        cfg = getattr(self, "config_manager", None)
        if cfg is None:
            return
        
        # 設定パネルコンテナ（「コメント表示エリア設定」と同じ構造）
        main_container = ttk.Frame(parent)
        main_container.pack(fill="both", expand=True, padx=8, pady=6)

        # スクロール可能な設定パネル
        canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ======================
        # Phase 2: プリセット選択UI
        # ======================
        preset_frame = ttk.LabelFrame(scroll_frame, text="🎨 スタイルプリセット", padding=(8, 6))
        preset_frame.pack(fill="x", padx=4, pady=(0, 8))

        ttk.Label(preset_frame, text="プリセット:").grid(row=0, column=0, sticky="w", pady=4)

        # プリセット名リストを取得（obs_configから取得）
        preset_names = ["default"]
        active_preset = "default"

        if hasattr(self, 'obs_config') and self.obs_config:
            preset_names = self.obs_config.get_preset_names() if hasattr(self.obs_config, 'get_preset_names') else ["default"]
            active_preset = self.obs_config.get_active_preset_name() if hasattr(self.obs_config, 'get_active_preset_name') else "default"
            # ソート: Default先頭、残りはアルファベット順
            default_names = [n for n in preset_names if n.lower() == "default"]
            other_names = sorted([n for n in preset_names if n.lower() != "default"])
            preset_names = default_names + other_names

        # デバッグログ
        logger.debug(f"利用可能なプリセット一覧: {preset_names}")
        logger.debug(f"現在のアクティブプリセット: {active_preset}")
        logger.debug(f"プリセット数: {len(preset_names)}")

        self.comment_preset_var = tk.StringVar(value=active_preset)
        self.comment_preset_combo = ttk.Combobox(preset_frame, textvariable=self.comment_preset_var,
                                    width=20, state="readonly")
        self.comment_preset_combo['values'] = tuple(preset_names)
        self.comment_preset_combo.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)
        self.comment_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_comment_preset())

        preset_frame.grid_columnconfigure(1, weight=1)

        # プリセット操作ボタン
        button_row = ttk.Frame(preset_frame)
        button_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        ttk.Button(button_row, text="💾 現在の設定を保存", command=self._save_current_preset).pack(side="left", padx=(0, 4))
        ttk.Button(button_row, text="🗑️ プリセットを削除", command=self._delete_current_preset).pack(side="left", padx=(0, 4))
        ttk.Button(button_row, text="🔄 デフォルトに戻す", command=self._reset_to_default_preset).pack(side="left")

        # 初期化完了後にプリセット一覧を再読み込み
        self.after(100, self._reload_preset_list)

        # プレビューは右側の共通プレビューパネルを使用

        # ======================
        # 役割別カラー（最優先で表示）
        # ======================
        role_frame = ttk.LabelFrame(scroll_frame, text="👥 役割別カラー", padding=(8, 6))
        role_frame.pack(fill="x", padx=4, pady=4)

        # 配信者の色（role.*を優先、なければstyle.role.*を読み込む）
        self.streamer_color = tk.StringVar(value=cfg.get("role.streamer.color", cfg.get("style.role.streamer.color", "#4A90E2")))
        self.streamer_color.trace_add("write", self._on_style_changed)
        ttk.Label(role_frame, text="配信者:").grid(row=0, column=0, sticky="w", pady=2)
        streamer_btn = ttk.Button(role_frame, text="選択", width=8,
                                  command=lambda: self._pick_color(self.streamer_color, "配信者の色"))
        streamer_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.streamer_color_preview = tk.Label(role_frame, text="  ", bg=self.streamer_color.get(), width=3, relief="solid")
        self.streamer_color_preview.grid(row=0, column=2, pady=2)

        # AIの色（role.*を優先、なければstyle.role.*を読み込む）
        self.ai_color = tk.StringVar(value=cfg.get("role.ai.color", cfg.get("style.role.ai.color", "#9B59B6")))
        self.ai_color.trace_add("write", self._on_style_changed)
        ttk.Label(role_frame, text="AI:").grid(row=1, column=0, sticky="w", pady=2)
        ai_btn = ttk.Button(role_frame, text="選択", width=8,
                           command=lambda: self._pick_color(self.ai_color, "AIの色"))
        ai_btn.grid(row=1, column=1, sticky="w", padx=(4, 8), pady=2)
        self.ai_color_preview = tk.Label(role_frame, text="  ", bg=self.ai_color.get(), width=3, relief="solid")
        self.ai_color_preview.grid(row=1, column=2, pady=2)

        # 視聴者の色（role.*を優先、なければstyle.role.*を読み込む）
        self.viewer_color = tk.StringVar(value=cfg.get("role.viewer.color", cfg.get("style.role.viewer.color", "#7F8C8D")))
        self.viewer_color.trace_add("write", self._on_style_changed)
        ttk.Label(role_frame, text="視聴者:").grid(row=2, column=0, sticky="w", pady=2)
        viewer_btn = ttk.Button(role_frame, text="選択", width=8,
                                command=lambda: self._pick_color(self.viewer_color, "視聴者の色"))
        viewer_btn.grid(row=2, column=1, sticky="w", padx=(4, 8), pady=2)
        self.viewer_color_preview = tk.Label(role_frame, text="  ", bg=self.viewer_color.get(), width=3, relief="solid")
        self.viewer_color_preview.grid(row=2, column=2, pady=2)

        # ======================
        # Phase 1: フォント・テキスト関連
        # ======================
        font_frame = ttk.LabelFrame(scroll_frame, text="📝 フォント・テキスト", padding=(8, 6))
        font_frame.pack(fill="x", padx=4, pady=4)

        self.name_show_var = tk.BooleanVar(
            value=bool(self.config_manager.get("style.name.show", True))
        )

        
        # プリセット選択
        preset_frame = ttk.LabelFrame(font_frame, text="🎯 スタイルプリセット", padding=(6, 4))
        preset_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        
        # 「名前を表示する」チェックボックスをpreset_frame内に配置（grid統一）
        ttk.Checkbutton(
            preset_frame,
            text="名前を表示する",
            variable=self.name_show_var,
            command=self._on_style_changed
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=(10, 0), pady=(0, 4))
        
        def apply_preset_simple():
            """シンプルプリセット"""
            self.name_font_size.set(24)
            self.name_font_bold.set(True)
            self.name_font_italic.set(False)
            self.name_use_custom_color.set(False)
            self.body_font_size.set(26)
            self.body_font_bold.set(False)
            self.body_font_italic.set(False)
            self.body_indent.set(0)
            logger.info("プリセット: シンプルを適用")
            self._on_style_changed()

        def apply_preset_indent():
            """インデント強調プリセット"""
            self.name_font_size.set(24)
            self.name_font_bold.set(True)
            self.name_font_italic.set(False)
            self.name_use_custom_color.set(True)
            self.name_custom_color.set("#FFFFFF")
            self.name_color_preview.config(bg="#FFFFFF")
            self.body_font_size.set(26)
            self.body_font_bold.set(False)
            self.body_font_italic.set(False)
            self.body_indent.set(15)
            logger.info("プリセット: インデント強調を適用")
            self._on_style_changed()

        def apply_preset_chat():
            """チャット風プリセット"""
            self.name_font_size.set(24)
            self.name_font_bold.set(True)
            self.name_font_italic.set(False)
            self.name_use_custom_color.set(True)
            self.name_custom_color.set("#FFD700")
            self.name_color_preview.config(bg="#FFD700")
            self.body_font_size.set(26)
            self.body_font_bold.set(False)
            self.body_font_italic.set(False)
            self.body_indent.set(5)
            logger.info("プリセット: チャット風を適用")
            self._on_style_changed()
        
        # ラベルは row=1 に
        ttk.Label(preset_frame, text="ワンクリックで設定を適用:").grid(row=1, column=0, sticky="w", pady=2)
        
        # ボタン行は row=2 に
        preset_buttons = ttk.Frame(preset_frame)
        preset_buttons.grid(row=2, column=0, sticky="w", pady=(4, 0))
        
        ttk.Button(preset_buttons, text="📋 シンプル", command=apply_preset_simple, width=12).pack(side="left", padx=(0, 4))
        ttk.Button(preset_buttons, text="➡インデント強調", command=apply_preset_indent, width=14).pack(side="left", padx=(0, 4))
        ttk.Button(preset_buttons, text="💬 チャット風", command=apply_preset_chat, width=12).pack(side="left")
        
        # プリセット説明は row=3 に
        preset_desc = ttk.Frame(preset_frame)
        preset_desc.grid(row=3, column=0, sticky="w", pady=(4, 0), padx=(10, 0))
        ttk.Label(preset_desc, text="• シンプル: 基本的な設定", foreground="gray", font=("", 8)).pack(anchor="w")
        ttk.Label(preset_desc, text="• インデント強調: 本文を15px字下げ、名前は明るい色", foreground="gray", font=("", 8)).pack(anchor="w")
        ttk.Label(preset_desc, text="• チャット風: 名前は金色、本文は5px字下げ", foreground="gray", font=("", 8)).pack(anchor="w")
        
        # セパレーター
        ttk.Separator(font_frame, orient="horizontal").grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        
        # 書体（フォント）- 全体共通
        self.font_family = tk.StringVar(value=cfg.get("style.font.family", "Yu Gothic UI"))
        self.font_family.trace_add("write", self._on_style_changed)
        ttk.Label(font_frame, text="書体（全体共通）:").grid(row=2, column=0, sticky="w", pady=2)
        font_combo = ttk.Combobox(font_frame, textvariable=self.font_family, width=20)
        font_combo['values'] = ("Yu Gothic UI", "Meiryo UI", "MS Gothic", "Arial", "Segoe UI")
        font_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=2)
        
        # セパレーター
        ttk.Separator(font_frame, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        
        # --- 名前の設定 ---
        ttk.Label(font_frame, text="👤 名前の設定", font=("", 9, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 2))
        
        # 名前のフォントサイズ
        self.name_font_size = tk.IntVar(value=int(cfg.get("style.name.font.size", 24)))
        self.name_font_size.trace_add("write", self._on_style_changed)
        ttk.Label(font_frame, text="サイズ:").grid(row=5, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(font_frame, from_=8, to=72, textvariable=self.name_font_size, width=8).grid(row=5, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # 名前の太字・斜体
        self.name_font_bold = tk.BooleanVar(value=bool(cfg.get("style.name.font.bold", True)))
        self.name_font_bold.trace_add("write", self._on_style_changed)
        self.name_font_italic = tk.BooleanVar(value=bool(cfg.get("style.name.font.italic", False)))
        self.name_font_italic.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(font_frame, text="太字", variable=self.name_font_bold).grid(row=6, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(font_frame, text="斜体", variable=self.name_font_italic).grid(row=6, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # 名前の色（独自設定を使うかどうか）
        self.name_use_custom_color = tk.BooleanVar(value=bool(cfg.get("style.name.use_custom_color", False)))
        self.name_use_custom_color.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(font_frame, text="名前に独自の色を使う", variable=self.name_use_custom_color).grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 2), padx=(20, 0))
        
        name_color_frame = ttk.Frame(font_frame)
        name_color_frame.grid(row=8, column=0, columnspan=3, sticky="w", padx=(40, 0))
        
        self.name_custom_color = tk.StringVar(value=cfg.get("style.name.custom_color", "#FFFFFF"))
        self.name_custom_color.trace_add("write", self._on_style_changed)
        ttk.Label(name_color_frame, text="色:").grid(row=0, column=0, sticky="w", pady=2)
        name_color_btn = ttk.Button(name_color_frame, text="選択", width=8,
                                    command=lambda: self._pick_color(self.name_custom_color, "名前の色"))
        name_color_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.name_color_preview = tk.Label(name_color_frame, text="  ", bg=self.name_custom_color.get(), width=3, relief="solid")
        self.name_color_preview.grid(row=0, column=2, pady=2)
        
        # セパレーター
        ttk.Separator(font_frame, orient="horizontal").grid(row=9, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        
        # --- 本文の設定 ---
        ttk.Label(font_frame, text="💬 本文の設定", font=("", 9, "bold")).grid(row=10, column=0, columnspan=3, sticky="w", pady=(4, 2))
        
        # 本文のフォントサイズ
        self.body_font_size = tk.IntVar(value=int(cfg.get("style.body.font.size", 26)))
        self.body_font_size.trace_add("write", self._on_style_changed)
        ttk.Label(font_frame, text="サイズ:").grid(row=11, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(font_frame, from_=8, to=72, textvariable=self.body_font_size, width=8).grid(row=11, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # 本文の太字・斜体
        self.body_font_bold = tk.BooleanVar(value=bool(cfg.get("style.body.font.bold", False)))
        self.body_font_bold.trace_add("write", self._on_style_changed)
        self.body_font_italic = tk.BooleanVar(value=bool(cfg.get("style.body.font.italic", False)))
        self.body_font_italic.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(font_frame, text="太字", variable=self.body_font_bold).grid(row=12, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Checkbutton(font_frame, text="斜体", variable=self.body_font_italic).grid(row=12, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # 本文のインデント
        self.body_indent = tk.IntVar(value=int(cfg.get("style.body.indent", 0)))
        self.body_indent.trace_add("write", self._on_style_changed)
        ttk.Label(font_frame, text="インデント（左空白）:").grid(row=13, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(font_frame, from_=0, to=100, textvariable=self.body_indent, width=8).grid(row=13, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(font_frame, text="px").grid(row=13, column=2, sticky="w", pady=2)
        
        # セパレーター
        ttk.Separator(font_frame, orient="horizontal").grid(row=14, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        
        # 文字の影
        shadow_sub = ttk.Frame(font_frame)
        shadow_sub.grid(row=15, column=0, columnspan=3, sticky="w", pady=4)
        
        self.shadow_enabled = tk.BooleanVar(value=bool(cfg.get("style.text.shadow.enabled", False)))
        self.shadow_enabled.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(shadow_sub, text="文字の影を表示（全体）", variable=self.shadow_enabled).pack(side="left")

        shadow_detail = ttk.Frame(font_frame)
        shadow_detail.grid(row=16, column=0, columnspan=3, sticky="w", padx=(20, 0))

        self.shadow_color = tk.StringVar(value=cfg.get("style.text.shadow.color", "#000000"))
        self.shadow_color.trace_add("write", self._on_style_changed)
        ttk.Label(shadow_detail, text="影の色:").grid(row=0, column=0, sticky="w", pady=2)
        shadow_color_btn = ttk.Button(shadow_detail, text="選択", width=8,
                                      command=lambda: self._pick_color(self.shadow_color, "影の色"))
        shadow_color_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.shadow_color_preview = tk.Label(shadow_detail, text="  ", bg=self.shadow_color.get(), width=3, relief="solid")
        self.shadow_color_preview.grid(row=0, column=2, pady=2)

        self.shadow_offset_x = tk.IntVar(value=int(cfg.get("style.text.shadow.offset_x", 2)))
        self.shadow_offset_x.trace_add("write", self._on_style_changed)
        self.shadow_offset_y = tk.IntVar(value=int(cfg.get("style.text.shadow.offset_y", 2)))
        self.shadow_offset_y.trace_add("write", self._on_style_changed)
        self.shadow_blur = tk.IntVar(value=int(cfg.get("style.text.shadow.blur", 0)))
        self.shadow_blur.trace_add("write", self._on_style_changed)
        
        ttk.Label(shadow_detail, text="オフセットX:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(shadow_detail, from_=-10, to=10, textvariable=self.shadow_offset_x, width=6).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=2)
        
        ttk.Label(shadow_detail, text="オフセットY:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(shadow_detail, from_=-10, to=10, textvariable=self.shadow_offset_y, width=6).grid(row=2, column=1, sticky="w", padx=(4, 0), pady=2)
        
        ttk.Label(shadow_detail, text="ぼかし:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Spinbox(shadow_detail, from_=0, to=20, textvariable=self.shadow_blur, width=6).grid(row=3, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # ======================
        # Phase 2: レイアウト関連
        # ======================
        layout_frame = ttk.LabelFrame(scroll_frame, text="📐 レイアウト", padding=(8, 6))
        layout_frame.pack(fill="x", padx=4, pady=4)
        
        # 名前の位置（8種類のプリセット）
        self.name_position = tk.StringVar(value=cfg.get("style.layout.name_position", "TOP_LEFT").upper())
        self.name_position.trace_add("write", self._on_style_changed)
        
        ttk.Label(layout_frame, text="🎯 名前の位置プリセット", font=("", 9, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(4, 2))
        
        # プリセット選択（2行×4列）
        name_pos_frame = ttk.Frame(layout_frame)
        name_pos_frame.grid(row=1, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=4)
        
        presets = [
            ("左上", "TOP_LEFT"),
            ("右上", "TOP_RIGHT"),
            ("左", "MIDDLE_LEFT"),
            ("右", "MIDDLE_RIGHT"),
            ("左下", "BOTTOM_LEFT"),
            ("右下", "BOTTOM_RIGHT"),
            ("上（中央）", "TOP_CENTER"),
            ("下（中央）", "BOTTOM_CENTER")
        ]
        
        for i, (label, value) in enumerate(presets):
            row = i // 4
            col = i % 4
            ttk.Radiobutton(name_pos_frame, text=label, value=value, variable=self.name_position)\
                .grid(row=row, column=col, sticky="w", padx=(0, 8), pady=2)
        
        # X/Yオフセット（微調整）
        ttk.Label(layout_frame, text="📏 位置の微調整", font=("", 9, "bold")).grid(row=2, column=0, columnspan=4, sticky="w", pady=(12, 2))
        
        self.name_offset_x = tk.IntVar(value=int(cfg.get("style.layout.name_offset_x", 0)))
        self.name_offset_x.trace_add("write", self._on_style_changed)
        ttk.Label(layout_frame, text="X座標オフセット:").grid(row=3, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(layout_frame, from_=-100, to=100, textvariable=self.name_offset_x, width=8).grid(row=3, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(layout_frame, text="px").grid(row=3, column=2, sticky="w", pady=2)
        
        self.name_offset_y = tk.IntVar(value=int(cfg.get("style.layout.name_offset_y", 0)))
        self.name_offset_y.trace_add("write", self._on_style_changed)
        ttk.Label(layout_frame, text="Y座標オフセット:").grid(row=4, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(layout_frame, from_=-100, to=100, textvariable=self.name_offset_y, width=8).grid(row=4, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(layout_frame, text="px").grid(row=4, column=2, sticky="w", pady=2)
        
        # 名前と本文の間隔
        self.name_body_spacing = tk.IntVar(value=int(cfg.get("style.layout.name_body_spacing", 4)))
        self.name_body_spacing.trace_add("write", self._on_style_changed)
        ttk.Label(layout_frame, text="名前と本文の間隔:").grid(row=5, column=0, sticky="w", pady=2, padx=(20, 0))
        ttk.Spinbox(layout_frame, from_=0, to=50, textvariable=self.name_body_spacing, width=8).grid(row=5, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(layout_frame, text="px").grid(row=5, column=2, sticky="w", pady=2)
        
        # セパレーター
        ttk.Separator(layout_frame, orient="horizontal").grid(row=6, column=0, columnspan=4, sticky="ew", pady=(8, 8))
        
        # 行間
        self.line_height = tk.DoubleVar(value=float(cfg.get("style.layout.line_height", 1.5)))
        self.line_height.trace_add("write", self._on_style_changed)
        ttk.Label(layout_frame, text="行間:").grid(row=7, column=0, sticky="w", pady=2)
        ttk.Spinbox(layout_frame, from_=1.0, to=3.0, increment=0.1, textvariable=self.line_height, width=8).grid(row=7, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # パディング（内側余白）
        self.padding_top = tk.IntVar(value=int(cfg.get("style.layout.padding.top", 8)))
        self.padding_top.trace_add("write", self._on_style_changed)
        self.padding_right = tk.IntVar(value=int(cfg.get("style.layout.padding.right", 12)))
        self.padding_right.trace_add("write", self._on_style_changed)
        self.padding_bottom = tk.IntVar(value=int(cfg.get("style.layout.padding.bottom", 8)))
        self.padding_bottom.trace_add("write", self._on_style_changed)
        self.padding_left = tk.IntVar(value=int(cfg.get("style.layout.padding.left", 12)))
        self.padding_left.trace_add("write", self._on_style_changed)
        
        ttk.Label(layout_frame, text="パディング（上右下左）:").grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 2))
        
        padding_grid = ttk.Frame(layout_frame)
        padding_grid.grid(row=9, column=0, columnspan=4, sticky="w", padx=(20, 0))
        
        ttk.Label(padding_grid, text="上:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Spinbox(padding_grid, from_=0, to=50, textvariable=self.padding_top, width=6).grid(row=0, column=1, sticky="w", padx=(4, 12), pady=2)
        
        ttk.Label(padding_grid, text="右:").grid(row=0, column=2, sticky="w", pady=2)
        ttk.Spinbox(padding_grid, from_=0, to=50, textvariable=self.padding_right, width=6).grid(row=0, column=3, sticky="w", padx=(4, 0), pady=2)
        
        ttk.Label(padding_grid, text="下:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(padding_grid, from_=0, to=50, textvariable=self.padding_bottom, width=6).grid(row=1, column=1, sticky="w", padx=(4, 12), pady=2)
        
        ttk.Label(padding_grid, text="左:").grid(row=1, column=2, sticky="w", pady=2)
        ttk.Spinbox(padding_grid, from_=0, to=50, textvariable=self.padding_left, width=6).grid(row=1, column=3, sticky="w", padx=(4, 0), pady=2)
        
        # ======================
        # Phase 3: 背景関連
        # ======================
        bg_frame = ttk.LabelFrame(scroll_frame, text="🎨 背景", padding=(8, 6))
        bg_frame.pack(fill="x", padx=4, pady=4)
        
        # 背景色
        self.bg_color = tk.StringVar(value=cfg.get("style.background.color", "#FFFFFF"))
        self.bg_color.trace_add("write", self._on_style_changed)
        ttk.Label(bg_frame, text="背景色:").grid(row=0, column=0, sticky="w", pady=2)
        bg_color_btn = ttk.Button(bg_frame, text="選択", width=8,
                                  command=lambda: self._pick_color(self.bg_color, "背景色"))
        bg_color_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.bg_color_preview = tk.Label(bg_frame, text="  ", bg=self.bg_color.get(), width=3, relief="solid")
        self.bg_color_preview.grid(row=0, column=2, pady=2)
        
        # 背景の透明度
        self.bg_opacity = tk.IntVar(value=int(cfg.get("style.background.opacity", 100)))
        self.bg_opacity.trace_add("write", self._on_style_changed)
        ttk.Label(bg_frame, text="透明度 (%):").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Scale(bg_frame, from_=0, to=100, variable=self.bg_opacity, orient="horizontal", length=150).grid(row=1, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=2)
        
        # 角丸
        self.border_radius = tk.IntVar(value=int(cfg.get("style.background.border_radius", 0)))
        self.border_radius.trace_add("write", self._on_style_changed)
        ttk.Label(bg_frame, text="角丸 (px):").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(bg_frame, from_=0, to=50, textvariable=self.border_radius, width=8).grid(row=2, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # 枠線
        self.border_enabled = tk.BooleanVar(value=bool(cfg.get("style.background.border.enabled", False)))
        self.border_enabled.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(bg_frame, text="枠線を表示", variable=self.border_enabled).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 2))
        
        border_detail = ttk.Frame(bg_frame)
        border_detail.grid(row=4, column=0, columnspan=3, sticky="w", padx=(20, 0))
        
        self.border_color = tk.StringVar(value=cfg.get("style.background.border.color", "#000000"))
        self.border_color.trace_add("write", self._on_style_changed)
        ttk.Label(border_detail, text="枠線の色:").grid(row=0, column=0, sticky="w", pady=2)
        border_color_btn = ttk.Button(border_detail, text="選択", width=8,
                                      command=lambda: self._pick_color(self.border_color, "枠線の色"))
        border_color_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.border_color_preview = tk.Label(border_detail, text="  ", bg=self.border_color.get(), width=3, relief="solid")
        self.border_color_preview.grid(row=0, column=2, pady=2)
        
        self.border_width = tk.IntVar(value=int(cfg.get("style.background.border.width", 1)))
        self.border_width.trace_add("write", self._on_style_changed)
        ttk.Label(border_detail, text="枠線の太さ:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(border_detail, from_=1, to=10, textvariable=self.border_width, width=6).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=2)
        
        # ======================
        # 吹き出し機能
        # ======================
        bubble_frame = ttk.LabelFrame(scroll_frame, text="💬 吹き出し", padding=(8, 6))
        bubble_frame.pack(fill="x", padx=4, pady=4)
        
        # 吹き出しの種類（5種類）
        self.bubble_type = tk.StringVar(value=cfg.get("style.bubble.type", "NONE").upper())
        self.bubble_type.trace_add("write", self._on_style_changed)
        
        ttk.Label(bubble_frame, text="吹き出しの種類:").grid(row=0, column=0, sticky="w", pady=2)
        
        bubble_types_frame = ttk.Frame(bubble_frame)
        bubble_types_frame.grid(row=1, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=4)
        
        bubble_types = [
            ("基本", "BASIC"),
            ("角丸", "ROUNDED"),
            ("雲形", "CLOUD"),
            ("思考", "THOUGHT"),
            ("なし", "NONE")
        ]
        
        for i, (label, value) in enumerate(bubble_types):
            ttk.Radiobutton(bubble_types_frame, text=label, value=value, variable=self.bubble_type)\
                .grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 12), pady=2)
        
        # しっぽの設定
        ttk.Label(bubble_frame, text="🔽 しっぽの設定", font=("", 9, "bold")).grid(row=2, column=0, columnspan=4, sticky="w", pady=(12, 2))

        # 1. しっぽを表示
        self.bubble_tail_enabled = tk.BooleanVar(value=bool(cfg.get("style.bubble.tail.enabled", True)))
        self.bubble_tail_enabled.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(bubble_frame, text="しっぽを表示", variable=self.bubble_tail_enabled).grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=2)

        # 2. 手動設定（向き）
        ttk.Label(bubble_frame, text="手動設定:").grid(row=4, column=0, sticky="w", pady=2, padx=(40, 0))

        self.bubble_tail_position = tk.StringVar(value=cfg.get("style.bubble.tail.position", "RIGHT").upper())  # デフォルトを「右」に変更
        self.bubble_tail_position.trace_add("write", self._on_style_changed)

        tail_pos_frame = ttk.Frame(bubble_frame)
        tail_pos_frame.grid(row=4, column=1, columnspan=3, sticky="w", padx=(4, 0), pady=2)

        for pos in [("上", "TOP"), ("下", "BOTTOM"), ("左", "LEFT"), ("右", "RIGHT")]:
            ttk.Radiobutton(tail_pos_frame, text=pos[0], value=pos[1], variable=self.bubble_tail_position)\
                .pack(side="left", padx=(0, 8))

        # 3. しっぽのサイズ
        self.bubble_tail_size = tk.IntVar(value=int(cfg.get("style.bubble.tail.size", 15)))
        self.bubble_tail_size.trace_add("write", self._on_style_changed)
        ttk.Label(bubble_frame, text="しっぽのサイズ:").grid(row=5, column=0, sticky="w", pady=2, padx=(40, 0))
        ttk.Spinbox(bubble_frame, from_=5, to=50, textvariable=self.bubble_tail_size, width=8).grid(row=5, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(bubble_frame, text="px").grid(row=5, column=2, sticky="w", pady=2)

        # 自動調整は削除（常に手動設定を使用）
        self.bubble_tail_auto = tk.BooleanVar(value=False)  # 常にFalse
        
        # 縁取り（アウトライン）
        ttk.Label(bubble_frame, text="✏️ 縁取り（テキスト）", font=("", 9, "bold")).grid(row=7, column=0, columnspan=4, sticky="w", pady=(12, 2))
        
        self.text_outline_enabled = tk.BooleanVar(value=bool(cfg.get("style.text.outline.enabled", False)))
        self.text_outline_enabled.trace_add("write", self._on_style_changed)
        ttk.Checkbutton(bubble_frame, text="テキストに縁取りを表示", variable=self.text_outline_enabled).grid(row=8, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=2)
        
        outline_detail = ttk.Frame(bubble_frame)
        outline_detail.grid(row=9, column=0, columnspan=4, sticky="w", padx=(40, 0))
        
        self.text_outline_color = tk.StringVar(value=cfg.get("style.text.outline.color", "#000000"))
        self.text_outline_color.trace_add("write", self._on_style_changed)
        ttk.Label(outline_detail, text="縁取りの色:").grid(row=0, column=0, sticky="w", pady=2)
        outline_color_btn = ttk.Button(outline_detail, text="選択", width=8,
                                      command=lambda: self._pick_color(self.text_outline_color, "縁取りの色"))
        outline_color_btn.grid(row=0, column=1, sticky="w", padx=(4, 8), pady=2)
        self.text_outline_color_preview = tk.Label(outline_detail, text="  ", bg=self.text_outline_color.get(), width=3, relief="solid")
        self.text_outline_color_preview.grid(row=0, column=2, pady=2)
        
        self.text_outline_width = tk.IntVar(value=int(cfg.get("style.text.outline.width", 2)))
        self.text_outline_width.trace_add("write", self._on_style_changed)
        ttk.Label(outline_detail, text="縁取りの太さ:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(outline_detail, from_=1, to=10, textvariable=self.text_outline_width, width=6).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Label(outline_detail, text="px").grid(row=1, column=2, sticky="w", pady=2)
        
        # テキスト配置（整列）
        ttk.Label(bubble_frame, text="📄 テキスト配置", font=("", 9, "bold")).grid(row=10, column=0, columnspan=4, sticky="w", pady=(12, 2))
        
        self.text_alignment = tk.StringVar(value=cfg.get("style.text.alignment", "LEFT").upper())
        self.text_alignment.trace_add("write", self._on_style_changed)
        
        align_frame = ttk.Frame(bubble_frame)
        align_frame.grid(row=11, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=4)
        
        for align in [("左揃え", "LEFT"), ("中央揃え", "CENTER"), ("右揃え", "RIGHT")]:
            ttk.Radiobutton(align_frame, text=align[0], value=align[1], variable=self.text_alignment)\
                .pack(side="left", padx=(0, 12))
        
        # 装飾アイコン
        ttk.Label(bubble_frame, text="🎨 装飾アイコン", font=("", 9, "bold")).grid(row=12, column=0, columnspan=4, sticky="w", pady=(12, 2))
        
        self.decoration_icon = tk.StringVar(value=cfg.get("style.decoration.icon", "NONE"))
        self.decoration_icon.trace_add("write", self._on_style_changed)
        
        ttk.Label(bubble_frame, text="アイコン:").grid(row=13, column=0, sticky="w", pady=2, padx=(20, 0))
        
        icon_combo = ttk.Combobox(bubble_frame, textvariable=self.decoration_icon, width=15)
        icon_combo['values'] = ("なし", "❤️", "⭐", "💬", "🎉", "💡", "🔥", "✨", "🎵", "📢")
        icon_combo.grid(row=13, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=2)
        
        self.decoration_position = tk.StringVar(value=cfg.get("style.decoration.position", "TOP_LEFT").upper())
        self.decoration_position.trace_add("write", self._on_style_changed)
        
        ttk.Label(bubble_frame, text="表示位置:").grid(row=14, column=0, sticky="w", pady=2, padx=(20, 0))
        
        deco_pos_frame = ttk.Frame(bubble_frame)
        deco_pos_frame.grid(row=14, column=1, columnspan=3, sticky="w", padx=(4, 0), pady=2)
        
        for pos in [("左上", "TOP_LEFT"), ("右上", "TOP_RIGHT"), ("左下", "BOTTOM_LEFT"), ("右下", "BOTTOM_RIGHT")]:
            ttk.Radiobutton(deco_pos_frame, text=pos[0], value=pos[1], variable=self.decoration_position)\
                .pack(side="left", padx=(0, 8))
        
        # レイアウト系フレームの列伸縮設定（あると気持ちよく広がる）
        try:
            for f in (scroll_frame, font_frame, layout_frame, bg_frame, role_frame):
                for c in range(3):
                    f.columnconfigure(c, weight=1)
        except Exception:
            pass

        # 初回プレビュー更新（GUIが完全に構築された後に実行）
        self.after(100, self._on_style_changed)
    
    def _pick_color(self, var: tk.StringVar, title: str):
        """カラーピッカーダイアログ"""
        color = colorchooser.askcolor(initialcolor=var.get(), title=title)
        if color[1]:
            var.set(color[1])
            # プレビューを更新
            if title == "影の色":
                self.shadow_color_preview.config(bg=color[1])
            elif title == "背景色":
                self.bg_color_preview.config(bg=color[1])
            elif title == "枠線の色":
                self.border_color_preview.config(bg=color[1])
            elif title == "配信者の色":
                self.streamer_color_preview.config(bg=color[1])
            elif title == "AIの色":
                self.ai_color_preview.config(bg=color[1])
            elif title == "視聴者の色":
                self.viewer_color_preview.config(bg=color[1])
            elif title == "名前の色":
                self.name_color_preview.config(bg=color[1])
            elif title == "縁取りの色":
                self.text_outline_color_preview.config(bg=color[1])
    
    def _hex_to_rgb(self, hx: str):
        """16進数カラーをRGBタプルに変換"""
        hx = hx.strip().lstrip('#')
        if len(hx) == 3:
            hx = ''.join(ch*2 for ch in hx)
        try:
            return tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return (255, 255, 255)

    def _blend_hex(self, bg_hex: str, fg_hex: str, alpha_pct: int) -> str:
        """Canvasが透過fill非対応なので、プレビュー背景色(#2b2b2b)に対して合成色を擬似計算"""
        bg = self._hex_to_rgb(bg_hex)
        fg = self._hex_to_rgb(fg_hex)
        a = max(0, min(100, int(alpha_pct))) / 100.0
        out = tuple(int(round(fg[i]*a + bg[i]*(1-a))) for i in range(3))
        return '#%02x%02x%02x' % out

    def _draw_text(self, canvas, x, y, text, font, fill, anchor="nw",
                   outline_enabled=False, outline_color="#000000", outline_width=2,
                   shadow_enabled=False, shadow_color="#000000", shadow_offset=(0, 0), **kw):
        """縁取り＆影つきテキスト描画（簡易）"""
        # 影
        if shadow_enabled and (shadow_offset != (0, 0)):
            sx = x + int(shadow_offset[0])
            sy = y + int(shadow_offset[1])
            canvas.create_text(sx, sy, text=text, font=font, fill=shadow_color, anchor=anchor, **kw)
        # 縁取り（外周にオフセット複写）
        if outline_enabled and outline_width > 0:
            for dx in (-outline_width, 0, outline_width):
                for dy in (-outline_width, 0, outline_width):
                    if dx == 0 and dy == 0:
                        continue
                    canvas.create_text(x+dx, y+dy, text=text, font=font, fill=outline_color, anchor=anchor, **kw)
        # 本体
        canvas.create_text(x, y, text=text, font=font, fill=fill, anchor=anchor, **kw)

    def _draw_bubble(self, canvas, x1, y1, x2, y2, *,
                     bg_color="#FFFFFF", bg_opacity=100, canvas_bg="#2b2b2b",
                     radius=0, border=False, border_color="#000000", border_width=1,
                     bubble_type="NONE", tail_enabled=True, tail_pos="BOTTOM", tail_size=15):
        """吹き出し本体＋しっぽ（簡易）。透明度は背景色とブレンドして疑似表現。"""
        fill = self._blend_hex(canvas_bg, bg_color, bg_opacity)
        # 本体（角丸対応の簡易近似）
        if radius > 0:
            r = min(radius, (x2-x1)//2, (y2-y1)//2)
            canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, fill=fill, outline="")
            canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, fill=fill, outline="")
            canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, fill=fill, outline="")
            canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, fill=fill, outline="")
            canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
            canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")
            if border:
                # 角丸枠（近似）
                canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, style="arc",
                                  outline=border_color, width=border_width)
                canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, style="arc",
                                  outline=border_color, width=border_width)
                canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, style="arc",
                                  outline=border_color, width=border_width)
                canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, style="arc",
                                  outline=border_color, width=border_width)
                canvas.create_line(x1+r, y1, x2-r, y1, fill=border_color, width=border_width)
                canvas.create_line(x1+r, y2, x2-r, y2, fill=border_color, width=border_width)
                canvas.create_line(x1, y1+r, x1, y2-r, fill=border_color, width=border_width)
                canvas.create_line(x2, y1+r, x2, y2-r, fill=border_color, width=border_width)
        else:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=border_color if border else "", width=border_width)

        # しっぽ
        if bubble_type != "NONE" and tail_enabled and tail_size > 0:
            if tail_pos == "TOP":
                pts = [( (x1+x2)//2, y1 - tail_size ),
                       ( (x1+x2)//2 - tail_size, y1 ),
                       ( (x1+x2)//2 + tail_size, y1 )]
            elif tail_pos == "BOTTOM":
                pts = [( (x1+x2)//2, y2 + tail_size ),
                       ( (x1+x2)//2 - tail_size, y2 ),
                       ( (x1+x2)//2 + tail_size, y2 )]
            elif tail_pos == "LEFT":
                pts = [( x1 - tail_size, (y1+y2)//2 ),
                       ( x1, (y1+y2)//2 - tail_size ),
                       ( x1, (y1+y2)//2 + tail_size )]
            else:  # RIGHT
                pts = [( x2 + tail_size, (y1+y2)//2 ),
                       ( x2, (y1+y2)//2 - tail_size ),
                       ( x2, (y1+y2)//2 + tail_size )]
            canvas.create_polygon(pts, fill=fill, outline=border_color if border else "", width=border_width)
    
    def _apply_comment_preset(self):
        """選択されたプリセットをGUIに適用"""
        if not hasattr(self, 'obs_config') or not self.obs_config:
            logger.warning("obs_config が利用できません")
            return

        if not hasattr(self.obs_config, 'apply_preset'):
            logger.warning("apply_preset メソッドが存在しません")
            return

        preset_name = self.comment_preset_var.get()
        if not self.obs_config.apply_preset(preset_name):
            logger.error(f"プリセット '{preset_name}' の適用に失敗しました")
            return

        # プリセットの内容を取得
        preset = self.obs_config.get_preset(preset_name) if hasattr(self.obs_config, 'get_preset') else {}

        # 各UI部品の値を更新
        if hasattr(self, 'flow_direction_area') and "display.flow.direction" in preset:
            self.flow_direction_area.set(preset["display.flow.direction"])

        # バブル設定
        if hasattr(self, 'bubble_type') and "bubble.shape" in preset:
            shape_map = {
                "square": "BASIC",
                "rounded": "ROUNDED",
                "comic": "CLOUD",
                "thought": "THOUGHT",
                "none": "NONE"
            }
            self.bubble_type.set(shape_map.get(preset["bubble.shape"], "ROUNDED"))
        if hasattr(self, 'bg_color') and "bubble.background.color" in preset:
            self.bg_color.set(preset["bubble.background.color"])
        if hasattr(self, 'bg_opacity') and "bubble.background.opacity" in preset:
            self.bg_opacity.set(preset["bubble.background.opacity"])
        if hasattr(self, 'border_enabled') and "bubble.border.enabled" in preset:
            self.border_enabled.set(preset["bubble.border.enabled"])
        if hasattr(self, 'border_color') and "bubble.border.color" in preset:
            self.border_color.set(preset["bubble.border.color"])
        if hasattr(self, 'border_width') and "bubble.border.width" in preset:
            self.border_width.set(preset["bubble.border.width"])
        if hasattr(self, 'border_radius') and "bubble.border.radius" in preset:
            self.border_radius.set(preset["bubble.border.radius"])

        # フォント設定
        if hasattr(self, 'font_family') and "style.font.family" in preset:
            self.font_family.set(preset["style.font.family"])
        if hasattr(self, 'name_font_size') and "style.name.font.size" in preset:
            self.name_font_size.set(preset["style.name.font.size"])
        if hasattr(self, 'name_font_bold') and "style.name.font.bold" in preset:
            self.name_font_bold.set(preset["style.name.font.bold"])
        if hasattr(self, 'body_font_size') and "style.body.font.size" in preset:
            self.body_font_size.set(preset["style.body.font.size"])
        if hasattr(self, 'body_font_bold') and "style.body.font.bold" in preset:
            self.body_font_bold.set(preset["style.body.font.bold"])

        # テキスト装飾
        if hasattr(self, 'text_outline_enabled') and "style.text.outline.enabled" in preset:
            self.text_outline_enabled.set(preset["style.text.outline.enabled"])
        if hasattr(self, 'text_outline_color') and "style.text.outline.color" in preset:
            self.text_outline_color.set(preset["style.text.outline.color"])
        if hasattr(self, 'text_outline_width') and "style.text.outline.width" in preset:
            self.text_outline_width.set(preset["style.text.outline.width"])
        if hasattr(self, 'shadow_enabled') and "style.text.shadow.enabled" in preset:
            self.shadow_enabled.set(preset["style.text.shadow.enabled"])
        if hasattr(self, 'shadow_color') and "style.text.shadow.color" in preset:
            self.shadow_color.set(preset["style.text.shadow.color"])
        if hasattr(self, 'shadow_offset_x') and "style.text.shadow.offset_x" in preset:
            self.shadow_offset_x.set(preset["style.text.shadow.offset_x"])
        if hasattr(self, 'shadow_offset_y') and "style.text.shadow.offset_y" in preset:
            self.shadow_offset_y.set(preset["style.text.shadow.offset_y"])
        if hasattr(self, 'shadow_blur') and "style.text.shadow.blur" in preset:
            self.shadow_blur.set(preset["style.text.shadow.blur"])

        # レイアウト
        if hasattr(self, 'line_height') and "style.layout.line_height" in preset:
            self.line_height.set(preset["style.layout.line_height"])

        # パディング
        if hasattr(self, 'padding_top') and "style.layout.padding.top" in preset:
            self.padding_top.set(preset["style.layout.padding.top"])
        if hasattr(self, 'padding_right') and "style.layout.padding.right" in preset:
            self.padding_right.set(preset["style.layout.padding.right"])
        if hasattr(self, 'padding_bottom') and "style.layout.padding.bottom" in preset:
            self.padding_bottom.set(preset["style.layout.padding.bottom"])
        if hasattr(self, 'padding_left') and "style.layout.padding.left" in preset:
            self.padding_left.set(preset["style.layout.padding.left"])

        # 役割別カラー
        if hasattr(self, 'streamer_color') and "role.streamer.color" in preset:
            self.streamer_color.set(preset["role.streamer.color"])
            if hasattr(self, 'streamer_color_preview'):
                self.streamer_color_preview.config(bg=preset["role.streamer.color"])
        if hasattr(self, 'ai_color') and "role.ai.color" in preset:
            self.ai_color.set(preset["role.ai.color"])
            if hasattr(self, 'ai_color_preview'):
                self.ai_color_preview.config(bg=preset["role.ai.color"])
        if hasattr(self, 'viewer_color') and "role.viewer.color" in preset:
            self.viewer_color.set(preset["role.viewer.color"])
            if hasattr(self, 'viewer_color_preview'):
                self.viewer_color_preview.config(bg=preset["role.viewer.color"])

        # プレビュー更新
        if hasattr(self, '_on_style_changed'):
            self._on_style_changed()

        # overlay.htmlへの反映（data.jsonを更新）
        if hasattr(self, 'file_output') and self.file_output:
            try:
                self.file_output.flush_to_files()
                logger.debug(f"[Preset] overlay.html用のdata.jsonを更新しました")
            except Exception as e:
                logger.error(f"[Preset] data.json更新エラー: {e}")

        logger.info(f"[Preset] プリセット '{preset_name}' を適用しました")

        # プリセット一覧を更新（カスタムプリセットの追加に対応）
        self._reload_preset_list()

    def _save_current_preset(self):
        """現在の設定を新しいプリセットとして保存"""
        from tkinter import simpledialog, messagebox

        if not hasattr(self, 'obs_config') or not self.obs_config or not hasattr(self.obs_config, 'save_preset'):
            messagebox.showerror("エラー", "プリセット保存機能が利用できません")
            return

        # プリセット名を入力
        preset_name = simpledialog.askstring(
            "プリセットを保存",
            "新しいプリセット名を入力してください:\n（半角英数字とアンダースコアのみ推奨）",
            parent=self
        )

        if not preset_name:
            return  # キャンセルされた

        # 名前のバリデーション
        if not preset_name.replace("_", "").isalnum():
            messagebox.showwarning("警告", "プリセット名は半角英数字とアンダースコアのみ使用してください")
            return

        # 組み込みプリセットと同じ名前は使えない
        if hasattr(self.obs_config, 'is_builtin_preset') and self.obs_config.is_builtin_preset(preset_name):
            messagebox.showwarning("警告", f"'{preset_name}' は組み込みプリセット名です。別の名前を使用してください")
            return

        # 既存のプリセットと同じ名前の場合は確認
        existing_presets = self.obs_config.get_preset_names() if hasattr(self.obs_config, 'get_preset_names') else []
        if preset_name in existing_presets:
            if not messagebox.askyesno("確認", f"プリセット '{preset_name}' は既に存在します。上書きしますか？"):
                return

        # 現在のGUI設定値を収集
        preset_data = {
            "display.flow.direction": self.flow_direction_area.get() if hasattr(self, 'flow_direction_area') else "DOWN",
            "bubble.enabled": True,
            "bubble.shape": self._get_bubble_shape_from_ui(),
            "bubble.background.color": self.bg_color.get() if hasattr(self, 'bg_color') else "#000000",
            "bubble.background.opacity": self.bg_opacity.get() if hasattr(self, 'bg_opacity') else 75,
            "bubble.border.enabled": self.border_enabled.get() if hasattr(self, 'border_enabled') else False,
            "bubble.border.color": self.border_color.get() if hasattr(self, 'border_color') else "#FFFFFF",
            "bubble.border.width": self.border_width.get() if hasattr(self, 'border_width') else 1,
            "bubble.border.radius": self.border_radius.get() if hasattr(self, 'border_radius') else 8,
            "bubble.shadow.enabled": True,
            "bubble.shadow.color": "#000000",
            "bubble.shadow.blur": 8,
            "style.font.family": self.font_family.get() if hasattr(self, 'font_family') else "Yu Gothic UI",
            "style.font.size_px": 26,
            "style.name.font.size": self.name_font_size.get() if hasattr(self, 'name_font_size') else 24,
            "style.name.font.bold": self.name_font_bold.get() if hasattr(self, 'name_font_bold') else True,
            "style.name.font.italic": self.name_font_italic.get() if hasattr(self, 'name_font_italic') else False,
            "style.body.font.size": self.body_font_size.get() if hasattr(self, 'body_font_size') else 26,
            "style.body.font.bold": self.body_font_bold.get() if hasattr(self, 'body_font_bold') else False,
            "style.body.font.italic": self.body_font_italic.get() if hasattr(self, 'body_font_italic') else False,
            "style.text.outline.enabled": self.text_outline_enabled.get() if hasattr(self, 'text_outline_enabled') else False,
            "style.text.outline.color": self.text_outline_color.get() if hasattr(self, 'text_outline_color') else "#000000",
            "style.text.outline.width": 2,
            "style.text.shadow.enabled": self.shadow_enabled.get() if hasattr(self, 'shadow_enabled') else False,
            "style.text.shadow.color": self.shadow_color.get() if hasattr(self, 'shadow_color') else "#000000",
            "style.text.shadow.offset_x": 2,
            "style.text.shadow.offset_y": 2,
            "style.text.shadow.blur": 0,
            "style.layout.line_height": 1.5,
            "style.layout.padding.top": self.padding_top.get() if hasattr(self, 'padding_top') else 12,
            "style.layout.padding.right": self.padding_right.get() if hasattr(self, 'padding_right') else 16,
            "style.layout.padding.bottom": self.padding_bottom.get() if hasattr(self, 'padding_bottom') else 12,
            "style.layout.padding.left": self.padding_left.get() if hasattr(self, 'padding_left') else 16,
            "role.streamer.color": self.streamer_color.get() if hasattr(self, 'streamer_color') else "#4A90E2",
            "role.ai.color": self.ai_color.get() if hasattr(self, 'ai_color') else "#9B59B6",
            "role.viewer.color": self.viewer_color.get() if hasattr(self, 'viewer_color') else "#7F8C8D",
            "effect.type.streamer": "fadeUp",
            "effect.type.ai": "pop",
            "effect.type.viewer": "fadeUp",
        }

        # プリセットを保存
        if self.obs_config.save_preset(preset_name, preset_data):
            # プリセット一覧を更新
            self._reload_preset_list()
            # 保存したプリセットを選択
            self.comment_preset_var.set(preset_name)

            messagebox.showinfo("成功", f"プリセット '{preset_name}' を保存しました")
            logger.info(f"プリセット '{preset_name}' を保存しました")
        else:
            messagebox.showerror("エラー", "プリセットの保存に失敗しました")

    def _get_bubble_shape_from_ui(self):
        """UIからバブル形状を取得"""
        if hasattr(self, 'bubble_type'):
            bubble_type = self.bubble_type.get()
            shape_map = {
                "BASIC": "square",
                "ROUNDED": "rounded",
                "CLOUD": "comic",
                "THOUGHT": "thought",
                "NONE": "none"
            }
            return shape_map.get(bubble_type, "rounded")
        return "rounded"

    def _delete_current_preset(self):
        """選択中のプリセットを削除"""
        from tkinter import messagebox

        if not hasattr(self, 'obs_config') or not self.obs_config or not hasattr(self.obs_config, 'delete_preset'):
            messagebox.showerror("エラー", "プリセット削除機能が利用できません")
            return

        preset_name = self.comment_preset_var.get()

        # 組み込みプリセットは削除不可
        if hasattr(self.obs_config, 'is_builtin_preset') and self.obs_config.is_builtin_preset(preset_name):
            messagebox.showwarning("警告", f"組み込みプリセット '{preset_name}' は削除できません")
            return

        # 確認ダイアログ
        if not messagebox.askyesno("確認", f"プリセット '{preset_name}' を削除しますか？"):
            return

        # プリセットを削除
        if self.obs_config.delete_preset(preset_name):
            # プリセット一覧を更新
            self._reload_preset_list()
            # アクティブプリセットに切り替え
            active_preset = self.obs_config.get_active_preset_name() if hasattr(self.obs_config, 'get_active_preset_name') else "default"
            self.comment_preset_var.set(active_preset)
            self._apply_comment_preset()

            messagebox.showinfo("成功", f"プリセット '{preset_name}' を削除しました")
            logger.info(f"プリセット '{preset_name}' を削除しました")
        else:
            messagebox.showerror("エラー", "プリセットの削除に失敗しました")

    def _reset_to_default_preset(self):
        """デフォルトプリセットに戻す"""
        from tkinter import messagebox

        if messagebox.askyesno("確認", "デフォルトプリセットに戻しますか？\n現在の設定は失われます。"):
            self.comment_preset_var.set("default")
            self._apply_comment_preset()
            messagebox.showinfo("完了", "デフォルトプリセットに戻しました")
            logger.info("デフォルトプリセットに戻しました")

    def _reload_preset_list(self):
        """config_handler内の全プリセットをComboboxに反映する"""
        if not hasattr(self, 'obs_config') or not self.obs_config:
            return

        if not hasattr(self, 'comment_preset_combo'):
            return

        # プリセット一覧を取得
        preset_names = []
        if hasattr(self.obs_config, 'get_preset_names'):
            preset_names = self.obs_config.get_preset_names()

        if not preset_names:
            preset_names = ["default"]

        # ソート: Default先頭、残りはアルファベット順
        default_names = [n for n in preset_names if n.lower() == "default"]
        other_names = sorted([n for n in preset_names if n.lower() != "default"])
        preset_names = default_names + other_names

        # Comboboxを更新
        self.comment_preset_combo['values'] = tuple(preset_names)

        # 現在の選択値が一覧にない場合はdefaultに戻す
        current_preset = self.comment_preset_var.get()
        if current_preset not in preset_names:
            current_preset = "default" if "default" in preset_names else preset_names[0]
            self.comment_preset_var.set(current_preset)

        logger.debug(f"プリセット一覧を更新: {len(preset_names)}件 - {preset_names}")

    def _on_comment_preview_resize(self, event):
        """コメントプレビューのリサイズイベント"""
        # リサイズイベントが頻繁に発生するため、100ms後に再描画
        if hasattr(self, '_comment_resize_timer'):
            self.after_cancel(self._comment_resize_timer)
        self._comment_resize_timer = self.after(100, self._on_style_changed)

    def _on_style_changed(self, *args):
        """
        trace_add用のコールバック: スタイル変更時にプレビューを更新

        変数変更 (trace_add) → 現在のロールのプレビューを更新
        """
        if hasattr(self, 'current_preview_role'):
            current_role = self.current_preview_role.get()
        else:
            current_role = "streamer"

        if hasattr(self, '_update_comment_role_preview'):
            self._update_comment_role_preview(current_role)

    def _bridge_html_overlay_keys(self):
        """
        UIで設定した値を、HTMLオーバーレイ（file_backend）が参照するキーに写すブリッジ。
        - display.text.size_px        ← 本文フォントサイズ
        - display.text.align          ← テキスト整列
        - ui.style_panel.max_width_px ← 最大横幅(px)
        - display.name_visibility     ← 名前の表示/非表示
        - display.flow.direction      ← 既存UI（UP/DOWN）
        - display.area.mode           ← 既存UI（SEPARATE/TIMELINE）
        """
        cfg = getattr(self, "config_manager", None)
        if not cfg:
            return
        try:
            # フォントサイズ（本文）
            if hasattr(self, "body_font_size"):
                cfg.set("display.text.size_px", int(self.body_font_size.get()))
            # テキスト整列
            if hasattr(self, "text_alignment"):
                cfg.set("display.text.align", (self.text_alignment.get() or "LEFT").upper())
            # 最大横幅：コメント枠の横幅設定を流用（無ければ960）
            max_w = 960
            if hasattr(self, "width_var"):
                max_w = max(120, int(self.width_var.get()))
            else:
                try:
                    max_w = int(cfg.get("display.box.width_px", 960) or 960)
                except Exception:
                    pass
            cfg.set("ui.style_panel.max_width_px", max_w)
            # 名前の表示/非表示（UI無ければ表示）
            show_name = True
            if hasattr(self, "name_show_var"):
                show_name = bool(self.name_show_var.get())
            cfg.set("display.name_visibility", "SHOW" if show_name else "HIDE")
            # 既存UIで持っている方向＆エリアモード（保険で上書き）
            if hasattr(self, "direction"):
                cfg.set("display.flow.direction", (self.direction.get() or "UP").upper())
            if hasattr(self, "mode_var"):
                cfg.set("display.area.mode", (self.mode_var.get() or "SEPARATE").upper())
        except Exception as e:
            print(f"[bridge] HTML overlay key mapping error: {e}")

    def _inject_unified_save_button(self, parent):
        """すべての設定を保存する統合ボタン"""
        import tkinter as tk
        from tkinter import ttk
        
        cfg = getattr(self, "config_manager", None)
        if cfg is None:
            return
        
        # 保存ボタン用のフレーム
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=8, pady=(12, 8))
        
        def _save_all():
            """全設定を一括保存"""
            try:
                # ★ コメント表示エリア（display_area.* → display.area.*）を先に保存
                if hasattr(self, "_save_area_config"):
                    self._save_area_config()

                # OBSキャンバス解像度設定
                if hasattr(self, 'canvas_preset'):
                    cfg.set("obs.canvas.preset", self.canvas_preset.get())
                if hasattr(self, 'canvas_width'):
                    cfg.set("obs.canvas.width", int(self.canvas_width.get()))
                if hasattr(self, 'canvas_height'):
                    cfg.set("obs.canvas.height", int(self.canvas_height.get()))
                    logger.debug(f"Canvas保存: {self.canvas_preset.get()} ({self.canvas_width.get()}x{self.canvas_height.get()})")

                # 折返し計算用の見積りが未設定ならデフォルトを入れる
                if cfg.get("display.wrap.char_px", None) is None:
                    cfg.set("display.wrap.char_px", 14)
                if cfg.get("display.wrap.line_px", None) is None:
                    cfg.set("display.wrap.line_px", 28)
                cfg.set("display.wrap.enabled", True)
                
                # フォント・テキスト設定
                if hasattr(self, 'font_family'):
                    cfg.set("style.font.family", self.font_family.get())
                    
                    # 名前の設定
                    cfg.set("style.name.font.size", int(self.name_font_size.get()))
                    cfg.set("style.name.font.bold", bool(self.name_font_bold.get()))
                    cfg.set("style.name.font.italic", bool(self.name_font_italic.get()))
                    cfg.set("style.name.use_custom_color", bool(self.name_use_custom_color.get()))
                    cfg.set("style.name.custom_color", self.name_custom_color.get())
                    
                    # 本文の設定
                    cfg.set("style.body.font.size", int(self.body_font_size.get()))
                    cfg.set("style.body.font.bold", bool(self.body_font_bold.get()))
                    cfg.set("style.body.font.italic", bool(self.body_font_italic.get()))
                    cfg.set("style.body.indent", int(self.body_indent.get()))
                    
                    # 文字の影（style.text.shadow.* キーに統一）
                    cfg.set("style.text.shadow.enabled", bool(self.shadow_enabled.get()))
                    cfg.set("style.text.shadow.color", self.shadow_color.get())
                    cfg.set("style.text.shadow.offset_x", int(self.shadow_offset_x.get()))
                    cfg.set("style.text.shadow.offset_y", int(self.shadow_offset_y.get()))
                    cfg.set("style.text.shadow.blur", int(self.shadow_blur.get()))
                    
                    # レイアウト設定
                    cfg.set("style.layout.name_position", self.name_position.get().upper())
                    cfg.set("style.layout.name_offset_x", int(self.name_offset_x.get()) if hasattr(self, 'name_offset_x') else 0)
                    cfg.set("style.layout.name_offset_y", int(self.name_offset_y.get()) if hasattr(self, 'name_offset_y') else 0)
                    cfg.set("style.layout.name_body_spacing", int(self.name_body_spacing.get()) if hasattr(self, 'name_body_spacing') else 4)
                    cfg.set("style.layout.line_height", float(self.line_height.get()))
                    cfg.set("style.layout.padding.top", int(self.padding_top.get()))
                    cfg.set("style.layout.padding.right", int(self.padding_right.get()))
                    cfg.set("style.layout.padding.bottom", int(self.padding_bottom.get()))
                    cfg.set("style.layout.padding.left", int(self.padding_left.get()))
                    
                    # 吹き出し設定
                    if hasattr(self, 'bubble_type'):
                        cfg.set("style.bubble.type", self.bubble_type.get().upper())
                        cfg.set("style.bubble.tail.enabled", bool(self.bubble_tail_enabled.get()))
                        cfg.set("style.bubble.tail.size", int(self.bubble_tail_size.get()))
                        cfg.set("style.bubble.tail.auto", bool(self.bubble_tail_auto.get()))
                        cfg.set("style.bubble.tail.position", self.bubble_tail_position.get().upper())
                    
                    # テキスト縁取り設定
                    if hasattr(self, 'text_outline_enabled'):
                        cfg.set("style.text.outline.enabled", bool(self.text_outline_enabled.get()))
                        cfg.set("style.text.outline.color", self.text_outline_color.get())
                        cfg.set("style.text.outline.width", int(self.text_outline_width.get()))
                    
                    # テキスト配置設定
                    if hasattr(self, 'text_alignment'):
                        cfg.set("style.text.alignment", self.text_alignment.get().upper())
                    
                    # 装飾アイコン設定
                    if hasattr(self, 'decoration_icon'):
                        cfg.set("style.decoration.icon", self.decoration_icon.get())
                        cfg.set("style.decoration.position", self.decoration_position.get().upper())
                    
                    # 背景設定
                    cfg.set("style.background.color", self.bg_color.get())
                    cfg.set("style.background.opacity", int(self.bg_opacity.get()))
                    cfg.set("style.background.border_radius", int(self.border_radius.get()))
                    cfg.set("style.background.border.enabled", bool(self.border_enabled.get()))
                    cfg.set("style.background.border.color", self.border_color.get())
                    cfg.set("style.background.border.width", int(self.border_width.get()))
                    
                    # 役割別カラー設定（role.* キーに統一）
                    cfg.set("role.streamer.color", self.streamer_color.get())
                    cfg.set("role.ai.color", self.ai_color.get())
                    cfg.set("role.viewer.color", self.viewer_color.get())
                
                # 保存実行
                cfg.save()
                logger.info("すべての設定を保存しました")

                # ユーザーにフィードバック
                self._update_status("設定を保存しました")

            except Exception as e:
                logger.error(f"保存エラー: {e}")
                self._update_status(f"保存エラー: {e}")
        
        # 大きめの保存ボタン
        save_btn = ttk.Button(btn_frame, text="💾 すべての設定を保存", command=_save_all)
        save_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 説明ラベル
        ttk.Label(btn_frame, text="（表示モード・枠サイズ・流れる方向などを一括保存）", 
                 foreground="gray").pack(side=tk.LEFT)

    def _load_default_presets(self):
        """
        デフォルトプリセット読み込み

        v17.5.7+: プリセット定義は config_handler.py に一元化。
        まずは OBSEffectsConfig（self.obs_config）から取得し、
        ダメな場合だけ外部 config_manager / DEFAULTS にフォールバックする。
        """
        # まずは空にしておく
        self.effects_presets.clear()

        try:
            # 1) 統合モジュールの obs_config から取得（ここに DEFAULTS が入っている）
            if getattr(self, "obs_config", None) is not None:
                presets_config = self.obs_config.get("obs.effects.presets", {})
            # 2) 外部の config_manager から取得（将来ここに保存される想定）
            elif self.config_manager and hasattr(self.config_manager, "get"):
                presets_config = self.config_manager.get("obs.effects.presets", {})
            else:
                presets_config = {}

            # 何も取れなかった場合は、DEFAULTS から直接フォールバック
            if not presets_config:
                try:
                    presets_config = OBSEffectsConfig.DEFAULTS.get("obs.effects.presets", {})
                    logger.warning("⚠️ obs.effects.presets が空だったため、DEFAULTS からフォールバックしました")
                except Exception:
                    presets_config = {}

            # ここまで来てまだ空なら、さすがに諦める
            if not presets_config:
                logger.error("❌ 絵文字エフェクトプリセットが1件も取得できませんでした")
                return

            # EffectPreset オブジェクトに変換して辞書に格納
            for preset_id, preset_data in presets_config.items():
                preset = EffectPreset(
                    name=preset_id,
                    description=preset_data.get("label", preset_id),
                    duration=float(preset_data.get("duration", 3.0)),
                    emoji=preset_data.get("emoji", []),
                    animation=preset_data.get("animation", "fall"),
                    count=int(preset_data.get("count", 50)),
                    area=preset_data.get("area", "full"),
                    color=preset_data.get("color", "#FF6B6B"),
                    trigger_words=preset_data.get("trigger_words", []),
                    obs_scene=preset_data.get("obs_scene", ""),
                    obs_source=preset_data.get("obs_source", ""),
                    size_min=preset_data.get("size_min", 32),
                    size_max=preset_data.get("size_max", 32),
                )
                self.effects_presets[preset_id] = preset

            logger.info(f"✅ {len(self.effects_presets)} 個のエフェクトプリセットを読み込みました")

        except Exception as e:
            logger.error(f"❌ プリセット読み込みエラー: {e}", exc_info=True)

    def _build_ui(self):
        """UI構築：上=ステータス / 中=Notebook+共通プレビュー / 下=共通ボタン"""
        import tkinter as tk
        from tkinter import ttk

        # ルート全体
        self.pack(fill=tk.BOTH, expand=True)

        # ── 下部: 共通ボタン（保存・読み込みなど） ──
        common_buttons_frame = ttk.Frame(self)
        common_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)

        def _save_all_settings():
            """すべての設定を保存"""
            try:
                # ★ コメント表示エリア（display_area.* → display.area.*）を先に保存
                if hasattr(self, "_save_area_config"):
                    self._save_area_config()

                # 表示エリア設定（新規）
                if hasattr(self, 'show_streamer'):
                    self.config_manager.set("display.show.streamer", bool(self.show_streamer.get()))
                if hasattr(self, 'show_ai'):
                    self.config_manager.set("display.show.ai", bool(self.show_ai.get()))
                if hasattr(self, 'show_viewer'):
                    self.config_manager.set("display.show.viewer", bool(self.show_viewer.get()))
                if hasattr(self, 'flow_direction_area'):
                    self.config_manager.set("display.flow.direction", (self.flow_direction_area.get() or "UP").upper())
                if hasattr(self, 'flow_pad_bottom_area'):
                    self.config_manager.set("display.flow.pad_bottom", bool(self.flow_pad_bottom_area.get()))


                # フォント系（UI→Configのオリジナル保存）
                if hasattr(self, 'font_family'):
                    self.config_manager.set("style.font.family", self.font_family.get())
                if hasattr(self, 'name_font_size'):
                    self.config_manager.set("style.name.font.size", int(self.name_font_size.get()))
                if hasattr(self, 'name_font_bold'):
                    self.config_manager.set("style.name.font.bold", bool(self.name_font_bold.get()))
                if hasattr(self, 'name_font_italic'):
                    self.config_manager.set("style.name.font.italic", bool(self.name_font_italic.get()))
                if hasattr(self, 'name_use_custom_color'):
                    self.config_manager.set("style.name.use_custom_color", bool(self.name_use_custom_color.get()))
                if hasattr(self, 'name_custom_color'):
                    self.config_manager.set("style.name.custom_color", self.name_custom_color.get())
                if hasattr(self, 'body_font_size'):
                    self.config_manager.set("style.body.font.size", int(self.body_font_size.get()))
                if hasattr(self, 'body_font_bold'):
                    self.config_manager.set("style.body.font.bold", bool(self.body_font_bold.get()))
                if hasattr(self, 'body_font_italic'):
                    self.config_manager.set("style.body.font.italic", bool(self.body_font_italic.get()))
                # 名前を表示するかどうか（UI復元用）
                if hasattr(self, 'name_show_var'):
                    self.config_manager.set("style.name.show", bool(self.name_show_var.get()))

                # 本文インデント
                if hasattr(self, 'body_indent'):
                    self.config_manager.set("style.body.indent", int(self.body_indent.get()))

                # 文字の影設定
                if hasattr(self, 'shadow_enabled'):
                    self.config_manager.set("style.text.shadow.enabled", bool(self.shadow_enabled.get()))
                    self.config_manager.set("style.text.shadow.color", self.shadow_color.get())
                    self.config_manager.set("style.text.shadow.offset_x", int(self.shadow_offset_x.get()))
                    self.config_manager.set("style.text.shadow.offset_y", int(self.shadow_offset_y.get()))
                    # Note: blur は config_handler に無いが、将来のために保存
                    if hasattr(self, 'shadow_blur'):
                        self.config_manager.set("style.text.shadow.blur", int(self.shadow_blur.get()))

                # レイアウト設定
                if hasattr(self, 'name_position'):
                    self.config_manager.set("style.layout.name_position", self.name_position.get().upper())
                if hasattr(self, 'name_offset_x'):
                    self.config_manager.set("style.layout.name_offset_x", int(self.name_offset_x.get()))
                if hasattr(self, 'name_offset_y'):
                    self.config_manager.set("style.layout.name_offset_y", int(self.name_offset_y.get()))
                if hasattr(self, 'name_body_spacing'):
                    self.config_manager.set("style.layout.name_body_spacing", int(self.name_body_spacing.get()))
                if hasattr(self, 'line_height'):
                    self.config_manager.set("style.layout.line_height", float(self.line_height.get()))
                if hasattr(self, 'padding_top'):
                    self.config_manager.set("style.layout.padding.top", int(self.padding_top.get()))
                    self.config_manager.set("style.layout.padding.right", int(self.padding_right.get()))
                    self.config_manager.set("style.layout.padding.bottom", int(self.padding_bottom.get()))
                    self.config_manager.set("style.layout.padding.left", int(self.padding_left.get()))

                # 背景設定
                if hasattr(self, 'bg_color'):
                    self.config_manager.set("style.background.color", self.bg_color.get())
                    self.config_manager.set("style.background.opacity", int(self.bg_opacity.get()))
                    self.config_manager.set("style.background.border_radius", int(self.border_radius.get()))
                if hasattr(self, 'border_enabled'):
                    self.config_manager.set("style.background.border.enabled", bool(self.border_enabled.get()))
                    self.config_manager.set("style.background.border.color", self.border_color.get())
                    self.config_manager.set("style.background.border.width", int(self.border_width.get()))

                # 役割別カラー設定
                if hasattr(self, 'streamer_color'):
                    self.config_manager.set("style.role.streamer.color", self.streamer_color.get())
                    self.config_manager.set("style.role.ai.color", self.ai_color.get())
                    self.config_manager.set("style.role.viewer.color", self.viewer_color.get())

                # 出力モードはHTML固定（v17.5.7以降、TXT出力は廃止）
                self.config_manager.set("display.output.mode", "HTML")

                # ←★ ここでHTMLブリッジを差し込む（UI→file_backendが読むキーへ）
                self._bridge_html_overlay_keys()

                # 最後に一回だけ保存
                self.config_manager.save()
                self._update_status("✅ すべての設定を保存しました")

                # （任意）OBS側へリフレッシュ通知
                if self.bus:
                    try:
                        self.bus.publish("OBS_OVERLAY_REFRESH", {"source": "obs_tab"})
                        self._export_overlay_snapshot()
                    except Exception:
                        pass

            except Exception as e:
                self._update_status(f"❌ 保存エラー: {e}")

        # 表示中のタブをリセットする関数（notebookは後で参照）
        self._reset_current_tab_func = None

        ttk.Button(common_buttons_frame, text="💾 すべての設定を保存",
                  command=_save_all_settings, width=20).pack(side="left", padx=(0, 8))

        def _reset_current_tab():
            """表示中のタブの設定をリセット"""
            if self._reset_current_tab_func:
                self._reset_current_tab_func()
            else:
                self._update_status("⚠️ リセット機能がまだ準備できていません")

        ttk.Button(common_buttons_frame, text="🔄 表示中のタブの設定をリセット",
                  command=_reset_current_tab, width=28).pack(side="left")

        # ── 左右を PanedWindow で管理（右側を一番上まで伸ばす） ──
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 左ペイン: ステータス + Notebook を縦に配置
        left_panel = ttk.Frame(paned_window)
        paned_window.add(left_panel, weight=1)

        # 左ペイン上部: OBS演出タブステータス
        status_outer = ttk.Frame(left_panel)
        status_outer.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        if hasattr(self, "_build_status_panel"):
            # ステータスパネルを共通ヘッダーとして配置
            self._build_status_panel(status_outer)

        # 左ペイン下部: 子タブNotebook
        notebook = ttk.Notebook(left_panel)
        notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 右ペイン: 共通プレビューパネル（一番上から下まで）
        self.preview_labelframe = ttk.LabelFrame(
            paned_window,
            text="📺 OBSプレビュー（共通）",
            padding=(8, 6),
        )
        paned_window.add(self.preview_labelframe, weight=1)

        # ── 📐 子タブ1: コメントの表示エリア設定（統合版） ───────────────────────
        area_tab = ttk.Frame(notebook)
        notebook.add(area_tab, text="📐 コメントの表示エリア設定")

        # ★順番が重要★ 先にコントロールを作成してから、プレビューを構築
        # 1) 先に「コメントの表示エリア設定」タブのコントロールを作る
        #    → ここで self.area_x / self.area_y / self.area_width / self.area_height などが生成される
        if hasattr(self, "_inject_unified_area_controls"):
            self._inject_unified_area_controls(area_tab)

        # 2) その設定を参照する「共通プレビューパネル」を後から構築
        #    → _build_shared_preview_panel 内で _update_area_preview() を呼んでも、すでに変数が存在する
        if hasattr(self, "_build_shared_preview_panel"):
            self._build_shared_preview_panel(self.preview_labelframe)

        # ── 🎨 子タブ2: コメントの装飾設定 ─────────────────────
        comment_tab = ttk.Frame(notebook)
        notebook.add(comment_tab, text="🎨 コメントの装飾設定")

        # コメント表示設定（フォント/色/配置/背景）
        if hasattr(self, "_inject_comment_style_controls"):
            self._inject_comment_style_controls(comment_tab)

        # ── 🎭 子タブ3: 演出効果 ─────────────────────────────
        effects_tab = ttk.Frame(notebook)
        notebook.add(effects_tab, text="🎭 演出効果")

        # 演出効果タブのUIを構築（既存のプリセット／プレビュー系を集約）
        self._build_effects_ui(effects_tab)

        # タブ別リセット機能を設定
        def _reset_tab_settings():
            """表示中のタブの設定をリセット"""
            current_tab_index = notebook.index(notebook.select())
            tab_names = ["コメントの表示エリア設定", "コメントの装飾設定", "演出効果"]

            if current_tab_index == 0:  # コメントの表示エリア設定
                if hasattr(self, '_reset_area_settings'):
                    self._reset_area_settings()
                    self._update_status(f"🔄 「{tab_names[0]}」タブの設定をリセットしました")
            elif current_tab_index == 1:  # コメントの装飾設定
                # スタイルプリセットは対象外なので、個別の設定のみリセット
                # デフォルトに戻すのではなく、現在のプリセットを再適用
                if hasattr(self, '_apply_comment_preset'):
                    self._apply_comment_preset()
                    self._update_status(f"🔄 「{tab_names[1]}」タブの設定を現在のプリセットに戻しました")
            elif current_tab_index == 2:  # 演出効果
                self._update_status(f"ℹ️ 「{tab_names[2]}」タブはプリセット管理なのでリセット対象外です")

        self._reset_current_tab_func = _reset_tab_settings

    def _build_shared_preview_panel(self, parent):
        """右側の共通プレビューパネル（HTML / OBSエリア / コメント）"""
        import tkinter as tk
        from tkinter import ttk

        # 上: HTMLオーバーレイ出力プレビュー（実際の機能ボタン）
        html_frame = ttk.LabelFrame(parent, text="🌐 HTMLオーバーレイ出力", padding=5)
        html_frame.pack(fill=tk.X, expand=False)

        # HTMLオーバーレイ出力の実際のボタンと機能を注入
        self._inject_html_overlay_controls(html_frame)

        # 中: OBSエリアプレビュー（コメント表示エリア設定 & 演出効果 共通）
        area_frame = ttk.LabelFrame(parent, text="🖼 コメント表示エリア（OBSプレビュー）", padding=5)
        area_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # プレビュー用のコンテナフレーム（リサイズ対応）
        preview_container = ttk.Frame(area_frame)
        preview_container.pack(fill="both", expand=True, pady=4, padx=4)

        self.area_preview_canvas = tk.Canvas(preview_container, bg='#1a1a1a',
                                            highlightthickness=1, highlightbackground='#444')
        self.area_preview_canvas.pack(fill="both", expand=True)

        # リサイズイベントハンドラ
        preview_container.bind("<Configure>", self._on_preview_resize)

        # プレビューエリアを描画（ドラッグ&リサイズ対応）
        self.preview_rect = None
        self.preview_drag_data = {"x": 0, "y": 0, "dragging": False, "resize_handle": None}

        # マウスイベントバインド（ドラッグ＆リサイズ機能）
        self.area_preview_canvas.bind("<Button-1>", self._on_preview_press)
        self.area_preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.area_preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)
        self.area_preview_canvas.bind("<Motion>", self._on_preview_motion)

        # 初期プレビュー描画
        self._update_area_preview()

        # 下: コメントデザインプレビュー（切り替えボタン付き）
        comment_frame = ttk.LabelFrame(parent, text="💬 コメント表示プレビュー", padding=5)
        comment_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # ロール切り替えボタン
        role_bar = ttk.Frame(comment_frame)
        role_bar.pack(fill=tk.X, pady=(0, 4))

        self.current_preview_role = tk.StringVar(value="streamer")

        ttk.Button(role_bar, text="配信者",
                  command=lambda: self._update_comment_role_preview("streamer")).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(role_bar, text="AIキャラ",
                  command=lambda: self._update_comment_role_preview("ai")).pack(side=tk.LEFT, padx=4)
        ttk.Button(role_bar, text="視聴者",
                  command=lambda: self._update_comment_role_preview("viewer")).pack(side=tk.LEFT, padx=4)

        # プレビュー表示エリア（共通）
        comment_preview_container = ttk.Frame(comment_frame)
        comment_preview_container.pack(fill="both", expand=True)

        self.comment_preview_canvas = tk.Canvas(comment_preview_container, bg="#2b2b2b", highlightthickness=0)
        self.comment_preview_canvas.pack(fill="both", expand=True)

        # コンテナのリサイズに追従
        comment_preview_container.bind("<Configure>", self._on_comment_preview_resize)

        # プレビュー更新用の変数を保存
        self.comment_preview_items = {
            'streamer': None,
            'ai': None,
            'viewer': None
        }

        # 初期描画
        self._update_comment_role_preview("streamer")

    def _update_comment_role_preview(self, role: str):
        """
        role: "streamer" / "ai" / "viewer"
        共通プレビューキャンバスに1つのコメントを描画する。
        スタイル設定を完全に反映した実装。
        """
        if role not in ("streamer", "ai", "viewer"):
            return

        # 現在のロールを保存
        if hasattr(self, 'current_preview_role'):
            self.current_preview_role.set(role)

        # キャンバスが存在しない場合は何もしない
        if not hasattr(self, 'comment_preview_canvas'):
            return

        # キャンバスをクリア
        self.comment_preview_canvas.delete("all")

        # ロールごとのサンプルデータ
        sample_data = {
            "streamer": {"name": "配信者", "text": "配信を開始\nします！"},
            "ai": {"name": "ぎゅるる", "text": "はーい！\n楽しみです♪"},
            "viewer": {"name": "視聴者A", "text": "わーい！\n楽しみです"}
        }

        sample = sample_data[role]

        # ── スタイル設定を取得 ──
        try:
            font_family = self.font_family.get() if hasattr(self, 'font_family') else "Yu Gothic UI"

            # 名前の設定
            name_font_size = int(self.name_font_size.get()) if hasattr(self, 'name_font_size') else 24
            name_font_bold = self.name_font_bold.get() if hasattr(self, 'name_font_bold') else False
            name_font_italic = self.name_font_italic.get() if hasattr(self, 'name_font_italic') else False
            name_use_custom_color = self.name_use_custom_color.get() if hasattr(self, 'name_use_custom_color') else False
            name_custom_color = self.name_custom_color.get() if hasattr(self, 'name_custom_color') else "#FFFFFF"

            # 本文の設定
            body_font_size = int(self.body_font_size.get()) if hasattr(self, 'body_font_size') else 12
            body_font_bold = self.body_font_bold.get() if hasattr(self, 'body_font_bold') else False
            body_font_italic = self.body_font_italic.get() if hasattr(self, 'body_font_italic') else False
            body_indent = int(self.body_indent.get()) if hasattr(self, 'body_indent') else 0

            # 背景・枠線設定
            bg_color = self.bg_color.get() if hasattr(self, 'bg_color') else "#FFFFFF"
            bg_opacity = int(self.bg_opacity.get()) if hasattr(self, 'bg_opacity') else 90
            border_radius = int(self.border_radius.get()) if hasattr(self, 'border_radius') else 10
            border_enabled = self.border_enabled.get() if hasattr(self, 'border_enabled') else False
            border_color = self.border_color.get() if hasattr(self, 'border_color') else "#000000"
            border_width = int(self.border_width.get()) if hasattr(self, 'border_width') else 2

            # パディング
            padding_top = int(self.padding_top.get()) if hasattr(self, 'padding_top') else 10
            padding_left = int(self.padding_left.get()) if hasattr(self, 'padding_left') else 10
            padding_right = int(self.padding_right.get()) if hasattr(self, 'padding_right') else 10
            padding_bottom = int(self.padding_bottom.get()) if hasattr(self, 'padding_bottom') else 10

            # 名前位置
            name_pos = self.name_position.get() if hasattr(self, 'name_position') else "TOP_LEFT"
            name_offset_x = int(self.name_offset_x.get()) if hasattr(self, 'name_offset_x') else 0
            name_offset_y = int(self.name_offset_y.get()) if hasattr(self, 'name_offset_y') else 0
            name_body_spacing = int(self.name_body_spacing.get()) if hasattr(self, 'name_body_spacing') else 4

            # 役割別カラー
            streamer_color = self.streamer_color.get() if hasattr(self, 'streamer_color') else "#4A90E2"
            ai_color = self.ai_color.get() if hasattr(self, 'ai_color') else "#9B59B6"
            viewer_color = self.viewer_color.get() if hasattr(self, 'viewer_color') else "#7F8C8D"

            role_color_map = {
                "streamer": streamer_color,
                "ai": ai_color,
                "viewer": viewer_color
            }
            role_color = role_color_map[role]

            # フォントスタイル
            name_font_weight = "bold" if name_font_bold else "normal"
            name_font_slant = "italic" if name_font_italic else "roman"
            name_font_tuple = (font_family, name_font_size, name_font_weight, name_font_slant)

            body_font_weight = "bold" if body_font_bold else "normal"
            body_font_slant = "italic" if body_font_italic else "roman"
            body_font_tuple = (font_family, body_font_size, body_font_weight, body_font_slant)

            # ── 吹き出しを描画 ──
            # キャンバスサイズを取得（最小値を確保）
            self.comment_preview_canvas.update_idletasks()
            canvas_width = max(self.comment_preview_canvas.winfo_width(), 400)
            canvas_height = max(self.comment_preview_canvas.winfo_height(), 200)

            # ===== テキストサイズから吹き出しサイズを算出 =====
            # フォントオブジェクト（実測用）
            name_font_obj = tkfont.Font(
                family=font_family,
                size=name_font_size,
                weight="bold" if name_font_bold else "normal",
                slant="italic" if name_font_italic else "roman",
            )
            body_font_obj = tkfont.Font(
                family=font_family,
                size=body_font_size,
                weight="bold" if body_font_bold else "normal",
                slant="italic" if body_font_italic else "roman",
            )

            sample = sample_data[role]

            # 各行の幅を計測（インデントも考慮）
            name_text = sample["name"]
            body_lines = sample["text"].splitlines() or [""]

            name_width = name_font_obj.measure(name_text)

            # body_indent は px 相当なので、ざっくり空白文字で足しておく
            indent_spaces = max(body_indent, 0) // max(body_font_obj.measure(" "), 1)
            body_widths = [
                body_font_obj.measure(" " * indent_spaces + line)
                for line in body_lines
            ]
            max_body_width = max(body_widths) if body_widths else 0

            text_width = max(name_width, max_body_width)

            # 高さ（行数 × 行間）を計算
            name_line_h = name_font_obj.metrics("linespace")
            body_line_h = body_font_obj.metrics("linespace")
            body_height = body_line_h * len(body_lines)

            # パディングと名前と本文の間隔を含めたボックスサイズ
            base_width = text_width + padding_left + padding_right
            base_height = (
                padding_top
                + name_line_h
                + name_body_spacing
                + body_height
                + padding_bottom
            )

            # キャンバスからはみ出さないようにクリップ
            box_width = min(int(base_width), canvas_width - 40)
            box_height = min(int(base_height), canvas_height - 40)

            # キャンバス中央に配置
            x1 = (canvas_width - box_width) // 2
            y1 = (canvas_height - box_height) // 2
            x2 = x1 + box_width
            y2 = y1 + box_height

            # 吹き出しのしっぽの向き
            tail_pos = self.bubble_tail_position.get().upper() if hasattr(self, 'bubble_tail_position') else "BOTTOM"
            if hasattr(self, 'bubble_tail_auto') and self.bubble_tail_auto.get():
                if "TOP" in name_pos:
                    tail_pos = "BOTTOM"
                elif "BOTTOM" in name_pos:
                    tail_pos = "TOP"
                elif "RIGHT" in name_pos:
                    tail_pos = "LEFT"
                else:
                    tail_pos = "RIGHT"

            self._draw_bubble(
                self.comment_preview_canvas, x1, y1, x2, y2,
                bg_color=bg_color,
                bg_opacity=bg_opacity,
                canvas_bg="#2b2b2b",
                radius=border_radius,
                border=border_enabled,
                border_color=border_color,
                border_width=border_width,
                bubble_type=self.bubble_type.get().upper() if hasattr(self, 'bubble_type') else "NONE",
                tail_enabled=self.bubble_tail_enabled.get() if hasattr(self, 'bubble_tail_enabled') else False,
                tail_pos=tail_pos,
                tail_size=self.bubble_tail_size.get() if hasattr(self, 'bubble_tail_size') else 15
            )

            # ── テキストを描画 ──
            text_x_body = x1 + padding_left
            text_y_body = y1 + padding_top

            # 名前の色（独自色を使うか役割別色を使うか）
            name_color = name_custom_color if name_use_custom_color else role_color
            body_color = role_color

            # 名前の位置を計算
            name_x, name_y = text_x_body, text_y_body

            if name_pos == "TOP_LEFT":
                name_x = x1 + padding_left + name_offset_x
                name_y = y1 + padding_top + name_offset_y
                body_y = name_y + name_font_size + name_body_spacing
                body_x = text_x_body
            elif name_pos == "TOP_RIGHT":
                name_x = x2 - padding_right + name_offset_x
                name_y = y1 + padding_top + name_offset_y
                body_y = name_y + name_font_size + name_body_spacing
                body_x = text_x_body
            elif name_pos == "TOP_CENTER":
                name_x = x1 + (box_width // 2) + name_offset_x
                name_y = y1 + padding_top + name_offset_y
                body_y = name_y + name_font_size + name_body_spacing
                body_x = text_x_body
            else:
                # デフォルト（左上）
                name_x = text_x_body + name_offset_x
                name_y = text_y_body + name_offset_y
                body_y = name_y + name_font_size + name_body_spacing
                body_x = text_x_body

            # anchorを位置に応じて設定
            if "RIGHT" in name_pos:
                name_anchor = "ne"
            elif "CENTER" in name_pos:
                name_anchor = "n"
            else:
                name_anchor = "nw"

            # 整列
            align = self.text_alignment.get().upper() if hasattr(self, 'text_alignment') else "LEFT"
            if align == "CENTER":
                body_anchor = "n"
                body_x = x1 + (box_width // 2)
            elif align == "RIGHT":
                body_anchor = "ne"
                body_x = x2 - padding_right
            else:
                body_anchor = "nw"
                body_x = text_x_body

            # 名前表示の判定
            show_name = True
            if hasattr(self, "name_show_var"):
                try:
                    show_name = bool(self.name_show_var.get())
                except Exception:
                    show_name = True

            # 名前を描画
            if show_name:
                self._draw_text(
                    self.comment_preview_canvas,
                    name_x, name_y,
                    sample["name"],
                    font=name_font_tuple,
                    fill=name_color,
                    anchor=name_anchor,
                    outline_enabled=self.text_outline_enabled.get() if hasattr(self, 'text_outline_enabled') else False,
                    outline_color=self.text_outline_color.get() if hasattr(self, 'text_outline_color') else "#000000",
                    outline_width=int(self.text_outline_width.get()) if hasattr(self, 'text_outline_width') else 2,
                    shadow_enabled=self.shadow_enabled.get() if hasattr(self, 'shadow_enabled') else False,
                    shadow_color=self.shadow_color.get() if hasattr(self, 'shadow_color') else "#000000",
                    shadow_offset=(int(self.shadow_offset_x.get()), int(self.shadow_offset_y.get())) if hasattr(self, 'shadow_offset_x') else (0, 0)
                )
            else:
                body_y = y1 + padding_top

            # 本文を描画
            self._draw_text(
                self.comment_preview_canvas,
                (body_x + body_indent) if align == "LEFT" else body_x,
                body_y,
                sample["text"],
                font=body_font_tuple,
                fill=body_color,
                anchor=body_anchor,
                outline_enabled=self.text_outline_enabled.get() if hasattr(self, 'text_outline_enabled') else False,
                outline_color=self.text_outline_color.get() if hasattr(self, 'text_outline_color') else "#000000",
                outline_width=int(self.text_outline_width.get()) if hasattr(self, 'text_outline_width') else 2,
                shadow_enabled=self.shadow_enabled.get() if hasattr(self, 'shadow_enabled') else False,
                shadow_color=self.shadow_color.get() if hasattr(self, 'shadow_color') else "#000000",
                shadow_offset=(int(self.shadow_offset_x.get()), int(self.shadow_offset_y.get())) if hasattr(self, 'shadow_offset_x') else (0, 0),
                width=box_width - padding_left - padding_right - body_indent if align == "LEFT" else box_width - padding_left - padding_right
            )

        except Exception as e:
            logger.exception(f"プレビュー更新エラー: {e}")

            # エラー時はシンプルな表示
            self.comment_preview_canvas.create_text(
                20, 20,
                text=f"プレビューエラー: {str(e)}",
                fill="red",
                anchor="nw",
                font=("Yu Gothic UI", 10)
            )

    def _build_effects_ui(self, parent):
        """演出効果タブのUI（プリセット一覧＋左下に簡易プレビュー）"""
        import tkinter as tk
        from tkinter import ttk

        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ヘッダー（接続状態・ボタン等）
        if hasattr(self, "_build_header"):
            self._build_header(main_frame)

        # プリセット一覧（1カラム）
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        presets_panel = ttk.LabelFrame(content_frame, text="🎭 エフェクトプリセット", padding="10")
        presets_panel.pack(fill=tk.BOTH, expand=True)

        # プリセット一覧（Listbox + ボタン）
        if hasattr(self, "_build_presets_panel"):
            self._build_presets_panel(presets_panel)

    def _build_header(self, parent):
        """ヘッダー部分"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # 接続状態
        self.connection_var = tk.StringVar(value="❌ 未接続")
        connection_label = ttk.Label(header_frame, textvariable=self.connection_var,
                                   font=("Arial", 10))
        connection_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # 自動エフェクト切り替え
        self.auto_var = tk.BooleanVar(value=self.auto_effects_enabled)
        auto_check = ttk.Checkbutton(header_frame, text="自動エフェクト",
                                   variable=self.auto_var,
                                   command=self._on_auto_toggle)
        auto_check.pack(side=tk.RIGHT, padx=(10, 0))

    def _build_presets_panel(self, parent):
        """プリセット管理パネル"""
        # リストボックス＋スクロールバー
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.presets_listbox = tk.Listbox(list_frame, height=8, font=("Arial", 10))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.presets_listbox.yview)
        self.presets_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.presets_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.presets_listbox.bind('<<ListboxSelect>>', self._on_preset_select)

        # エフェクト密度（プリセット count に掛ける倍率）
        density_frame = ttk.Frame(parent)
        density_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(density_frame, text="エフェクト密度:").grid(row=0, column=0, sticky="w")

        density_spin = ttk.Spinbox(
            density_frame,
            from_=0.2,
            to=3.0,
            increment=0.2,
            textvariable=self.effect_density_var,
            width=5
        )
        density_spin.grid(row=0, column=1, sticky="w", padx=(5, 0))

        ttk.Label(density_frame, text="×（0.2〜3.0）").grid(row=0, column=2, sticky="w", padx=(5, 0))

        # プリセット操作ボタン
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="▶ 実行", command=self._on_execute_preset).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="✏️ 編集", command=self._on_edit_preset).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="➕ 追加", command=self._on_add_preset).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="🗑️ 削除", command=self._on_delete_preset).pack(side=tk.LEFT)
        
        self._update_presets_list()

    def _build_status_panel(self, parent):
        """ステータスパネル（WebSocketタブと同じスタイルに統一）"""
        status_frame = ttk.LabelFrame(parent, text="📊 OBS演出タブステータス", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # 1段目：状態 + 最後のエフェクト（左寄せ）
        status_row = ttk.Frame(status_frame)
        status_row.pack(fill=tk.X, pady=(0, 8), anchor="w")

        # 状態
        state_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        state_frame.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(state_frame, text="状態: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.status_var = tk.StringVar(value="準備完了")
        self.status_label = tk.Label(state_frame, textvariable=self.status_var, fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=(0, 5))

        # 最後のエフェクト
        effect_frame = tk.Frame(status_row, bg="#2b2b2b", relief=tk.RIDGE, borderwidth=1)
        effect_frame.pack(side=tk.LEFT)
        tk.Label(effect_frame, text="最後のエフェクト: ", bg="#2b2b2b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 0))
        self.last_effect_var = tk.StringVar(value="なし")
        self.last_effect_label = tk.Label(effect_frame, textvariable=self.last_effect_var, fg="#90EE90", bg="#2b2b2b", font=("Arial", 9, "bold"))
        self.last_effect_label.pack(side=tk.LEFT, padx=(0, 5))

        # 2段目：カウント表示のみ（左寄せ）
        counter_row = ttk.Frame(status_frame)
        counter_row.pack(fill=tk.X, anchor="w")

        # カウント表示（左端）
        self.stats_var = tk.StringVar(value="総実行: 0 | チャット: 0 | AI: 0 | 手動: 0")
        self.stats_label = tk.Label(counter_row, textvariable=self.stats_var, fg="#FFD700", bg="#2b2b2b", font=("Arial", 9))
        self.stats_label.pack(side=tk.LEFT)

    def _update_presets_list(self):
        """プリセットリスト更新"""
        self.presets_listbox.delete(0, tk.END)
        for preset_id, preset in self.effects_presets.items():
            status = "✅" if preset.enabled else "❌"
            display_text = f"{status} {preset.description} ({preset.duration}s)"
            self.presets_listbox.insert(tk.END, display_text)

    def _subscribe_events(self):
        """イベント購読"""
        if not self.bus:
            return

        # 既存
        self.bus.subscribe(Events.CHAT_MESSAGE, self._on_chat_message)
        self.bus.subscribe(Events.AI_RESPONSE, self._on_ai_response)

        # --- Phase 7: ONECOMME_COMMENT / VOICE_REQUEST 購読 ---
        if hasattr(Events, "ONECOMME_COMMENT"):
            self.bus.subscribe(Events.ONECOMME_COMMENT, self._on_onecomme_comment)

        if hasattr(Events, "VOICE_REQUEST"):
            self.bus.subscribe(Events.VOICE_REQUEST, self._on_voice_request)

        # v17: 配信者プロフィール更新イベントを購読
        if hasattr(Events, "STREAMER_PROFILE_UPDATE"):
            self.bus.subscribe(Events.STREAMER_PROFILE_UPDATE, self._on_streamer_profile_update)
            logger.info("🐛 [DEBUG] STREAMER_PROFILE_UPDATE 購読完了")

    def _on_chat_message(self, data: Optional[Dict[str, Any]], sender=None, **kwargs):
        """CHAT_MESSAGE → オーバーレイ表示 + 自動エフェクト (Phase 2: メッセージ表示を常に実行)"""
        auto_enabled = self.auto_var.get() if hasattr(self, 'auto_var') else False
        logger.debug(f"📨 CHAT_MESSAGE 受信: auto_enabled={auto_enabled}")

        try:
            payload = data or {}
            text = payload.get("message") or payload.get("text") or ""
            username = payload.get("username", "Unknown")

            # v17.5.7+: role フィールドをサポート（配信者/視聴者の区別）
            role = payload.get("role", ROLE_VIEWER)
            # role の正規化
            if role not in [ROLE_STREAMER, ROLE_AI, ROLE_VIEWER]:
                role = ROLE_VIEWER

            # v17.5.7+: username が空/デフォルトで、role=streamer の場合は Config から取得
            if role == ROLE_STREAMER and (not username or username == "Unknown"):
                if hasattr(self, 'config_manager') and self.config_manager:
                    username = self.config_manager.get("streamer.display_name", "配信者") or "配信者"

            if not text:
                logger.debug("⚠️ メッセージが空のため処理スキップ")
                return

            logger.info(f"💬 チャットメッセージ処理 ({role}): {username}: {text[:50]}...")

            # ✅ Phase 2: メッセージ表示は auto_enabled に関係なく常に実行
            if _USE_INTEGRATED_MODULES and hasattr(self, "effects") and self.effects:
                logger.debug(f"📦 統合モジュールを使用してメッセージを追加 (role={role})")

                # Phase X: role に応じた effectType を取得
                effect_type = "fadeUp"  # デフォルト
                if hasattr(self, "obs_config") and self.obs_config:
                    effect_type_key = f"effect.type.{role}"
                    effect_type = self.obs_config.get(effect_type_key, "fadeUp") or "fadeUp"
                    logger.debug(f"🎨 effectType: {effect_type} (role={role})")

                self.effects.push_message(
                    role=role,  # v17.5.7: 動的に role を設定
                    name=username,
                    text=text,
                    effect_type=effect_type,  # Phase X: effectType を追加
                )
                # ファイル出力
                if hasattr(self, "file_output") and self.file_output:
                    logger.debug("💾 ファイル出力を実行")
                    self.file_output.flush_to_files()
                else:
                    logger.error("❌ file_output が存在しません")
            # フォールバック（統合モジュールが無い場合）
            elif hasattr(self, '_overlay_items'):
                logger.warning("⚠️ フォールバックモードを使用")
                self._overlay_items.append({
                    "role": "viewer",
                    "name": username,
                    "text": text,
                    "ts": time.time()
                })
                self._export_overlay_snapshot()
            else:
                logger.error("❌ 統合モジュールもフォールバックも利用できません")

            # ✅ Phase 2: 自動エフェクトは auto_enabled が ON の時のみ実行
            if not auto_enabled:
                logger.debug("⚠️ 自動エフェクトがOFFのため、エフェクトトリガー判定をスキップ")
                return

            # エフェクトトリガー判定
            text_lower = text.lower()
            for preset_id, preset in self.effects_presets.items():
                if not getattr(preset, "enabled", False):
                    continue
                for trigger in getattr(preset, "trigger_words", []):
                    if trigger.lower() in text:
                        self._execute_effect(preset_id, "chat", username)
                        return
        except Exception as e:
            self._update_status(f"チャット処理エラー: {e}")


    def _on_ai_response(self, data: Optional[Dict[str, Any]], sender=None, **kwargs):
        """AI_RESPONSE → オーバーレイ表示 + 自動エフェクト (Phase 2: メッセージ表示を常に実行)"""
        auto_enabled = self.auto_var.get() if hasattr(self, 'auto_var') else False
        logger.debug(f"🤖 AI_RESPONSE 受信: auto_enabled={auto_enabled}")

        try:
            payload = data or {}
            text = payload.get("ai_response") or payload.get("text") or ""

            if not text:
                logger.debug("⚠️ AI応答が空のため処理スキップ")
                return

            logger.info(f"🤖 AI応答処理: {text[:50]}...")

            # --- 統合モジュール使用 (Phase X: effectType サポート) ---
            if _USE_INTEGRATED_MODULES and hasattr(self, "effects") and self.effects:
                logger.debug("📦 統合モジュールを使用してAI応答を追加")

                # Phase X: role に応じた effectType を取得
                effect_type = "pop"  # デフォルト (AI は pop)
                if hasattr(self, "obs_config") and self.obs_config:
                    effect_type = self.obs_config.get("effect.type.ai", "pop") or "pop"
                    logger.debug(f"🎨 effectType: {effect_type} (role=ai)")

                self.effects.push_message(
                    role=ROLE_AI,
                    name="AI",
                    text=text,
                    effect_type=effect_type,  # Phase X: effectType を追加
                )
                # ファイル出力
                if hasattr(self, "file_output") and self.file_output:
                    logger.debug("💾 ファイル出力を実行")
                    self.file_output.flush_to_files()
                else:
                    logger.error("❌ file_output が存在しません")
            # フォールバック（統合モジュールが無い場合）
            elif hasattr(self, '_overlay_items'):
                logger.warning("⚠️ フォールバックモードを使用")
                self._overlay_items.append({
                    "role": "ai",
                    "name": "AI",
                    "text": text,
                    "ts": time.time()
                })
                self._export_overlay_snapshot()
            else:
                logger.error("❌ 統合モジュールもフォールバックも利用できません")

            # ✅ Phase 2: 自動エフェクトは auto_enabled が ON の時のみ実行
            if not auto_enabled:
                logger.debug("⚠️ 自動エフェクトがOFFのため、エフェクトトリガー判定をスキップ")
                return

            # エフェクトトリガー判定
            response = text.lower()
            if any(w in response for w in ["おめでとう", "すごい", "素晴らしい"]):
                self._execute_effect("confetti", "ai", "AI")
            elif any(w in response for w in ["かわいい", "好き", "愛"]):
                self._execute_effect("heart", "ai", "AI")
            elif any(w in response for w in ["ありがとう", "感謝"]):
                self._execute_effect("thanks", "ai", "AI")

        except Exception as e:
            self._update_status(f"AI応答処理エラー: {e}")

    def _on_onecomme_comment(self, data: Optional[Dict[str, Any]], sender=None, **kwargs):
        """ONECOMME_COMMENT → オーバーレイ表示 + 自動エフェクト (Phase 2: メッセージ表示を常に実行)"""
        auto_enabled = self.auto_var.get() if hasattr(self, 'auto_var') else False
        logger.debug(f"📡 ONECOMME_COMMENT 受信: auto_enabled={auto_enabled}")

        try:
            payload = data or {}
            # キー名は ONECOMME_COMMENT payload に合わせて調整
            username = (
                payload.get("user_name")
                or payload.get("username")
                or payload.get("user")
                or "Unknown"
            )
            text = (
                payload.get("message")
                or payload.get("comment")
                or payload.get("text")
                or ""
            )
            if not text:
                logger.debug("⚠️ OneCommeコメントが空のため処理スキップ")
                return

            logger.info(f"📡 OneCommeコメント処理: {username}: {text[:50]}...")

            # --- 統合モジュール使用 (Phase X: effectType サポート) ---
            if _USE_INTEGRATED_MODULES and hasattr(self, "effects") and self.effects:
                logger.debug("📦 統合モジュールを使用してOneCommeコメントを追加")

                # Phase X: role に応じた effectType を取得
                effect_type = "fadeUp"  # デフォルト
                if hasattr(self, "obs_config") and self.obs_config:
                    effect_type = self.obs_config.get("effect.type.viewer", "fadeUp") or "fadeUp"
                    logger.debug(f"🎨 effectType: {effect_type} (role=viewer)")

                self.effects.push_message(
                    role=ROLE_VIEWER,
                    name=username,
                    text=text,
                    effect_type=effect_type,  # Phase X: effectType を追加
                )
                # ファイル出力
                if hasattr(self, "file_output") and self.file_output:
                    logger.debug("💾 ファイル出力を実行")
                    self.file_output.flush_to_files()
                else:
                    logger.error("❌ file_output が存在しません")
            # フォールバック（統合モジュールが無い場合）
            elif hasattr(self, '_overlay_items'):
                logger.warning("⚠️ フォールバックモードを使用")
                self._overlay_items.append({
                    "role": "viewer",
                    "name": username,
                    "text": text,
                    "ts": time.time()
                })
                self._export_overlay_snapshot()
            else:
                logger.error("❌ 統合モジュールもフォールバックも利用できません")

            # ✅ Phase 2: 自動エフェクトは auto_enabled が ON の時のみ実行
            if not auto_enabled:
                logger.debug("⚠️ 自動エフェクトがOFFのため、エフェクトトリガー判定をスキップ")
                return

            # エフェクトトリガー判定（既存のプリセットと同じロジック）
            text_lower = text.lower()
            for preset_id, preset in self.effects_presets.items():
                if not getattr(preset, "enabled", False):
                    continue
                for trigger in getattr(preset, "trigger_words", []):
                    if trigger.lower() in text_lower:
                        self._execute_effect(preset_id, "viewer", username)
                        break

        except Exception as e:
            self._update_status(f"ONECOMME_COMMENT処理エラー: {e}")

    def _on_voice_request(self, data: Optional[Dict[str, Any]], sender=None, **kwargs):
        """VOICE_REQUEST → 現在の読み上げステータス / overlay 連携 (Phase 7)"""
        logger.debug("🔊 VOICE_REQUEST 受信")

        try:
            payload = data or {}
            text = payload.get("text") or ""
            if not text:
                logger.debug("⚠️ 音声テキストが空のため処理スキップ")
                return

            # role 判定
            role = payload.get("role")
            if not role:
                if payload.get("is_ai") or payload.get("ai_response"):
                    role = ROLE_AI
                else:
                    role = ROLE_STREAMER

            name = (
                payload.get("speaker_name")
                or payload.get("user_name")
                or payload.get("username")
                or ("AI" if role == ROLE_AI else "Streamer")
            )

            logger.info(f"🔊 音声読み上げ処理: {name}({role}): {text[:50]}...")

            # --- live.json 更新（音声再生状態を記録） ---
            if _USE_INTEGRATED_MODULES and hasattr(self, "file_output") and self.file_output:
                live_json_path = os.path.join(self.file_output.out_dir, "live.json")
                live_data = {
                    "voice": {
                        "role": role,
                        "name": name,
                        "text": text,
                        "timestamp": time.time(),
                    },
                    "status": "playing"
                }
                try:
                    os.makedirs(os.path.dirname(live_json_path), exist_ok=True)
                    with open(live_json_path, "w", encoding="utf-8") as f:
                        json.dump(live_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"✅ live.json 書き込み完了: {live_json_path}")
                except Exception as e:
                    logger.error(f"❌ live.json 書き込みエラー: {e}", exc_info=True)
                    self._update_status(f"live.json 書き込みエラー: {e}")
            else:
                logger.warning("⚠️ file_outputが存在しないため、live.json を書き込めません")

        except Exception as e:
            logger.error(f"❌ VOICE_REQUEST処理エラー: {e}", exc_info=True)
            self._update_status(f"VOICE_REQUEST処理エラー: {e}")

    def _on_streamer_profile_update(self, payload, sender=None):
        """
        配信者プロフィール更新イベントを受信したときの処理（v17統一イベント）。

        MessageBus からは h(data, sender=sender) という形で呼ばれるので、
        第1引数=payload, 第2引数=sender (キーワード引数) の順で受け取る。
        """
        if payload is None:
            logger.warning("[OBSEffectsTab] STREAMER_PROFILE_UPDATE 受信: payload が None です")
            return

        name = payload.get("name", "")
        platform = payload.get("platform", "")
        reason = payload.get("reason", "")

        logger.info(
            "[OBSEffectsTab] STREAMER_PROFILE_UPDATE 受信 sender=%s name=%s platform=%s reason=%s",
            sender,
            name,
            platform,
            reason,
        )

        # 将来的には:
        # - payload["profile"] 全体を元に HTML テンプレートをレンダリング
        # - 配信者情報バルーンを画面に表示
        # などに利用する想定。

    def _on_preset_select(self, event):
        """プリセット選択"""
        selection = self.presets_listbox.curselection()
        if selection:
            preset_ids = list(self.effects_presets.keys())
            if 0 <= selection[0] < len(preset_ids):
                preset_id = preset_ids[selection[0]]
                self.selected_preset = preset_id
                preset = self.effects_presets[preset_id]
                self._update_preview(preset)

    def _on_execute_preset(self):
        """プリセット実行"""
        if self.selected_preset:
            self._execute_effect(self.selected_preset, "manual", "User")

    def _execute_effect(self, effect_id: str, trigger_type: str, source: str):
        """エフェクト実行（EffectsHandler + file_backend + OBS通知）"""
        if effect_id not in self.effects_presets:
            logger.warning("⚠️ 未定義のエフェクトIDが指定されました: %s", effect_id)
            return

        preset = self.effects_presets[effect_id]

        # 統計更新
        self.stats["total_effects"] += 1
        self.stats[f"{trigger_type}_triggered"] += 1

        # 履歴追加
        self.effect_history.append({
            "effect": preset.description,
            "trigger_type": trigger_type,
            "source": source,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })

        # ==== 配線追加部分 ====

        # 1) EffectsHandler にエフェクトキュー追加
        if hasattr(self, "effects") and self.effects and hasattr(self.effects, "enqueue_effect"):
            # エフェクト密度倍率（0.2〜3.0、デフォルト 1.0）
            try:
                density = float(self.effect_density_var.get()) if hasattr(self, "effect_density_var") else 1.0
            except Exception:
                density = 1.0

            base_count = getattr(preset, "count", 30)
            override_count = max(1, int(base_count * density))

            params = {
                "duration": preset.duration,
                "emoji": preset.emoji,
                "animation": preset.animation,
                "count": override_count,
                "area": preset.area,
                "size_min": getattr(preset, "size_min", 32),
                "size_max": getattr(preset, "size_max", 32),
            }
            try:
                self.effects.enqueue_effect(preset.name, params)
            except Exception as e:
                logger.exception("❌ エフェクトキュー投入に失敗: %s", e)

        # 2) data.json を更新
        if hasattr(self, "file_output") and self.file_output:
            try:
                self.file_output.flush_to_files()
            except Exception as e:
                logger.exception("❌ data.json書き出し失敗: %s", e)

        # ==== ここまで追加 ====

        # UI 更新
        self.last_effect_var.set(f"{preset.description} ({source})")
        self._update_status(f"エフェクト実行: {preset.description}")
        self._update_stats_display()

        # OBS 側へ通知（将来拡張用）
        self._notify_obs_effect(preset)

        preset.last_used = datetime.now()

    def _notify_obs_effect(self, preset: EffectPreset):
        """OBS効果通知"""
        self.bus.publish(Events.STATUS_UPDATE, {
            "source": "obs_effects",
            "kind": "effect_executed",
            "preset": preset.name,
            "description": preset.description,
            "obs_scene": preset.obs_scene,
            "obs_source": preset.obs_source
        })

    def _on_auto_toggle(self):
        """自動エフェクト切り替え"""
        self.auto_effects_enabled = self.auto_var.get()
        status = "有効" if self.auto_effects_enabled else "無効"
        self._update_status(f"自動エフェクト: {status}")

    def _on_add_preset(self):
        """プリセット追加"""
        self._show_preset_dialog()

    def _on_edit_preset(self):
        """プリセット編集"""
        if self.selected_preset:
            self._show_preset_dialog(self.selected_preset)

    def _on_delete_preset(self):
        """プリセット削除"""
        if self.selected_preset:
            if messagebox.askyesno("確認", f"プリセット '{self.effects_presets[self.selected_preset].description}' を削除しますか？"):
                del self.effects_presets[self.selected_preset]
                self._update_presets_list()
                self._update_status("プリセット削除完了")

    def _show_preset_dialog(self, edit_preset_id: str = None):
        """プリセット編集ダイアログ"""
        dialog = tk.Toplevel(self)
        dialog.title("プリセット編集" if edit_preset_id else "プリセット追加")
        dialog.geometry("500x700")
        dialog.transient(self)
        dialog.grab_set()
        
        # 既存データ
        if edit_preset_id:
            preset = self.effects_presets[edit_preset_id]
        else:
            # TODO: 将来的にこのダイアログに emoji, animation, area, count フィールドを追加
            preset = EffectPreset(
                name="new",
                description="新しいエフェクト",
                duration=3.0,
                emoji=["✨"],  # デフォルト絵文字
                animation="fall",  # デフォルトアニメーション
                count=50,  # デフォルト個数
                area="full"  # デフォルトエリア
            )
        
        # フォーム
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # 名前（ID）
        ttk.Label(frame, text="ID:").grid(row=0, column=0, sticky="w", pady=5)
        id_var = tk.StringVar(value=preset.name)
        ttk.Entry(frame, textvariable=id_var).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=5)

        # 説明
        ttk.Label(frame, text="説明:").grid(row=1, column=0, sticky="w", pady=5)
        desc_var = tk.StringVar(value=preset.description)
        ttk.Entry(frame, textvariable=desc_var).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=5)

        # カラー（プレビュー用）
        ttk.Label(frame, text="カラー:").grid(row=2, column=0, sticky="w", pady=5)
        color_frame = ttk.Frame(frame)
        color_frame.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=5)

        color_var = tk.StringVar(value=preset.color)
        color_entry = ttk.Entry(color_frame, textvariable=color_var, width=10)
        color_entry.pack(side=tk.LEFT)

        def choose_color():
            color = colorchooser.askcolor(color=color_var.get())[1]
            if color:
                color_var.set(color)

        ttk.Button(color_frame, text="選択", command=choose_color).pack(side=tk.LEFT, padx=(5, 0))

        # 絵文字（スペース or 改行区切り）
        ttk.Label(frame, text="絵文字:").grid(row=3, column=0, sticky="nw", pady=5)

        emoji_frame = ttk.Frame(frame)
        emoji_frame.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=5)

        emoji_text = tk.Text(emoji_frame, height=3, width=30)
        emoji_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        emoji_text.insert("1.0", " ".join(preset.emoji))

        def open_emoji_palette():
            self._show_emoji_palette_dialog(emoji_text)

        ttk.Button(emoji_frame, text="🧩 絵文字パレット", command=open_emoji_palette).pack(side=tk.TOP, pady=(5, 0))

        # アニメーション
        ttk.Label(frame, text="アニメーション:").grid(row=4, column=0, sticky="w", pady=5)
        animation_var = tk.StringVar(value=preset.animation)
        animation_combo = ttk.Combobox(
            frame,
            textvariable=animation_var,
            values=("fall", "rise", "scatter", "burst", "flow", "pop"),
            state="readonly",
            width=12,
        )
        animation_combo.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=5)

        # 表示エリア
        ttk.Label(frame, text="表示エリア:").grid(row=5, column=0, sticky="w", pady=5)
        area_var = tk.StringVar(value=preset.area)
        area_combo = ttk.Combobox(
            frame,
            textvariable=area_var,
            values=("full", "bottom", "center", "top"),
            state="readonly",
            width=12,
        )
        area_combo.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=5)

        # 生成数
        ttk.Label(frame, text="生成数:").grid(row=6, column=0, sticky="w", pady=5)
        count_var = tk.IntVar(value=preset.count)
        count_spin = ttk.Spinbox(
            frame,
            from_=1,
            to=200,
            increment=1,
            textvariable=count_var,
            width=6,
        )
        count_spin.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=5)

        # 継続時間
        ttk.Label(frame, text="継続時間(秒):").grid(row=7, column=0, sticky="w", pady=5)
        duration_var = tk.DoubleVar(value=preset.duration)
        duration_spin = ttk.Spinbox(
            frame,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=duration_var,
        )
        duration_spin.grid(row=7, column=1, sticky="ew", padx=(10, 0), pady=5)

        # トリガーワード
        ttk.Label(frame, text="トリガーワード:").grid(row=8, column=0, sticky="nw", pady=5)
        triggers_text = tk.Text(frame, height=4, width=30)
        triggers_text.grid(row=8, column=1, sticky="ew", padx=(10, 0), pady=5)
        triggers_text.insert("1.0", "\n".join(preset.trigger_words))

        # OBS設定
        ttk.Label(frame, text="OBSシーン:").grid(row=9, column=0, sticky="w", pady=5)
        scene_var = tk.StringVar(value=preset.obs_scene)
        ttk.Entry(frame, textvariable=scene_var).grid(row=9, column=1, sticky="ew", padx=(10, 0), pady=5)

        ttk.Label(frame, text="OBSソース:").grid(row=10, column=0, sticky="w", pady=5)
        source_var = tk.StringVar(value=preset.obs_source)
        ttk.Entry(frame, textvariable=source_var).grid(row=10, column=1, sticky="ew", padx=(10, 0), pady=5)

        # サイズ設定
        ttk.Label(frame, text="サイズ最小(px):").grid(row=11, column=0, sticky="w", pady=5)
        size_min_var = tk.IntVar(value=getattr(preset, "size_min", 32))
        size_min_spin = ttk.Spinbox(
            frame,
            from_=16,
            to=128,
            increment=4,
            textvariable=size_min_var,
            width=6,
        )
        size_min_spin.grid(row=11, column=1, sticky="w", padx=(10, 0), pady=5)

        ttk.Label(frame, text="サイズ最大(px):").grid(row=12, column=0, sticky="w", pady=5)
        size_max_var = tk.IntVar(value=getattr(preset, "size_max", 32))
        size_max_spin = ttk.Spinbox(
            frame,
            from_=16,
            to=128,
            increment=4,
            textvariable=size_max_var,
            width=6,
        )
        size_max_spin.grid(row=12, column=1, sticky="w", padx=(10, 0), pady=5)

        frame.columnconfigure(1, weight=1)
        
        # ボタン
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def save_preset():
            preset_id = id_var.get().strip()
            if not preset_id:
                messagebox.showerror("エラー", "IDを入力してください")
                return
            
            triggers = [line.strip() for line in triggers_text.get("1.0", tk.END).strip().split("\n") if line.strip()]

            # 絵文字テキストからリストを生成（スペース / 改行区切り）
            raw_emoji = emoji_text.get("1.0", tk.END).strip()
            if raw_emoji:
                emoji = [token for token in raw_emoji.split() if token]
            else:
                emoji = ["✨"]

            # アニメーション・エリア・個数
            animation = animation_var.get().strip() or "fall"
            area = area_var.get().strip() or "full"

            try:
                count = max(1, int(count_var.get()))
            except Exception:
                count = 50

            new_preset = EffectPreset(
                name=preset_id,
                description=desc_var.get().strip() or preset_id,
                duration=duration_var.get(),
                emoji=emoji,
                animation=animation,
                count=count,
                area=area,
                color=color_var.get(),
                trigger_words=triggers,
                obs_scene=scene_var.get().strip(),
                obs_source=source_var.get().strip(),
                size_min=int(size_min_var.get()),
                size_max=int(size_max_var.get())
            )
            
            self.effects_presets[preset_id] = new_preset
            self._update_presets_list()
            self._save_settings()
            dialog.destroy()
            self._update_status(f"プリセット保存: {new_preset.description}")
        
        ttk.Button(btn_frame, text="保存", command=save_preset).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="キャンセル", command=dialog.destroy).pack(side=tk.RIGHT)

    def _show_emoji_palette_dialog(self, target_text_widget):
        """絵文字パレットダイアログ"""
        import tkinter as tk
        from tkinter import ttk, messagebox
        import json
        import os

        # 絵文字カタログを読み込む
        catalog_path = os.path.join(os.path.dirname(__file__), "emoji_catalog.json")
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            categories = catalog.get("categories", {})
        except Exception as e:
            logger.warning(f"絵文字カタログの読み込みに失敗: {e}")
            # フォールバック: 最小セット
            categories = {
                "celebration": {"name": "お祝い", "emojis": ["🎉", "🎊", "✨", "🎁", "🎂"]},
                "hearts": {"name": "ハート", "emojis": ["❤️", "💖", "💗", "💕", "💓"]},
                "basic": {"name": "基本", "emojis": ["👍", "👏", "🙏", "🔥", "💬"]}
            }

        # ダイアログ作成
        dialog = tk.Toplevel(self)
        dialog.title("絵文字パレット")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左側：カテゴリリスト
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))

        ttk.Label(left_frame, text="カテゴリ:").pack(anchor="w")
        category_listbox = tk.Listbox(left_frame, width=20, height=15)
        category_listbox.pack(fill=tk.BOTH, expand=True)

        # カテゴリを追加
        category_ids = list(categories.keys())
        for cat_id in category_ids:
            cat_info = categories[cat_id]
            cat_name = cat_info.get("name", cat_id)
            category_listbox.insert(tk.END, cat_name)

        # 右側：絵文字グリッド
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(right_frame, text="絵文字を選択:").pack(anchor="w")

        # スクロール可能なキャンバス
        canvas = tk.Canvas(right_frame, bg="white")
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def on_category_select(event):
            """カテゴリ選択時に絵文字を表示"""
            selection = category_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            cat_id = category_ids[idx]
            cat_info = categories[cat_id]
            emojis = cat_info.get("emojis", [])

            # 既存のボタンをクリア
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            # 絵文字をグリッド表示
            col = 0
            row = 0
            max_cols = 8

            for emoji in emojis:
                def make_click_handler(e):
                    return lambda: on_emoji_click(e)

                btn = tk.Button(
                    scrollable_frame,
                    text=emoji,
                    font=("Arial", 20),
                    width=2,
                    height=1,
                    command=make_click_handler(emoji)
                )
                btn.grid(row=row, column=col, padx=2, pady=2)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

        def on_emoji_click(emoji):
            """絵文字クリック時にテキストウィジェットに追加"""
            current = target_text_widget.get("1.0", tk.END).strip()
            if current:
                target_text_widget.insert(tk.END, " " + emoji)
            else:
                target_text_widget.insert("1.0", emoji)

        category_listbox.bind("<<ListboxSelect>>", on_category_select)

        # 初期選択
        if category_ids:
            category_listbox.selection_set(0)
            category_listbox.event_generate("<<ListboxSelect>>")

        # 閉じるボタン
        ttk.Button(dialog, text="閉じる", command=dialog.destroy).pack(pady=10)

    def _on_obs_settings(self):
        """OBS設定ダイアログ"""
        messagebox.showinfo("OBS設定", "OBS WebSocket設定画面\n（実装予定）\n\nホスト: localhost:4455\nパスワード: 設定が必要")

    def _on_show_stats(self):
        """統計表示"""
        stats_window = tk.Toplevel(self)
        stats_window.title("統計情報")
        stats_window.geometry("500x400")
        stats_window.transient(self)
        
        frame = ttk.Frame(stats_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 統計表示
        stats_text = tk.Text(frame, wrap=tk.WORD, font=("Courier", 10))
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=stats_text.yview)
        stats_text.configure(yscrollcommand=scrollbar.set)
        
        stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 統計データ生成
        runtime = datetime.now() - self.stats['session_start']
        hours, remainder = divmod(runtime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        stats_content = f"""
📊 OBS演出効果 統計情報
{'='*50}

🕐 セッション情報:
  開始時刻: {self.stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}
  実行時間: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}

🎭 エフェクト実行統計:
  総実行回数: {self.stats['total_effects']}
  チャット連動: {self.stats['chat_triggered']}
  AI連動: {self.stats['ai_triggered']}
  手動実行: {self.stats['manual_triggered']}

📋 プリセット情報:
  登録プリセット数: {len(self.effects_presets)}
  有効プリセット数: {sum(1 for p in self.effects_presets.values() if p.enabled)}

🔥 人気プリセット TOP3:
"""
        
        # 使用回数でソート（簡易版）
        sorted_presets = sorted(
            self.effects_presets.items(),
            key=lambda x: (x[1].last_used or datetime.min),
            reverse=True
        )[:3]
        
        for i, (preset_id, preset) in enumerate(sorted_presets, 1):
            last_used = preset.last_used.strftime('%H:%M:%S') if preset.last_used else "未使用"
            stats_content += f"  {i}. {preset.description} (最終: {last_used})\n"
        
        if self.effect_history:
            stats_content += f"\n📜 実行履歴 (最新10件):\n"
            for entry in self.effect_history[-10:]:
                stats_content += f"  {entry['timestamp']} - {entry['effect']} ({entry['trigger_type']}: {entry['source']})\n"
        
        stats_content += f"\n⚙️ 設定状況:\n"
        stats_content += f"  自動エフェクト: {'有効' if self.auto_effects_enabled else '無効'}\n"
        stats_content += f"  OBS接続: {'接続中' if self.obs_connected else '未接続'}\n"
        
        stats_text.insert("1.0", stats_content)
        stats_text.config(state=tk.DISABLED)

    def _update_status(self, message: str):
        """ステータス更新"""
        self.status_var.set(message)
        # STATUS_UPDATE通知
        self.bus.publish(Events.STATUS_UPDATE, {
            "source": "obs_effects",
            "kind": "status", 
            "message": message,
            "level": "info"
        })

    def _update_stats_display(self):
        """統計表示更新"""
        stats_text = (f"総実行: {self.stats['total_effects']} | "
                     f"チャット: {self.stats['chat_triggered']} | "
                     f"AI: {self.stats['ai_triggered']} | "
                     f"手動: {self.stats['manual_triggered']}")
        self.stats_var.set(stats_text)

    def _load_settings(self):
        """設定読み込み"""
        try:
            # ConfigManagerから設定を読み込み
            self.auto_effects_enabled = self.config_manager.get('obs.auto_effects', True)
            self.auto_var.set(self.auto_effects_enabled)
            
            # OBS接続状態（仮）
            obs_enabled = self.config_manager.get('obs.enabled', False)
            if obs_enabled:
                self.connection_var.set("🟡 設定済み")
            
            # カスタムプリセット読み込み（v17.5.7+ 絵文字エフェクト対応）
            custom_presets = self.config_manager.get('obs.custom_presets', {})
            for preset_id, preset_data in custom_presets.items():
                if isinstance(preset_data, dict):
                    preset = EffectPreset(
                        name=preset_id,
                        description=preset_data.get('description', preset_id),
                        duration=preset_data.get('duration', 3.0),
                        emoji=preset_data.get('emoji', ["✨"]),  # 旧形式互換用デフォルト
                        animation=preset_data.get('animation', 'fall'),
                        count=preset_data.get('count', 50),
                        area=preset_data.get('area', 'full'),
                        color=preset_data.get('color', '#FF6B6B'),
                        trigger_words=preset_data.get('trigger_words', []),
                        obs_scene=preset_data.get('obs_scene', ''),
                        obs_source=preset_data.get('obs_source', '')
                    )
                    self.effects_presets[preset_id] = preset
            
            self._update_presets_list()
            self._update_status("設定読み込み完了")
            
        except Exception as e:
            self._update_status(f"設定読み込みエラー: {e}")

    def _save_settings(self):
        """設定保存"""
        try:
            # 自動エフェクト設定
            self.config_manager.set('obs.auto_effects', self.auto_effects_enabled)
            
            # カスタムプリセット保存（デフォルト以外）
            default_ids = {'confetti', 'fireworks', 'heart', 'sparkle', 'welcome', 'thanks'}
            custom_presets = {}
            
            for preset_id, preset in self.effects_presets.items():
                if preset_id not in default_ids:
                    custom_presets[preset_id] = {
                        'description': preset.description,
                        'color': preset.color,
                        'duration': preset.duration,
                        'emoji': preset.emoji,
                        'animation': preset.animation,
                        'count': preset.count,
                        'area': preset.area,
                        'trigger_words': preset.trigger_words,
                        'obs_scene': preset.obs_scene,
                        'obs_source': preset.obs_source,
                    }
            
            self.config_manager.set('obs.custom_presets', custom_presets)
            self.config_manager.save()
            
            self._update_status("設定保存完了")
            
        except Exception as e:
            self._update_status(f"設定保存エラー: {e}")

    def _inject_html_overlay_controls(self, parent):
        """HTML出力モード切替とプレビュー（シンプル版） - 共通プレビューパネル用"""
        import tkinter as tk
        from tkinter import ttk
        import webbrowser
        import os

        cfg = self.config_manager

        # 説明文（parentに直接追加）
        desc_label = ttk.Label(parent,
                               text="💡 プレビューを開くボタンを押すと、インターネットブラウザで確認ができます。",
                               foreground="gray", wraplength=600)
        desc_label.pack(anchor="w", pady=(0, 8), fill="x")

        # プレビューボタン
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=(4, 0))

        def _open_preview():
            """overlay.htmlをブラウザで開く（v17.5.7+: HTTP サーバー経由）"""
            try:
                # ★ 1) 先にコメント表示エリアの座標を保存（display_area.* → display.area.*）
                if hasattr(self, "_save_area_config"):
                    self._save_area_config()

                # ★ 2) 現在のConfig＋表示キューを data.json に書き出し
                if hasattr(self, '_export_overlay_snapshot'):
                    self._export_overlay_snapshot()

            except Exception as e:
                logger.error(f"[OBSEffectsTabUI] プレビュー前の設定保存エラー: {e}")

            # overlay.html の存在確認
            html_path = OVERLAY_OUT_DIR / "overlay.html"
            if not html_path.exists():
                self._update_status("⚠️ overlay.htmlが見つかりません（HTML出力を有効にしてチャットを送信してください）")
                return

            # HTTP サーバーを起動して開く
            try:
                self._start_preview_server()
                if self._preview_server_port:
                    url = f"http://127.0.0.1:{self._preview_server_port}/overlay.html"
                    webbrowser.open(url)
                    self._update_status(f"🌐 プレビューを開きました: {url}")
                    return
            except Exception as e:
                logger.warning(f"⚠️ HTTPサーバー起動失敗: {e}")

            # フォールバック: file:// で開く（CORS制限あり）
            webbrowser.open("file:///" + str(html_path).replace("\\", "/"))
            self._update_status("🌐 file:// でプレビューを開きました（コメント表示にはHTTPサーバーが必要です）")

        ttk.Button(btn_frame, text="🌐 プレビューを開く", command=_open_preview, width=18).pack(side="left", padx=(0, 4))

        def _refresh_preview():
            """プレビューを更新（F5キーと同じ役割）"""
            try:
                # ★ 1) 先にコメント表示エリアの座標を保存（display_area.* → display.area.*）
                if hasattr(self, "_save_area_config"):
                    self._save_area_config()

                # ★ 2) 現在のConfig＋表示キューを data.json に書き出し
                if hasattr(self, '_export_overlay_snapshot'):
                    self._export_overlay_snapshot()
                    self._update_status("🔄 プレビューを更新しました")

                # 3) エリアプレビュー（キャンバス）の再描画
                if hasattr(self, '_update_area_preview'):
                    self._update_area_preview()

                # 4) コメントサンプル側のプレビューも更新
                if hasattr(self, '_update_comment_role_preview') and hasattr(self, 'current_preview_role'):
                    current_role = self.current_preview_role.get()
                    self._update_comment_role_preview(current_role)

            except Exception as e:
                logger.error(f"[OBSEffectsTabUI] プレビュー更新エラー: {e}")
                self._update_status(f"⚠️ プレビューエラー: {str(e)}")

        ttk.Button(btn_frame, text="🔄 プレビュー更新", command=_refresh_preview, width=18).pack(side="left")

        # テストボタン（2段目）
        test_btn_frame = ttk.Frame(parent)
        test_btn_frame.pack(fill="x", pady=(8, 0))

        def _test_streamer():
            """配信者コメントテスト（コメント表示のみ）"""
            if hasattr(self, 'effects') and self.effects:
                self.effects.push_message(
                    role="streamer",
                    name="配信者",
                    text="配信者のテストコメントです 🎤",
                    effect_type=None
                )
                # ファイル出力
                if hasattr(self, 'file_output') and self.file_output:
                    self.file_output.flush_to_files()
                self._update_status("👤 配信者コメントテストを実行しました")
            else:
                self._update_status("⚠️ EffectsHandlerが初期化されていません")

        def _test_ai_char():
            """AIキャラコメントテスト（コメント表示のみ）"""
            if hasattr(self, 'effects') and self.effects:
                self.effects.push_message(
                    role="ai",
                    name="AIキャラ",
                    text="AIキャラのテスト応答です！素晴らしいですね ✨",
                    effect_type=None
                )
                # ファイル出力
                if hasattr(self, 'file_output') and self.file_output:
                    self.file_output.flush_to_files()
                self._update_status("🤖 AIキャラコメントテストを実行しました")
            else:
                self._update_status("⚠️ EffectsHandlerが初期化されていません")

        def _test_viewer():
            """視聴者コメントテスト（コメント表示のみ）"""
            if hasattr(self, 'effects') and self.effects:
                self.effects.push_message(
                    role="viewer",
                    name="視聴者",
                    text="視聴者のテストメッセージです 🎉",
                    effect_type=None
                )
                # ファイル出力
                if hasattr(self, 'file_output') and self.file_output:
                    self.file_output.flush_to_files()
                self._update_status("👥 視聴者コメントテストを実行しました")
            else:
                self._update_status("⚠️ EffectsHandlerが初期化されていません")

        ttk.Button(test_btn_frame, text="👤 配信者", command=_test_streamer, width=12).pack(side="left", padx=(0, 4))
        ttk.Button(test_btn_frame, text="🤖 AIキャラ", command=_test_ai_char, width=12).pack(side="left", padx=(0, 4))
        ttk.Button(test_btn_frame, text="👥 視聴者", command=_test_viewer, width=12).pack(side="left")

        # 補足説明
        info_label = ttk.Label(parent,
                              text="※ レイアウトや見た目の設定は「🧩 表示設定」「🎨 コメントの装飾設定」タブで行えます",
                              foreground="gray", font=("", 8))
        info_label.pack(anchor="w", pady=(8, 0))

    def _start_preview_server(self):
        """overlay_out ディレクトリで簡易HTTPサーバーを起動（v17.5.7+）"""
        # すでに起動済みの場合はスキップ
        if self._preview_server_thread and self._preview_server_thread.is_alive():
            logger.info(f"✅ プレビューサーバーは既に起動中 (port={self._preview_server_port})")
            return

        def _run_server():
            """HTTPサーバーをバックグラウンドで実行"""
            try:
                # overlay_out ディレクトリをカレントディレクトリとして設定
                original_dir = os.getcwd()
                os.chdir(OVERLAY_OUT_DIR)

                # ポート8000を試行、使用中なら8001～8010を順に試す
                port = 8000
                for attempt_port in range(8000, 8011):
                    try:
                        # allow_reuse_address を設定してポート再利用を許可
                        socketserver.TCPServer.allow_reuse_address = True
                        httpd = socketserver.TCPServer(("", attempt_port), http.server.SimpleHTTPRequestHandler)
                        self._preview_server_port = attempt_port
                        self._preview_httpd = httpd
                        logger.info(f"🌐 HTTPサーバー起動: http://127.0.0.1:{attempt_port}")
                        httpd.serve_forever()
                        break
                    except OSError as e:
                        if attempt_port == 8010:
                            logger.error(f"❌ HTTPサーバー起動失敗: ポート8000-8010すべて使用中")
                            raise
                        continue
            except Exception as e:
                logger.error(f"❌ HTTPサーバーエラー: {e}")
            finally:
                os.chdir(original_dir)

        # デーモンスレッドとして起動（メインプログラム終了時に自動終了）
        self._preview_server_thread = threading.Thread(target=_run_server, daemon=True)
        self._preview_server_thread.start()

        # サーバーが起動するまで少し待機
        time.sleep(0.5)

    def cleanup(self):
        """クリーンアップ"""
        try:
            # v17.5.7+: HTTP サーバーを終了
            if self._preview_httpd:
                try:
                    self._preview_httpd.shutdown()
                    logger.info("🛑 HTTPサーバーを終了しました")
                except Exception as e:
                    logger.warning(f"⚠️ HTTPサーバー終了エラー: {e}")

            self._save_settings()
            self._update_status("OBS演出タブ終了")
        except Exception as e:
            logger.error(f"OBS演出タブクリーンアップエラー: {e}")
    
    def _export_overlay_snapshot(self):
        """現在のConfigとキューを data.json に書き出す"""
        # v17.5.7: 統合モジュール（file_backend.py）を優先使用
        if _USE_INTEGRATED_MODULES and hasattr(self, 'file_output') and self.file_output:
            # 統合モジュールの file_backend.py を使用（自動で正しい streams 構造を出力）
            self.file_output.flush_to_files()
            return

        # フォールバック版: 統合モジュールが無い場合のみ古い形式で出力
        cfg = getattr(self, "config_manager", None)
        if not cfg or not hasattr(self, "_overlay_backend"):
            return
        # v17.5.7以降、HTML固定（TXT出力は廃止）
        mode = "HTML"

        # Configを"HTMLが読むキー名"で収集（既にブリッジ済みなのでそのまま取る）
        snapshot_cfg = {
            "display": {
                "text": {
                    "size_px": cfg.get("display.text.size_px", 26),
                    "alignment": cfg.get("style.text.alignment", "LEFT")  # ← キー名を修正
                },
                "name_visibility": cfg.get("display.name_visibility", "SHOW"),
                "flow": {"direction": cfg.get("display.flow.direction", "UP")},
                "area": {"mode": cfg.get("display.area.mode", "SEPARATE")}
            },
            "ui": {
                "style_panel": {
                    "max_width_px": cfg.get("ui.style_panel.max_width_px", 960)
                }
            },
            "style": {
                "font": {"family": cfg.get("style.font.family","Yu Gothic UI")},
                "name": {
                    "font": {
                        "size": cfg.get("style.name.font.size", 12),
                        "bold": cfg.get("style.name.font.bold", True),
                        "italic": cfg.get("style.name.font.italic", False)
                    },
                    "use_custom_color": cfg.get("style.name.use_custom_color", False),
                    "custom_color": cfg.get("style.name.custom_color", "#FFFFFF")
                },
                "body": {
                    "font": {
                        "size": cfg.get("style.body.font.size", 26),
                        "bold": cfg.get("style.body.font.bold", False),
                        "italic": cfg.get("style.body.font.italic", False)
                    },
                    "indent": cfg.get("style.body.indent", 0)
                },
                "text": {
                    "outline": {
                        "enabled": cfg.get("style.text.outline.enabled", False),
                        "color": cfg.get("style.text.outline.color", "#000000"),
                        "width": cfg.get("style.text.outline.width", 2)
                    },
                    "shadow": {
                        "enabled": cfg.get("style.text.shadow.enabled", False),
                        "color": cfg.get("style.text.shadow.color", "#000000"),
                        "offset_x": cfg.get("style.text.shadow.offset_x", 2),
                        "offset_y": cfg.get("style.text.shadow.offset_y", 2)
                    }
                },
                "layout": {
                    "line_height": cfg.get("style.layout.line_height", 1.5),
                    "padding": {
                        "top": cfg.get("style.layout.padding.top", 8),
                        "right": cfg.get("style.layout.padding.right", 12),
                        "bottom": cfg.get("style.layout.padding.bottom", 8),
                        "left": cfg.get("style.layout.padding.left", 12),
                    },
                },
                "background": {
                    "color": cfg.get("style.background.color", "#FFFFFF"),
                    "opacity": cfg.get("style.background.opacity", 100),
                    "border_radius": cfg.get("style.background.border_radius", 0),
                    "border": {
                        "enabled": cfg.get("style.background.border.enabled", False),
                        "color": cfg.get("style.background.border.color", "#000000"),
                        "width": cfg.get("style.background.border.width", 1)
                    }
                },
                "role": {
                    "streamer": {"color": cfg.get("style.role.streamer.color", "#4A90E2")},
                    "ai": {"color": cfg.get("style.role.ai.color", "#9B59B6")},
                    "viewer": {"color": cfg.get("style.role.viewer.color", "#7F8C8D")}
                }
            }
        }
        # 書き出し
        self._overlay_backend.write_snapshot(snapshot_cfg, self._overlay_items)


# ===== v17.3 エクスポート =====
# メインファイル (main_v_17_3.py) からの読み込みに対応

# 互換性確保（クラス名エイリアス）
ObsEffectsTabApp = OBSEffectsTabUI
OBSEffectsTab = OBSEffectsTabUI  # __init__.py用
OBSEffectsApp = OBSEffectsTabUI  # メインファイル用

# Factory関数群
def create_obs_tab(parent, message_bus=None, config_manager=None):
    """
    v17.3 メインfactory
    メインファイルの _create_obs_tab_safe() から呼ばれる
    """
    return OBSEffectsTabUI(parent, message_bus=message_bus, config_manager=config_manager)

def create_obs_effects_tab(parent, message_bus=None, config_manager=None):
    """サブfactory（互換性維持）"""
    return OBSEffectsTabUI(parent, message_bus=message_bus, config_manager=config_manager)

def create_tab(parent, message_bus=None, config_manager=None):
    """汎用factory（フォールバック用）"""
    return OBSEffectsTabUI(parent, message_bus=message_bus, config_manager=config_manager)

# ===== スタンドアロン実行 =====
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # パス追加
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))  # ← ルートを通す
    
    # テストアプリ
    root = tk.Tk()
    root.title("OBS演出効果タブ - スタンドアロンテスト")
    root.geometry("900x700")
    
    try:
        # 共有モジュールを試行
        from shared.message_bus import get_message_bus
        from shared.unified_config_manager import UnifiedConfigManager
        
        bus = get_message_bus()
        config = UnifiedConfigManager()
        
        logger.info("共有モジュール読み込み成功")
    except Exception as e:
        logger.warning(f"共有モジュール読み込み失敗: {e}")
        bus = None
        config = None

    # タブ作成（共通ボタンは_build_ui内で自動生成される）
    app = OBSEffectsTabUI(root, message_bus=bus, config_manager=config)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    logger.info("OBS演出効果タブ スタンドアロン起動")
    root.mainloop()
