"""Annonces de location (In'li, CDC Habitat…) : T3 <= BUDGET_MAX € CC à Paris, dans le 92 et le 78.

Chaque site est un module de sources/ ; ce fichier les lance, filtre, dédoublonne et exporte.
"""

import os
import time

import pandas as pd

from sources import SOURCES
from sources.commun import AccesBloque

DEPARTEMENTS = ["75", "92", "78"]
PIECES = 3
BUDGET_MAX = 1400
CSV = "annonces.csv"
CARTE = "annonces.html"
COLONNES = ["source", "id", "ville", "code_postal", "loyer", "charges_comprises", "loyer_hc",
            "charges", "stationnement", "pieces", "surface_m2", "latitude", "longitude", "position", "photo", "url"]


def ecrire_carte(df):
    """Remplit carte_template.html avec les annonces et écrit la page à ouvrir dans un navigateur."""
    gabarit = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carte_template.html")
    with open(gabarit, encoding="utf-8") as f:
        page = f.read()
    donnees = df.to_json(orient="records", force_ascii=False).replace("</", "<\\/")
    page = (page.replace("__DATA__", donnees)
                .replace("__DATE__", time.strftime("%d/%m/%Y à %H:%M"))
                .replace("__BUDGET__", str(BUDGET_MAX))
                .replace("__PIECES__", str(PIECES)))
    with open(CARTE, "w", encoding="utf-8") as f:
        f.write(page)


def exporter(resultats):
    df = pd.DataFrame(resultats).reindex(columns=COLONNES)
    if len(df):
        df = df.sort_values("loyer")
    df.to_csv(CSV, index=False, encoding="utf-8-sig", sep=";")
    ecrire_carte(df)
    return df


def main():
    toutes, erreurs = {}, []
    for source in SOURCES:
        try:
            for a in source.scrape(DEPARTEMENTS):
                toutes.setdefault((a["source"], a["id"] or a["url"]), a)  # dédoublonnage par site
        except AccesBloque as e:
            erreurs.append(f"{source.NOM} : {e}")
            print(f"ERREUR {source.NOM} : {e}")

    if not toutes:
        print("Aucune annonce récupérée : tous les sites ont échoué (voir les erreurs ci-dessus).")
        raise SystemExit(1)

    print(f"{len(toutes)} annonces uniques récupérées.")
    resultats = [
        a for a in toutes.values()
        if a["type"] == "appartement" and a["pieces"] == PIECES
        and (a["code_postal"] or "")[:2] in DEPARTEMENTS
        and a["loyer"] is not None and a["loyer"] <= BUDGET_MAX
    ]
    if not resultats:
        exporter([])
        print(f"Aucun appartement T{PIECES} à {BUDGET_MAX} € maximum dans les départements "
              f"{', '.join(DEPARTEMENTS)} pour le moment.")
        return

    print(f"Lecture du détail de {len(resultats)} annonce(s)...")
    modules = {s.NOM: s for s in SOURCES}
    for a in resultats:
        modules[a["source"]].enrichir(a)

    df = exporter(resultats)
    with pd.option_context("display.max_columns", None, "display.width", 250, "display.max_colwidth", 60):
        print(df.drop(columns=["photo"]).to_string(index=False))
    print(f"\n{len(df)} annonce(s) exportée(s) dans {CSV} et {CARTE} (ouvrez-le dans votre navigateur)")
    if erreurs:
        print("Attention, sites en échec : " + " ; ".join(erreurs))


if __name__ == "__main__":
    main()
