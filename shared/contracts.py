#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ぎゅるるボット v16 Phase3 - 統一契約定義（修正版）
全レイヤー共通のデータ構造と正規化関数

🔥 修正内容:
- safe_service_update()の引数仕様統一
- 辞書形式でのupdates受け取りに変更
- エラーハンドリング強化
- ServiceState更新の安全性向上

✅ ServiceState統一定義
✅ 正規化関数統一
✅ インポート一本化対応
✅ extract_event_name エクスポート
✅ 引数重複エラー完全修正

Author: Claude & ユーザー
Version: 16.3.3-fixed
License: MIT
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Dict, Union
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServiceState:
    """
    サービス状態の統一データクラス
    全てのタブ・UI・マネージャでこの型のみを使用
    """
    key: str
    enabled: bool = False
    connected: bool = False
    name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def update_state(self, *, enabled: Optional[bool] = None, 
                     connected: Optional[bool] = None, **kwargs):
        """
        状態更新メソッド
        
        Args:
            enabled: 有効状態
            connected: 接続状態
            **kwargs: その他のメタデータ
        """
        if enabled is not None:
            self.enabled = bool(enabled)
        if connected is not None:
            self.connected = bool(connected)
        if kwargs:
            self.meta.update(kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'key': self.key,
            'enabled': self.enabled,
            'connected': self.connected,
            'name': self.name,
            'meta': self.meta.copy()
        }
    
    def __str__(self) -> str:
        status = "🟢" if self.connected else "🔴" if self.enabled else "⚫"
        return f"{status} {self.name or self.key} (enabled={self.enabled}, connected={self.connected})"


def normalize_service(key: str, raw: Any) -> ServiceState:
    """
    🔧 統一サービス正規化関数
    dict/オブジェクト/その他の形式を ServiceState に統一変換
    
    Args:
        key: サービスキー
        raw: 生データ（dict、オブジェクト、その他）
        
    Returns:
        ServiceState: 正規化されたサービス状態
    """
    try:
        # 既に ServiceState なら そのまま返す
        if isinstance(raw, ServiceState):
            return raw
        
        # dict の場合
        if isinstance(raw, dict):
            return ServiceState(
                key=key,
                enabled=bool(raw.get("enabled", False)),
                connected=bool(raw.get("connected", False)),
                name=str(raw.get("name", key)),
                meta=raw.get("meta", {})
            )
        
        # オブジェクトの場合 - 属性を探す
        if hasattr(raw, '__dict__'):
            enabled = getattr(raw, 'enabled', getattr(raw, 'is_enabled', False))
            connected = getattr(raw, 'connected', getattr(raw, 'is_connected', False))
            name = getattr(raw, 'name', key)
            
            return ServiceState(
                key=key,
                enabled=bool(enabled),
                connected=bool(connected),
                name=str(name)
            )
        
        # その他の場合はデフォルト値
        logger.warning(f"⚠️ 不明なサービス形式を正規化: {type(raw)} -> ServiceState")
        return ServiceState(key=key, enabled=False, connected=False, name=key)
        
    except Exception as e:
        logger.error(f"❌ サービス正規化エラー ({key}): {e}")
        return ServiceState(key=key, enabled=False, connected=False, name=key)


def normalize_services_dict(services: Dict[str, Any]) -> Dict[str, ServiceState]:
    """
    サービス辞書の一括正規化
    
    Args:
        services: 生サービス辞書
        
    Returns:
        Dict[str, ServiceState]: 正規化されたサービス辞書
    """
    try:
        result = {}
        for key, value in services.items():
            result[key] = normalize_service(key, value)
        return result
        
    except Exception as e:
        logger.error(f"❌ サービス辞書正規化エラー: {e}")
        return {}


