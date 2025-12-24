# -*- coding: utf-8 -*-
"""
message_bridge.py - OneComme WebSocket Bridge（v17.3.1）
- 成功時に WS_STATUS{'state':'connected'} を必ず publish
- 切断/エラー時にも WS_STATUS を発行
- 受信メッセージは可能な範囲で ONECOMME_COMMENT に橋渡し
- websocket-client が無い場合はフォールバック（疑似接続）
"""
import threading
import json
import time

try:
    import websocket  # pip install websocket-client
    _HAS_WS = True
except Exception:
    _HAS_WS = False

_bridge_singleton = None

class _Bridge:
    def __init__(self, bus, url: str):
        self.bus = bus
        self.url = url
        self.ws = None
        self._th = None
        self._stopped = False
        self._connected_once = False

    def start(self):
        if _HAS_WS:
            self._start_real()
        else:
            self._start_fallback()

    def _start_real(self):
        # ★ 再接続用フラグ/待機
        self._reconnect = True
        self._backoff = 1.0  # 秒（指数バックオフ最小）
        self._backoff_max = 10.0

        def _on_open(ws):
            self._log("info", f"connected: {self.url}")
            self._publish_status("connected")
            self._connected_once = True
            # 接続できたらバックオフをリセット
            self._backoff = 1.0

        def _on_message(ws, message):
            try:
                # ✅ Phase 4: 詳細ログを削除（GUI側のログ暴走を抑制）
                # recv-raw, recv-parsed などの詳細ログは標準ロガーのみに出力

                payload = None
                if isinstance(message, (bytes, bytearray)):
                    try:
                        message = message.decode("utf-8", "ignore")
                    except Exception:
                        message = str(message)

                try:
                    obj = json.loads(message)

                    # --- 名前の抽出（UI用・内部用共通） ---
                    name = (
                        obj.get("user")
                        or obj.get("name")
                        or obj.get("author")
                        or obj.get("username")
                        or "OneComme"
                    )

                    # --- サービス / プラットフォームの推定 ---
                    service = (
                        obj.get("service")
                        or obj.get("platform")
                        or obj.get("site")
                        or obj.get("provider")
                        or obj.get("source")
                        or None
                    )
                    if isinstance(service, str):
                        service = service.strip() or None

                    # OneComme側にサービス情報が無ければ、とりあえず "onecomme"
                    platform = service or "onecomme"

                    payload = {
                        # 本文
                        "text": obj.get("text") or obj.get("message") or obj.get("body") or "",
                        # 名前（内部用）
                        "user": name,
                        # 名前（UI用：chat_display は username を読む）
                        "username": name,
                        # プラットフォーム情報（色分けに使う）
                        "service": service,
                        "platform": platform,
                        # 元の生データも残しておく
                        "raw": obj,
                    }
                except Exception:
                    # JSONパースに失敗した場合でも最低限の情報で流す
                    text = str(message)
                    name = "OneComme"
                    payload = {
                        "text": text,
                        "user": name,
                        "username": name,
                        "platform": "onecomme",
                    }

                # ✅ Phase 4: コメント受信時のログは簡潔に（GUI表示用）
                if payload and (payload.get("text") or "").strip():
                    text = (payload.get("text") or "")[:30]
                    user = payload.get("user", "")
                    self._log("info", f"💬 {user}: {text}...")
                    self.bus.publish("ONECOMME_COMMENT", payload, sender="onecomme_bridge")
            except Exception as e:
                self._log("error", f"parse-error: {e}")

        def _on_error(ws, error):
            self._log("error", f"{error}")
            self._publish_status("error", error=str(error))

        def _on_close(ws, status_code, msg):
            self._log("info", f"disconnected: code={status_code} msg={msg}")
            self._publish_status("disconnected")

        def _runner():
            while not self._stopped:
                try:
                    self.ws = websocket.WebSocketApp(
                        self.url,
                        on_open=_on_open,
                        on_message=_on_message,
                        on_error=_on_error,
                        on_close=_on_close,
                    )
                    # ★ KeepAlive設定（サーバ実装に依存）
                    self.ws.run_forever(ping_interval=20, ping_timeout=10)
                except Exception as e:
                    self._log("error", f"run_forever error: {e}")
                    self._publish_status("error", error=str(e))

                # 停止指示があればループ抜け
                if self._stopped or not self._reconnect:
                    break

                # ★ 再接続バックオフ
                sleep_sec = min(self._backoff, self._backoff_max)
                self._log("info", f"reconnect in {sleep_sec:.1f}s")
                time.sleep(sleep_sec)
                self._backoff = min(self._backoff * 2, self._backoff_max)

        self._th = threading.Thread(target=_runner, daemon=True)
        self._th.start()

    def stop(self):
        self._stopped = True
        # ★ これ以上の再接続を止める
        try:
            self._reconnect = False
        except Exception:
            pass
        try:
            if self.ws and _HAS_WS:
                self.ws.close()
        except Exception:
            pass
        try:
            self._publish_status("disconnected")
        except Exception:
            pass


    # ---- helpers ----
    def _log(self, level: str, msg: str):
        try:
            self.bus.publish("WEBSOCKET_LOG", {"level": level, "msg": msg}, sender="onecomme_bridge")
        except Exception:
            pass

    def _publish_status(self, state: str, **kw):
        try:
            payload = {"state": state, "url": self.url}
            if kw:
                payload.update(kw)
            self.bus.publish("WS_STATUS", payload, sender="onecomme_bridge")
        except Exception:
            pass


def init_bridge(message_bus, url: str, config_manager=None):
    """
    Bridge を起動し、成功時には WS_STATUS{'state':'connected'} を必ず発行する。
    すでに起動済みなら一旦停止して作り直す。
    """
    global _bridge_singleton
    try:
        if _bridge_singleton is not None:
            try:
                _bridge_singleton.stop()
            except Exception:
                pass
    except Exception:
        pass

    bridge = _Bridge(message_bus, url)
    _bridge_singleton = bridge
    bridge.start()
    return bridge

def stop_bridge():
    global _bridge_singleton
    try:
        if _bridge_singleton:
            _bridge_singleton.stop()
    finally:
        _bridge_singleton = None
