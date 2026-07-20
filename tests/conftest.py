import os

# Qt must run headless during tests. Set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
