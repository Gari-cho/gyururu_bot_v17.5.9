# ==========================================================
# 🧰 Settings (Backup/Restore) Tab - Minimal Skeleton (v17.3)
# ファイル: tab_settings/app.py
# 目的  : ユーザー環境のバックアップ作成・復元プレビュー枠組みのみ
# 依存  : shared.message_bus, shared.unified_config_manager（注入も可）
# 警告  : まだ“実データの上書き復元”は実装しない（プレビューまで）
# ==========================================================

import os
import sys
import io
import json
import zipfile
import time
import shutil
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----- パスブートストラップ（プロジェクトルートを sys.path に追加） -----
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ----- Bus / Config のフォールバック（統合起動で注入される想定） -----
BUS_AVAILABLE = False
CONFIG_AVAILABLE = False

try:
    from shared.message_bus import get_message_bus
    BUS_AVAILABLE = True
except Exception:
    def get_message_bus():
        class _DummyBus:
            def publish(self, *a, **k): pass
            def subscribe(self, *a, **k): pass
        return _DummyBus()

try:
    from shared.unified_config_manager import UnifiedConfigManager
    CONFIG_AVAILABLE = True
except Exception:
    class UnifiedConfigManager:
        def __init__(self, *a, **k): pass
        def get(self, *a, **k): return None
        def set(self, *a, **k): pass
        def save(self): pass


# ----- バックアップ対象のデフォルト定義（後で公開直前に微調整） -----
DEFAULT_INCLUDE_PATHS = [
    # JSON/設定
    os.path.join(_PROJECT_ROOT, "configs"),
    os.path.join(_PROJECT_ROOT, "tab_ai_unified", "presets"),
    os.path.join(_PROJECT_ROOT, "tab_obs_effects", "presets"),
    # オーバーレイ出力
    os.path.join(_PROJECT_ROOT, "tab_obs_effects", "overlay_out"),
]

# 除外するパターン（安全第一）
DEFAULT_EXCLUDES = [
    ".git", "__pycache__", ".DS_Store",
    # APIキーなどの秘密は除外（.env は“伏字コピー”のみ作る）
    ".env",
    # 大容量／ビルド成果物など
    "dist", "build", "*.exe", "*.mp4", "*.zip",
]

# バックアップ保存先の既定フォルダ
DEFAULT_BACKUP_DIR = os.path.join(_PROJECT_ROOT, "backups")

# ZIP内に格納するマニフェスト名
MANIFEST_NAME = "manifest.json"


