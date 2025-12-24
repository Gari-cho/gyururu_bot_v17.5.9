# -*- coding: utf-8 -*-
"""
tab_obs_effects/emoji_presets.py
絵文字エフェクトプリセット定義

このモジュールは OBS演出タブで使用する絵文字エフェクトのプリセット定義を管理します。
config_handler.py から参照されます。

各プリセットの構造:
- label: 表示名（絵文字＋日本語）
- emoji: 使用する絵文字配列
- animation: アニメーションタイプ（fall/rise/scatter/flow/pop）
- duration: エフェクト継続時間（秒）
- count: 生成する絵文字の数
- area: 表示エリア（full/center/bottom）
- trigger_words: トリガーワード配列（チャット連動用）
"""

# 絵文字エフェクトプリセット定義
EMOJI_EFFECT_PRESETS = {
    # ========== 既存6プリセット（絵文字化） ==========
    "confetti": {
        "label": "🎉 紙吹雪",
        "emoji": ["🎉", "🎊", "✨", "⭐", "🌟"],
        "animation": "fall",
        "duration": 4.0,
        "count": 50,
        "area": "full",
        "trigger_words": ["紙吹雪", "🎉", "おめでとう", "やったー", "すごい"]
    },
    "fireworks": {
        "label": "🎆 花火",
        "emoji": ["🎆", "🎇", "💥", "✨", "🌟"],
        "animation": "scatter",
        "duration": 3.0,
        "count": 40,
        "area": "center",
        "trigger_words": ["花火", "🎆", "盛り上がれ", "ファイヤー"]
    },
    "heart": {
        "label": "💖 ハート",
        "emoji": ["❤️", "💖", "💗", "💕", "💓", "🩷"],
        "animation": "rise",
        "duration": 3.0,
        "count": 25,
        "area": "bottom",
        "trigger_words": ["ハート", "💕", "かわいい", "好き"]
    },
    "sparkle": {
        "label": "✨ キラキラ",
        "emoji": ["✨", "⭐", "🌟", "💫"],
        "animation": "pop",
        "duration": 4.0,
        "count": 35,
        "area": "full",
        "trigger_words": ["キラキラ", "✨", "輝く", "美しい"]
    },
    "welcome": {
        "label": "👋 歓迎",
        "emoji": ["👋", "🙌", "🎉", "✨", "💐"],
        "animation": "flow",
        "duration": 5.0,
        "count": 30,
        "area": "full",
        "trigger_words": ["初見", "はじめまして", "よろしく", "👋"]
    },
    "thanks": {
        "label": "🙏 感謝",
        "emoji": ["🙏", "💕", "✨", "🌸", "💐"],
        "animation": "rise",
        "duration": 3.5,
        "count": 20,
        "area": "bottom",
        "trigger_words": ["ありがとう", "感謝", "thanks", "🙏"]
    },

    # ========== 新規10プリセット ==========
    "sakura": {
        "label": "🌸 桜吹雪",
        "emoji": ["🌸", "🌷", "💮"],
        "animation": "fall",
        "duration": 5.0,
        "count": 40,
        "area": "full",
        "trigger_words": ["桜", "🌸", "春", "花見"]
    },
    "lucky": {
        "label": "🍀 幸運",
        "emoji": ["🍀", "⭐", "✨", "🌈"],
        "animation": "scatter",
        "duration": 3.0,
        "count": 30,
        "area": "center",
        "trigger_words": ["幸運", "🍀", "ラッキー", "当たり"]
    },
    "fire": {
        "label": "🔥 炎上／盛り上がり",
        "emoji": ["🔥", "💥", "⚡"],
        "animation": "rise",
        "duration": 3.0,
        "count": 35,
        "area": "bottom",
        "trigger_words": ["炎上", "🔥", "熱い", "盛り上がれ"]
    },
    "snow": {
        "label": "❄️ 雪",
        "emoji": ["❄️", "⛄", "🌨️"],
        "animation": "fall",
        "duration": 5.0,
        "count": 45,
        "area": "full",
        "trigger_words": ["雪", "❄️", "冬", "寒い"]
    },
    "music": {
        "label": "🎵 音符",
        "emoji": ["🎵", "🎶", "🎤", "🎸"],
        "animation": "flow",
        "duration": 4.0,
        "count": 25,
        "area": "full",
        "trigger_words": ["音楽", "🎵", "歌", "メロディ"]
    },
    "lol": {
        "label": "😂 爆笑",
        "emoji": ["😂", "🤣", "😆", "💀"],
        "animation": "pop",
        "duration": 3.0,
        "count": 30,
        "area": "full",
        "trigger_words": ["笑", "😂", "草", "www", "爆笑"]
    },
    "clap": {
        "label": "👏 拍手",
        "emoji": ["👏", "🙌", "✨"],
        "animation": "flow",
        "duration": 3.0,
        "count": 35,
        "area": "full",
        "trigger_words": ["拍手", "👏", "パチパチ", "すごい"]
    },
    "halloween": {
        "label": "🎃 ハロウィン",
        "emoji": ["🎃", "👻", "🦇", "🕷️"],
        "animation": "scatter",
        "duration": 4.0,
        "count": 35,
        "area": "full",
        "trigger_words": ["ハロウィン", "🎃", "Halloween"]
    },
    "cat": {
        "label": "🐱 にゃんこ",
        "emoji": ["🐱", "😺", "🐾", "💕"],
        "animation": "pop",
        "duration": 4.0,
        "count": 20,
        "area": "full",
        "trigger_words": ["猫", "🐱", "にゃん", "ねこ"]
    },
    "money": {
        "label": "💰 お金",
        "emoji": ["💰", "💵", "🪙", "✨"],
        "animation": "fall",
        "duration": 4.0,
        "count": 40,
        "area": "full",
        "trigger_words": ["お金", "💰", "札束", "金"]
    },
}