def safe_service_update(service: ServiceState, updates: Dict[str, Any]) -> bool:
    """
    安全なサービス状態更新（修正版）
    
    🔥 修正内容:
    - 引数を辞書形式のupdatesのみに統一
    - enabled, connected等の個別引数を廃止
    - エラーハンドリング強化
    - 戻り値でのフィードバック追加
    
    Args:
        service: 対象サービス（ServiceStateオブジェクト）
        updates: 更新データの辞書
            例: {'enabled': True, 'connected': False, 'name': '新しい名前'}
        
    Returns:
        bool: 更新成功フラグ
        
    Examples:
        >>> service = ServiceState(key="test")
        >>> success = safe_service_update(service, {'enabled': True, 'connected': False})
        >>> print(success)  # True
    """
    try:
        if not isinstance(service, ServiceState):
            logger.error(f"❌ 無効なサービスオブジェクト: {type(service)}")
            return False
        
        if not isinstance(updates, dict):
            logger.error(f"❌ 無効な更新データ: {type(updates)}")
            return False
        
        # enabled/connected の直接更新
        if 'enabled' in updates:
            service.enabled = bool(updates['enabled'])
        
        if 'connected' in updates:
            service.connected = bool(updates['connected'])
        
        if 'name' in updates:
            service.name = str(updates['name'])
        
        # meta の更新（予約キー以外）
        reserved_keys = {'enabled', 'connected', 'name', 'key'}
        meta_updates = {k: v for k, v in updates.items() if k not in reserved_keys}
        
        if meta_updates:
            if not isinstance(service.meta, dict):
                service.meta = {}
            service.meta.update(meta_updates)
        
        logger.debug(f"✅ サービス状態更新成功 ({service.key}): {updates}")
        return True
        
    except Exception as e:
        logger.error(f"❌ サービス状態更新エラー ({service.key if hasattr(service, 'key') else 'unknown'}): {e}")
        return False


def extract_event_name(event: Any) -> str:
    """
    イベント名抽出関数（統一版）
    Enum/文字列/オブジェクト混在対応
    
    Args:
        event: イベント（Enum、文字列、オブジェクト）
        
    Returns:
        str: イベント名
    """
    try:
        # 文字列の場合はそのまま
        if isinstance(event, str):
            return event
        
        # Enum の場合は name 属性
        if hasattr(event, 'name'):
            return str(event.name)
        
        # value 属性がある場合
        if hasattr(event, 'value'):
            return str(event.value)
        
        # その他の場合は文字列変換
        return str(event)
        
    except Exception as e:
        logger.warning(f"⚠️ イベント名抽出エラー: {e} - 'unknown_event' を返します")
        return "unknown_event"


def normalize_message_payload(payload: Any) -> Dict[str, Any]:
    """
    メッセージペイロード正規化
    
    Args:
        payload: 生ペイロード
        
    Returns:
        Dict[str, Any]: 正規化されたペイロード
    """
    try:
        if payload is None:
            return {}
        
        if isinstance(payload, dict):
            return payload.copy()
        
        if hasattr(payload, '__dict__'):
            return payload.__dict__.copy()
        
        # プリミティブ型の場合
        return {'data': payload}
        
    except Exception as e:
        logger.warning(f"⚠️ ペイロード正規化エラー: {e}")
        return {'error': str(e)}


def validate_service_state(service: Any, service_key: str = "unknown") -> bool:
    """
    サービス状態の妥当性検証
    
    Args:
        service: 検証対象サービス
        service_key: サービスキー（ログ用）
        
    Returns:
        bool: 妥当性
    """
    try:
        if isinstance(service, ServiceState):
            # ServiceState の場合は基本的に妥当
            return True
        
        if isinstance(service, dict):
            # dict の場合は必要なキーがあるかチェック
            required_keys = ['enabled', 'connected']
            missing_keys = [key for key in required_keys if key not in service]
            
            if missing_keys:
                logger.debug(f"🔍 dict型サービス不完全 ({service_key}): 不足キー {missing_keys}")
                return False
            
            return True
        
        # オブジェクトの場合は属性チェック
        if hasattr(service, 'enabled') or hasattr(service, 'is_enabled'):
            return True
        
        logger.debug(f"🔍 不明なサービス形式 ({service_key}): {type(service)}")
        return False
        
    except Exception as e:
        logger.warning(f"⚠️ サービス状態検証エラー ({service_key}): {e}")
        return False


def get_service_summary(services: Dict[str, ServiceState]) -> Dict[str, Any]:
    """
    サービス状態サマリー取得
    
    Args:
        services: サービス辞書
        
    Returns:
        Dict[str, Any]: サマリー情報
    """
    try:
        total = len(services)
        enabled = sum(1 for s in services.values() if s.enabled)
        connected = sum(1 for s in services.values() if s.connected)
        
        return {
            'total_services': total,
            'enabled_services': enabled,
            'connected_services': connected,
            'disconnected_services': enabled - connected,
            'disabled_services': total - enabled,
            'service_keys': list(services.keys()),
            'connected_services_list': [
                key for key, service in services.items() 
                if service.connected
            ],
            'health_percentage': (connected / max(enabled, 1)) * 100 if enabled > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"❌ サービスサマリー取得エラー: {e}")
        return {
            'error': str(e),
            'total_services': len(services) if services else 0
        }


