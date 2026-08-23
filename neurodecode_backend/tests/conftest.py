from __future__ import annotations

import os

# Must be set before app.state (and anything importing it) is first imported,
# since it reads settings once at module load time.
os.environ.setdefault("NEURODECODE_FIRESTORE_ENABLED", "0")
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
