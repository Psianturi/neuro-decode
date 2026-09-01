from __future__ import annotations

from app.notification_store import NotificationStore
from app.profile_store import ProfileStore
from app.push_device_store import PushDeviceStore
from app.push_sender import PushSender
from app.rule_debug_store import RuleDebugStore
from app.session_store import SessionStore
from app.settings import get_settings

LATEST_SESSION_MAX_ITEMS = 10

settings = get_settings()

session_store = SessionStore(
    firestore_enabled=settings.firestore_enabled,
    firestore_collection=settings.firestore_collection,
    firestore_event_collection=settings.firestore_event_collection,
    firestore_project=settings.firestore_project,
    max_memory_items=LATEST_SESSION_MAX_ITEMS,
)
profile_store = ProfileStore(
    firestore_enabled=settings.firestore_enabled,
    profile_collection=settings.firestore_profile_collection,
    profile_memory_collection=settings.firestore_profile_memory_collection,
    firestore_project=settings.firestore_project,
)
notification_store = NotificationStore(
    firestore_enabled=settings.firestore_enabled,
    notification_collection=settings.firestore_notification_collection,
    firestore_project=settings.firestore_project,
)
rule_debug_store = RuleDebugStore(max_items=settings.admin_debug_max_items)
push_device_store = PushDeviceStore(
    firestore_enabled=settings.firestore_enabled,
    device_collection=settings.firestore_push_device_collection,
    firestore_project=settings.firestore_project,
)
push_sender = PushSender(enabled=settings.fcm_enabled)
