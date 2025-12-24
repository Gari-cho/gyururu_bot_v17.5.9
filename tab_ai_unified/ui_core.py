#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧩 ui_core.py — AI技術設定タブの最小UIコア（v17.2）
- ViewModel を介して設定を保存
- MessageBusへ "AI_CONFIG_UPDATED" 通知
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from shared.message_bus import get_message_bus
    BUS = get_message_bus()
except Exception:
    BUS = None

from .view_model import AITechnicalViewModel  # 同ディレクトリ想定

def create_ai_technical_ui(parent, config_manager=None, message_bus=None):
    """
    - response_probability（0.0-1.0）
    - プロバイダー表示（読み取り専用）
    - 保存ボタンでVM.save() → Bus通知
    """
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    vm = AITechnicalViewModel(config_manager=config_manager)

    # プロバイダー
    prov_box = ttk.LabelFrame(frame, text="AIプロバイダー", padding=10)
    prov_box.pack(fill="x", padx=10, pady=(10, 6))

    prov = tk.StringVar(value=vm.provider)
    ttk.Label(prov_box, text="現在のプロバイダー:").pack(side="left")
    ttk.Entry(prov_box, textvariable=prov, state="readonly", width=24).pack(side="left", padx=6)

    # 応答確率
    prob_box = ttk.LabelFrame(frame, text="応答確率", padding=10)
    prob_box.pack(fill="x", padx=10, pady=6)

    prob_scale = ttk.Scale(prob_box, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                           command=lambda v: prob_label.config(text=f"{float(v)*100:.0f}%"))
    prob_scale.set(vm.response_prob)
    prob_scale.pack(fill="x")

    prob_label = ttk.Label(prob_box, text=f"{vm.response_prob*100:.0f}%")
    prob_label.pack(anchor="e")

    # 保存
    button_row = ttk.Frame(frame)
    button_row.pack(fill="x", padx=10, pady=(6, 12))

    def _save():
        try:
            vm.set_response_prob(float(prob_scale.get()))
            vm.save()  # ViewModelに委譲（config_resolver/UnifiedConfigへ自動保存）
            if (message_bus or BUS):
                (message_bus or BUS).publish("AI_CONFIG_UPDATED",
                                             {"response_probability": vm.response_prob},
                                             sender="ai_technical_tab")
            messagebox.showinfo("保存", "AI技術設定を保存しました。")
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

    ttk.Button(button_row, text="💾 保存", command=_save).pack(side="right")

    return frame
