from __future__ import annotations

from app.services.taskbar_service import TaskbarProgress, average_progress


def test_average_progress_basic():
    assert average_progress([50.0, 100.0]) == 75
    assert average_progress([0.0, 0.0]) == 0


def test_average_progress_empty():
    assert average_progress([]) == 0


def test_average_progress_clamped():
    assert average_progress([120.0, 130.0]) == 100
    assert average_progress([-10.0, -20.0]) == 0


def test_taskbar_progress_calls_are_safe_when_unavailable():
    # A bogus hwnd must never raise from the public methods.
    taskbar = TaskbarProgress(0)
    taskbar.set_progress(50)
    taskbar.set_indeterminate()
    taskbar.clear()
