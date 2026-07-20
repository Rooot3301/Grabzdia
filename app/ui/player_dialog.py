from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def _format_time(ms: int) -> str:
    seconds = max(0, ms // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class PlayerDialog(QDialog):
    """Minimal embedded video/audio player for a local file."""

    def __init__(self, path: str, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or "Lecture")
        self.resize(900, 580)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget(self)
        self.video.setMinimumHeight(360)
        self.player.setVideoOutput(self.video)

        self.play_button = QPushButton("Pause")
        self.play_button.setObjectName("primaryButton")
        self.play_button.clicked.connect(self._toggle)

        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(self.player.setPosition)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("mutedText")

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(110)
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(self.play_button)
        controls.addWidget(self.position, 1)
        controls.addWidget(self.time_label)
        controls.addWidget(QLabel("🔊"))
        controls.addWidget(self.volume)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.video, 1)
        layout.addLayout(controls)

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(self._on_error)

        self.audio.setVolume(0.8)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("Pause" if playing else "Lire")

    def _on_position(self, position: int) -> None:
        if not self.position.isSliderDown():
            self.position.setValue(position)
        self.time_label.setText(f"{_format_time(position)} / {_format_time(self.player.duration())}")

    def _on_duration(self, duration: int) -> None:
        self.position.setRange(0, duration)

    def _on_error(self, _error, message: str) -> None:
        self.time_label.setText(message or "Lecture impossible")

    def closeEvent(self, event) -> None:
        self.player.stop()
        event.accept()
