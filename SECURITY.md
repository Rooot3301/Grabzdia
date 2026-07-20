# Politique de sécurité

## Signaler une vulnérabilité

Ouvrez un ticket sur https://github.com/Rooot3301/MediaGrab/issues (ou utilisez
le bouton **Paramètres → Signaler un problème** dans l'application, qui joint des
logs anonymisés). Merci de décrire l'impact et les étapes de reproduction.

## Posture de sécurité

MediaGrab est conçu pour être sûr et respectueux de la vie privée :

- **100 % local** : aucun compte, aucun serveur applicatif, aucune télémétrie.
- **Aucune exécution shell** : les binaires externes (yt-dlp, FFmpeg) sont
  lancés via `QProcess.setProgram()` + `setArguments(list)` — jamais via un
  shell ni une chaîne concaténée. Pas d'`eval`, `exec`, `pickle` ni
  désérialisation dangereuse.
- **Réseau restreint** : les composants et les mises à jour sont téléchargés en
  **HTTPS** depuis des hôtes officiels fixes (releases GitHub de yt-dlp et de
  MediaGrab, builds FFmpeg de gyan.dev). L'installateur de mise à jour n'est
  accepté que s'il provient d'un hôte GitHub en HTTPS.
- **URL validées** : seules les URL HTTP/HTTPS sont acceptées ; les adresses
  locales/privées et les identifiants intégrés sont rejetés (anti-SSRF). Les
  miniatures ne sont récupérées qu'en http(s).
- **Fichiers** : modèle de nom restreint (aucun séparateur de chemin ni `..`),
  noms de fichiers assainis, destination validée et testée en écriture.
- **Logs locaux** : les secrets usuels (tokens, cookies, clés) sont masqués, et
  les journaux de plus de 30 jours sont supprimés automatiquement.

## Composants tiers

yt-dlp (Unlicense), FFmpeg (LGPL/GPL) et PySide6/Qt (LGPL v3) restent soumis à
leurs licences respectives. Voir la fenêtre **À propos** dans l'application.
