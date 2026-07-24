# Publier une release

MediaGrab a deux canaux de diffusion, alimentés par les Releases GitHub :

- **LIVE (stable)** : releases normales, taguées `vX.Y.Z` sur `main`.
- **EVO (beta)** : pre-releases, taguées `vX.Y.Z-evo.N` sur `evocati`.

Le développement se fait sur `evocati`. `main` est protégée : on n'y arrive que
par Pull Request depuis `evocati`, avec la CI verte.

## Couper une beta EVO

```bash
git checkout evocati
git pull
git tag v1.1.0-evo.1
git push origin v1.1.0-evo.1
```

Le workflow `release.yml` build l'installateur et publie une **pre-release**
`v1.1.0-evo.1` avec `MediaGrab-Setup-1.1.0-evo.1.exe` en asset.

## Promouvoir en LIVE (stable)

1. Ouvrir une Pull Request `evocati -> main` sur GitHub.
2. Attendre que le check `ci` soit vert, puis merger.
3. Taguer la version stable sur `main` :

```bash
git checkout main
git pull
git tag v1.1.0
git push origin v1.1.0
```

Le workflow publie une **release stable** `v1.1.0`.

## Règles

- Le tag est l'unique source de version : ne pas éditer `app/version.py` à la
  main, la CI l'écrit depuis le tag.
- Format des tags : `vX.Y.Z` (stable) ou `vX.Y.Z-evo.N` (beta). Tout autre
  format fait échouer le build (`tools/set_version.py`).
- Les builds ne sont pas signés pour l'instant ; SmartScreen avertit (normal).
