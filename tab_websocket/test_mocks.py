# -*- coding: utf-8 -*-
"""
test_mocks.py - テスト用モック群
"""
import logging
logger = logging.getLogger(__name__)

class MockBus:
    def __init__(self):
        self.events = []

    def publish(self, ev, data=None, sender=None):
        msg = {"event": ev, "data": data, "sender": sender}
        self.events.append(msg)
        logger.info(f"[MockBus] {ev}: {data}")

    def subscribe(self, ev, cb):
        logger.info(f"[MockBus] subscribe: {ev}")

class MockHandler:
    def __init__(self):
        self.log = []

    def on_open(self): self.log.append("open")
    def on_message(self, msg): self.log.append(("msg", msg))
    def on_close(self): self.log.append("close")
    def on_error(self, e): self.log.append(("error", e))
