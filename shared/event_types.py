# -*- coding: utf-8 -*-
"""
shared/event_types.py  (v17.3 minimal-stable + alias)
- すべてのタブ／ブリッジ／コネクタで参照するイベント名の正本
- 旧名 → 新名 の正規化もここで吸収（normalize_event_key）
"""

from __future__ import annotations
from typing import Dict


class Events:
    # lifecycle / system
    APP_STARTED = "APP_STARTED"
    TAB_READY = "TAB_READY"
    STATUS_UPDATE = "STATUS_UPDATE"
    STATUS_LOG = "STATUS_LOG"
    ERROR_ALERT = "ERROR_ALERT"

    # chat / comments
    CHAT_MESSAGE = "CHAT_MESSAGE"
    ONECOMME_COMMENT = "ONECOMME_COMMENT"
    """
    ONECOMME_COMMENT payload 仕様（v17.5 Multi Comment Bridge）

    全てのコメント取得元コネクタは、以下の統一フォーマットでイベントを発行します。

    payload = {
        "source": str,          # コネクタ識別子
                               # 例: "onecomme_legacy", "onecomme_new",
                               #     "multiviewer", "manual"

        "platform": str,        # プラットフォーム名
                               # 例: "youtube", "twitch", "niconico", "unknown"

        "user_id": str,         # ユーザーID（取得できない場合は空文字列）

        "user_name": str,       # ユーザー名（表示名）

        "message": str,         # コメント本文

        "raw": dict,           # 元のJSONデータ（そのまま保存）

        # ---- 後方互換フィールド（既存コードが動作し続けるため） ----
        "text": str,           # message のコピー
        "user": str,           # user_name のコピー
    }

    後方互換性:
    - 既存のコードは payload["text"] や payload["user"] で動作し続けます
    - 新しいコードは payload["message"], payload["user_name"] を使用してください
    """

    # ai
    AI_REQUEST = "AI_REQUEST"           # 下流AIへ「生成依頼」
    AI_RESPONSE = "AI_RESPONSE"         # AIからの返答（推奨）
    AI_REPLY = "AI_REPLY"               # 旧称（互換）
    AI_CONFIG_UPDATED = "AI_CONFIG_UPDATED"
    AI_STATUS_REQUEST = "AI_STATUS_REQUEST"
    AI_STATUS_UPDATE = "AI_STATUS_UPDATE"
    AI_TEST_REQUEST = "AI_TEST_REQUEST"  # 接続テスト用（v17.3）
    AI_PERSONALITY_CHANGED = "AI_PERSONALITY_CHANGED"
    CONFIG_UPDATE = "CONFIG_UPDATE"     # UnifiedConfig 全般の更新通知

    # voice
    VOICE_PLAY = "VOICE_PLAY"
    VOICE_REQUEST = "VOICE_REQUEST"

    # streamer profile
    STREAMER_PROFILE_READY = "STREAMER_PROFILE_READY"
    STREAMER_PROFILE_UPDATE = "STREAMER_PROFILE_UPDATE"  # v17: プロフィール更新通知


# 旧名→新名マップ（雑多な呼称をここで吸収）
_ALIAS: Dict[str, str] = {
    "ai_reply": Events.AI_RESPONSE,
    "airesult": Events.AI_RESPONSE,
    "ai_res": Events.AI_RESPONSE,
    "tabready": Events.TAB_READY,
    "voiceplay": Events.VOICE_PLAY,
    "config_update": Events.CONFIG_UPDATE,
    "configupdated": Events.CONFIG_UPDATE,
    "ai_test": Events.AI_TEST_REQUEST,
}


def normalize_event_key(key: str) -> str:
    """雑多な表記を正規化して返す。無ければそのまま。"""
    if not key:
        return key
    k = str(key).strip()
    k_std = _ALIAS.get(k.lower())
    return k_std or k


# 別名（互換）
ET = Events
EventTypes = Events

# ==== 旧スタイルの「定数 import」互換 =========================
# 例:
#   from shared.event_types import AI_REQUEST, AI_STATUS_UPDATE
# のような呼び出しをすべて吸収する
AI_REQUEST = Events.AI_REQUEST
AI_RESPONSE = Events.AI_RESPONSE
AI_TEST_REQUEST = Events.AI_TEST_REQUEST
AI_CONFIG_UPDATED = Events.AI_CONFIG_UPDATED
AI_STATUS_REQUEST = Events.AI_STATUS_REQUEST
AI_STATUS_UPDATE = Events.AI_STATUS_UPDATE
CONFIG_UPDATE = Events.CONFIG_UPDATE

CHAT_MESSAGE = Events.CHAT_MESSAGE
ONECOMME_COMMENT = Events.ONECOMME_COMMENT
VOICE_PLAY = Events.VOICE_PLAY
VOICE_REQUEST = Events.VOICE_REQUEST
STREAMER_PROFILE_READY = Events.STREAMER_PROFILE_READY
STREAMER_PROFILE_UPDATE = Events.STREAMER_PROFILE_UPDATE
