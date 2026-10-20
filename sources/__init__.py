"""Un module par site. Chaque module expose NOM, scrape(departements) et enrichir(annonce).

Pour ajouter un site : créer sources/<site>.py sur ce modèle et l'ajouter à SOURCES.
"""

from . import cdc_habitat, inli

SOURCES = [inli, cdc_habitat]
