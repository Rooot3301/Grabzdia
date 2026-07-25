Ce dossier est **optionnel**.

Depuis la version 1.0, Grabzdia télécharge automatiquement `yt-dlp.exe`,
`ffmpeg.exe` et `ffprobe.exe` au premier lancement, depuis leurs sources
officielles, vers `%LOCALAPPDATA%\Grabzdia\bin`.

Vous pouvez toutefois placer ici ces trois exécutables pour un usage hors-ligne
ou en développement. Grabzdia les recherche dans cet ordre :

1. `%LOCALAPPDATA%\Grabzdia\bin` (téléchargés automatiquement) ;
2. ce dossier `bin/` ;
3. le `PATH` du système.

Les `.exe` ne sont pas suivis par Git.
