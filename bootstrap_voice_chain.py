# -*- coding: utf-8 -*-
"""
VoiceChain Bootstrap - v17.3 ダミー版

現時点では本番の VoiceChain は未実装のため、
import エラーを防ぎつつ「何もしない」最小実装を提供する。
将来、本格的なルーティングを実装するときはこのファイルを差し替える。
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def bootstrap_voice_chain(
    bus: Optional[Any] = None,
    config_manager: Optional[Any] = None,
    voice_manager: Optional[Any] = None,
) -> None:
    """
    VoiceChain の初期化ダミー関数。
    - 例外を絶対に投げない
    - 何もルーティングを追加しない
    - ログだけ1行残す
    """
    logger.info("🔗 VoiceChain Bootstrap: ダミー版を使用中（処理はスキップ）")
    # 将来的にここにルーティング構築処理を追加する
    return None
