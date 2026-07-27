from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from app.ui.widgets import NoWheelComboBox, NoWheelSpinBox


def _wheel_down() -> QWheelEvent:
    """Un cran de molette vers le bas, tel que Qt le livre à un widget."""
    return QWheelEvent(
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_combo_ignores_wheel(qtbot):
    combo = NoWheelComboBox()
    combo.addItems(["un", "deux", "trois"])
    combo.setCurrentIndex(1)
    qtbot.addWidget(combo)
    event = _wheel_down()
    QApplication.sendEvent(combo, event)
    assert combo.currentIndex() == 1
    assert not event.isAccepted()  # doit remonter au QScrollArea parent


def test_spinbox_ignores_wheel(qtbot):
    spin = NoWheelSpinBox()
    spin.setRange(1, 4)
    spin.setValue(2)
    qtbot.addWidget(spin)
    event = _wheel_down()
    QApplication.sendEvent(spin, event)
    assert spin.value() == 2
    assert not event.isAccepted()  # doit remonter au QScrollArea parent


def test_values_are_still_settable(qtbot):
    combo = NoWheelComboBox()
    combo.addItems(["un", "deux"])
    spin = NoWheelSpinBox()
    spin.setRange(0, 10)
    qtbot.addWidget(combo)
    qtbot.addWidget(spin)
    combo.setCurrentIndex(1)
    spin.setValue(7)
    assert combo.currentIndex() == 1
    assert spin.value() == 7


def test_focus_policy_is_strong(qtbot):
    """WheelFocus (défaut) laisse la molette voler le focus au survol."""
    combo = NoWheelComboBox()
    spin = NoWheelSpinBox()
    qtbot.addWidget(combo)
    qtbot.addWidget(spin)
    assert combo.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert spin.focusPolicy() == Qt.FocusPolicy.StrongFocus
