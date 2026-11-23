from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.services.disk_service import DiskService

logger = logging.getLogger(__name__)

_COINIT_APARTMENTTHREADED = 0x2


class ExplorerService:
    """« Ouvrir le dossier » qui sélectionne le fichier téléchargé.

    Ordre de repli : fichier sélectionné dans l'Explorateur → dossier du fichier
    → dossier de destination. Renvoie False si rien n'existe sur le disque, pour
    que l'appelant décide quoi afficher.
    """

    @staticmethod
    def reveal(final_path: str, destination: str = "") -> bool:
        media = DiskService.resolve_media_path(final_path, destination)
        if media and ExplorerService._select_file(Path(media)):
            return True
        for folder in ExplorerService._folder_candidates(final_path, destination, media):
            if folder.is_dir():
                return ExplorerService._open_folder(folder)
        return False

    @staticmethod
    def _folder_candidates(final_path: str, destination: str, media: str | None) -> list[Path]:
        candidates: list[Path] = []
        if media:
            candidates.append(Path(media).parent)
        if final_path:
            path = Path(final_path)
            candidates += [path, path.parent]
        if destination:
            candidates.append(Path(destination))
        return candidates

    @staticmethod
    def _open_folder(folder: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @staticmethod
    def _select_file(path: Path) -> bool:
        """Ouvre l'Explorateur sur le dossier avec `path` sélectionné.

        Passe par l'API shell native plutôt que `explorer /select,` : les titres
        de vidéos contiennent souvent des virgules, guillemets ou caractères
        Unicode que la ligne de commande d'explorer.exe interprète mal.
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            from ctypes import wintypes

            shell32 = ctypes.WinDLL("shell32")
            ole32 = ctypes.WinDLL("ole32")
            shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
            shell32.ILCreateFromPathW.restype = ctypes.c_void_p
            shell32.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
            shell32.SHOpenFolderAndSelectItems.restype = ctypes.c_long
            shell32.ILFree.argtypes = [ctypes.c_void_p]
            shell32.ILFree.restype = None
            ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
            ole32.CoInitializeEx.restype = ctypes.c_long

            # Qt initialise déjà OLE sur le thread GUI ; on équilibre seulement
            # ce qu'on ouvre nous-mêmes (S_OK / S_FALSE).
            init = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
            try:
                pidl = shell32.ILCreateFromPathW(str(path.resolve()))
                if not pidl:
                    return False
                try:
                    return shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0) >= 0
                finally:
                    shell32.ILFree(pidl)
            finally:
                if init >= 0:  # pas RPC_E_CHANGED_MODE ni autre échec
                    ole32.CoUninitialize()
        except Exception:  # noqa: BLE001 (repli silencieux sur l'ouverture du dossier)
            logger.warning("Sélection du fichier dans l'Explorateur impossible : %s", path, exc_info=True)
            return False
