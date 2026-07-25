"""Migration unique des données de l'ancienne app MediaGrab vers Grabzdia.

Au premier lancement de Grabzdia, si les dossiers de données Grabzdia n'existent
pas encore mais que ceux de MediaGrab existent, on les recopie pour que
l'utilisateur ne perde ni ses réglages/historique ni les binaires déjà
téléchargés (yt-dlp/FFmpeg). Opération idempotente : elle ne s'exécute qu'une
fois, tant que la cible n'existe pas.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.utils.paths import appdata_dir, local_appdata_dir

# Nom historique de l'ancienne application (à conserver littéralement pour
# retrouver les données existantes des utilisateurs MediaGrab).
_LEGACY_NAME = "MediaGrab"


def should_migrate(new_dir: Path, legacy_dir: Path) -> bool:
    return legacy_dir.is_dir() and not new_dir.exists()


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)


def migrate_legacy_data(new_roaming: Path, new_local: Path, legacy_roaming: Path, legacy_local: Path) -> bool:
    migrated = False
    for legacy_dir, new_dir in ((legacy_roaming, new_roaming), (legacy_local, new_local)):
        if should_migrate(new_dir, legacy_dir):
            _copy_tree(legacy_dir, new_dir)
            migrated = True
    return migrated


def run_migration() -> bool:
    new_roaming = appdata_dir()
    new_local = local_appdata_dir()
    legacy_roaming = new_roaming.parent / _LEGACY_NAME
    legacy_local = new_local.parent / _LEGACY_NAME
    try:
        did = migrate_legacy_data(new_roaming, new_local, legacy_roaming, legacy_local)
        if did:
            logging.info("Données MediaGrab migrées vers Grabzdia.")
        return did
    except OSError as error:
        logging.warning("Migration des données ignorée : %s", error)
        return False
