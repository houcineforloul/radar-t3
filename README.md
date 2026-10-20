# Radar T3 (In'li, CDC Habitat — 75 / 92 / 78)

Installation (Windows, PowerShell) :

```powershell
python -m venv .venv   # Python 3.12+ recommandé (3.11 fonctionne aussi)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Exécution :

```powershell
python scraper.py
```

Résultats : tableau dans le terminal, `annonces.csv` (séparateur `;`) et `annonces.html` (carte interactive à ouvrir dans le navigateur).

Réglages (budget, pièces, départements) : en haut de `scraper.py`.
Ajouter un site : créer `sources/<site>.py` sur le modèle de `sources/inli.py` (NOM, `scrape()`, `enrichir()`), puis l'ajouter à `SOURCES` dans `sources/__init__.py`.
