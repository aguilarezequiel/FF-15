"""
Metadatos de campeones y hechizos desde Data Dragon, el CDN de Riot.

Es público: no pide API key ni tiene rate limit. Por eso vive aparte del
cliente con pool de keys — mezclarlos obligaría a gastar cuota en algo que
no la necesita.

De acá sale todo lo que el pipeline sabe de un campeón más allá de su id:
sus tags (Tank, Mage, ...) y sus estadísticas base. Es lo que permite
construir los agregados de composición de cada equipo.
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
CDN = "https://ddragon.leagueoflegends.com/cdn"

# Ids de hechizos de invocador que el esquema cuenta por equipo. Están acá,
# con nombre, en vez de sueltos como números mágicos en el transform.
# Smite (11) no está: es obligatorio para el jungla, así que contarlo daba
# 1 en toda partida real —varianza cero— y se sacó del esquema.
SPELL_FLASH = 4
SPELL_TELEPORT = 12
SPELL_IGNITE = 14

TAGS = ["Tank", "Mage", "Assassin", "Marksman", "Fighter", "Support"]


def latest_version(timeout: int = 10) -> str:
    """La versión más reciente publicada en el CDN."""
    r = requests.get(VERSIONS_URL, timeout=timeout)
    r.raise_for_status()
    return r.json()[0]


def fetch_champions(version: str, timeout: int = 15) -> dict:
    """champion.json crudo, tal como lo devuelve el CDN."""
    r = requests.get(f"{CDN}/{version}/data/en_US/champion.json",
                     timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_spells(version: str, timeout: int = 15) -> dict:
    """summoner.json crudo."""
    r = requests.get(f"{CDN}/{version}/data/en_US/summoner.json",
                     timeout=timeout)
    r.raise_for_status()
    return r.json()


def index_champions(champion_json: dict) -> dict[int, dict]:
    """Indexa por id numérico, que es como los devuelve match-v5.

    El CDN los publica indexados por nombre interno ("MonkeyKing"), pero
    las partidas traen `championId`. Sin este reindexado habría que hacer
    una búsqueda lineal por cada uno de los 10 campeones de cada partida.
    """
    salida = {}
    for datos in champion_json.get("data", {}).values():
        cid = int(datos["key"])
        info = datos.get("info", {})
        stats = datos.get("stats", {})
        salida[cid] = {
            "name": datos.get("name"),
            "tags": datos.get("tags", []),
            "attack": info.get("attack", 0),
            "defense": info.get("defense", 0),
            "magic": info.get("magic", 0),
            "difficulty": info.get("difficulty", 0),
            "hp": stats.get("hp", 0),
            "armor": stats.get("armor", 0),
            "attackrange": stats.get("attackrange", 0),
        }
    return salida


def index_spells(summoner_json: dict) -> dict[int, dict]:
    """Indexa los hechizos por id numérico."""
    return {
        int(d["key"]): {"name": d.get("name")}
        for d in summoner_json.get("data", {}).values()
    }
