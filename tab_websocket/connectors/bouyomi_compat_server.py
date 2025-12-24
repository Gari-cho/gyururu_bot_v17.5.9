# -*- coding: utf-8 -*-
"""
BouyomiCompatServerConnector - 棒読みちゃん互換TCPサーバ

マルチコメントビューワー（MCV）などから棒読みちゃん互換プロトコルで
送信されるテキストを受信するTCPサーバです。

特徴:
- デフォルトポート: 50010（設定で変更可能）
- 受信テキストを MessageBus に publish
- 複数クライアント同時接続対応
- スレッドセーフ設計

棒読みちゃんプロトコル仕様（簡易版）:
  Command(2) + Speed(2) + Tone(2) + Volume(2) + Voice(2) + Encoding(1) + Length(4) + Text(可変)
  ※今回は最小実装として、テキスト部分の取得に集中
"""

import socket
import struct
import threading
import json
from typing import Optional
from urllib.parse import parse_qs, urlparse
from .base import BaseCommentConnector


class BouyomiCompatServerConnector(BaseCommentConnector):
    """
    棒読みちゃん互換TCPサーバコネクタ

    WebSocketではなくTCPサーバとして動作し、
    マルチコメントビューワーなどから送られてくるテキストを受信します。
    """

    def __init__(self, message_bus, logger):
        super().__init__(message_bus, logger)
        self.port = 50010  # デフォルトポート
        self.server_socket: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._stopped = False
        self._client_threads = []

    def connect(self, port: int = 50010) -> bool:
        """
        TCPサーバを起動

        Args:
            port: 待受ポート番号（デフォルト: 50010）

        Returns:
            bool: サーバ起動に成功した場合True
        """
        try:
            self.port = int(port)
        except (ValueError, TypeError):
            self._log("error", f"⚠️ 不正なポート番号: {port}")
            return False

        # 既存のサーバがあれば停止
        if self._server_thread and self._server_thread.is_alive():
            self.disconnect()

        # サーバ起動
        self._stopped = False
        try:
            self._start_server()
            self._log("info", f"🛰 待受開始: 0.0.0.0:{self.port}")
            self._publish_status("connected")
            self.connected = True
            return True
        except Exception as e:
            self._log("error", f"❌ サーバ起動失敗: {e}")
            self._publish_status("error", error=str(e))
            return False

    def disconnect(self):
        """TCPサーバを停止"""
        self._stopped = True
        self.connected = False

        # サーバソケットを閉じる
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

        # クライアントスレッドの終了を待つ（タイムアウト付き）
        for thread in self._client_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
        self._client_threads.clear()

        self._log("info", "🛑 待受停止")
        self._publish_status("disconnected")

    def _start_server(self):
        """TCPサーバを起動（別スレッドで実行）"""

        def _server_loop():
            try:
                # ソケット作成
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(("0.0.0.0", self.port))
                self.server_socket.listen(5)
                self.server_socket.settimeout(1.0)  # accept のタイムアウト

                self._log("info", f"🔌 TCPサーバ起動: ポート {self.port}")

                while not self._stopped:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        self._log("info", f"📥 クライアント接続: {addr}")

                        # クライアント処理スレッドを起動
                        client_thread = threading.Thread(
                            target=self._handle_client,
                            args=(client_socket, addr),
                            daemon=True,
                        )
                        client_thread.start()
                        self._client_threads.append(client_thread)

                    except socket.timeout:
                        # タイムアウトは正常（ループ継続）
                        continue
                    except Exception as e:
                        if not self._stopped:
                            self._log("error", f"❌ accept エラー: {e}")

            except Exception as e:
                self._log("error", f"❌ サーバループエラー: {e}")
                self._publish_status("error", error=str(e))
            finally:
                if self.server_socket:
                    try:
                        self.server_socket.close()
                    except Exception:
                        pass

        self._server_thread = threading.Thread(target=_server_loop, daemon=True)
        self._server_thread.start()

    def _handle_client(self, client_socket: socket.socket, addr: tuple):
        """
        クライアント接続を処理（HTTP / TCP バイナリプロトコル対応）

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
        """
        try:
            # 最初の数バイトを覗き見（peekで非破壊読み込み）
            try:
                first_bytes = client_socket.recv(4, socket.MSG_PEEK)
                if not first_bytes:
                    return
            except Exception as e:
                self._log("debug", f"初期データ読み込みエラー: {e}")
                return

            # HTTPリクエストか判定（GET / POST で始まるか）
            if first_bytes.startswith(b'GET ') or first_bytes.startswith(b'POST'):
                self._log("debug", f"🌐 HTTPリクエスト検出: {addr}")
                self._handle_http_request(client_socket, addr)
            else:
                self._log("debug", f"📦 TCPバイナリプロトコル検出: {addr}")
                self._handle_tcp_binary(client_socket, addr)

        except Exception as e:
            self._log("error", f"❌ クライアント処理エラー: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            self._log("debug", f"📤 クライアント切断: {addr}")

    def _handle_http_request(self, client_socket: socket.socket, addr: tuple):
        """
        HTTP リクエストを処理（GET/POST対応）

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
        """
        try:
            # HTTPヘッダーを読み込み（\r\n\r\n まで）
            header_data = b""
            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                header_data += chunk
                # HTTPヘッダー終了（\r\n\r\n）を検出
                if b"\r\n\r\n" in header_data:
                    break
                # タイムアウト防止（最大8KB）
                if len(header_data) > 8192:
                    break

            # ヘッダーとボディを分離
            if b"\r\n\r\n" in header_data:
                header_part, body_part = header_data.split(b"\r\n\r\n", 1)
            else:
                header_part = header_data
                body_part = b""

            # ヘッダーをデコード
            try:
                header_text = header_part.decode("utf-8", errors="ignore")
            except Exception:
                self._log("error", "❌ HTTPヘッダーのデコード失敗")
                return

            # リクエストラインを解析
            lines = header_text.split("\r\n")
            if not lines:
                return

            request_line = lines[0]
            self._log("info", f"🌐 HTTP: {request_line}")

            # メソッドとパスを抽出
            parts = request_line.split()
            if len(parts) < 2:
                self._send_http_response(client_socket, 400, "Bad Request")
                return

            method = parts[0].upper()
            path_with_query = parts[1]

            # パースURLからパスとクエリを分離
            parsed = urlparse(path_with_query)
            path = parsed.path
            query_params = parse_qs(parsed.query)

            # Content-Lengthを取得（POSTの場合）
            content_length = 0
            for line in lines[1:]:
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                    break

            # POSTの場合、ボディを読み込み
            if method == "POST" and content_length > 0:
                # 既に読み込んだボディ部分の長さを確認
                remaining = content_length - len(body_part)
                if remaining > 0:
                    # 残りのボディを読み込み
                    additional_body = self._recv_exact(client_socket, remaining)
                    if additional_body:
                        body_part += additional_body

            # エンドポイント処理
            if path == "/getvoicelist":
                self._handle_getvoicelist(client_socket, addr)
            elif path.lower() == "/talk":
                # POST /talk (JSON) または GET /talk (query params)
                if method == "POST":
                    self._handle_talk_post(client_socket, addr, body_part)
                else:
                    self._handle_talk_get(client_socket, addr, query_params)
            else:
                self._log("warning", f"⚠️ 未知のエンドポイント: {path}")
                self._send_http_response(client_socket, 404, "Not Found")

        except Exception as e:
            self._log("error", f"❌ HTTPリクエスト処理エラー: {e}")

    def _handle_getvoicelist(self, client_socket: socket.socket, addr: tuple):
        """
        /getvoicelist エンドポイント（接続確認用）

        ダミーの音声リストを返す（棒読みちゃん互換形式）
        """
        self._log("info", "✅ /getvoicelist - 接続確認")

        # 棒読みちゃん互換の音声リスト形式: "ID\t音声名\t種別"
        # わんコメが音声リストを確認して、有効と判断するために必要
        voice_list = [
            "0\tMicrosoft Haruka Desktop - Japanese\t0",
            "1\tMicrosoft Zira Desktop - English (United States)\t0",
            "2\tVOICEVOX:ずんだもん\t0",
            "3\tVOICEVOX:四国めたん\t0"
        ]
        response_body = "\n".join(voice_list)
        self._send_http_response(client_socket, 200, "OK", response_body, content_type="text/plain; charset=utf-8")

    def _handle_talk_get(self, client_socket: socket.socket, addr: tuple, query_params: dict):
        """
        GET /Talk エンドポイント（接続テストボタン用）

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
            query_params: クエリパラメータ
        """
        # text パラメータを取得
        text_list = query_params.get("text", [])
        if not text_list:
            self._log("warning", "⚠️ GET /Talk: text パラメータなし")
            self._send_http_response(client_socket, 400, "Bad Request")
            return

        text = text_list[0]  # 最初の値を取得
        if not text:
            self._log("warning", "⚠️ GET /Talk: text が空")
            self._send_http_response(client_socket, 400, "Bad Request")
            return

        self._log("info", f"💬 GET /Talk 受信: {text[:100]}")
        self._publish_comment_event(text, addr)

        # 200 OK を返す
        self._send_http_response(client_socket, 200, "OK")

    def _handle_talk_post(self, client_socket: socket.socket, addr: tuple, body_data: bytes):
        """
        POST /Talk エンドポイント（実コメント・コメントテスター用）

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
            body_data: POSTボディ（JSON）
        """
        try:
            # JSONをパース
            body_text = body_data.decode("utf-8", errors="ignore")
            data = json.loads(body_text)

            # text フィールドを取得
            text = data.get("text", "")
            if not text:
                self._log("warning", "⚠️ POST /Talk: text フィールドなし")
                self._send_http_response(client_socket, 400, "Bad Request")
                return

            self._log("info", f"💬 POST /Talk 受信: {text[:100]}")
            self._publish_comment_event(text, addr)

            # 200 OK を返す
            self._send_http_response(client_socket, 200, "OK")

        except json.JSONDecodeError as e:
            self._log("error", f"❌ POST /Talk: JSON解析エラー: {e}")
            self._send_http_response(client_socket, 400, "Bad Request - Invalid JSON")
        except Exception as e:
            self._log("error", f"❌ POST /Talk: 処理エラー: {e}")
            self._send_http_response(client_socket, 500, "Internal Server Error")

    def _send_http_response(self, client_socket: socket.socket, status_code: int, status_text: str, body: str = "", content_type: str = "text/plain"):
        """
        HTTPレスポンスを送信

        Args:
            client_socket: クライアントソケット
            status_code: HTTPステータスコード
            status_text: ステータステキスト
            body: レスポンスボディ
            content_type: Content-Type
        """
        try:
            body_bytes = body.encode("utf-8")
            response = (
                f"HTTP/1.1 {status_code} {status_text}\r\n"
                f"Content-Type: {content_type}; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                f"Connection: close\r\n"
                "\r\n"
            ).encode("utf-8") + body_bytes

            client_socket.sendall(response)
        except Exception as e:
            self._log("error", f"❌ HTTPレスポンス送信エラー: {e}")

    def _handle_tcp_binary(self, client_socket: socket.socket, addr: tuple):
        """
        TCPバイナリプロトコル（従来の棒読みちゃんプロトコル）を処理

        Args:
            client_socket: クライアントソケット
            addr: クライアントアドレス
        """
        try:
            while not self._stopped:
                # まず15バイト読み込み（標準の棒読みちゃんプロトコル）
                try:
                    header_15 = self._recv_exact(client_socket, 15)
                    if not header_15:
                        break  # 接続終了
                except Exception as e:
                    self._log("debug", f"ヘッダ読み込みエラー: {e}")
                    break

                # デバッグ: 受信した生データを16進ダンプ
                self._log("debug", f"🔍 受信データ(hex): {header_15.hex()}")
                self._log("debug", f"🔍 受信データ(ascii): {header_15[:15]}")

                try:
                    # 15バイトヘッダー版として解析
                    # Command(2) + Speed(2) + Tone(2) + Volume(2) + Voice(2) + Encoding(1) + Length(4)
                    command, speed, tone, volume, voice, encoding, text_length = struct.unpack("<HhhhhBI", header_15)

                    self._log("debug", f"📦 15バイトヘッダー: cmd={command:04x} enc={encoding} len={text_length}")

                    # 長さチェック
                    if text_length > 10000 or text_length < 0:
                        self._log("warning", f"⚠️ 異常なテキスト長: {text_length}バイト")
                        break

                    # テキストデータを読み込み
                    text_bytes = self._recv_exact(client_socket, text_length)
                    if not text_bytes:
                        self._log("debug", f"⚠️ テキストデータ読み込み失敗: length={text_length}")
                        break

                    # デバッグ: 受信データの16進ダンプ
                    self._log("debug", f"📦 受信データ: {text_bytes.hex()} (encoding={encoding}, len={len(text_bytes)})")

                    # エンコーディング判定
                    # 0: UTF-8, 1: Unicode, 2: Shift_JIS
                    if encoding == 0:
                        text = text_bytes.decode("utf-8", errors="ignore")
                    elif encoding == 2:
                        text = text_bytes.decode("shift_jis", errors="ignore")
                    else:
                        # Unicode（UTF-16LE）または不明な場合はUTF-8でフォールバック
                        try:
                            text = text_bytes.decode("utf-16-le", errors="ignore")
                        except Exception:
                            text = text_bytes.decode("utf-8", errors="ignore")

                    self._log("debug", f"📝 デコード結果: '{text}' (len={len(text)})")

                    text = text.strip()
                    self._log("debug", f"✂️ strip後: '{text}' (len={len(text)})")

                    if text:
                        self._log("info", f"💬 受信: {text[:100]}")
                        self._publish_comment_event(text, addr)
                    else:
                        self._log("warning", f"⚠️ テキストが空です（strip後）")

                except struct.error as e:
                    self._log("error", f"❌ プロトコル解析エラー: {e}")
                    break
                except Exception as e:
                    self._log("error", f"❌ メッセージ処理エラー: {e}")
                    continue

        except Exception as e:
            self._log("error", f"❌ TCPバイナリ処理エラー ({addr}): {e}")

    def _recv_exact(self, sock: socket.socket, length: int) -> Optional[bytes]:
        """
        指定バイト数を確実に受信

        Args:
            sock: ソケット
            length: 受信バイト数

        Returns:
            bytes: 受信データ（失敗時はNone）
        """
        data = b""
        while len(data) < length:
            try:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    return None  # 接続終了
                data += chunk
            except Exception:
                return None
        return data

    def _publish_comment_event(self, text: str, addr: tuple):
        """
        受信したテキストをコメントイベントとして発行

        Args:
            text: 受信テキスト
            addr: クライアントアドレス
        """
        payload = {
            "source": "multi_comment_viewer",
            "platform": "unknown",
            "user_id": "",
            "user_name": "MCV",
            "message": text,
            "raw": {
                "protocol": "bouyomi_compat",
                "remote_addr": f"{addr[0]}:{addr[1]}",
            },
            # 後方互換用
            "text": text,
            "user": "MCV",
        }

        self._publish_comment(payload)

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
                {"level": level, "msg": f"[MCV Bouyomi] {message}"},
                sender=self.__class__.__name__,
            )
        except Exception:
            pass
