# -*- coding: utf-8 -*-
"""
tab_streamer_profile パッケージ
- v17系のタブ検出規約に従い、create_tab / create_config_tab / create_streamer_profile_tab を公開
- App / TabApp クラスエイリアスも提供
"""

from .app import (
    StreamerProfileTab,
    create_streamer_profile_tab,
    create_streamer_profile_tab as create_tab,
    create_streamer_profile_tab as create_config_tab,
    App,
    TabApp,
)

__all__ = [
    "StreamerProfileTab",
    "create_streamer_profile_tab",
    "create_tab",
    "create_config_tab",
    "App",
    "TabApp",
]
