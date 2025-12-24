# -*- coding: utf-8 -*-
"""
bouyomi_compat_server.py - 棒読みちゃん互換TCPサーバー

Multi Comment Viewer (MCV) などの棒読みちゃん連携アプリから
コメントを受信し、MessageBus経由でぎゅるるボットに配信する。

プロトコル仕様: docs/BOUYOMI_PROTOCOL_SPEC.md 参照
"""
import asyncio
import struct
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BouyomiCompatServer:
    """
    棒読みちゃん互換TCPサーバー

    MCVからのコメントを受信し、ONECOMME_COMMENTとしてMessageBusに配信する。
    """

    def __init__(self, message_bus, host: str = "0.0.0.0", port: int = 50010):
        """
        初期化

        Args:
            message_bus: MessageBusインスタンス
            host: 待ち受けアドレス（デフォルト: すべてのインターフェース）
            port: 待ち受けポート（デフォルト: 50010）
        """
        self.message_bus = message_bus
        self.host = host
        self.port = port

        self.server: Optional[asyncio.Server] = None
        self.server_task: Optional[asyncio.Task] = None
        self._running = False
        self._shutdown_event = asyncio.Event()

        # 統計
        self.connection_count = 0
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = 0

        logger.info(f"📢 BouyomiCompatServer 初期化: {host}:{port}")

    async def start(self) -> bool:
        """
        サーバー起動

        Returns:
            起動成功時 True
        """
        if self._running:
            logger.warning("⚠️ BouyomiCompatServer は既に起動しています")
            return True

        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port
            )

            self._running = True
            self._shutdown_event.clear()

            # サーバータスク開始
            self.server_task = asyncio.create_task(
                self._run_server(),
                name="bouyomi_compat_server"
            )

            logger.info(f"✅ BouyomiCompatServer 起動成功: {self.host}:{self.port}")
            self._log_to_bus("info", f"TCP待ち受け開始: {self.host}:{self.port}")

            return True

        except Exception as e:
            logger.error(f"❌ BouyomiCompatServer 起動失敗: {e}")
            self._log_to_bus("error", f"TCP起動失敗: {e}")
            return False

    async def stop(self) -> None:
        """サーバー停止"""
        if not self._running:
            return

        try:
            self._running = False
            self._shutdown_event.set()

            # サーバークローズ
            if self.server:
                self.server.close()
                await self.server.wait_closed()

            # タスクキャンセル
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass

            logger.info("✅ BouyomiCompatServer 停止完了")
            self._log_to_bus("info", "TCP待ち受け停止")

        except Exception as e:
            logger.error(f"❌ BouyomiCompatServer 停止エラー: {e}")

    async def _run_server(self) -> None:
        """サーバー実行ループ"""
        try:
            logger.info("📢 BouyomiCompatServer ループ開始")

            # サーバー実行（接続待ち受け）
            await self._shutdown_event.wait()

            logger.info("📢 BouyomiCompatServer ループ終了")

        except asyncio.CancelledError:
            logger.info("📢 BouyomiCompatServer ループキャンセル")
            raise
        except Exception as e:
            logger.error(f"❌ BouyomiCompatServer ループエラー: {e}")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """
        クライアント接続処理

        Args:
            reader: StreamReader
            writer: StreamWriter
        """
        addr = writer.get_extra_info('peername')
        self.connection_count += 1
        conn_id = self.connection_count

        logger.info(f"🔌 BouyomiCompat接続 #{conn_id}: {addr}")
        self._log_to_bus("info", f"接続 #{conn_id}: {addr}")

        try:
            while not self._shutdown_event.is_set():
                # ヘッダー読み込み（最大15バイト）
                header_data = await asyncio.wait_for(
                    reader.read(15),
                    timeout=30.0
                )

                if not header_data:
                    # 接続終了
                    break

                # パケット解析
                result = await self._parse_packet(header_data, reader)

                if result:
                    # MessageBusに配信
                    await self._publish_comment(result, conn_id, addr)
                    self.message_count += 1
                    self.last_message_time = time.time()
                else:
                    self.error_count += 1

        except asyncio.TimeoutError:
            logger.debug(f"📢 接続 #{conn_id} タイムアウト（正常）: {addr}")
        except asyncio.CancelledError:
            logger.debug(f"📢 接続 #{conn_id} キャンセル: {addr}")
            raise
        except Exception as e:
            logger.error(f"❌ 接続 #{conn_id} エラー: {e}")
            self.error_count += 1
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

            logger.info(f"🔌 BouyomiCompat切断 #{conn_id}: {addr}")

    async def _parse_packet(
        self,
        header_data: bytes,
        reader: asyncio.StreamReader
    ) -> Optional[Dict[str, Any]]:
        """
        パケット解析

        Args:
            header_data: ヘッダーデータ（15バイトまたは12バイト）
            reader: 残りのデータを読むためのStreamReader

        Returns:
            解析結果の辞書、または失敗時None
        """
        try:
            header_len = len(header_data)

            # 15バイトヘッダー版を試行
            if header_len >= 15:
                try:
                    command, speed, tone, volume, voice, char_code, msg_length = \
                        struct.unpack('<HHHHHbi', header_data[:15])

                    logger.debug(
                        f"📦 15バイトヘッダー: cmd={command:04x} speed={speed} "
                        f"tone={tone} vol={volume} voice={voice} "
                        f"char={char_code} len={msg_length}"
                    )

                    # メッセージ本文読み込み
                    if msg_length > 0:
                        text_data = await asyncio.wait_for(
                            reader.read(msg_length),
                            timeout=5.0
                        )

                        # 文字コードでデコード
                        text = self._decode_text(text_data, char_code)

                        return {
                            "text": text,
                            "command": command,
                            "speed": speed,
                            "tone": tone,
                            "volume": volume,
                            "voice": voice,
                            "char_code": char_code,
                            "protocol_version": "15byte"
                        }

                except struct.error:
                    pass  # 15バイト版失敗、12バイト版を試行

            # 12バイトヘッダー版を試行
            if header_len >= 12:
                try:
                    command, speed, tone, volume, voice, text_length = \
                        struct.unpack('<HHHHHH', header_data[:12])

                    logger.debug(
                        f"📦 12バイトヘッダー: cmd={command:04x} speed={speed} "
                        f"tone={tone} vol={volume} voice={voice} len={text_length}"
                    )

                    # メッセージ本文読み込み
                    if text_length > 0:
                        text_data = await asyncio.wait_for(
                            reader.read(text_length),
                            timeout=5.0
                        )

                        # Shift_JISでデコード
                        text = text_data.decode('shift_jis', errors='ignore')

                        return {
                            "text": text,
                            "command": command,
                            "speed": speed,
                            "tone": tone,
                            "volume": volume,
                            "voice": voice,
                            "char_code": 2,  # Shift_JIS
                            "protocol_version": "12byte"
                        }

                except struct.error as e:
                    logger.error(f"❌ 12バイトヘッダー解析失敗: {e}")

            # どちらも失敗
            logger.warning(f"⚠️ パケット解析失敗: header_len={header_len}")
            return None

        except Exception as e:
            logger.error(f"❌ パケット解析エラー: {e}")
            return None

    def _decode_text(self, text_data: bytes, char_code: int) -> str:
        """
        文字コード指定でテキストをデコード

        Args:
            text_data: バイト列
            char_code: 文字コード (0=UTF-8, 1=UTF-16LE, 2=Shift_JIS)

        Returns:
            デコードされたテキスト
        """
        try:
            if char_code == 0:
                return text_data.decode('utf-8', errors='ignore')
            elif char_code == 1:
                return text_data.decode('utf-16le', errors='ignore')
            else:  # 2 or default
                return text_data.decode('shift_jis', errors='ignore')
        except Exception as e:
            logger.warning(f"⚠️ デコードエラー(char_code={char_code}): {e}")
            # フォールバック: UTF-8で試行
            try:
                return text_data.decode('utf-8', errors='ignore')
            except:
                return str(text_data)

    async def _publish_comment(
        self,
        parsed: Dict[str, Any],
        conn_id: int,
        addr: Any
    ) -> None:
        """
        解析済みコメントをMessageBusに配信

        Args:
            parsed: 解析結果
            conn_id: 接続ID
            addr: クライアントアドレス
        """
        try:
            text = parsed.get("text", "").strip()
            if not text:
                logger.debug("📢 空テキストのためスキップ")
                return

            # ONECOMME_COMMENT形式でpublish
            payload = {
                "type": "comment",
                "data": {
                    "name": f"MCV#{conn_id}",
                    "comment": text,
                    "id": f"mcv_{int(time.time() * 1000)}_{conn_id}_{self.message_count}",
                    "hasGift": False,
                    "timestamp": int(time.time() * 1000),
                    "isPinned": False,
                    "isMembership": False,
                    "isOwner": False,
                    "service": "MultiCommentViewer",

                    # デバッグ用: プロトコル情報
                    "_bouyomi_speed": parsed.get("speed"),
                    "_bouyomi_tone": parsed.get("tone"),
                    "_bouyomi_volume": parsed.get("volume"),
                    "_bouyomi_voice": parsed.get("voice"),
                    "_bouyomi_protocol": parsed.get("protocol_version"),
                }
            }

            # MessageBusに配信
            self.message_bus.publish(
                "ONECOMME_COMMENT",
                payload,
                sender="bouyomi_compat_server"
            )

            logger.info(f"📨 コメント配信 #{conn_id}: '{text[:50]}...'")
            self._log_to_bus("info", f"コメント受信: '{text[:30]}...'")

        except Exception as e:
            logger.error(f"❌ コメント配信エラー: {e}")

    def _log_to_bus(self, level: str, msg: str) -> None:
        """MessageBusにログ配信"""
        try:
            if self.message_bus:
                self.message_bus.publish(
                    "WEBSOCKET_LOG",
                    {"level": level, "msg": f"[Bouyomi] {msg}"},
                    sender="bouyomi_compat_server"
                )
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """ステータス取得"""
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "connection_count": self.connection_count,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "last_message_time": self.last_message_time,
        }

    def is_running(self) -> bool:
        """実行中かどうか"""
        return self._running


