"""Nom de plateforme lisible dérivé d'une URL de téléchargement.

Utilisé sur la page Accueil pour afficher « YouTube » plutôt que
« youtube.com » sous chaque entrée récente. On reste sur les hôtes qu'on
supporte de façon fiable ; l'inconnu retombe sur le nom de domaine
capitalisé, jamais sur une chaîne vide.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

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


# YouTube ID : 11 caractères base64 URL-safe. La regex sert de garde pour
# éviter de reconstruire une URL de miniature avec un identifiant douteux.
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _youtube_video_id(url: str) -> str:
    """Extrait l'identifiant vidéo YouTube d'une URL, ou '' si absent.

    Couvre les formes courantes :
      https://www.youtube.com/watch?v=<id>
      https://youtu.be/<id>
      https://www.youtube.com/shorts/<id>
      https://m.youtube.com/watch?v=<id>&t=1s
      https://www.youtube.com/embed/<id>
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        return ""
    if host == "youtu.be" or host.endswith(".youtu.be"):
        candidate = parts.path.lstrip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        if parts.path == "/watch":
            candidate = (parse_qs(parts.query).get("v") or [""])[0]
        elif parts.path.startswith(("/shorts/", "/embed/", "/v/")):
            candidate = parts.path.split("/")[2] if len(parts.path.split("/")) > 2 else ""
        else:
            candidate = ""
    else:
        return ""
    return candidate if _YT_ID_RE.match(candidate) else ""


def infer_thumbnail_url(url: str) -> str:
    """Devine une URL de miniature stable à partir de l'URL de la vidéo.

    Utile pour l'historique migré depuis une version antérieure à la
    persistance de thumbnail_url : on peut afficher une miniature sans
    stocker quoi que ce soit ni relancer yt-dlp.

    Aujourd'hui : YouTube uniquement (i.ytimg.com sert `hqdefault.jpg`
    pour toute vidéo publique en 480×360, sans authentification). Retour
    '' pour les hôtes qu'on ne sait pas déduire.
    """
    video_id = _youtube_video_id(url)
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return ""
