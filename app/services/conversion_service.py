"""Conversion après téléchargement : arguments FFmpeg, choix d'encodeur,
chemins et règles de remplacement de l'original. Logique pure, sans Qt.

Spec : docs/superpowers/specs/2026-11-23-conversion-montage-design.md
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

PRESET_LABELS: dict[str, str] = {"": "Aucune", "edit": "Montage (H.264)", "compact": "Compacte (H.265)"}

_ORDERS: dict[str, list[str]] = {
    "edit": ["h264_nvenc", "h264_amf", "h264_qsv", "libx264"],
    "compact": ["hevc_nvenc", "hevc_amf", "hevc_qsv", "libx265"],
}

# Réglages qualité par encodeur. Montage : qualité visuellement transparente ;
# Compacte : environ moitié de la taille d'un H.264 équivalent.
_ENCODER_ARGS: dict[str, list[str]] = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "21", "-b:v", "0"],
    "hevc_nvenc": ["-c:v", "hevc_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "27", "-b:v", "0", "-tag:v", "hvc1"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22"],
    "hevc_amf": ["-c:v", "hevc_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "25", "-qp_p", "27", "-tag:v", "hvc1"],
    "h264_qsv": ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "21"],
    "hevc_qsv": ["-c:v", "hevc_qsv", "-preset", "medium", "-global_quality", "26", "-tag:v", "hvc1"],
    "libx264": ["-c:v", "libx264", "-preset", "medium", "-crf", "20"],
    "libx265": ["-c:v", "libx265", "-preset", "medium", "-crf", "25", "-tag:v", "hvc1"],
}

ENCODER_LABELS: dict[str, str] = {
    encoder: (
        "GPU NVIDIA" if encoder.endswith("_nvenc")
        else "GPU AMD" if encoder.endswith("_amf")
        else "GPU Intel" if encoder.endswith("_qsv")
        else "processeur"
    )
    for encoder in _ENCODER_ARGS
}

LARGER_NOTE = "Conversion plus lourde que l’original : original conservé."


class ConversionService:
    # Premier encodeur qui a fonctionné, par préréglage, pour la session :
    # les conversions suivantes partent directement dessus.
    preferred: ClassVar[dict[str, str]] = {}

    @staticmethod
    def encoder_order(preset: str) -> list[str]:
        if preset not in _ORDERS:
            raise ValueError(f"Préréglage de conversion inconnu : {preset!r}")
        order = list(_ORDERS[preset])
        first = ConversionService.preferred.get(preset)
        if first in order:
            order.remove(first)
            order.insert(0, first)
        return order

    @staticmethod
    def encoder_args(encoder: str) -> list[str]:
        return list(_ENCODER_ARGS[encoder])

    @staticmethod
    def ffmpeg_arguments(source: Path, temp: Path, encoder: str) -> list[str]:
        return [
            "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1", "-y",
            "-i", str(source),
            # 0:V = flux vidéo hors images attachées (miniature intégrée).
            "-map", "0:V:0", "-map", "0:a?", "-map", "0:s?",
            *ConversionService.encoder_args(encoder),
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr",
            "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
            "-map_metadata", "0", "-movflags", "+faststart",
            str(temp),
        ]

    @staticmethod
    def probe_arguments(source: Path) -> list[str]:
        return ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)]

    @staticmethod
    def target_path(source: Path) -> Path:
        return source.with_suffix(".mp4")

    @staticmethod
    def temp_path(source: Path) -> Path:
        return source.with_name(source.stem + ".converting.mp4")

    @staticmethod
    def finalize(source: Path, temp: Path, preset: str) -> tuple[Path, str]:
        """Remplace l'original par le fichier converti selon le préréglage.

        Montage : remplace toujours (le but est la compatibilité). Compacte :
        seulement si le résultat est plus léger. Renvoie (chemin final, note).
        """
        if preset == "compact" and temp.stat().st_size >= source.stat().st_size:
            temp.unlink(missing_ok=True)
            return source, LARGER_NOTE
        target = ConversionService.target_path(source)
        os.replace(temp, target)
        if source != target:
            source.unlink(missing_ok=True)
        return target, ""
