Ce dossier est **optionnel**.

Depuis la version 1.0, MediaGrab télécharge automatiquement `yt-dlp.exe`,
`ffmpeg.exe` et `ffprobe.exe` au premier lancement, depuis leurs sources
officielles, vers `%LOCALAPPDATA%\MediaGrab\bin`.

Vous pouvez toutefois placer ici ces trois exécutables pour un usage hors-ligne
ou en développement. MediaGrab les recherche dans cet ordre :

1. `%LOCALAPPDATA%\MediaGrab\bin` (téléchargés automatiquement) ;
2. ce dossier `bin/` ;
3. le `PATH` du système.

Les `.exe` ne sont pas suivis par Git.
