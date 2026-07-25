# Contribuer à Grabzdia

## Branches

- **`main`** — canal LIVE (stable), protégée. Aucun push direct : on y arrive
  uniquement par Pull Request depuis `evocati` avec la CI verte.
- **`evocati`** — canal EVO (dev/beta). Toute évolution se développe ici.

## Boucle de développement

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

.\run.ps1
python -m pytest
python -m ruff check app tests tools
```

La CI (`ci.yml`) rejoue `ruff` + `pytest` sur chaque push/PR vers `main` et
`evocati`. Une PR vers `main` ne peut être mergée que si `ci` est vert.

## Publier

Voir [docs/RELEASE.md](docs/RELEASE.md).
