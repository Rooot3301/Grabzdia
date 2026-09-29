"""Nom de plateforme lisible dérivé d'une URL de téléchargement.

Utilisé sur la page Accueil pour afficher « YouTube » plutôt que
« youtube.com » sous chaque entrée récente. On reste sur les hôtes qu'on
supporte de façon fiable ; l'inconnu retombe sur le nom de domaine
capitalisé, jamais sur une chaîne vide.
"""
from __future__ import annotations

from urllib.parse import urlsplit

# Suffixes → label. On matche par suffixe pour couvrir les sous-domaines
# régionaux (fr.tiktok.com, m.youtube.com, etc.) sans lister chaque variante.
_KNOWN_HOSTS: tuple[tuple[str, str], ...] = (
    ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"),
    ("vimeo.com", "Vimeo"),
    ("twitch.tv", "Twitch"),
    ("tiktok.com", "TikTok"),
    ("soundcloud.com", "SoundCloud"),
    ("dailymotion.com", "Dailymotion"),
    ("facebook.com", "Facebook"),
    ("instagram.com", "Instagram"),
    ("twitter.com", "X"),
    ("x.com", "X"),
    ("reddit.com", "Reddit"),
    ("bilibili.com", "Bilibili"),
    ("nicovideo.jp", "Niconico"),
)


def source_label(url: str) -> str:
    """« YouTube », « Twitch », etc. depuis une URL. Défaut : hôte capitalisé."""
    host = (urlsplit(url).hostname or "").lower().lstrip(".")
    if not host:
        return ""
    for suffix, label in _KNOWN_HOSTS:
        if host == suffix or host.endswith("." + suffix):
            return label
    # Retire un www. éventuel puis capitalise le domaine principal
    # (ex. « example.com » -> « Example »).
    base = host[4:] if host.startswith("www.") else host
    root = base.split(".")[0]
    return root.capitalize() if root else host