# グローバルインスタンス管理
_server_singleton: Optional[BouyomiCompatServer] = None


async def start_server(message_bus, host: str = "0.0.0.0", port: int = 50010) -> Optional[BouyomiCompatServer]:
    """
    サーバー起動（シングルトン）

    Args:
        message_bus: MessageBusインスタンス
        host: 待ち受けアドレス
        port: 待ち受けポート

    Returns:
        サーバーインスタンス（起動失敗時None）
    """
    global _server_singleton

    try:
        # 既存サーバーがあれば停止
        if _server_singleton and _server_singleton.is_running():
            await _server_singleton.stop()

        # 新規作成
        server = BouyomiCompatServer(message_bus, host, port)
        success = await server.start()

        if success:
            _server_singleton = server
            return server
        else:
            return None

    except Exception as e:
        logger.error(f"❌ Bouyomiサーバー起動エラー: {e}")
        return None


async def stop_server() -> None:
    """サーバー停止"""
    global _server_singleton

    try:
        if _server_singleton:
            await _server_singleton.stop()
    finally:
        _server_singleton = None


def get_server() -> Optional[BouyomiCompatServer]:
    """現在のサーバーインスタンス取得"""
    return _server_singleton


__all__ = [
    "BouyomiCompatServer",
    "start_server",
    "stop_server",
    "get_server",
]
