from __future__ import annotations

try:
    import firebase_admin
except Exception:
    firebase_admin = None


def ensure_firebase_admin_initialized() -> bool:
    """Initialize the default firebase_admin app once, shared by push and auth.

    Returns False if the firebase_admin package isn't installed. Safe to call
    repeatedly — only the first call actually initializes anything.
    """
    if firebase_admin is None:
        return False
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return True
