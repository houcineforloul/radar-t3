"""In'li (https://www.inli.fr) : annonces dans le HTML, 24 par page, ?page=N."""

import math
import re

import requests
from bs4 import BeautifulSoup

from .commun import AccesBloque, get, gps_depuis_page, montant

NOM = "In'li"
BASE = "https://www.inli.fr"
PAGES = {
    "75": f"{BASE}/locations/offres/paris_d:75/",
    "92": f"{BASE}/locations/offres/hauts-de-seine_d:92/",
    "78": f"{BASE}/locations/offres/yvelines_d:78/",
}
PAR_PAGE = 24


def parse_carte(carte):
    lien = carte.select_one("a[href]")
    if not lien:
        return None
    href = lien["href"]
    url = BASE + href if href.startswith("/") else href
    m_cp = re.search(r"-(\d{5})/", href)

    prix = carte.select_one(".featured-price span.demi-condensed")
    suffixe = carte.select_one(".featured-price span.book-condensed")
    # Première photo de la carte (on ignore le gabarit JS "${this.data.image}")
    photo = next((img["src"] for img in carte.select("img.featured-image[src]")
                  if img["src"].startswith("http")), None)

    details = carte.select_one(".featured-details span")
    lignes = [l.strip() for l in details.get_text("\n").split("\n") if l.strip()] if details else []
    pieces = surface = None
    if lignes:
        caract = lignes[0]
        if caract.lower().startswith("studio"):
            pieces = 1
        else:
            m = re.search(r"(\d+)\s*pi[eè]ce", caract)
            pieces = int(m.group(1)) if m else None
        m = re.search(r"([\d.,]+)\s*m²", caract)
        surface = float(m.group(1).replace(",", ".")) if m else None

    return {
        "source": NOM,
        "id": url.rstrip("/").rsplit("/", 1)[-1],
        "type": "maison" if "/location-maison-" in href else "appartement",
        "ville": lignes[-1] if len(lignes) > 1 else None,
        "code_postal": m_cp.group(1) if m_cp else None,
        "loyer": montant(prix.get_text()) if prix else None,
        "charges_comprises": bool(suffixe and suffixe.get_text(strip=True).lower() == "cc"),
        "pieces": pieces,
        "surface_m2": surface,
        "photo": photo,
        "url": url,
    }


def scrape_departement(dep, url_base):
    annonces, page, nb_pages, total = [], 1, 1, 0
    while page <= nb_pages:
        url = url_base if page == 1 else f"{url_base}?page={page}"
        soup = BeautifulSoup(get(url), "html.parser")
        if page == 1:
            entete = soup.select_one(".sf-results-head h5")
            m = re.search(r"(\d+)", entete.get_text()) if entete else None
            total = int(m.group(1)) if m else 0
            nb_pages = max(1, math.ceil(total / PAR_PAGE))
            print(f"[{NOM} {dep}] {total} logements annoncés, {nb_pages} page(s)")
        cartes = soup.select("div.featured-items > div.featured-item")
        if not cartes:
            if page == 1 and total:
                raise AccesBloque(f"[{NOM} {dep}] {total} logements annoncés mais aucune carte trouvée : "
                                  "les sélecteurs HTML ont probablement changé.")
            break
        annonces += [a for a in map(parse_carte, cartes) if a]
        page += 1
    return annonces


def scrape(departements):
    """Toutes les annonces des départements demandés (sans filtre)."""
    annonces = []
    for dep in departements:
        if dep in PAGES:
            annonces += scrape_departement(dep, PAGES[dep])
    return annonces


def enrichir(annonce):
    """Page détail : loyer hors charges, charges, stationnement éventuel, coordonnées GPS."""
    try:
        page = get(annonce["url"])
    except (AccesBloque, requests.HTTPError) as e:
        print(f"  ! détail indisponible pour {annonce['id']} : {e}")
        return
    soup = BeautifulSoup(page, "html.parser")
    for li in soup.select(".advert-price-block li"):
        libelle = li.get_text(" ", strip=True).lower()
        valeur = montant(li.select_one("span").get_text()) if li.select_one("span") else None
        if libelle.startswith("loyer hors charges"):
            annonce["loyer_hc"] = valeur
        elif libelle.startswith("provisions de charges"):
            annonce["charges"] = valeur
        elif "stationnement" in libelle and "dépôt" not in libelle:
            annonce["stationnement"] = valeur
    gps_depuis_page(annonce, page)
