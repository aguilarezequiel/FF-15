"""
Semilla de jugadores: el recorrido de la escalera de la cola solo/duo.

Es el punto de entrada al grafo social de la fuente. Riot no publica un
listado de partidas: publica un ranking de jugadores, y a cada jugador se
le pueden pedir sus últimas partidas. Así que para llegar a las partidas
hay que pasar primero por los jugadores.

Los tiers se recorren en orden aleatorio a propósito. Si se recorrieran
siempre de IRON hacia arriba, una corrida cortada por la mitad dejaría un
dataset con puros jugadores de bronce, y el modelo aprendería el sesgo de
recolección en vez de la señal. Mezclando, cualquier corte deja una
muestra parecida al total.

Ojo con la interpretación de la muestra: los jugadores se muestrean por
escalera, pero de cada partida entran los 10 participantes sin importar su
rango. La distribución de rangos del dataset NO es la de la semilla.
"""
from __future__ import annotations

import logging
import random
from collections.abc import Iterator

from lol.riot import APEX_TIERS, DIVISIONS, RiotClient

log = logging.getLogger(__name__)


def iter_puuids(client: RiotClient, platform: str,
                tiers: list[str], max_paginas: int = 40,
                semilla: int | None = None) -> Iterator[tuple[str, str]]:
    """Va entregando `(puuid, tier)` de la escalera de `platform`.

    Es un generador y no una lista porque la corrida se corta cuando se
    alcanza la cuota de partidas, no cuando se agota la escalera: pedir
    todas las páginas por adelantado gastaría cuota en jugadores que no
    se van a visitar nunca.

    `semilla` fija el `random` para poder reproducir un recorrido.
    """
    rnd = random.Random(semilla)
    vistos: set[str] = set()

    for page in range(1, max_paginas + 1):
        tiers_mezclados = list(tiers)
        rnd.shuffle(tiers_mezclados)

        for tier in tiers_mezclados:
            # Los apex no tienen divisiones y su endpoint no pagina.
            divisiones = ["I"] if tier in APEX_TIERS else DIVISIONS
            if tier in APEX_TIERS and page > 1:
                continue

            for division in divisiones:
                entradas = client.league_entries(platform, tier, division,
                                                 page)
                if not entradas:
                    continue

                rnd.shuffle(entradas)
                log.info("%s · %s %s · página %s · %s jugadores",
                         platform, tier, division, page, len(entradas))

                for e in entradas:
                    puuid = e.get("puuid")
                    if not puuid or puuid in vistos:
                        continue
                    vistos.add(puuid)
                    yield puuid, tier
