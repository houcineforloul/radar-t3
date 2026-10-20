"""Outils partagés par tous les sites : requêtes polies, montants, coordonnées GPS."""

import re
import time

import requests

DELAI = 1.0  # secondes entre deux requêtes

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
})


class AccesBloque(Exception):
    pass


def get_reponse(url, tentatives=4):
    """GET poli avec délai et nouvelles tentatives ; renvoie la réponse (redirections suivies)."""
    for i in range(1, tentatives + 1):
        time.sleep(DELAI)
        try:
            r = session.get(url, timeout=20)
        except requests.RequestException as e:
            if i == tentatives:
                raise AccesBloque(f"Connexion impossible à {url} : {e}") from e
            time.sleep(5 * i)  # laisse Windows libérer des ports (WinError 10048)
            continue
        if r.status_code in (403, 429):
            raise AccesBloque(f"Accès refusé (HTTP {r.status_code}) sur {url}. "
                              "Le site limite ou bloque les requêtes : réessayez plus tard.")
        if "captcha" in r.text.lower()[:5000]:
            raise AccesBloque(f"Un CAPTCHA est demandé sur {url} : arrêt (pas de contournement).")
        r.raise_for_status()
        return r
    raise AccesBloque(url)


def get(url, tentatives=4):
    return get_reponse(url, tentatives).text


def montant(texte):
    """'1 057 € ' -> 1057.0 ; '1 570,09 €' -> 1570.09 (espaces insécables, virgule décimale)."""
    chiffres = re.sub(r"[^\d,.]", "", texte or "").replace(",", ".")
    return float(chiffres) if chiffres else None


def gps_depuis_page(annonce, page):
    """Coordonnées du widget de quartier (alentoor) ou d'une carte Google ; sinon centre de la commune."""
    m = (re.search(r'"latitude"\s*:\s*(-?[\d.]+)\s*,\s*"longitude"\s*:\s*(-?[\d.]+)', page)
         or re.search(r"lat:\s*(-?[\d.]+),\s*lng:\s*(-?[\d.]+)", page))
    if m:
        annonce["latitude"], annonce["longitude"] = float(m.group(1)), float(m.group(2))
        annonce["position"] = "exacte"
    else:
        centre_commune(annonce)


def centre_commune(annonce):
    """Repli : centre de la commune (API officielle geo.api.gouv.fr)."""
    try:
        time.sleep(DELAI)
        r = session.get("https://geo.api.gouv.fr/communes", timeout=20,
                        params={"codePostal": annonce["code_postal"], "fields": "nom,centre"})
        communes = r.json()
    except (requests.RequestException, ValueError):
        return
    nom = (annonce["ville"] or "").lower().replace(" ", "-")
    commune = next((c for c in communes if c["nom"].lower().replace(" ", "-") == nom),
                   communes[0] if communes else None)
    if commune:
        annonce["longitude"], annonce["latitude"] = commune["centre"]["coordinates"]
        annonce["position"] = "centre de la commune"
