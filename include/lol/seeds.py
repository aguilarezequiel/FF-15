"""
Semilla de jugadores: el recorrido de la escalera de la cola solo/duo.

Es el punto de entrada al grafo social de la fuente. Riot no publica un
listado de partidas: publica un ranking de jugadores, y a cada jugador se
le pueden pedir sus últimas partidas. Así que para llegar a las partidas
hay que pasar primero por los jugadores.

Los tiers se recorren en orden aleatorio a propósito, pero hay que ser
preciso sobre qué consigue eso y qué no. Si se recorrieran siempre de
IRON hacia arriba, toda corrida cortada daría el mismo dataset de puros
jugadores de bronce. Mezclando, el tier que toca cambia de corrida en
corrida — pero **no** se obtiene una muestra parecida al total.

El motivo es de aritmética: una página de escalera trae 205 jugadores y
cada uno rinde hasta `PARTIDAS_POR_JUGADOR` partidas, así que una sola
combinación tier/división alcanza para llenar una cuota de miles. La
corrida corta antes de pasar al segundo tier y el orden mezclado nunca
llega a recorrerse. Medido sobre el dataset del 6/9/2026 (19.145 filas):
cada plataforma quedó con un rango casi puro y distinto entre sí —NA1
33% SILVER, LA1 39% GRANDMASTER—, con elo medio de 1.627 a 3.231 y
desvío interno de 223 a 440.

O sea que el sesgo de recolección no se elimina: se vuelve aleatorio en
vez de determinista. Para muestrear la escalera entera habría que rotar
de tier cada N jugadores en vez de confiar en el shuffle. Mientras eso
no se haga, el sesgo se declara y se mide, no se ignora: ver la parte de
limitaciones en `docs/documentacion-proyecto.html`.

Ojo también con la interpretación de la muestra: los jugadores se
muestrean por escalera, pero de cada partida entran los 10 participantes
sin importar su rango. La distribución de rangos del dataset NO es la de
la semilla.
"""
from __future__ import annotations

import logging
import random
from collections.abc import Iterator

from lol.riot import APEX_TIERS, DIVISIONS, RiotClient

log = logging.getLogger(__name__)


def iter_puuids(client: RiotClient, platform: str,
                tiers: list[str], max_paginas: int = 40,
                semilla: int | None = None
                ) -> Iterator[tuple[str, str, str | None]]:
    """Va entregando `(puuid, tier, owner_key)` de la escalera de `platform`.

    Es un generador y no una lista porque la corrida se corta cuando se
    alcanza la cuota de partidas, no cuando se agota la escalera: pedir
    todas las páginas por adelantado gastaría cuota en jugadores que no
    se van a visitar nunca.

    `owner_key` es la key que trajo ese `puuid`: Riot lo entrega
    encriptado para ella, así que todo pedido posterior sobre ese
    jugador (`match_ids`, y luego `league_by_puuid`/`mastery` si ese
    `puuid` vuelve a aparecer como semilla) tiene que reusarla. Ver
    `RiotClient._request`.

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
                entradas, owner_key = client.league_entries(
                    platform, tier, division, page)
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
                    yield puuid, tier, owner_key
