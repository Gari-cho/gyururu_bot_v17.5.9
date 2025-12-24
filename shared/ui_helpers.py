#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI共通ヘルパー関数
ステータスバーのスタイル統一など、全タブで共通するUI設定を提供
"""

def apply_statusbar_style(widget):
    """
    ステータスバー（Frame/Label等）に統一スタイルを適用する。
    既存の更新処理は壊さず、見た目だけ統一する。

    Args:
        widget: ステータスバーとして使用するウィジェット（Frame, Label等）

    Returns:
        tuple: (背景色, 文字色)
    """
    bg = "#66DD66"  # 明るい緑
    fg = "#000000"  # 黒

    try:
        widget.configure(background=bg, foreground=fg)
    except Exception:
        # ttkウィジェットの場合は configure が効かないことがあるため
        # 可能な範囲で style 経由 or 直接設定を試みる
        try:
            widget.configure(background=bg)
        except Exception:
            pass

    return bg, fg
