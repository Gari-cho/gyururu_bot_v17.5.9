#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配信者設定タブ - v17 統合対応版（2カラムUI + 拡張機能）
- 左右2カラム構造
- 既存項目（基本情報、性格、配信スタイル、関係性）維持
- 新項目追加（プレイスタイル、活動モチベ、架空プロフィール、AI関係、詳細メモ）
- コンボボックス「+」ボタンで候補追加機能
- MessageBus publish/subscribe
- UnifiedConfigManager 優先、JSONへフォールバック
- cleanup() 実装（購読解除）
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
from pathlib import Path
from datetime import datetime
import logging
from typing import Any, Optional, Dict, List

# イベント定義
from shared.event_types import Events

# ロガー
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ====== Bus Topics ======
BUS_EVT_UPDATED = "STREAMER_PROFILE_UPDATED"
BUS_EVT_LOADED = "STREAMER_PROFILE_LOADED"
BUS_EVT_REQUEST = "STREAMER_PROFILE_REQUEST"
BUS_EVT_RESPONSE = "STREAMER_PROFILE_RESPONSE"

# ====== Config Keys / Files ======
CFG_KEY = "tabs.streamer_profile"
STREAMER_NAME_KEY = "streamer.display_name"  # v17.5.7: 簡易アクセス用キー
CFG_DIR = Path("configs")
CFG_PATH = CFG_DIR / "streamer_profile.json"


