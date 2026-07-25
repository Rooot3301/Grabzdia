from __future__ import annotations

import app
import app.version


def test_single_version_source():
    assert app.__version__ == app.version.__version__
