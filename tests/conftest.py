import os
import tempfile

# Qt must run headless during tests. Set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox all app data: tests construct real services/MainWindow, which would
# otherwise read and WRITE the user's real %APPDATA%/%LOCALAPPDATA% (settings,
# history, queue, logs). Redirect them to a throwaway directory.
_sandbox = tempfile.mkdtemp(prefix="mediagrab-tests-")
os.environ["APPDATA"] = _sandbox
os.environ["LOCALAPPDATA"] = _sandbox
