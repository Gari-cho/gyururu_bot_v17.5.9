# -*- coding: utf-8 -*-
"""
TCPCommentClientConnector - TCPコメントクライアントコネクタ

外部のTCPコメントサーバー（例: tcp_test_comment_server.py）に接続し、
JSON形式のコメントを受信してMessageBusに送信します。

特徴:
- BaseCommentConnectorを継承した統一インターフェース
- JSON 1行受信 → ONECOMME_COMMENT イベント発行
- 接続失敗時の自動タイムアウト対応（MultiConnectionPanel側で処理）
- スレッドセーフ設計

受信フォーマット（JSON）:
{
    "author": "視聴者名",
    "comment": "コメント本文",
    "user_id": "user_001",
    "platform": "test"  // オプション
}
"""

import socket
import json
import threading
from typing import Optional
from .base import BaseCommentConnector


class TCPCommentClientConnector(BaseCommentConnector):
    """
    TCPコメントクライアントコネクタ

    外部TCPサーバーに接続し、JSON形式のコメントを受信して
    MessageBusに送信します。
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stopped = False
        self._host = ""
        self._port = 0

    def connect(self, url: str) -> bool:
        """
        TCPサーバーに接続

        Args:
            url: 接続先（"host:port" 形式、例: "127.0.0.1:50000"）

        Returns:
            bool: 接続開始に成功した場合True
        """
        # URL解析（"host:port" 形式）
        try:
            if ":" in url:
                host, port_str = url.rsplit(":", 1)
                port = int(port_str)
            else:
                self._log("error", f"⚠️ 不正なURL形式: {url} (正: host:port)")
                return False
        except (ValueError, TypeError) as e:
            self._log("error", f"⚠️ URL解析エラー: {url} → {e}")
            return False

        self._host = host
        self._port = port
        self._url = url

        # 既存の接続があれば切断
        if self._thread and self._thread.is_alive():
            self.disconnect()

        # 接続開始
        self._stopped = False
        try:
            self._start_client()
            self._log("info", f"🔌 接続開始: {url}")
            return True
        except Exception as e:
            self._log("error", f"❌ 接続開始エラー: {e}")
            self._publish_status("error", error=str(e))
            return False

    def disconnect(self):
        """TCP接続を切断"""
        self._stopped = True
        self.connected = False

        # ソケットを閉じる
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        # 受信スレッドの終了を待つ
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._log("info", "🛑 切断完了")
        self._publish_status("disconnected")

    def _start_client(self):
        """TCPクライアントを起動（別スレッドで実行）"""

        def _client_loop():
            try:
                # ソケット作成
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(5.0)  # 接続タイムアウト

                # 接続
                self._log("info", f"🔗 接続中: {self._host}:{self._port}")
                self._socket.connect((self._host, self._port))

                # 接続成功
                self.connected = True
                self._log("info", f"✅ 接続成功: {self._host}:{self._port}")
                self._publish_status("connected")

                # 受信タイムアウトを長めに設定（切断検知用）
                self._socket.settimeout(30.0)

                # ファイルオブジェクトとして扱う（行単位受信用）
                with self._socket.makefile("r", encoding="utf-8") as f:
                    while not self._stopped:
                        # 1行読み込み
                        line = f.readline()
                        if not line:
                            # EOF（サーバー側が切断）
                            self._log("info", "📡 サーバーが切断しました")
                            break

                        line = line.strip()
                        if not line:
                            continue

                        # JSON解析
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError as e:
                            self._log("warning", f"⚠️ JSONデコードエラー: {line[:50]} → {e}")
                            continue

                        # コメント処理
                        try:
                            self._handle_comment(payload)
                        except Exception as e:
                            self._log("error", f"❌ コメント処理エラー: {e}")
                            continue

            except socket.timeout:
                self._log("error", "❌ 接続タイムアウト")
                self._publish_status("error", error="接続タイムアウト")
            except ConnectionRefusedError:
                self._log("error", f"❌ 接続拒否: {self._host}:{self._port}")
                self._publish_status("error", error="接続拒否（サーバーが起動していない可能性）")
            except Exception as e:
                if not self._stopped:
                    self._log("error", f"❌ クライアントループエラー: {e}")
                    self._publish_status("error", error=str(e))
            finally:
                self.connected = False
                if self._socket:
                    try:
                        self._socket.close()
                    except Exception:
                        pass
                    self._socket = None

                if not self._stopped:
                    self._log("info", "🛑 接続終了")
                    self._publish_status("disconnected")

        self._thread = threading.Thread(target=_client_loop, daemon=True)
        self._thread.start()

    def _handle_comment(self, payload: dict):
        """
        受信したJSONコメントを処理

        Args:
            payload: JSONペイロード
                期待フィールド:
                - author: str (必須)
                - comment: str (必須)
                - user_id: str (オプション)
                - platform: str (オプション、デフォルト: "tcp")
        """
        # 必須フィールドチェック
        author = payload.get("author") or "unknown"
        comment = payload.get("comment") or payload.get("text") or ""

        if not comment:
            self._log("debug", f"⚠️ コメントが空です: {payload}")
            return

        # user_id 取得
        user_id = payload.get("user_id") or ""

        # platform 取得
        platform = payload.get("platform") or "tcp"

        # ログ出力
        self._log("info", f"💬 受信: [{author}] {comment[:50]}")

        # ONECOMME_COMMENT イベントとして発行
        comment_payload = {
            "source": "tcp_comment_client",
            "platform": platform,
            "user_id": user_id,
            "user_name": author,
            "message": comment,
            "raw": payload,
            # 後方互換用
            "text": comment,
            "user": author,
            "author": author,
        }

        self._publish_comment(comment_payload)

    def _log(self, level: str, message: str):
        """
        ログ出力（BaseCommentConnector をオーバーライド）

        WEBSOCKET_LOG イベントも発行して、connection_panel のログに表示します。
        """
        # 親クラスのログ出力
        super()._log(level, message)

        # WEBSOCKET_LOG イベント発行（connection_panel が購読）
        try:
            self.message_bus.publish(
                "WEBSOCKET_LOG",
                {"level": level, "msg": f"[TCP Client] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
