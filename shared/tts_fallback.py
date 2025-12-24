# -*- coding: utf-8 -*-
"""
shared.tts_fallback
v17.3 minimal: Windows SAPI の簡易ラッパ & フォールバック
- speak_text(text, voice=None, rate=1.0, volume=1.0) をエクスポート（必須互換）
- SAPI が使えなければログだけ出して False を返す
"""

import logging
logger = logging.getLogger(__name__)

try:
    import win32com.client  # pywin32
    import pythoncom  # COM初期化用
    _HAS_SAPI = True
except Exception:
    _HAS_SAPI = False

# グローバルな SAPI オブジェクトは都度生成（COM 参照保持の不具合回避用）
def _create_sapi():
    if not _HAS_SAPI:
        return None
    try:
        # ✅ マルチスレッド環境で COM を初期化（必須）
        try:
            pythoncom.CoInitialize()
        except Exception:
            # すでに初期化されている場合は無視
            pass

        return win32com.client.Dispatch("SAPI.SpVoice")
    except Exception as e:
        logger.error(f"SAPI Dispatch error: {e}")
        return None

def is_available() -> bool:
    """OS標準TTS（SAPI）が利用可能かを返す。"""
    return _HAS_SAPI and (_create_sapi() is not None)

def speak_text(text: str, voice: str | None = None, rate: float = 1.0, volume: float = 1.0) -> bool:
    """
    必須互換API：
    - 他モジュールは from shared.tts_fallback import speak_text を期待
    - True=再生試行（成功） / False=未実行 or 失敗

    Params:
        text   : 再生するテキスト
        voice  : （未使用）将来の音声切替用プレースホルダ
        rate   : -10～+10 相当を想定（1.0 を 0 とみなして丸め）
        volume : 0.0～1.0 を 0～100 に変換
    """
    if not text or not isinstance(text, str):
        return False

    spk = _create_sapi()
    if spk is None:
        logger.info(f"🔈 (fallback log only) {text[:40]}...")
        return False  # フォールバック（実音声なし）

    # 速度と音量をSAPI値へ
    try:
        # rate: 1.0 を 0 とみなして -10～+10 に丸め（ざっくり）
        sapi_rate = 0
        try:
            # 0.5→-5, 1.0→0, 1.5→+5 くらいの感覚
            sapi_rate = max(-10, min(10, int(round((rate - 1.0) * 10))))
        except Exception:
            sapi_rate = 0

        sapi_volume = 100
        try:
            sapi_volume = max(0, min(100, int(round(volume * 100))))
        except Exception:
            sapi_volume = 100

        spk.Rate = sapi_rate
        spk.Volume = sapi_volume
    except Exception as e:
        logger.warning(f"SAPI param set error: {e}")

    try:
        spk.Speak(text)
        logger.info(f"🔊 OS TTS音声再生: {text[:40]}...")
        return True
    except Exception as e:
        logger.error(f"SAPI Speak error: {e}")
        return False

def stop_speaking() -> None:
    """将来の停止API用プレースホルダ。現状は未実装（SAPIは即時停止APIが限定的）。"""
    return None

__all__ = ["speak_text", "is_available", "stop_speaking"]
