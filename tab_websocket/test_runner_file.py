# -*- coding: utf-8 -*-
"""
test_runner_file.py - WebSocket系一括テスト
"""
import logging
import time
from message_bridge import init_bridge, stop_bridge
from test_mocks import MockBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    bus = MockBus()
    logger.info("=== Bridge起動テスト開始 ===")
    bridge = init_bridge(bus, "ws://127.0.0.1:11180/sub")
    time.sleep(7)
    stop_bridge()
    logger.info("=== テスト完了 ===")
