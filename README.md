# MediaGrab

MediaGrab est une application Windows locale (Python 3.12 + PySide6) qui analyse
une URL compatible avec yt-dlp, télécharge une vidéo ou en extrait l'audio, et
enregistre le fichier dans le dossier de votre choix. Aucun compte, serveur
distant ni système de télémétrie : tout se passe sur votre machine.

Utilisez MediaGrab uniquement pour les contenus que vous êtes autorisé à
télécharger. Le logiciel ne contourne ni les DRM, ni les abonnements, ni les
protections d'accès ou d'authentification. Vous restez responsable du respect
des droits d'auteur, des licences et des conditions des plateformes.

## Fonctionnalités

- interface à barre latérale, thème sombre, entièrement en français ;
- analyse asynchrone (`yt-dlp --dump-single-json`) : titre, miniature, durée,
  auteur, plateforme et résolution maximale ;
- vidéo MP4/MKV/WebM avec limites de qualité et préférence de codec ;
- extraction audio MP3/M4A/FLAC/WAV/Opus ;
- dossier de destination par téléchargement, dernier dossier mémorisé ;
- file parallèle (deux téléchargements par défaut), progression, annulation et
  relance ;
- sous-titres, métadonnées, miniature intégrée et archive anti-doublons ;
- historique et paramètres en JSON atomique ;
- **téléchargement automatique de yt-dlp et FFmpeg au premier lancement** ;
- **bouton de mise à jour de yt-dlp** dans les paramètres ;
- **mise à jour de l'application** depuis les releases GitHub (vérification au
  démarrage, téléchargement et lancement de l'installateur) ;
- **notifications natives** de fin de téléchargement ;
- raccourcis clavier et panneau de logs.

La « pause » réelle n'est pas exposée : annuler conserve les fichiers `.part`,
puis Relancer permet à yt-dlp de reprendre.

## Installation (utilisateur)

Téléchargez `MediaGrab-Setup-<version>.exe` puis lancez-le. L'installateur crée
les raccourcis et un désinstalleur ; aucune permission administrateur n'est
requise (installation par utilisateur).

Au **premier démarrage**, MediaGrab propose de télécharger `yt-dlp` et `FFmpeg`
(~40 à 90 Mo) depuis leurs sources officielles vers votre dossier utilisateur.
Une connexion Internet est nécessaire à ce moment-là uniquement.

## Données locales

- paramètres : `%APPDATA%\MediaGrab\settings.json`
- historique : `%APPDATA%\MediaGrab\history.json`
- archive : `%APPDATA%\MediaGrab\download_archive.txt`
- composants : `%LOCALAPPDATA%\MediaGrab\bin\`
- logs : `%LOCALAPPDATA%\MediaGrab\logs\`
- destination initiale : `%USERPROFILE%\Downloads\MediaGrab`

Les paramètres et l'historique sont écrits par remplacement atomique. Les
cookies ne sont pas stockés et les secrets usuels sont masqués dans les logs.
La désinstallation ne supprime pas vos données personnelles.

## Développement

Prérequis : Python 3.12 x64 (ou `uv`).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Lancer et vérifier :

```powershell
.\run.ps1
python -m pytest
python -m ruff check app tests
```

Raccourcis : `Entrée` analyse l'URL, `Ctrl+O` choisit un dossier,
`Ctrl+Entrée` télécharge, `Ctrl+,` ouvre les paramètres, `Ctrl+L` affiche les
logs.

L'icône de l'application se régénère depuis `assets/logo.svg` :

```powershell
python assets\make_icon.py
```

## Construire l'exécutable

```powershell
.\build.ps1
```

Le script prépare l'environnement, installe les dépendances, régénère l'icône si
besoin, lance Ruff et pytest, nettoie `build/` et `dist/`, puis produit
`dist\MediaGrab\MediaGrab.exe`. Le build s'arrête si une validation échoue. Les
binaires yt-dlp/FFmpeg ne sont **pas** embarqués (ils sont téléchargés au
premier lancement).

## Construire l'installateur

Installez [Inno Setup 6](https://jrsoftware.org/isdl.php), puis :

```powershell
.\installer\build-installer.ps1
```

Le script build l'application, lit la version dans `app/version.py`, puis compile
`installer\Output\MediaGrab-Setup-<version>.exe`.

### Signature de code

L'exécutable et l'installateur sont signés (Authenticode) au nom de **Root3301**
via `installer\sign.ps1`, qui crée un certificat auto-signé au premier usage.
Un certificat auto-signé n'étant pas reconnu par une autorité publique, Windows
SmartScreen affiche tout de même « éditeur inconnu » ; la signature garantit
l'intégrité et porte l'identité Root3301. Un certificat commercial est nécessaire
pour supprimer l'avertissement pour tous les utilisateurs.

## Dépannage

- **téléchargement des composants échoué** : vérifiez votre connexion, puis
  réessayez depuis Paramètres → Composants ;
- **contenu privé ou indisponible** : MediaGrab ne tente pas de contourner
  l'accès ;
- **destination inaccessible** : choisissez un dossier existant où votre compte
  peut écrire ;
- **fusion/extraction en erreur** : mettez à jour yt-dlp depuis les paramètres ;
- **URL non prise en charge** : mettez à jour yt-dlp (les plateformes évoluent
  souvent).

## Licence

MediaGrab est distribué sous licence **MIT** (Dev by Root3301) — voir
[LICENSE](LICENSE). yt-dlp et FFmpeg, téléchargés au premier lancement, restent
soumis à leurs licences respectives.

## Architecture

La logique est séparée entre `models`, `utils`, `parsers`, `services` et `ui`
(`ui/pages` pour les écrans, `ui/sidebar` pour la navigation). Toutes les
commandes externes passent par `QProcess.setProgram()` et
`setArguments(list[str])` ; aucune commande shell ni option libre fournie par
l'utilisateur n'est exécutée. Les URL sont validées (anti-SSRF) avant tout appel.
