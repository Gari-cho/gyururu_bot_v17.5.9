# re-export bridges symbols
try:
    from .streamer_profile_message_bridge import StreamerProfileMessageBridge
except Exception:
    # keep import errors soft to allow app to boot without this bridge
    StreamerProfileMessageBridge = None
