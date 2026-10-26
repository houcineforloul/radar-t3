"""CDC Habitat (https://www.cdc-habitat.fr) : pages de résultats SEO en HTML, 16 annonces par page.

Seules les pages /recherche/location/... et /annonces-immobilieres/location/... sont utilisées
(le moteur /Recherche/search et les paramètres nbPiece/nbLoyer... sont interdits par robots.txt).
"""

import re

import requests
from bs4 import BeautifulSoup

from .commun import AccesBloque, get_reponse, get, gps_depuis_page, montant, session

NOM = "CDC Habitat"
BASE = "https://www.cdc-habitat.fr"
PAGES = {
    "75": f"{BASE}/recherche/location/ile-de-france/paris",
    "92": f"{BASE}/recherche/location/ile-de-france/hauts-de-seine",
    "78": f"{BASE}/recherche/location/ile-de-france/yvelines",
}


def parse_carte(carte):
    bouton = carte.select_one("button[data-idlot]")
    lien = carte.select_one("a[href*='/annonces-immobilieres/location/']")
    if not bouton or not lien:
        return None
    href = lien["href"]
    url = BASE + href if href.startswith("/") else href

    type_ = carte.select_one(".description .type")
    type_ = type_.get_text(strip=True).lower() if type_ else ""
    titre = carte.select_one(".description h3")
    titre = titre.get_text(" ", strip=True) if titre else ""
    pieces = surface = None
    if re.match(r"studio", titre, re.I):
        pieces = 1
    else:
        m = re.search(r"(\d+)\s*pi[eè]ce", titre)
        pieces = int(m.group(1)) if m else None
    m = re.search(r"([\d.,]+)\s*m²", titre)
    surface = float(m.group(1).replace(",", ".")) if m else None

    lieu = carte.select_one(".description .location")
    m = re.match(r"(.*?)\s*\((\d{5})\)", lieu.get_text(" ", strip=True)) if lieu else None
    prix = carte.select_one(".description .price")
    photo = next((img["src"] for img in carte.select(".image img[src]")
                  if img["src"].startswith("http") and "image_stationnement" not in img["src"]), None)

    return {
        "source": NOM,
        "id": str(bouton["data-idlot"]),
        "type": type_,
        "ville": m.group(1).title() if m else None,
        "code_postal": m.group(2) if m else None,
        "loyer": montant(prix.get_text()) if prix else None,
        "charges_comprises": None,
        "pieces": pieces,
        "surface_m2": surface,
        "photo": photo,
        "url": url,
    }


def scrape_departement(dep, url_depart, deja_vus):
    annonces, url, page, total = [], url_depart, 1, 0
    while url:
        session.cookies.clear()  # le cookie portailCommercial retient la dernière page vue
        r = get_reponse(url)
        if page > 1 and not re.search(r"/page-(\d+)", r.url):
            break  # redirigé vers la page 1 : plus de page
        soup = BeautifulSoup(r.text, "html.parser")
        if page == 1:
            m = re.search(r"(\d+)\s+logements?\s+disponibles?", soup.get_text(" "))
            total = int(m.group(1)) if m else 0
        cartes = soup.select("#listeResultats article.residenceCard")
        nouvelles = 0
        for carte in cartes:
            a = parse_carte(carte)
            if a and a["id"] not in deja_vus:
                deja_vus.add(a["id"])
                annonces.append(a)
                nouvelles += 1
        if page == 1 and total and not cartes:
            raise AccesBloque(f"[{NOM} {dep}] {total} logements annoncés mais aucune carte trouvée : "
                              "les sélecteurs HTML ont probablement changé.")
        suivant = soup.select_one("link[rel=next][href]")
        if not nouvelles or not suivant:
            break
        url = suivant["href"]
        page += 1
    print(f"[{NOM} {dep}] {total} logements annoncés, {page} page(s)")
    return annonces


def scrape(departements):
    """Toutes les annonces des départements demandés (sans filtre), dédoublonnées par id."""
    annonces, deja_vus = [], set()
    for dep in departements:
        if dep in PAGES:
            annonces += scrape_departement(dep, PAGES[dep], deja_vus)
    return annonces


def enrichir(annonce):
    """Page détail : charges comprises, charges, loyer hors charges, coordonnées GPS."""
    try:
        page = get(annonce["url"])
    except (AccesBloque, requests.HTTPError) as e:
        print(f"  ! détail indisponible pour {annonce['id']} : {e}")
        return
    soup = BeautifulSoup(page, "html.parser")
    bloc = soup.select_one("section.residenceInfo")
    if bloc and re.search(r"charges\s+comprises", bloc.get_text(" ", strip=True), re.I):
        annonce["charges_comprises"] = True
    modal = soup.select_one("#aProposPrixModal")
    if modal:
        charges, dans_dont = 0.0, False
        for ligne in modal.select(".flex"):
            cases = ligne.find_all("div", recursive=False)
            libelle = cases[0].get_text(" ", strip=True).lower() if cases else ""
            if libelle == "dont":
                dans_dont = True
                continue
            if dans_dont and len(cases) >= 2 and (libelle.startswith("charges g") or
                                                  libelle.startswith("charges de chauffage")):
                v = montant(cases[1].get_text())
                if v is not None:
                    charges += v
            elif libelle.startswith("dépôt") or "zone soumise" in libelle:
                dans_dont = False
        if charges and annonce.get("loyer") is not None:
            annonce["charges"] = round(charges, 2)
            annonce["loyer_hc"] = round(annonce["loyer"] - charges, 2)
    gps_depuis_page(annonce, page)
