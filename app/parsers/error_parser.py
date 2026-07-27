"""Traduire la sortie brute de yt-dlp en un motif d'échec lisible.

Les règles sont ordonnées du plus spécifique au plus générique : la première
qui correspond gagne. La correspondance est une sous-chaîne insensible à la
casse, ce qui tolère les reformulations de yt-dlp d'une version à l'autre.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_RAW = 2000
MAX_REASON = 200
_ERROR_PREFIX = "ERROR:"


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """Motif court, conseil actionnable éventuel, et sortie retenue."""

    reason: str
    hint: str = ""
    raw: str = ""


# (sondes, motif, conseil) — l'ordre porte la logique : du précis au général.
RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("private video",),
     "Vidéo privée",
     "Seul son propriétaire peut y accéder."),
    (("members-only", "this channel's members"),
     "Réservée aux membres",
     "Un abonnement à la chaîne est nécessaire."),
    (("sign in to confirm your age", "age-restricted"),
     "Limite d'âge",
     "La source exige une session connectée, que Grabzdia n'utilise pas."),
    (("video unavailable", "no longer available"),
     "Vidéo indisponible",
     "Elle a été supprimée ou rendue privée."),
    # « available in your country » sans le « not » : YouTube écrit « has not made
    # this video available in your country », où not et available sont séparés.
    (("available in your country", "geo restricted", "geo-restricted"),
     "Bloquée dans votre pays",
     "La source refuse l'accès depuis votre région."),
    (("requested format is not available",),
     "Format demandé indisponible",
     "Réessayez en qualité « Automatique » ou « Meilleure qualité »."),
    (("http error 429", "too many requests"),
     "Trop de requêtes",
     "La source limite le débit. Patientez quelques minutes."),
    (("http error 404",),
     "Adresse introuvable",
     "Le lien est erroné ou a expiré."),
    (("http error 403", "forbidden"),
     "Accès refusé",
     "La source a rejeté la requête."),
    (("unable to download webpage", "getaddrinfo", "failed to resolve", "network is unreachable"),
     "Problème de réseau",
     "Vérifiez votre connexion."),
    (("no space left on device", "errno 28"),
     "Espace disque insuffisant",
     "Libérez de la place ou changez de destination."),
    (("permission denied", "errno 13"),
     "Accès refusé au dossier",
     "Choisissez une autre destination."),
    (("certificate_verify_failed", "sslerror"),
     "Problème de certificat",
     "Un antivirus ou un proxy intercepte peut-être la connexion."),
    (("unsupported url",),
     "Source non prise en charge",
     "yt-dlp ne reconnaît pas ce site."),
    (("nsig extraction failed", "please report this issue"),
     "yt-dlp est peut-être dépassé",
     "Mettez yt-dlp à jour depuis les Paramètres."),
    (("postprocessing", "ffmpeg exited"),
     "Échec du post-traitement",
     "Le média a été téléchargé mais la conversion a échoué."),
)


def diagnose(lines: list[str], exit_code: int) -> Diagnosis:
    """Motif d'échec déduit des dernières lignes de yt-dlp.

    Deux replis, dans cet ordre : la dernière ligne `ERROR:` telle quelle, puis
    le code de sortie. On en dit donc toujours plus que « le téléchargement a
    échoué ».
    """
    raw = "\n".join(lines)[-MAX_RAW:]
    haystack = raw.lower()
    for probes, reason, hint in RULES:
        if any(probe in haystack for probe in probes):
            return Diagnosis(reason=reason, hint=hint, raw=raw)
    errors = [line for line in lines if line.strip().upper().startswith(_ERROR_PREFIX)]
    if errors:
        message = errors[-1].strip()[len(_ERROR_PREFIX):].strip()
        return Diagnosis(reason=message[:MAX_REASON], raw=raw)
    return Diagnosis(reason=f"yt-dlp s'est arrêté avec le code {exit_code}.", raw=raw)
