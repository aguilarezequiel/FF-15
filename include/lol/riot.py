"""
Cliente de la Riot Games API.

Proyecto Integrador — Ciencia de Datos — UTN FRM — 2026.

Riot aplica los rate limits **por región**, no globalmente: una misma key
puede seguir pegándole a `euw1` aunque esté en cooldown en `la2`. Por eso
la contabilidad del limitador es por par **(key, host)** y no por key.

El pacing es *proactivo*: antes de disparar una request se verifica que
haya cupo en las dos ventanas (20 req/s y 100 req/2 min). Esperar al 429
para frenar funciona, pero desperdicia una request y el tiempo de ida y
vuelta cada vez. El 429 queda igual como red de contención.

La key nunca sale de acá hardcodeada: se recibe por parámetro. Quien la
lee de la Connection de Airflow es la tarea, no este módulo.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

# Plataforma -> región continental. Son DOS familias de hosts distintas y
# confundirlas da 404: league-v4, summoner-v4 y champion-mastery-v4 viven en
# el host de plataforma; match-v5 vive en el de región continental.
PLATFORM_ROUTING = {
    "la2": {"region": "americas", "name": "LAS"},
    "la1": {"region": "americas", "name": "LAN"},
    "br1": {"region": "americas", "name": "BR"},
    "na1": {"region": "americas", "name": "NA"},
    "euw1": {"region": "europe", "name": "EUW"},
    "kr": {"region": "asia", "name": "KR"},
}

ALL_TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD",
             "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]

# Los tres de arriba no tienen divisiones y su endpoint devuelve la liga
# entera: no acepta `page`. Meterlos en un bucle de páginas re-pide la
# misma lista una y otra vez, gastando cuota al pedo.
APEX_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}

DIVISIONS = ["I", "II", "III", "IV"]

# Proxy de MMR. Riot NO expone el MMR real, así que esto es una variable
# DERIVADA, construida por el grupo, no un dato observado. Hay que
# presentarla como tal: ver references/dataset-schema.md.
TIER_BASE_MMR = {
    "IRON": 800, "BRONZE": 1100, "SILVER": 1400, "GOLD": 1700,
    "PLATINUM": 2000, "EMERALD": 2300, "DIAMOND": 2600, "MASTER": 2900,
    "GRANDMASTER": 3200, "CHALLENGER": 3500,
}
RANK_BONUS = {"IV": 0, "III": 75, "II": 150, "I": 225}

ELO_POR_DEFECTO = 1500
WINRATE_POR_DEFECTO = 0.50

# Límites de una development/personal key, por key y por host.
PER_SECOND_LIMIT = 20
PER_SECOND_WINDOW = 1.0
PER_TWO_MIN_LIMIT = 100
PER_TWO_MIN_WINDOW = 120.0

QUEUE_SOLO_DUO = 420


class RiotKeysExhausted(RuntimeError):
    """Todas las keys del pool quedaron inválidas o vencidas.

    Las development keys vencen cada 24 hs. Este error existe para que el
    mensaje sea inequívoco: no es un bug del pipeline, hay que regenerar
    la key en developer.riotgames.com.
    """


class _KeyDueñaInvalida(Exception):
    """Señal interna: la key dueña de un puuid ya no sirve.

    No se propaga fuera de `_request`: significa "saltear este pedido",
    no "se acabaron las keys", porque las otras keys del pool siguen
    perfectamente vivas para todo lo demás.
    """


class RiotClient:
    """Cliente con pool de keys y limitador por (key, host).

    `api_keys` puede traer una sola key o varias — una por integrante del
    grupo. Como Riot cuenta los límites por región y por key, N keys sobre
    M hosts dan N*M baldes independientes, y eso es lo que hace viable
    juntar miles de partidas dentro de la ventana de 24 hs.
    """

    def __init__(self, api_keys: list[str] | str, timeout: int = 12):
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]
        self.keys = [k for k in api_keys if k]
        if not self.keys:
            raise ValueError(
                "No se recibió ninguna API key. Cargala en la Connection "
                "`riot_api` (campo password); si son varias, separalas por "
                "coma.")

        self.timeout = timeout
        self._lock = threading.Lock()
        self._windows: dict[str, dict[str, deque]] = {k: {} for k in self.keys}
        self._cooldowns: dict[str, dict[str, float]] = {k: {} for k in self.keys}
        self._invalidas: set[str] = set()
        self._idx = 0

        # Un jugador aparece en muchas partidas: sin estas cachés, cada
        # partida re-pediría los mismos 10 perfiles.
        self._cache_liga: dict[str, dict] = {}
        self._cache_maestria: dict[str, dict] = {}

        self.pedidas = 0

        log.info("RiotClient con %s key(s) en pool, throttle por (key, host)",
                 len(self.keys))

    # ------------------------------------------------------------ throttle

    @staticmethod
    def _host_de(url: str) -> str:
        return urlparse(url).netloc

    def _tomar_turno(self, host: str, key: str | None = None) -> str:
        """Devuelve una key con cupo para `host`, esperando si hace falta.

        No castiga a una key en un host donde sí tiene cupo sólo porque
        está en cooldown en otro: los baldes son independientes.

        Si `key` viene dada, no rota: espera cupo en ESA key puntual. Es
        el caso de un pedido sobre un `puuid`, que sólo se puede resolver
        con la key que lo emitió (ver `_KeyDueñaInvalida` más abajo).
        """
        while True:
            ahora = time.time()
            esperas = []

            with self._lock:
                if key is not None:
                    if key in self._invalidas:
                        raise _KeyDueñaInvalida(key)
                    candidatas = [key]
                else:
                    candidatas = [k for k in self.keys if k not in self._invalidas]
                    if not candidatas:
                        raise RiotKeysExhausted(
                            "Todas las API keys del pool están vencidas o son "
                            "inválidas. Las development keys duran 24 hs: "
                            "regenerala en https://developer.riotgames.com y "
                            "actualizá la Connection `riot_api`.")

                for _ in range(len(candidatas)):
                    self._idx = (self._idx + 1) % len(candidatas)
                    key = candidatas[self._idx]

                    hasta = self._cooldowns[key].get(host, 0.0)
                    if hasta > ahora:
                        esperas.append(hasta - ahora)
                        continue

                    ventana = self._windows[key].setdefault(host, deque())
                    while ventana and ahora - ventana[0] > PER_TWO_MIN_WINDOW:
                        ventana.popleft()

                    if len(ventana) >= PER_TWO_MIN_LIMIT:
                        esperas.append(
                            PER_TWO_MIN_WINDOW - (ahora - ventana[0]))
                        continue

                    recientes, mas_viejo = 0, ahora
                    for t in reversed(ventana):
                        if ahora - t >= PER_SECOND_WINDOW:
                            break
                        recientes += 1
                        mas_viejo = t
                    if recientes >= PER_SECOND_LIMIT:
                        esperas.append(
                            PER_SECOND_WINDOW - (ahora - mas_viejo))
                        continue

                    ventana.append(ahora)
                    return key

            dormir = min(esperas) if esperas else 0.05
            time.sleep(min(max(dormir, 0.02), 2.0))

    # ------------------------------------------------------------- request

    def _request(self, url: str, params: dict | None = None,
                 max_retries: int = 10, owner_key: str | None = None
                 ) -> tuple[dict | list | None, str | None]:
        """Hace el GET y devuelve `(datos, key_que_respondió)`.

        Devolver la key usada es lo que le permite a quien llama (sobre
        todo `league_entries` y `match`) marcar de quién es un `puuid`:
        Riot lo devuelve encriptado *para esa key puntual*, y pedir algo
        con él usando otra key distinta da `400 Bad Request - Exception
        decrypting`, no un error que sugiera la causa real. Ver
        `owner_key` acá abajo y en los endpoints que lo reciben.

        Si `owner_key` viene dada, el pedido no rota de key: sólo esa
        key puede leer ese `puuid`. Si esa key vale venció, no hay
        fallback posible — se salta el pedido en vez de gastar
        reintentos contra una key que nunca va a servir para esto.
        """
        host = self._host_de(url)
        for intento in range(max_retries):
            try:
                key = self._tomar_turno(host, key=owner_key)
            except _KeyDueñaInvalida:
                log.warning("Key ...%s (dueña de este puuid) venció o es "
                            "inválida; no hay otra key que pueda leerlo. "
                            "Se salta %s.", owner_key[-6:], host)
                return None, None

            try:
                r = requests.get(url, headers={"X-Riot-Token": key},
                                 params=params, timeout=self.timeout)
            except requests.RequestException as e:
                log.warning("Error de red en %s (%s). Reintento %s.",
                            host, e, intento + 1)
                time.sleep(0.5 * (intento + 1))
                continue

            with self._lock:
                self.pedidas += 1

            if r.status_code == 200:
                return r.json(), key

            if r.status_code == 429:
                espera = int(r.headers.get("Retry-After", 5))
                with self._lock:
                    self._cooldowns[key][host] = time.time() + espera + 1
                log.info("429: key ...%s pausada %ss en %s.",
                         key[-6:], espera, host)
                continue

            if r.status_code in (401, 403):
                with self._lock:
                    self._invalidas.add(key)
                log.warning("Key ...%s inválida o vencida (%s). Fuera del "
                            "pool. Quedan %s.", key[-6:], r.status_code,
                            len(self.keys) - len(self._invalidas))
                continue

            if r.status_code == 404:
                return None, key

            log.warning("HTTP %s en %s. Reintento %s.",
                        r.status_code, host, intento + 1)
            time.sleep(0.5 * (intento + 1))

        log.warning("Se agotaron los reintentos para %s", url)
        return None, None

    # ----------------------------------------------------------- endpoints

    def ping(self, platform: str = "la2") -> bool:
        """Chequeo barato de que la API responde y la key sigue viva.

        Se usa en el sensor del DAG: descubrir que la key venció después
        de tres horas de corrida es el peor de los mundos.
        """
        url = (f"https://{platform}.api.riotgames.com/lol/league/v4/"
               f"challengerleagues/by-queue/RANKED_SOLO_5x5")
        data, _ = self._request(url)
        return data is not None

    def league_entries(self, platform: str, tier: str, division: str = "I",
                       page: int = 1) -> tuple[list[dict], str | None]:
        """Escalera de la cola solo/duo. Es la semilla de jugadores.

        Los tiers apex usan otro endpoint, que devuelve la liga completa y
        no pagina. Devolver [] cuando se pide page > 1 evita re-recorrer
        la misma lista de challengers una y otra vez.

        Devuelve también la key que respondió: cada `puuid` de la lista
        viene encriptado para ESA key puntual, y hay que reusarla en todo
        pedido posterior sobre ese jugador (`match_ids`, `league_by_puuid`,
        `mastery`) — con otra key, Riot tira `400 Bad Request - Exception
        decrypting`. Ver `_request`.
        """
        tier = tier.upper()
        if tier in APEX_TIERS:
            if page > 1:
                return [], None
            url = (f"https://{platform}.api.riotgames.com/lol/league/v4/"
                   f"{tier.lower()}leagues/by-queue/RANKED_SOLO_5x5")
            data, key = self._request(url)
            return (data.get("entries", []) if data else []), key

        url = (f"https://{platform}.api.riotgames.com/lol/league/v4/entries/"
               f"RANKED_SOLO_5x5/{tier}/{division}")
        data, key = self._request(url, params={"page": page})
        return (data if isinstance(data, list) else []), key

    def match_ids(self, region: str, puuid: str, count: int = 15,
                  start: int = 0, owner_key: str | None = None) -> list[str]:
        """Ids de las últimas partidas clasificatorias del jugador.

        `owner_key` es la key que emitió este `puuid` (la de
        `league_entries` o la de `match`, según de dónde haya salido). Sin
        ella el pool rotaría de key y Riot rechazaría el pedido: ver
        `_request`.
        """
        url = (f"https://{region}.api.riotgames.com/lol/match/v5/matches/"
               f"by-puuid/{puuid}/ids")
        params = {"count": count, "start": start,
                  "queue": QUEUE_SOLO_DUO, "type": "ranked"}
        data, _ = self._request(url, params=params, owner_key=owner_key)
        return data or []

    def match(self, region: str, match_id: str
              ) -> tuple[dict | None, str | None]:
        """Detalle completo de una partida. Es la respuesta más pesada.

        Devuelve también la key que respondió: los `puuid` de los 10
        participantes vienen embebidos en esta respuesta, encriptados
        para ESA key, no para la que se usó para llegar al `match_id`
        (que no necesita key dueña porque no es un dato encriptado). Hay
        que reusarla para `league_by_puuid`/`mastery` de esos jugadores.
        """
        url = (f"https://{region}.api.riotgames.com/lol/match/v5/matches/"
               f"{match_id}")
        return self._request(url)

    def league_by_puuid(self, platform: str, puuid: str,
                        owner_key: str | None = None) -> dict | None:
        """Entradas de liga del jugador, crudas. Cacheado por puuid."""
        clave = f"{platform}:{puuid}"
        with self._lock:
            if clave in self._cache_liga:
                return self._cache_liga[clave]
        url = (f"https://{platform}.api.riotgames.com/lol/league/v4/entries/"
               f"by-puuid/{puuid}")
        data, _ = self._request(url, owner_key=owner_key)
        with self._lock:
            self._cache_liga[clave] = data
        return data

    def mastery(self, platform: str, puuid: str, champion_id: int,
                owner_key: str | None = None) -> dict | None:
        """Maestría del jugador con ese campeón, cruda. Cacheado."""
        clave = f"{platform}:{puuid}:{champion_id}"
        with self._lock:
            if clave in self._cache_maestria:
                return self._cache_maestria[clave]
        url = (f"https://{platform}.api.riotgames.com/lol/champion-mastery/"
               f"v4/champion-masteries/by-puuid/{puuid}/by-champion/"
               f"{champion_id}")
        data, _ = self._request(url, owner_key=owner_key)
        with self._lock:
            self._cache_maestria[clave] = data
        return data


# ------------------------------------------------------------- derivaciones
# Funciones puras sobre las respuestas crudas. Viven acá y no en el cliente
# porque la capa plata las vuelve a aplicar leyendo del bronce, sin red.

def resumen_liga(entradas: list[dict] | None) -> dict:
    """De las entradas de liga crudas al elo estimado y el winrate.

    Se lee sólo la cola RANKED_SOLO_5x5: un jugador puede tener también
    flex, y mezclarlas compararía cosas distintas.

    Sin entrada de solo/duo el jugador queda en los valores por defecto.
    No es un nulo escondido: codifica "habilidad desconocida, asumimos
    promedio", y hay que poder defender esa decisión.
    """
    for e in (entradas or []):
        if e.get("queueType") != "RANKED_SOLO_5x5":
            continue
        tier = (e.get("tier") or "").upper()
        rank = e.get("rank") or "I"
        lp = e.get("leaguePoints", 0) or 0
        wins = e.get("wins", 0) or 0
        losses = e.get("losses", 0) or 0
        total = max(1, wins + losses)
        return {
            "estimated_elo": (TIER_BASE_MMR.get(tier, ELO_POR_DEFECTO)
                              + RANK_BONUS.get(rank, 0) + int(lp * 0.5)),
            "winrate": round(wins / total, 4),
            "es_unranked": 0,
        }
    return {"estimated_elo": ELO_POR_DEFECTO,
            "winrate": WINRATE_POR_DEFECTO,
            "es_unranked": 1}


def resumen_maestria(data: dict | None) -> dict:
    """Puntos de maestría y bandera de 'main'.

    El umbral de 50.000 puntos lo eligió el grupo; no viene de Riot.
    """
    puntos = (data or {}).get("championPoints", 0) or 0
    return {"championPoints": puntos, "is_main": 1 if puntos >= 50_000 else 0}
