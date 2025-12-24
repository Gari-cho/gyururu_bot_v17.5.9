# -*- coding: utf-8 -*-
"""
Connectors Package - v17.5 Multi Comment Bridge

複数のコメント取得元（OneComme旧/新、マルチコメントビューワー、任意URL）を
統一的に扱うためのコネクタパッケージです。
"""

from .base import BaseCommentConnector
from .onecomme_legacy import OneCommeLegacyConnector
from .onecomme_new import OneCommeNewConnector
from .multiviewer import MultiViewerConnector
from .manual_connector import ManualConnector
from .bouyomi_compat_server import BouyomiCompatServerConnector
from .tcp_comment_client import TCPCommentClientConnector

__all__ = [
    "BaseCommentConnector",
    "OneCommeLegacyConnector",
    "OneCommeNewConnector",
    "MultiViewerConnector",
    "ManualConnector",
    "BouyomiCompatServerConnector",
    "TCPCommentClientConnector",
]