# 🚀 便利な定数・エイリアス
class ServiceKeys:
    """よく使われるサービスキー定数"""
    WEBSOCKET = "websocket"
    MQTT = "mqtt"
    VOICE = "voice"
    CHAT = "chat"
    AI_RESPONSE = "ai_response"
    LOG = "log"
    ONECOMME = "onecomme"
    MESSAGEBUS = "messagebus"  # ✅ 追加: MessageBus統合対応
    VOICEVOX = "voicevox"

# 🔥 新機能: バッチ更新サポート
def batch_service_update(services: Dict[str, ServiceState], 
                        updates: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
    """
    複数サービスの一括更新
    
    Args:
        services: サービス辞書
        updates: サービスごとの更新データ
            例: {'onecomme': {'enabled': True}, 'voicevox': {'connected': False}}
    
    Returns:
        Dict[str, bool]: サービス別の更新成功フラグ
    """
    results = {}
    
    try:
        for service_key, update_data in updates.items():
            if service_key in services:
                service = services[service_key]
                success = safe_service_update(service, update_data)
                results[service_key] = success
                
                if success:
                    logger.info(f"✅ バッチ更新成功: {service_key}")
                else:
                    logger.warning(f"⚠️ バッチ更新失敗: {service_key}")
            else:
                logger.warning(f"⚠️ 未知のサービス: {service_key}")
                results[service_key] = False
        
        return results
        
    except Exception as e:
        logger.error(f"❌ バッチ更新エラー: {e}")
        return {key: False for key in updates.keys()}

# エクスポート一覧（明示的に公開API定義）
__all__ = [
    'ServiceState',
    'normalize_service', 
    'normalize_services_dict',
    'safe_service_update',  # 🔥 修正版
    'extract_event_name',
    'normalize_message_payload',
    'validate_service_state',
    'get_service_summary',
    'ServiceKeys',
    'batch_service_update'  # 🔥 新機能
]


if __name__ == "__main__":
    # 🧪 修正版テスト
    import json
    
    print("🧪 contracts.py 修正版テスト開始")
    
    # ServiceState作成テスト
    service = ServiceState(key="test_service")
    print(f"✅ ServiceState作成: {service}")
    
    # 修正版safe_service_update テスト
    print("\n🔧 safe_service_update修正版テスト:")
    
    # 正常ケース
    updates1 = {'enabled': True, 'connected': False, 'name': 'テストサービス'}
    result1 = safe_service_update(service, updates1)
    print(f"  テスト1 - 正常更新: {result1} -> {service}")
    
    # 部分更新
    updates2 = {'connected': True}
    result2 = safe_service_update(service, updates2)
    print(f"  テスト2 - 部分更新: {result2} -> {service}")
    
    # エラーケース
    result3 = safe_service_update("invalid", {'enabled': True})
    print(f"  テスト3 - 無効サービス: {result3}")
    
    result4 = safe_service_update(service, "invalid_updates")
    print(f"  テスト4 - 無効更新データ: {result4}")
    
    # バッチ更新テスト
    print("\n📦 バッチ更新テスト:")
    services = {
        'onecomme': ServiceState(key='onecomme', name='わんコメ'),
        'voicevox': ServiceState(key='voicevox', name='VOICEVOX')
    }
    
    batch_updates = {
        'onecomme': {'enabled': True, 'connected': True},
        'voicevox': {'enabled': True, 'connected': False}
    }
    
    batch_results = batch_service_update(services, batch_updates)
    print(f"  バッチ更新結果: {batch_results}")
    
    for key, service in services.items():
        print(f"  {key}: {service}")
    
    # サマリー取得テスト
    print("\n📊 サマリーテスト:")
    summary = get_service_summary(services)
    print(f"  サマリー: {json.dumps(summary, ensure_ascii=False, indent=2)}")
    
    print("\n✅ contracts.py修正版テスト完了")