import logging
import os
import sys

# 4スペース（関数レベル）
def setup_quiet_logging(default_level: str = "INFO") -> None:
    """
    ルートロガーに重複してハンドラが積まれるのを防ぎ、
    noisyなライブラリを静音化。環境変数 GYURURU_LOG_LEVEL で上書き可。
    """
    level_name = os.getenv("GYURURU_LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    # 既に当パッチのハンドラがあれば増やさない
    for h in root.handlers:
        if getattr(h, "_gyururu_handler", False):
            root.setLevel(level)
            break
    else:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler._gyururu_handler = True  # 自印
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root.handlers.clear()  # 既存の基本ハンドラを一掃（重複防止）
        root.addHandler(handler)
        root.setLevel(level)

    # noisy系を抑制
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("comtypes").setLevel(logging.WARNING)

    # モジュールごとに伝播止め（二重出力防止）
    for name in (
        "shared.unified_config_manager",
        "tab_ai_unified",
        "tab_chat",
        "tab_voice",
        "tab_websocket.app",
        "ai_integration_manager",
        "gyururu_main_v17_3",
    ):
        lg = logging.getLogger(name)
        lg.propagate = False  # ルートへ二重伝播しない
        if not lg.handlers:
            # ルートに任せる（個別ハンドラ不要）
            pass

def get_logger(name: str) -> logging.Logger:
    """
    各モジュールから使う取得関数。setup_quiet_logging適用後に呼ばれる想定。
    """
    return logging.getLogger(name)
