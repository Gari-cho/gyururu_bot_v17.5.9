# v17.5 Multi Comment Bridge コネクタ

このディレクトリには、v17.5 "Multi Comment Bridge" で導入された、複数のコメント取得元を統一的に扱うためのコネクタモジュールが含まれています。

## 概要

v17.5では、OneComme（旧/新）、マルチコメントビューワー、任意URL接続の4つの接続方式を並列で使用できるようになりました。各接続方式は独立したコネクタクラスとして実装されており、`BaseCommentConnector` を継承しています。

## アーキテクチャ

```
BaseCommentConnector (抽象基底クラス)
    ├─ OneCommeLegacyConnector (OneComme 旧WebSocket方式)
    ├─ OneCommeNewConnector (OneComme 新接続方式 - 最小実装)
    ├─ MultiViewerConnector (マルチコメントビューワー - 最小実装)
    └─ ManualConnector (任意URL接続)
```

## ファイル構成

- **base.py**: 全コネクタの基底クラス
- **onecomme_legacy.py**: OneComme 旧WebSocket方式（message_bridge.py から移植）
- **onecomme_new.py**: OneComme 新接続方式（最小実装）
- **multiviewer.py**: マルチコメントビューワー接続（最小実装）
- **manual_connector.py**: 任意URL接続
- **__init__.py**: パッケージエクスポート

## BaseCommentConnector インターフェース

全てのコネクタは以下のメソッドを実装しています：

```python
class BaseCommentConnector(ABC):
    def connect(self, url: str) -> bool:
        """接続開始"""

    def disconnect(self):
        """接続切断"""

    def is_connected(self) -> bool:
        """接続状態を取得"""

    def get_url(self) -> str:
        """現在の接続URLを取得"""
```

## イベント発行

全てのコネクタは、受信したコメントを統一フォーマットで `ONECOMME_COMMENT` イベントとして発行します。

### Payload 仕様

```python
{
    "source": str,          # コネクタ識別子
                           # 例: "onecomme_legacy", "onecomme_new",
                           #     "multiviewer", "manual"

    "platform": str,        # プラットフォーム名
                           # 例: "youtube", "twitch", "niconico", "unknown"

    "user_id": str,         # ユーザーID（取得できない場合は空文字列）

    "user_name": str,       # ユーザー名（表示名）

    "message": str,         # コメント本文

    "raw": dict,           # 元のJSONデータ（そのまま保存）

    # ---- 後方互換フィールド ----
    "text": str,           # message のコピー
    "user": str,           # user_name のコピー
}
```

### 後方互換性

既存のコード（tab_chat, tab_voice, ai_integration_manager）は `payload["text"]` や `payload["user"]` を使用しているため、これらのフィールドも同時に設定されます。

## 使用例

```python
from tab_websocket.connectors import OneCommeLegacyConnector
from shared.message_bus import get_message_bus
import logging

# MessageBus とロガーを取得
bus = get_message_bus()
logger = logging.getLogger(__name__)

# コネクタインスタンス作成
connector = OneCommeLegacyConnector(bus, logger)

# 接続
success = connector.connect("ws://127.0.0.1:22280/ws")

if success:
    print("接続開始に成功しました")

# 切断
connector.disconnect()
```

## 実装状況

| コネクタ | 実装状態 | 備考 |
|---------|---------|------|
| OneCommeLegacy | ✅ 完全実装 | message_bridge.py から移植 |
| OneCommeNew | 🚧 最小実装 | 新方式の仕様が判明次第拡張 |
| MultiViewer | 🚧 最小実装 | JSONフォーマット判明次第拡張 |
| Manual | ✅ 完全実装 | 柔軟なフィールド検出で対応 |

## テスト

コネクタの基本動作を確認するテストスクリプトが用意されています：

```bash
cd tab_websocket
python3 test_connectors.py
```

## 今後の拡張

1. **OneCommeNewConnector**: 新しい接続方式の仕様が判明次第、実装を追加
2. **MultiViewerConnector**: マルチコメントビューワーのJSONフォーマットに合わせて調整
3. **再接続機能**: MultiViewer と Manual にも自動再接続機能を追加（必要に応じて）
4. **エラーハンドリング**: より詳細なエラー分類と処理

## 関連ファイル

- `tab_websocket/multi_connection_panel.py`: 複数コネクタのUIパネル
- `shared/event_types.py`: ONECOMME_COMMENT イベントの payload 仕様
- `tab_websocket/message_bridge.py`: 旧実装（参考用）