class StreamerProfileTab:
    """配信者設定タブ（v17 統合対応版 - 2カラムUI）"""

    def __init__(self, parent, message_bus=None, config_manager=None):
        self.parent = parent
        self.message_bus = message_bus
        self.config_manager = config_manager

        # ========== UI Variables ==========
        # 基本情報
        self.streamer_name_var = tk.StringVar(value="配信者さん")
        self.platform_var = tk.StringVar(value="YouTube")
        self.genre_var = tk.StringVar(value="雑談")

        # 性格・特徴
        self.personality_vars: Dict[str, tk.BooleanVar] = {}

        # 配信スタイル
        self.frequency_var = tk.StringVar(value="週3-4回")
        self.time_slot_var = tk.StringVar(value="夜")
        self.audience_var = tk.StringVar(value="20-30代")
        self.play_style_var = tk.StringVar(value="設定しない")
        self.motivation_var = tk.StringVar(value="設定しない")

        # 架空プロフィール（新規）
        self.species_var = tk.StringVar(value="設定しない")
        self.age_var = tk.StringVar(value="設定しない")  # 新規：年齢
        self.first_person_var = tk.StringVar(value="設定しない")
        self.second_person_var = tk.StringVar(value="設定しない")
        self.speaking_preset_var = tk.StringVar(value="設定しない")

        # AIキャラとの関係
        self.relationship_var = tk.StringVar(value="相棒")
        self.nickname_var = tk.StringVar(value="配信者さん")
        self.ai_relation_level_var = tk.StringVar(value="親友")

        # --- Phase 6: AI投入プロフィール選択（4択） ---
        self.profile_ai_mode_var = tk.StringVar(value="fiction")  # both/real/fiction/none

        # --- 特記事項チェックボックス ---
        self.left_notes_include_var = tk.BooleanVar(value=True)  # 左側特記事項をプロフィールに含める
        self.right_notes_include_var = tk.BooleanVar(value=True)  # 右側特記事項をプロフィールに含める

        # ========== コンボボックス候補リスト ==========
        self.play_style_choices = [
            "設定しない", "のんびり探索", "攻略重視", "ネタプレイ",
            "ストーリー重視", "縛りプレイ", "RTA・スピードラン"
        ]
        self.motivation_choices = [
            "設定しない", "交流が楽しい", "自分の成長のため",
            "ゲームが好きすぎる", "有名になりたい", "お小遣い稼ぎ"
        ]
        self.species_choices = [
            "設定しない", "人間", "猫耳", "犬耳", "エルフ",
            "ドラゴン", "妖精", "ロボット", "AI"
        ]
        self.age_choices = [
            "設定しない", "10代前半", "10代後半", "20代前半", "20代後半",
            "30代前半", "30代後半", "40代", "50代以上"
        ]
        self.first_person_choices = [
            "設定しない", "わたし", "ぼく", "おれ", "あたし",
            "うち", "自分", "〇〇（名前）"
        ]
        self.second_person_choices = [
            "設定しない", "あなた", "きみ", "おまえ", "〇〇さん",
            "〇〇くん", "〇〇ちゃん", "みんな"
        ]
        self.speaking_preset_choices = [
            "設定しない", "フレンドリー", "丁寧", "元気", "クール",
            "おっとり", "ツンデレ", "ギャル系", "お嬢様"
        ]
        self.relationship_choices = [
            "相棒", "友達", "先輩後輩", "家族", "ペット", "アシスタント"
        ]
        self.ai_relation_level_choices = [
            "知り合い", "友達", "親友", "家族", "運命の相手"
        ]

        # 解除用
        self._bus_tokens = []

        logger.info("🎬 配信者設定タブ 初期化(v17 - 2カラムUI)")

    # ========== MessageBus helper ==========
    def _bus_publish(self, topic: str, data: Optional[dict] = None) -> None:
        try:
            if self.message_bus is None:
                return
            if hasattr(self.message_bus, "publish"):
                self.message_bus.publish(topic, data)
            elif hasattr(self.message_bus, "send"):
                try:
                    self.message_bus.send(topic, data)
                except TypeError:
                    self.message_bus.send({"topic": topic, "data": data})
        except Exception as e:
            logger.warning(f"⚠️ Bus publish 失敗: {e}")

    def _bus_subscribe(self, topic: str, handler) -> None:
        if self.message_bus is None:
            return
        try:
            if hasattr(self.message_bus, "subscribe"):
                token = self.message_bus.subscribe(topic, handler)
                self._bus_tokens.append(token if token is not None else (topic, handler))
            elif hasattr(self.message_bus, "on"):
                self.message_bus.on(topic, handler)
                self._bus_tokens.append((topic, handler))
        except Exception as e:
            logger.warning(f"⚠️ Bus subscribe 失敗: {e}")

    def _bus_unsubscribe_all(self) -> None:
        if not self._bus_tokens or self.message_bus is None:
            return
        try:
            if hasattr(self.message_bus, "unsubscribe"):
                for token in self._bus_tokens:
                    try:
                        self.message_bus.unsubscribe(token)
                    except Exception:
                        if isinstance(token, tuple) and len(token) == 2:
                            t, cb = token
                            try:
                                self.message_bus.unsubscribe(t, cb)
                            except Exception:
                                pass
            elif hasattr(self.message_bus, "off"):
                for token in self._bus_tokens:
                    if isinstance(token, tuple) and len(token) == 2:
                        t, cb = token
                        try:
                            self.message_bus.off(t, cb)
                        except Exception:
                            pass
        finally:
            self._bus_tokens.clear()

    # ========== UI build ==========
    def create_ui(self):
        root = ttk.Frame(self.parent, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        # ボタンバー（先に配置して下部に固定）
        self._build_buttons(root)

        # スクロール可能な領域（2カラムコンテンツ）
        canvas = tk.Canvas(root, highlightthickness=0)
        scroll = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 2カラムレイアウト
        left_column = ttk.Frame(content_frame)
        right_column = ttk.Frame(content_frame)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        # 左カラム構築
        self._build_left_column(left_column)

        # 右カラム構築
        self._build_right_column(right_column)

        # Bus購読（外部要求に応答）
        self._bus_subscribe(BUS_EVT_REQUEST, self._on_profile_request)

        logger.info("✅ 配信者設定UI 構築完了（2カラムUI）")
        return root

    # ========== 左カラム ==========
    def _build_left_column(self, parent: ttk.Frame) -> None:
        """左カラム：AIに渡すプロフィール、性格・特徴、配信スタイル、特記事項"""
        self._sec_ai_mode_select(parent)
        self._sec_personality(parent)
        self._sec_streaming_style(parent)
        self._sec_left_notes(parent)

    def _sec_basic(self, parent: ttk.Frame) -> None:
        """基本情報セクション"""
        frame = ttk.LabelFrame(parent, text="🎭 基本情報", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # 配信者名
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="配信者名:", width=14).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.streamer_name_var, width=28).pack(
            side=tk.LEFT, padx=6
        )

        # プラットフォーム
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="プラットフォーム:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row2,
            textvariable=self.platform_var,
            width=26,
            values=["YouTube", "Twitch", "ニコニコ生放送", "その他"],
        ).pack(side=tk.LEFT, padx=6)

        # ジャンル
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="ジャンル:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row3,
            textvariable=self.genre_var,
            width=26,
            values=["雑談", "ゲーム", "歌", "料理", "お絵描き", "勉強", "作業", "その他"],
        ).pack(side=tk.LEFT, padx=6)

    def _sec_personality(self, parent: ttk.Frame) -> None:
        """性格・特徴セクション"""
        frame = ttk.LabelFrame(parent, text="🌟 性格・特徴", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="性格（複数可）:").pack(anchor="w")

        traits = [
            "明るい", "元気", "おっとり", "クール", "ツンデレ", "天然",
            "おねえさん系", "妹系", "ボーイッシュ", "上品", "庶民的", "毒舌"
        ]

        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X, pady=(4, 0))

        for i, trait in enumerate(traits):
            var = tk.BooleanVar()
            self.personality_vars[trait] = var
            ttk.Checkbutton(grid, text=trait, variable=var).grid(
                row=i // 4, column=i % 4, sticky="w", padx=(0, 10), pady=2
            )

        ttk.Label(frame, text="特技・趣味:").pack(anchor="w", pady=(10, 0))
        self.hobbies_text = tk.Text(frame, height=3, width=40)
        self.hobbies_text.pack(fill=tk.X, pady=(4, 0))
        self.hobbies_text.insert("1.0", "ゲーム、歌、お絵描き")

    def _sec_streaming_style(self, parent: ttk.Frame) -> None:
        """配信スタイルセクション（既存項目 + 新規項目）"""
        frame = ttk.LabelFrame(parent, text="🎯 配信スタイル", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # 頻度
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="頻度:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row1,
            textvariable=self.frequency_var,
            width=26,
            values=["毎日", "週5-6回", "週3-4回", "週1-2回", "不定期"],
        ).pack(side=tk.LEFT, padx=6)

        # 時間帯
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="時間帯:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row2,
            textvariable=self.time_slot_var,
            width=26,
            values=["朝", "昼", "夕方", "夜", "深夜", "不定期"],
        ).pack(side=tk.LEFT, padx=6)

        # 視聴者層
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="視聴者層:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row3,
            textvariable=self.audience_var,
            width=26,
            values=["10代", "20-30代", "30-40代", "40代以上", "幅広い年齢層"],
        ).pack(side=tk.LEFT, padx=6)

        # 区切り線
        ttk.Separator(frame, orient="horizontal").pack(fill=tk.X, pady=8)

        # プレイスタイル（新規・+ボタン付き）
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="プレイスタイル:", width=14).pack(side=tk.LEFT)
        self.play_style_combo = ttk.Combobox(
            row4,
            textvariable=self.play_style_var,
            width=23,
            values=self.play_style_choices,
        )
        self.play_style_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row4,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.play_style_var,
                "play_style_choices",
                self.play_style_combo,
                "プレイスタイル"
            ),
        ).pack(side=tk.LEFT)

        # 活動モチベ（新規・+ボタン付き）
        row5 = ttk.Frame(frame)
        row5.pack(fill=tk.X, pady=2)
        ttk.Label(row5, text="活動モチベ:", width=14).pack(side=tk.LEFT)
        self.motivation_combo = ttk.Combobox(
            row5,
            textvariable=self.motivation_var,
            width=23,
            values=self.motivation_choices,
        )
        self.motivation_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row5,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.motivation_var,
                "motivation_choices",
                self.motivation_combo,
                "活動モチベ"
            ),
        ).pack(side=tk.LEFT)

    def _sec_left_notes(self, parent: ttk.Frame) -> None:
        """左側：特記事項セクション（プロフィールに含めるチェックボックス付き）"""
        frame = ttk.LabelFrame(parent, text="📝 特記事項", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # チェックボックス
        ttk.Checkbutton(
            frame,
            text="プロフィールに含める",
            variable=self.left_notes_include_var
        ).pack(anchor="w", padx=6, pady=(4, 4))

        # テキストエリア
        self.left_notes_text = tk.Text(frame, height=8, wrap="word")
        self.left_notes_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def _sec_real_profile_text(self, parent: ttk.Frame) -> None:
        """Phase 7: 現実プロフィール（AI用）入力欄"""
        frame = ttk.LabelFrame(parent, text="📄 現実プロフィール（AI用）", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(
            frame,
            text="※基本情報や配信スタイルなど、現実の情報をAIに渡したい場合はこちら"
        ).pack(anchor="w", padx=6, pady=(4, 2))

        self.real_profile_text = tk.Text(frame, height=8, wrap="word")
        self.real_profile_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def _sec_fiction_profile_text(self, parent: ttk.Frame) -> None:
        """Phase 7: 架空プロフィール（AI用）入力欄"""
        frame = ttk.LabelFrame(parent, text="🎭 架空プロフィール（AI用）", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(
            frame,
            text="※配信用の設定（キャラ設定）を書きたい場合はこちら"
        ).pack(anchor="w", padx=6, pady=(4, 2))

        self.fiction_profile_text = tk.Text(frame, height=8, wrap="word")
        self.fiction_profile_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # ========== 右カラム ==========
    def _build_right_column(self, parent: ttk.Frame) -> None:
        """右カラム：AIとの関係、架空プロフィール、特記事項"""
        self._sec_ai_relation(parent)
        self._sec_virtual_profile(parent)
        self._sec_right_notes(parent)

    def _sec_ai_mode_select(self, parent: ttk.Frame) -> None:
        """Phase 6: AIに渡すプロフィール選択（4択・横並び）"""
        frame = ttk.LabelFrame(parent, text="🤖 AIに渡すプロフィール", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # ラジオボタンを横並びに配置
        radio_row = ttk.Frame(frame)
        radio_row.pack(fill=tk.X)

        ttk.Radiobutton(
            radio_row,
            text="両方を渡す",
            value="both",
            variable=self.profile_ai_mode_var,
            command=self._on_profile_ai_mode_changed
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            radio_row,
            text="現実のみ",
            value="real",
            variable=self.profile_ai_mode_var,
            command=self._on_profile_ai_mode_changed
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            radio_row,
            text="架空のみ",
            value="fiction",
            variable=self.profile_ai_mode_var,
            command=self._on_profile_ai_mode_changed
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            radio_row,
            text="無し（AIに渡さない）",
            value="none",
            variable=self.profile_ai_mode_var,
            command=self._on_profile_ai_mode_changed
        ).pack(side=tk.LEFT)

    def _sec_virtual_profile(self, parent: ttk.Frame) -> None:
        """架空プロフィール（キャラ設定）セクション"""
        frame = ttk.LabelFrame(parent, text="🎭 架空プロフィール（キャラ設定）", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 種族
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="種族:", width=14).pack(side=tk.LEFT)
        self.species_combo = ttk.Combobox(
            row1,
            textvariable=self.species_var,
            width=23,
            values=self.species_choices,
        )
        self.species_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row1,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.species_var,
                "species_choices",
                self.species_combo,
                "種族"
            ),
        ).pack(side=tk.LEFT)

        # 年齢
        row1_5 = ttk.Frame(frame)
        row1_5.pack(fill=tk.X, pady=2)
        ttk.Label(row1_5, text="年齢:", width=14).pack(side=tk.LEFT)
        self.age_combo = ttk.Combobox(
            row1_5,
            textvariable=self.age_var,
            width=23,
            values=self.age_choices,
        )
        self.age_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row1_5,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.age_var,
                "age_choices",
                self.age_combo,
                "年齢"
            ),
        ).pack(side=tk.LEFT)

        # 注記ラベル（年齢の下に追加）
        ttk.Label(
            frame,
            text="※AIが話題を合わせるだけに使用し、会話には年齢を出さない",
            font=("", 9),
            foreground="gray"
        ).pack(anchor="w", padx=6, pady=(2, 6))

        # 一人称
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="一人称:", width=14).pack(side=tk.LEFT)
        self.first_person_combo = ttk.Combobox(
            row2,
            textvariable=self.first_person_var,
            width=23,
            values=self.first_person_choices,
        )
        self.first_person_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row2,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.first_person_var,
                "first_person_choices",
                self.first_person_combo,
                "一人称"
            ),
        ).pack(side=tk.LEFT)

        # 二人称
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="二人称:", width=14).pack(side=tk.LEFT)
        self.second_person_combo = ttk.Combobox(
            row3,
            textvariable=self.second_person_var,
            width=23,
            values=self.second_person_choices,
        )
        self.second_person_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row3,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.second_person_var,
                "second_person_choices",
                self.second_person_combo,
                "二人称"
            ),
        ).pack(side=tk.LEFT)

        # 口調プリセット
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="口調プリセット:", width=14).pack(side=tk.LEFT)
        self.speaking_preset_combo = ttk.Combobox(
            row4,
            textvariable=self.speaking_preset_var,
            width=23,
            values=self.speaking_preset_choices,
        )
        self.speaking_preset_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row4,
            text="＋",
            width=3,
            command=lambda: self._add_choice_to_combo(
                self.speaking_preset_var,
                "speaking_preset_choices",
                self.speaking_preset_combo,
                "口調プリセット"
            ),
        ).pack(side=tk.LEFT)

        # 区切り線
        ttk.Separator(frame, orient="horizontal").pack(fill=tk.X, pady=8)

        # 好きなもの
        ttk.Label(frame, text="好きなもの:").pack(anchor="w", pady=(4, 0))
        self.favorite_things_text = tk.Text(frame, height=2, width=40)
        self.favorite_things_text.pack(fill=tk.X, pady=(2, 4))

        # 嫌いなもの
        ttk.Label(frame, text="嫌いなもの:").pack(anchor="w", pady=(4, 0))
        self.hates_text = tk.Text(frame, height=2, width=40)
        self.hates_text.pack(fill=tk.X, pady=(2, 4))

        # 得意なこと
        ttk.Label(frame, text="得意なこと:").pack(anchor="w", pady=(4, 0))
        self.skills_text = tk.Text(frame, height=2, width=40)
        self.skills_text.pack(fill=tk.X, pady=(2, 4))

    def _sec_ai_relation(self, parent: ttk.Frame) -> None:
        """AIキャラとの関係セクション"""
        frame = ttk.LabelFrame(parent, text="🤝 AIキャラとの関係", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        # 関係性
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="関係性:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row1,
            textvariable=self.relationship_var,
            width=26,
            values=self.relationship_choices,
        ).pack(side=tk.LEFT, padx=6)

        # 呼び方
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="呼び方:", width=14).pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.nickname_var, width=28).pack(
            side=tk.LEFT, padx=6
        )

        # 関係レベル（新規）
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="関係レベル:", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            row3,
            textvariable=self.ai_relation_level_var,
            width=26,
            values=self.ai_relation_level_choices,
        ).pack(side=tk.LEFT, padx=6)

    def _sec_detail_memo(self, parent: ttk.Frame) -> None:
        """詳細プロフィールメモ（追記用）セクション"""
        frame = ttk.LabelFrame(parent, text="📝 詳細プロフィールメモ（追記用）", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 注釈ラベル
        ttk.Label(
            frame,
            text="※追加したい設定内容があれば書き込んでください。",
            font=("", 9)
        ).pack(anchor="w", pady=(0, 4))

        # テキストエリア
        self.detail_memo_text = tk.Text(frame, height=8, wrap=tk.WORD)
        self.detail_memo_text.pack(fill=tk.BOTH, expand=True)

    def _sec_right_notes(self, parent: ttk.Frame) -> None:
        """右側：特記事項セクション（プロフィールに含めるチェックボックス付き）"""
        frame = ttk.LabelFrame(parent, text="📝 特記事項", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # チェックボックス
        ttk.Checkbutton(
            frame,
            text="プロフィールに含める",
            variable=self.right_notes_include_var
        ).pack(anchor="w", padx=6, pady=(4, 4))

        # テキストエリア
        self.right_notes_text = tk.Text(frame, height=8, wrap="word")
        self.right_notes_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # ========== ボタン群 ==========
    def _build_buttons(self, parent: ttk.Frame) -> None:
        """保存・読込・リセット・プレビューボタン（下部バー）"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))

        ttk.Button(button_frame, text="💾 保存", command=self.save_profile).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(button_frame, text="📖 読込", command=self.load_profile).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(button_frame, text="🔄 リセット", command=self.reset_profile).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(button_frame, text="👁️ プレビュー", command=self.preview_profile).pack(
            side=tk.LEFT
        )

    # ========== コンボボックス「+」ボタン機能 ==========
    def _add_choice_to_combo(
        self,
        var: tk.StringVar,
        choices_attr: str,
        combo_widget: ttk.Combobox,
        label: str = "項目"
    ) -> None:
        """コンボボックスに新しい選択肢を追加"""
        # 現在の入力値を取得
        current_value = var.get().strip()

        # 「設定しない」または空文字の場合は新規入力を促す
        if not current_value or current_value == "設定しない":
            new_value = simpledialog.askstring(
                f"{label}の追加",
                f"新しい{label}を入力してください:",
                parent=self.parent
            )
            if not new_value or not new_value.strip():
                return
            current_value = new_value.strip()

        # 候補リストを取得
        choices: List[str] = getattr(self, choices_attr, [])

        # 重複チェック
        if current_value in choices:
            messagebox.showinfo(
                "既に存在",
                f"「{current_value}」は既に候補に存在します。",
                parent=self.parent
            )
            return

        # 候補リストに追加
        choices.append(current_value)
        setattr(self, choices_attr, choices)

        # コンボボックスを更新
        combo_widget.config(values=choices)
        var.set(current_value)

        logger.info(f"✅ {label}候補に追加: {current_value}")

    # ========== データ収集・適用 ==========
    def _collect_profile_data(self) -> Dict[str, Any]:
        """UIから現在のプロフィールデータを収集"""
        traits = [t for t, v in self.personality_vars.items() if v.get()]

        return {
            "basic_info": {
                "name": self.streamer_name_var.get(),
                "platform": self.platform_var.get(),
                "genre": self.genre_var.get(),
            },
            "personality": {
                "traits": traits,
                "hobbies": self.hobbies_text.get("1.0", tk.END).strip(),
            },
            "streaming_style": {
                "frequency": self.frequency_var.get(),
                "time_slot": self.time_slot_var.get(),
                "audience": self.audience_var.get(),
                "play_style": self.play_style_var.get(),
                "motivation": self.motivation_var.get(),
            },
            "virtual_profile": {
                "species": self.species_var.get(),
                "age": self.age_var.get(),
                "first_person": self.first_person_var.get(),
                "second_person": self.second_person_var.get(),
                "speaking_preset": self.speaking_preset_var.get(),
                "favorite_things": self.favorite_things_text.get("1.0", tk.END).strip(),
                "hates": self.hates_text.get("1.0", tk.END).strip(),
                "skills": self.skills_text.get("1.0", tk.END).strip(),
            },
            "relationship": {
                "type": self.relationship_var.get(),
                "nickname": self.nickname_var.get(),
                "ai_relation_level": self.ai_relation_level_var.get(),
            },
            "detail_profile_memo": self.detail_memo_text.get("1.0", tk.END).strip(),
            "left_notes": {
                "text": self.left_notes_text.get("1.0", tk.END).strip(),
                "include": self.left_notes_include_var.get(),
            },
            "right_notes": {
                "text": self.right_notes_text.get("1.0", tk.END).strip(),
                "include": self.right_notes_include_var.get(),
            },
            "choices": {
                "play_style": self.play_style_choices,
                "motivation": self.motivation_choices,
                "species": self.species_choices,
                "age": self.age_choices,
                "first_person": self.first_person_choices,
                "second_person": self.second_person_choices,
                "speaking_preset": self.speaking_preset_choices,
            },
            "timestamp": datetime.now().isoformat(),
            "version": "v17-2column-integrated",
        }

    def _apply_profile_data(self, profile: Dict[str, Any]) -> None:
        """保存されたプロフィールデータをUIに反映"""
        try:
            # 基本情報
            basic = profile.get("basic_info", {})
            self.streamer_name_var.set(basic.get("name", "配信者さん"))
            self.platform_var.set(basic.get("platform", "YouTube"))
            self.genre_var.set(basic.get("genre", "雑談"))

            # 性格・特徴
            personality = profile.get("personality", {})
            traits = personality.get("traits", [])
            for t, v in self.personality_vars.items():
                v.set(t in traits)
            self.hobbies_text.delete("1.0", tk.END)
            self.hobbies_text.insert("1.0", personality.get("hobbies", "ゲーム、歌、お絵描き"))

            # 配信スタイル
            streaming = profile.get("streaming_style", {})
            self.frequency_var.set(streaming.get("frequency", "週3-4回"))
            self.time_slot_var.set(streaming.get("time_slot", "夜"))
            self.audience_var.set(streaming.get("audience", "20-30代"))
            self.play_style_var.set(streaming.get("play_style", "設定しない"))
            self.motivation_var.set(streaming.get("motivation", "設定しない"))

            # 架空プロフィール
            virtual = profile.get("virtual_profile", {})
            self.species_var.set(virtual.get("species", "設定しない"))
            self.age_var.set(virtual.get("age", "設定しない"))
            self.first_person_var.set(virtual.get("first_person", "設定しない"))
            self.second_person_var.set(virtual.get("second_person", "設定しない"))
            self.speaking_preset_var.set(virtual.get("speaking_preset", "設定しない"))

            self.favorite_things_text.delete("1.0", tk.END)
            self.favorite_things_text.insert("1.0", virtual.get("favorite_things", ""))

            self.hates_text.delete("1.0", tk.END)
            self.hates_text.insert("1.0", virtual.get("hates", ""))

            self.skills_text.delete("1.0", tk.END)
            self.skills_text.insert("1.0", virtual.get("skills", ""))

            # AIとの関係
            relationship = profile.get("relationship", {})
            self.relationship_var.set(relationship.get("type", "相棒"))
            self.nickname_var.set(relationship.get("nickname", "配信者さん"))
            self.ai_relation_level_var.set(relationship.get("ai_relation_level", "親友"))

            # 詳細メモ
            detail_memo = profile.get("detail_profile_memo", "")
            self.detail_memo_text.delete("1.0", tk.END)
            self.detail_memo_text.insert("1.0", detail_memo)

            # 左側特記事項
            left_notes = profile.get("left_notes", {})
            self.left_notes_text.delete("1.0", tk.END)
            self.left_notes_text.insert("1.0", left_notes.get("text", ""))
            self.left_notes_include_var.set(left_notes.get("include", True))

            # 右側特記事項
            right_notes = profile.get("right_notes", {})
            self.right_notes_text.delete("1.0", tk.END)
            self.right_notes_text.insert("1.0", right_notes.get("text", ""))
            self.right_notes_include_var.set(right_notes.get("include", True))

            # コンボボックス候補リスト
            choices = profile.get("choices", {})
            if choices:
                for key, values in choices.items():
                    attr_name = f"{key}_choices"
                    if hasattr(self, attr_name) and values:
                        setattr(self, attr_name, values)
                        # コンボボックスウィジェットを更新
                        combo_name = f"{key}_combo"
                        if hasattr(self, combo_name):
                            combo_widget = getattr(self, combo_name)
                            combo_widget.config(values=values)

            # Phase 6: AI投入プロフィール選択（4択）復元
            # ConfigManagerから直接読み込み（profileに含まれていない可能性があるため）
            try:
                if self.config_manager and hasattr(self.config_manager, "get"):
                    mode = self.config_manager.get("streamer_profile.ai_mode", "fiction")
                else:
                    mode = "fiction"

                if mode not in ("both", "real", "fiction", "none"):
                    mode = "fiction"
                self.profile_ai_mode_var.set(mode)
                logger.info(f"✅ AI投入プロフィールモードを復元: {mode}")
            except Exception as e:
                logger.warning(f"⚠️ AI投入モード復元失敗: {e}")
                self.profile_ai_mode_var.set("fiction")

            # Phase 7: 現実・架空プロフィール（AI用）復元
            try:
                if self.config_manager and hasattr(self.config_manager, "get"):
                    real_text = self.config_manager.get("streamer_profile.real.text", "")
                else:
                    real_text = ""
                self.real_profile_text.delete("1.0", "end")
                self.real_profile_text.insert("1.0", real_text)
                logger.info(f"✅ 現実プロフィール復元 ({len(real_text)} chars)")
            except Exception as e:
                logger.warning(f"⚠️ 現実プロフィール復元失敗: {e}")

            try:
                if self.config_manager and hasattr(self.config_manager, "get"):
                    fiction_text = self.config_manager.get("streamer_profile.fiction.text", "")
                else:
                    fiction_text = ""
                self.fiction_profile_text.delete("1.0", "end")
                self.fiction_profile_text.insert("1.0", fiction_text)
                logger.info(f"✅ 架空プロフィール復元 ({len(fiction_text)} chars)")
            except Exception as e:
                logger.warning(f"⚠️ 架空プロフィール復元失敗: {e}")

            logger.info("✅ プロフィールデータをUIに反映しました")

        except Exception as e:
            logger.warning(f"⚠️ UI反映エラー: {e}")

    # ========== 保存・読込・リセット・プレビュー ==========
    def save_profile(self) -> None:
        """プロフィールを保存"""
        profile = self._collect_profile_data()
        saved = False

        # ConfigManager 優先
        try:
            if self.config_manager and hasattr(self.config_manager, "set"):
                self.config_manager.set(CFG_KEY, profile)

                # v17.5.7: 配信者名を簡易アクセス用キーにも保存
                streamer_name = profile.get("basic_info", {}).get("name", "配信者")
                self.config_manager.set(STREAMER_NAME_KEY, streamer_name)

                # Phase 7: 現実・架空プロフィール（AI用）を別キーで保存
                try:
                    real_text = self.real_profile_text.get("1.0", "end").strip()
                    self.config_manager.set("streamer_profile.real.text", real_text)
                    logger.info(f"💾 現実プロフィール保存 ({len(real_text)} chars)")
                except Exception as e:
                    logger.warning(f"⚠️ 現実プロフィール保存失敗: {e}")

                try:
                    fiction_text = self.fiction_profile_text.get("1.0", "end").strip()
                    self.config_manager.set("streamer_profile.fiction.text", fiction_text)
                    logger.info(f"💾 架空プロフィール保存 ({len(fiction_text)} chars)")
                except Exception as e:
                    logger.warning(f"⚠️ 架空プロフィール保存失敗: {e}")

                if hasattr(self.config_manager, "save"):
                    self.config_manager.save()
                saved = True
                logger.info(f"💾 ConfigManager に保存 (name={streamer_name})")
        except Exception as e:
            logger.info(f"ℹ️ ConfigManager 保存不可: {e}")

        # JSONフォールバック
        if not saved:
            try:
                CFG_DIR.mkdir(exist_ok=True)
                CFG_PATH.write_text(
                    json.dumps(profile, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                saved = True
                logger.info(f"💾 JSON保存: {CFG_PATH}")
            except Exception as e:
                logger.error(f"❌ JSON保存エラー: {e}")
                messagebox.showerror("保存エラー", f"設定の保存に失敗: {e}")
                return

        # MessageBus通知（既存イベント）
        self._bus_publish(BUS_EVT_UPDATED, profile)

        # v17統一イベント送信
        self._publish_profile_update(reason="manual_save")

        messagebox.showinfo("保存完了", "配信者設定を保存しました！")

    def load_profile(self) -> None:
        """プロフィールを読込"""
        loaded = None

        # ConfigManager 優先
        try:
            if self.config_manager and hasattr(self.config_manager, "get"):
                loaded = self.config_manager.get(CFG_KEY, None)
                if loaded:
                    logger.info("📖 ConfigManager から読込")
        except Exception as e:
            logger.info(f"ℹ️ ConfigManager 読込不可: {e}")

        # JSONフォールバック
        if loaded is None and CFG_PATH.exists():
            try:
                loaded = json.loads(CFG_PATH.read_text(encoding="utf-8"))
                logger.info(f"📖 JSONから読込: {CFG_PATH}")
            except Exception as e:
                logger.warning(f"⚠️ JSON読込エラー: {e}")

        # UIに反映
        if loaded:
            self._apply_profile_data(loaded)
        else:
            logger.info("📄 設定なし（デフォルト使用）")

        # MessageBus通知（既存イベント）
        self._bus_publish(BUS_EVT_LOADED, loaded or self._collect_profile_data())

        # v17統一イベント送信
        self._publish_profile_update(reason="initial_load")

    def reset_profile(self) -> None:
        """プロフィールをリセット"""
        if not messagebox.askyesno("確認", "配信者設定をリセットしますか？"):
            return

        # 基本情報リセット
        self.streamer_name_var.set("配信者さん")
        self.platform_var.set("YouTube")
        self.genre_var.set("雑談")

        # 性格・特徴リセット
        for v in self.personality_vars.values():
            v.set(False)
        self.hobbies_text.delete("1.0", tk.END)
        self.hobbies_text.insert("1.0", "ゲーム、歌、お絵描き")

        # 配信スタイルリセット
        self.frequency_var.set("週3-4回")
        self.time_slot_var.set("夜")
        self.audience_var.set("20-30代")
        self.play_style_var.set("設定しない")
        self.motivation_var.set("設定しない")

        # 架空プロフィールリセット
        self.species_var.set("設定しない")
        self.age_var.set("設定しない")
        self.first_person_var.set("設定しない")
        self.second_person_var.set("設定しない")
        self.speaking_preset_var.set("設定しない")
        self.favorite_things_text.delete("1.0", tk.END)
        self.hates_text.delete("1.0", tk.END)
        self.skills_text.delete("1.0", tk.END)

        # AIとの関係リセット
        self.relationship_var.set("相棒")
        self.nickname_var.set("配信者さん")
        self.ai_relation_level_var.set("親友")

        # 詳細メモリセット
        self.detail_memo_text.delete("1.0", tk.END)

        # 左側特記事項リセット
        self.left_notes_text.delete("1.0", tk.END)
        self.left_notes_include_var.set(True)

        # 右側特記事項リセット
        self.right_notes_text.delete("1.0", tk.END)
        self.right_notes_include_var.set(True)

        # Phase 7: 現実・架空プロフィール（AI用）リセット（存在する場合のみ）
        if hasattr(self, 'real_profile_text'):
            self.real_profile_text.delete("1.0", tk.END)
        if hasattr(self, 'fiction_profile_text'):
            self.fiction_profile_text.delete("1.0", tk.END)

        # リセット後に保存
        self.save_profile()

    def preview_profile(self) -> None:
        """プロフィールをプレビュー表示"""
        try:
            data = self._collect_profile_data()

            text = (
                "🎬 配信者プロフィール プレビュー\n"
                "=" * 60 + "\n\n"
                "【👤 基本情報】\n"
                f"  名前: {data['basic_info']['name']}\n"
                f"  プラットフォーム: {data['basic_info']['platform']}\n"
                f"  ジャンル: {data['basic_info']['genre']}\n\n"
                "【🌟 性格・特徴】\n"
                f"  性格: {', '.join(data['personality']['traits']) or '未設定'}\n"
                f"  趣味: {data['personality']['hobbies']}\n\n"
                "【🎯 配信スタイル】\n"
                f"  頻度: {data['streaming_style']['frequency']}\n"
                f"  時間帯: {data['streaming_style']['time_slot']}\n"
                f"  視聴者層: {data['streaming_style']['audience']}\n"
                f"  プレイスタイル: {data['streaming_style']['play_style']}\n"
                f"  活動モチベ: {data['streaming_style']['motivation']}\n\n"
                "【🎭 架空プロフィール】\n"
                f"  種族: {data['virtual_profile']['species']}\n"
                f"  年齢: {data['virtual_profile']['age']}\n"
                f"  一人称: {data['virtual_profile']['first_person']}\n"
                f"  二人称: {data['virtual_profile']['second_person']}\n"
                f"  口調: {data['virtual_profile']['speaking_preset']}\n"
                f"  好き: {data['virtual_profile']['favorite_things'] or '未設定'}\n"
                f"  嫌い: {data['virtual_profile']['hates'] or '未設定'}\n"
                f"  得意: {data['virtual_profile']['skills'] or '未設定'}\n\n"
                "【🤝 AIキャラとの関係】\n"
                f"  関係性: {data['relationship']['type']}\n"
                f"  呼び方: {data['relationship']['nickname']}\n"
                f"  関係レベル: {data['relationship']['ai_relation_level']}\n\n"
                "【📝 詳細メモ】\n"
                f"  {data['detail_profile_memo'] or '未記入'}\n\n"
                "【📝 左側特記事項】\n"
                f"  含める: {'はい' if data.get('left_notes', {}).get('include', True) else 'いいえ'}\n"
                f"  {data.get('left_notes', {}).get('text', '') or '未記入'}\n\n"
                "【📝 右側特記事項】\n"
                f"  含める: {'はい' if data.get('right_notes', {}).get('include', True) else 'いいえ'}\n"
                f"  {data.get('right_notes', {}).get('text', '') or '未記入'}\n"
            )

            # プレビューウィンドウ
            window = tk.Toplevel(self.parent)
            window.title("🎬 配信者設定プレビュー")
            window.geometry("600x700")

            body = ttk.Frame(window, padding=10)
            body.pack(fill=tk.BOTH, expand=True)

            text_widget = tk.Text(body, wrap=tk.WORD, font=("Consolas", 10))
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert("1.0", text)
            text_widget.config(state=tk.DISABLED)

            ttk.Button(window, text="閉じる", command=window.destroy).pack(pady=6)

        except Exception as e:
            logger.error(f"❌ プレビューエラー: {e}")
            messagebox.showerror("プレビューエラー", str(e))

    # ========== Phase 6: AI用プロフィール生成 ==========
    def _get_real_profile_text(self) -> str:
        """現実プロフィール文字列を取得（基本情報+性格+配信スタイル）"""
        try:
            data = self._collect_profile_data()
            lines = []

            # 基本情報
            lines.append(f"配信者名: {data['basic_info']['name']}")
            lines.append(f"プラットフォーム: {data['basic_info']['platform']}")
            lines.append(f"ジャンル: {data['basic_info']['genre']}")

            # 性格
            traits = data['personality']['traits']
            if traits:
                lines.append(f"性格: {', '.join(traits)}")
            hobbies = data['personality'].get('hobbies', '').strip()
            if hobbies:
                lines.append(f"趣味: {hobbies}")

            # 配信スタイル
            lines.append(f"配信頻度: {data['streaming_style']['frequency']}")
            lines.append(f"配信時間帯: {data['streaming_style']['time_slot']}")
            lines.append(f"視聴者層: {data['streaming_style']['audience']}")

            play_style = data['streaming_style'].get('play_style', '設定しない')
            if play_style != "設定しない":
                lines.append(f"プレイスタイル: {play_style}")

            motivation = data['streaming_style'].get('motivation', '設定しない')
            if motivation != "設定しない":
                lines.append(f"活動モチベ: {motivation}")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"❌ 現実プロフィール取得エラー: {e}")
            return ""

    def _get_fiction_profile_text(self) -> str:
        """架空プロフィール文字列を取得（キャラ設定+AIとの関係）"""
        try:
            data = self._collect_profile_data()
            lines = []

            # 架空プロフィール
            species = data['virtual_profile'].get('species', '設定しない')
            if species != "設定しない":
                lines.append(f"種族: {species}")

            age = data['virtual_profile'].get('age', '設定しない')
            if age != "設定しない":
                lines.append(f"年齢: {age}")

            first_person = data['virtual_profile'].get('first_person', '設定しない')
            if first_person != "設定しない":
                lines.append(f"一人称: {first_person}")

            second_person = data['virtual_profile'].get('second_person', '設定しない')
            if second_person != "設定しない":
                lines.append(f"二人称: {second_person}")

            speaking = data['virtual_profile'].get('speaking_preset', '設定しない')
            if speaking != "設定しない":
                lines.append(f"口調: {speaking}")

            favorite = data['virtual_profile'].get('favorite_things', '').strip()
            if favorite:
                lines.append(f"好きなもの: {favorite}")

            hates = data['virtual_profile'].get('hates', '').strip()
            if hates:
                lines.append(f"嫌いなもの: {hates}")

            skills = data['virtual_profile'].get('skills', '').strip()
            if skills:
                lines.append(f"得意なこと: {skills}")

            # AIとの関係
            lines.append(f"AIとの関係: {data['relationship']['type']}")
            lines.append(f"AIからの呼び方: {data['relationship']['nickname']}")
            lines.append(f"関係の深さ: {data['relationship']['ai_relation_level']}")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"❌ 架空プロフィール取得エラー: {e}")
            return ""

    def build_profile_text_for_ai(self) -> str:
        """
        Phase 7改訂: AIに渡すプロフィール文字列を生成（Text欄から直接読取）
        mode: both/real/fiction/none
        both の順序は 架空→現実 固定
        """
        mode = (self.profile_ai_mode_var.get() or "none").strip()

        # Phase 7: Text欄から直接読み取る（入力し直し不要）
        real_text = self.real_profile_text.get("1.0", "end").strip()
        fiction_text = self.fiction_profile_text.get("1.0", "end").strip()

        if mode == "none":
            return ""

        if mode == "real":
            return f"【現実プロフィール】\n{real_text}".strip() if real_text else ""

        if mode == "fiction":
            return f"【架空プロフィール】\n{fiction_text}".strip() if fiction_text else ""

        # mode == "both"
        parts = []
        if fiction_text:
            parts.append("【架空プロフィール】\n" + fiction_text)
        if real_text:
            parts.append("【現実プロフィール】\n" + real_text)
        return "\n\n".join(parts).strip()

    # ========== MessageBus 応答 ==========
    def _on_profile_request(self, *_args, **_kwargs) -> None:
        """外部からのプロフィール要求に応答"""
        try:
            self._bus_publish(BUS_EVT_RESPONSE, self._collect_profile_data())
        except Exception as e:
            logger.warning(f"⚠️ REQUEST 応答失敗: {e}")

    # ========== プロフィール更新通知（v17統一イベント）==========
    def _get_current_profile_data(self) -> dict:
        """
        UnifiedConfigManager から現在の tabs.streamer_profile を取得して返す。
        存在しない場合は空の dict を返す。
        """
        try:
            if self.config_manager and hasattr(self.config_manager, "get"):
                profile = self.config_manager.get(CFG_KEY, {})
                if not isinstance(profile, dict):
                    logger.warning("tabs.streamer_profile が dict ではありません。初期化します。")
                    return {}
                return profile
            return {}
        except Exception:
            logger.exception("tabs.streamer_profile の取得中にエラーが発生しました")
            return {}

    def _publish_profile_update(self, reason: str = "manual_save") -> None:
        """
        配信者プロフィールが更新されたことを他タブに通知する（v17統一イベント）。
        payload には tabs.streamer_profile の内容をそのまま含め、
        よく使う基本情報はトップレベルにも展開する。
        """
        if not hasattr(self, "message_bus") or self.message_bus is None:
            # message_bus がない場合は何もしない（スタンドアロンモード想定）
            logger.debug("message_bus が未設定のため STREAMER_PROFILE_UPDATE は送信しません")
            return

        profile = self._get_current_profile_data()
        basic_info = profile.get("basic_info", {}) if isinstance(profile, dict) else {}

        payload = {
            # 現在の tabs.streamer_profile のスナップショット
            "profile": profile,

            # 取り回ししやすいように、よく使う項目をトップレベルにも展開
            "name": basic_info.get("name", ""),
            "platform": basic_info.get("platform", ""),
            "genre": basic_info.get("genre", ""),

            # 送信理由（初期ロード / 手動保存 など）
            "reason": reason,
        }

        try:
            self._bus_publish(
                Events.STREAMER_PROFILE_UPDATE,
                payload
            )
            logger.info(
                "📡 STREAMER_PROFILE_UPDATE を送信しました reason=%s name=%s platform=%s",
                reason,
                payload["name"],
                payload["platform"],
            )
        except Exception:
            logger.exception("STREAMER_PROFILE_UPDATE 送信中にエラーが発生しました")

    # ========== cleanup ==========
    # ========== Phase 6: mode変更時の保存・通知 ==========
    def _on_profile_ai_mode_changed(self) -> None:
        """AI投入プロフィールモード変更時の処理"""
        try:
            mode = (self.profile_ai_mode_var.get() or "none").strip()

            # 設定保存
            if self.config_manager and hasattr(self.config_manager, "set"):
                try:
                    self.config_manager.set("streamer_profile.ai_mode", mode)
                    logger.info(f"✅ AI投入プロフィールモードを保存: {mode}")
                except Exception as e:
                    logger.warning(f"⚠️ AI投入モード保存失敗: {e}")

            # MessageBus通知
            payload = {
                "profile_text": self.build_profile_text_for_ai(),
                "ai_mode": mode,
            }
            try:
                self._bus_publish("STREAMER_PROFILE_FOR_AI_UPDATED", payload)
                logger.info(f"📡 AI投入プロフィール更新通知送信: mode={mode}")
            except Exception as e:
                logger.warning(f"⚠️ AI投入プロフィール通知失敗: {e}")

        except Exception as e:
            logger.error(f"❌ AI投入モード変更処理エラー: {e}")

    def cleanup(self) -> None:
        """タブ終了時のクリーンアップ"""
        self._bus_unsubscribe_all()
        logger.info("🧹 配信者設定タブ cleanup 完了")


# ===== エクスポート（v17 規約）=====
def create_streamer_profile_tab(parent, message_bus=None, config_manager=None, **kwargs):
    """タブ生成関数（v17規約）"""
    tab = StreamerProfileTab(parent, message_bus=message_bus, config_manager=config_manager)
    tab.create_ui()

    # 起動時に即ロードして他タブへ通知
    try:
        tab.load_profile()
    except Exception as e:
        logger.warning(f"⚠️ 初期ロードで警告: {e}")

    return tab


# エイリアス（後方互換性維持）
create_config_tab = create_streamer_profile_tab
create_tab = create_streamer_profile_tab


# ===== クラスエイリアス（クラス検出にも対応）=====
class App(StreamerProfileTab):
    pass


class TabApp(StreamerProfileTab):
    pass


# ===== スタンドアロンテスト =====
if __name__ == "__main__":
    # 依存が無い環境でもテストできるよう最小スタブを使う
    try:
        from .minimal_tab_stubs import StubBus, StubConfig
        bus = StubBus()
        cfg = StubConfig()
    except Exception:
        bus = None
        cfg = None

    root = tk.Tk()
    root.title("配信者設定タブ - 単体テスト（2カラムUI）")
    root.geometry("1000x700")
    app = create_streamer_profile_tab(root, message_bus=bus, config_manager=cfg)
    root.mainloop()
    if hasattr(app, "cleanup"):
        app.cleanup()