# ===== クラス: SettingsBackupTab（TTK Frame） =====
class SettingsBackupTab(ttk.Frame):
        def __init__(self, parent, message_bus=None, config_manager: Optional[UnifiedConfigManager]=None, **kwargs):
                super().__init__(parent, **kwargs)
                self.bus = message_bus or get_message_bus()
                self.config = config_manager or UnifiedConfigManager()

                self.include_paths: List[str] = list(DEFAULT_INCLUDE_PATHS)
                self.excludes: List[str] = list(DEFAULT_EXCLUDES)
                self.backup_dir: str = DEFAULT_BACKUP_DIR

                os.makedirs(self.backup_dir, exist_ok=True)
                self._setup_ui()

                logger.info("✅ 設定管理タブ: 雛形ロード（バックアップ/復元フレームのみ）")
                try:
                        # タブ準備完了イベント（存在すれば）
                        self.bus.publish("TAB_READY", {"tab": "settings", "mode": "backup/restore-minimal"})
                except Exception:
                        pass

        # ----- UI構築（def _setup_ui）: おおよそ 60行 付近 -----
        def _setup_ui(self):
                # レイアウト：左右2ペイン（左=バックアップ、右=復元）
                self.columnconfigure(0, weight=1)
                self.columnconfigure(1, weight=1)
                self.rowconfigure(0, weight=1)

                # 左ペイン：バックアップ
                left = ttk.LabelFrame(self, text="📦 バックアップの作成（収集→ZIP化）")
                left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

                # 収集パス一覧
                self.include_list = tk.Listbox(left, height=8)
                for p in self.include_paths:
                        self.include_list.insert(tk.END, p)
                self.include_list.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
                left.rowconfigure(0, weight=1)
                left.columnconfigure(0, weight=1)

                # 追加/削除ボタン
                ttk.Button(left, text="＋ 追加", command=self._on_add_include).grid(row=1, column=0, sticky="w", padx=6, pady=2)
                ttk.Button(left, text="－ 削除", command=self._on_remove_include).grid(row=1, column=1, sticky="w", padx=6, pady=2)

                # 保存先
                ttk.Label(left, text="保存先フォルダ:").grid(row=2, column=0, sticky="w", padx=6, pady=2)
                self.backup_dir_var = tk.StringVar(value=self.backup_dir)
                ttk.Entry(left, textvariable=self.backup_dir_var, width=48).grid(row=2, column=1, sticky="we", padx=6, pady=2)
                ttk.Button(left, text="参照", command=self._on_browse_backup_dir).grid(row=2, column=2, sticky="we", padx=6, pady=2)

                # 実行
                ttk.Button(left, text="📦 バックアップ作成", command=self._on_backup_click).grid(row=3, column=0, columnspan=3, sticky="we", padx=6, pady=8)

                # 右ペイン：復元
                right = ttk.LabelFrame(self, text="♻️ 復元（プレビュー／選択復元）")
                right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
                right.columnconfigure(0, weight=1)
                right.rowconfigure(2, weight=1)

                # ZIP選択
                ttk.Label(right, text="バックアップZIP:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
                self.restore_zip_path = tk.StringVar(value="")
                row0 = ttk.Frame(right)
                row0.grid(row=1, column=0, sticky="we")
                row0.columnconfigure(0, weight=1)
                ttk.Entry(row0, textvariable=self.restore_zip_path).grid(row=0, column=0, sticky="we", padx=6, pady=2)
                ttk.Button(row0, text="参照", command=self._on_restore_browse).grid(row=0, column=1, sticky="we", padx=6, pady=2)

                # プレビューと実行
                self.preview_box = tk.Text(right, height=16, state="disabled")
                self.preview_box.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)

                row3 = ttk.Frame(right)
                row3.grid(row=3, column=0, sticky="e", padx=6, pady=4)
                ttk.Button(row3, text="🔍 プレビュー", command=self._on_preview_restore).grid(row=0, column=0, padx=4)
                ttk.Button(row3, text="⚠️ 復元(選択) 実行", command=self._on_restore_selected).grid(row=0, column=1, padx=4)

        # ----- 収集パスの追加/削除 -----
        def _on_add_include(self):
                path = filedialog.askdirectory(title="追加するフォルダを選択", initialdir=_PROJECT_ROOT)
                if path and path not in self.include_paths:
                    self.include_paths.append(path)
                    self.include_list.insert(tk.END, path)

        def _on_remove_include(self):
                sel = list(self.include_list.curselection())
                sel.reverse()
                for idx in sel:
                    p = self.include_list.get(idx)
                    try:
                        self.include_paths.remove(p)
                    except ValueError:
                        pass
                    self.include_list.delete(idx)

        def _on_browse_backup_dir(self):
                d = filedialog.askdirectory(title="バックアップ保存先", initialdir=self.backup_dir)
                if d:
                    self.backup_dir = d
                    self.backup_dir_var.set(d)

        # ----- バックアップ作成フロー（クリック） -----
        def _on_backup_click(self):
                try:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"gyururu_backup_{ts}.zip"
                        dst_zip = os.path.join(self.backup_dir, safe_name)
                        os.makedirs(self.backup_dir, exist_ok=True)

                        file_list = self._collect_filelist(self.include_paths, self.excludes)
                        manifest = self._build_manifest(file_list)

                        self._zip_backup(dst_zip, file_list, manifest)
                        try:
                                self.bus.publish("BACKUP_DONE", {"path": dst_zip, "files": len(file_list)})
                        except Exception:
                                pass

                        messagebox.showinfo("バックアップ", f"✅ バックアップを作成しました\n{dst_zip}")
                        logger.info(f"📦 BACKUP_DONE: {dst_zip} ({len(file_list)} files)")
                except Exception as e:
                        logger.exception("バックアップ作成でエラー")
                        messagebox.showerror("バックアップ", f"❌ 失敗: {e}")

        # ----- 復元：ZIP選択 -----
        def _on_restore_browse(self):
                p = filedialog.askopenfilename(
                        title="バックアップZIPを選択",
                        initialdir=self.backup_dir,
                        filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
                )
                if p:
                        self.restore_zip_path.set(p)

        # ----- 復元：プレビュー -----
        def _on_preview_restore(self):
                z = self.restore_zip_path.get().strip()
                if not z or not os.path.exists(z):
                        messagebox.showwarning("復元", "バックアップZIPを選択してください。")
                        return
                try:
                        preview = self._scan_restore_zip(z)
                        self._write_preview(preview)
                        try:
                                self.bus.publish("RESTORE_PREVIEW_READY", {"zip": z, "summary": preview.get("summary", {})})
                        except Exception:
                                pass
                        logger.info("🔍 復元プレビュー生成完了")
                except Exception as e:
                        logger.exception("復元プレビューでエラー")
                        messagebox.showerror("復元", f"❌ プレビュー失敗: {e}")

        # ----- 復元：実行（選択復元の実体は後日） -----
        def _on_restore_selected(self):
                messagebox.showinfo(
                        "復元（選択）",
                        "この雛形では“復元の実適用”は無効です。\nプレビュー→差分選択→適用 を公開直前に実装します。"
                )

        # ================== 収集・ZIP作成ユーティリティ ==================
        def _collect_filelist(self, include_paths: List[str], excludes: List[str]) -> List[str]:
                files: List[str] = []
                ex_patterns = [e.lower() for e in excludes]

                def _is_excluded(path: str) -> bool:
                        lp = path.lower()
                        # ワイルドカードっぽい末尾（*.zip 等）を簡易対応
                        for pat in ex_patterns:
                                if "*" in pat:
                                        if pat.startswith("*.") and lp.endswith(pat[1:]):
                                                return True
                                elif pat in lp.replace("\\", "/").split("/"):
                                        return True
                        return False

                for target in include_paths:
                        if os.path.isfile(target):
                                if not _is_excluded(target):
                                        files.append(target)
                                continue
                        for root, dirs, filenames in os.walk(target):
                                # 除外ディレクトリを落とす
                                dirs[:] = [d for d in dirs if not _is_excluded(os.path.join(root, d))]
                                for f in filenames:
                                        p = os.path.join(root, f)
                                        if not _is_excluded(p):
                                                files.append(p)

                # .env は原本を入れない（伏字コピーを manifest に格納）
                env_path = os.path.join(_PROJECT_ROOT, ".env")
                if env_path in files:
                        try:
                                files.remove(env_path)
                        except ValueError:
                                pass
                return files

        def _build_manifest(self, file_list: List[str]) -> Dict[str, Any]:
                masked_env: Dict[str, str] = {}
                env_path = os.path.join(_PROJECT_ROOT, ".env")
                if os.path.exists(env_path):
                        try:
                                with open(env_path, "r", encoding="utf-8") as rf:
                                        for line in rf:
                                                if "=" in line:
                                                        k, v = line.strip().split("=", 1)
                                                        if not k:
                                                                continue
                                                        masked_env[k] = "****" if v else ""
                        except Exception:
                                masked_env = {"error": "read_failed"}

                return {
                        "schema": "gyururu-backup-manifest@1",
                        "timestamp": int(time.time()),
                        "project_root": _PROJECT_ROOT,
                        "counts": {
                                "files": len(file_list),
                        },
                        "env_masked": masked_env,
                        "note": "復元時はマスク済みの .env は含まれません。必要に応じて手動復元してください。",
                }

        def _zip_backup(self, zip_path: str, file_list: List[str], manifest: Dict[str, Any]):
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        # マニフェスト
                        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

                        # 実ファイル
                        for abs_path in file_list:
                                # ZIP内の相対パス（プロジェクトルート相対）
                                try:
                                        arcname = os.path.relpath(abs_path, _PROJECT_ROOT)
                                except ValueError:
                                        # 万一ルート外ならファイル名のみ
                                        arcname = os.path.basename(abs_path)
                                zf.write(abs_path, arcname)

        # ================== 復元プレビュー（まだ適用はしない） ==================
        def _scan_restore_zip(self, zip_path: str) -> Dict[str, Any]:
                with zipfile.ZipFile(zip_path, "r") as zf:
                        names = zf.namelist()
                        summary = {
                                "total": len(names),
                                "manifest_found": MANIFEST_NAME in names,
                                "unsafe_writes": 0,
                        }
                        # 既存ファイルと衝突しそうな件数をざっくり数える
                        unsafe = []
                        for name in names:
                                if name.endswith("/"):  # ディレクトリ
                                        continue
                                if name == MANIFEST_NAME:
                                        continue
                                dst = os.path.join(_PROJECT_ROOT, name)
                                if os.path.exists(dst):
                                        summary["unsafe_writes"] += 1
                                        unsafe.append(name)

                        return {
                                "summary": summary,
                                "unsafe_list": unsafe[:100],  # 多すぎると重いので概数
                        }

        def _write_preview(self, preview: Dict[str, Any]):
                self.preview_box.configure(state="normal")
                self.preview_box.delete("1.0", tk.END)
                self.preview_box.insert(tk.END, "🔍 復元プレビュー\n")
                self.preview_box.insert(tk.END, json.dumps(preview, ensure_ascii=False, indent=2))
                self.preview_box.configure(state="disabled")

        # 将来の実装用プレースホルダ
        def _restore_selected(self):
                # （公開直前に）差分選択→上書き／新規のみコピー等を実装予定
                pass

        # クリーンアップ
        def cleanup(self):
                try:
                        self.bus.publish("TAB_CLOSED", {"tab": "settings"})
                except Exception:
                        pass


# ===== Factory（メイン統合用） =====
def create_settings_tab(parent, message_bus=None, config_manager: Optional[UnifiedConfigManager]=None, **kwargs):
        """
        メイン側から呼び出される想定のファクトリ。
        例:
            from tab_settings.app import create_settings_tab
            tab = create_settings_tab(parent, message_bus=bus, config_manager=config)
        """
        return SettingsBackupTab(parent, message_bus=message_bus, config_manager=config_manager, **kwargs)

# 後方互換エイリアス
create_tab = create_settings_tab
SettingsTab = SettingsBackupTab

__all__ = [
        "SettingsBackupTab",
        "SettingsTab",
        "create_settings_tab",
        "create_tab",
]


# ===== スタンドアロン起動（動作確認用） =====
if __name__ == "__main__":
        root = tk.Tk()
        root.title("Settings (Backup/Restore) - Minimal v17.3")
        tab = SettingsBackupTab(root)
        root.protocol("WM_DELETE_WINDOW", lambda: (tab.cleanup(), root.destroy()))
        root.mainloop()
