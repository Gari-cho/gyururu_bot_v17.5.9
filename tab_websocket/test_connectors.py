#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v17.5 Multi Comment Bridge コネクタの基本動作テスト

このスクリプトは、各コネクタクラスが正しくインスタンス化できるか、
基本的なメソッドが正常に動作するかを確認します。
"""

import sys
import os
import logging

# パス調整
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# MessageBus モック
class MockMessageBus:
    def __init__(self):
        self.published_events = []

    def publish(self, event_key, data=None, sender=None):
        self.published_events.append({
            'event': event_key,
            'data': data,
            'sender': sender,
        })
        logger.info(f"📤 Event published: {event_key} (sender: {sender})")

    def subscribe(self, event_key, handler):
        logger.info(f"📥 Event subscribed: {event_key}")
        return (event_key, handler)

# Logger モック
class MockLogger:
    def info(self, msg):
        logger.info(f"ℹ️  {msg}")

    def warning(self, msg):
        logger.warning(f"⚠️  {msg}")

    def error(self, msg):
        logger.error(f"❌ {msg}")

    def debug(self, msg):
        logger.debug(f"🔍 {msg}")


def test_connector_instantiation():
    """コネクタのインスタンス化テスト"""
    print("\n" + "="*60)
    print("📋 Test 1: コネクタのインスタンス化")
    print("="*60)

    from connectors import (
        BaseCommentConnector,
        OneCommeLegacyConnector,
        OneCommeNewConnector,
        MultiViewerConnector,
        ManualConnector,
    )

    mock_bus = MockMessageBus()
    mock_logger = MockLogger()

    connectors = {
        'OneCommeLegacy': OneCommeLegacyConnector,
        'OneCommeNew': OneCommeNewConnector,
        'MultiViewer': MultiViewerConnector,
        'Manual': ManualConnector,
    }

    results = {}
    for name, connector_class in connectors.items():
        try:
            instance = connector_class(mock_bus, mock_logger)
            results[name] = '✅ Success'
            print(f"  ✅ {name}: インスタンス化成功")
        except Exception as e:
            results[name] = f'❌ Failed: {e}'
            print(f"  ❌ {name}: インスタンス化失敗 - {e}")

    return all('✅' in v for v in results.values())


def test_connector_interface():
    """コネクタのインターフェーステスト"""
    print("\n" + "="*60)
    print("📋 Test 2: コネクタのインターフェース")
    print("="*60)

    from connectors import OneCommeLegacyConnector

    mock_bus = MockMessageBus()
    mock_logger = MockLogger()

    connector = OneCommeLegacyConnector(mock_bus, mock_logger)

    # 必須メソッドの存在確認
    required_methods = ['connect', 'disconnect', 'is_connected', 'get_url']

    all_ok = True
    for method_name in required_methods:
        if hasattr(connector, method_name):
            print(f"  ✅ {method_name}: 存在")
        else:
            print(f"  ❌ {method_name}: 存在しない")
            all_ok = False

    # 初期状態の確認
    if not connector.is_connected():
        print(f"  ✅ 初期状態: 未接続")
    else:
        print(f"  ❌ 初期状態: 接続済み（異常）")
        all_ok = False

    return all_ok


def test_event_publishing():
    """イベント発行テスト"""
    print("\n" + "="*60)
    print("📋 Test 3: イベント発行機能")
    print("="*60)

    from connectors import OneCommeLegacyConnector

    mock_bus = MockMessageBus()
    mock_logger = MockLogger()

    connector = OneCommeLegacyConnector(mock_bus, mock_logger)

    # _publish_comment メソッドのテスト
    test_payload = {
        "source": "onecomme_legacy",
        "platform": "youtube",
        "user_id": "test_user_123",
        "user_name": "テストユーザー",
        "message": "こんにちは！",
        "raw": {"test": "data"},
    }

    connector._publish_comment(test_payload)

    # イベントが発行されたか確認
    if len(mock_bus.published_events) > 0:
        event = mock_bus.published_events[-1]
        if event['event'] == 'ONECOMME_COMMENT':
            print(f"  ✅ ONECOMME_COMMENT イベント発行成功")

            # 後方互換フィールドの確認
            data = event['data']
            if 'text' in data and 'user' in data:
                print(f"  ✅ 後方互換フィールド (text, user) が存在")
                return True
            else:
                print(f"  ❌ 後方互換フィールドが存在しない")
                return False
        else:
            print(f"  ❌ 予期しないイベント: {event['event']}")
            return False
    else:
        print(f"  ❌ イベントが発行されていない")
        return False


def test_payload_format():
    """payloadフォーマットテスト"""
    print("\n" + "="*60)
    print("📋 Test 4: Payload フォーマット")
    print("="*60)

    from connectors import OneCommeLegacyConnector

    mock_bus = MockMessageBus()
    mock_logger = MockLogger()

    connector = OneCommeLegacyConnector(mock_bus, mock_logger)

    test_payload = {
        "source": "onecomme_legacy",
        "platform": "youtube",
        "user_id": "test_user_123",
        "user_name": "テストユーザー",
        "message": "こんにちは！",
        "raw": {},
    }

    connector._publish_comment(test_payload)

    if len(mock_bus.published_events) > 0:
        event_data = mock_bus.published_events[-1]['data']

        # v17.5 統一フォーマットのフィールド確認
        required_fields = ['source', 'platform', 'user_name', 'message', 'raw']
        all_ok = True

        for field in required_fields:
            if field in event_data:
                print(f"  ✅ フィールド '{field}': 存在")
            else:
                print(f"  ❌ フィールド '{field}': 存在しない")
                all_ok = False

        # 後方互換フィールド確認
        compat_fields = ['text', 'user']
        for field in compat_fields:
            if field in event_data:
                print(f"  ✅ 後方互換フィールド '{field}': 存在")
            else:
                print(f"  ❌ 後方互換フィールド '{field}': 存在しない")
                all_ok = False

        return all_ok
    else:
        print(f"  ❌ イベントが発行されていない")
        return False


def main():
    """メインテスト関数"""
    print("\n" + "="*60)
    print("🧪 v17.5 Multi Comment Bridge コネクタテスト")
    print("="*60)

    results = {
        'インスタンス化': test_connector_instantiation(),
        'インターフェース': test_connector_interface(),
        'イベント発行': test_event_publishing(),
        'Payloadフォーマット': test_payload_format(),
    }

    print("\n" + "="*60)
    print("📊 テスト結果サマリー")
    print("="*60)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")

    all_passed = all(results.values())

    print("\n" + "="*60)
    if all_passed:
        print("🎉 全てのテストが成功しました！")
        print("="*60)
        return 0
    else:
        print("⚠️  一部のテストが失敗しました")
        print("="*60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
