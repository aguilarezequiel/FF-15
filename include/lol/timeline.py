"""
Del timeline crudo de match-v5 al estado de la partida en el minuto N.

Todo lo de este módulo es **puro**, igual que `transform`: recibe el JSON
de la partida y el de su línea de tiempo tal como los guardó el bronce, y
devuelve un diccionario con las columnas de `schema.columnas_minuto`. El
minuto de corte es un parámetro y no una constante: el bronce guarda el
timeline completo, así que pasar del minuto 5 al 10 es volver a correr la
plata, sin pedirle nada a Riot.

El timeline trae dos cosas y de cada una sale una parte de la fila:

* **Cuadros** (`frames`), uno por minuto, con una foto de cada jugador:
  oro, experiencia, súbditos, nivel. Se toma el primer cuadro cuyo
  `timestamp` alcanza el minuto de corte.
* **Eventos** (`events`), con su `timestamp` en milisegundos: asesinatos,
  torres, placas, monstruos épicos, wards. Se cuentan los que pasaron
  hasta el minuto de corte inclusive.

Los eventos nombran a los jugadores por `participantId` (1 a 10), no por
equipo. El equipo sale del `participantId` del detalle de la partida, y
no del `puuid`: el `puuid` viene encriptado por key, y la partida y su
timeline pueden haber llegado con keys distintas del pool.

Hay una lectura de la fuente que no se pudo verificar al escribir esto, y
por eso existe `chequeo_contra_partida`: en `BUILDING_KILL` y en
`TURRET_PLATE_DESTROYED`, `teamId` se toma como el equipo **dueño** de la
torre —el que la pierde—, así que el punto se le anota al rival. El
chequeo recorre la partida entera y compara los conteos con los totales
que trae el detalle de la partida; si esa lectura estuviera al revés, las
torres no coincidirían en ninguna partida y se vería en el reporte.
"""
from __future__ import annotations

from lol import schema
from lol.transform import PartidaDescartada, admitir

MS_POR_MINUTO = 60_000
EQUIPOS = (100, 200)

# Las métricas que salen de los eventos y se pueden comparar contra los
# totales del detalle de la partida. Oro, xp, CS y nivel no tienen un
# total final equivalente en el detalle, así que no se chequean.
CHEQUEOS = ["kills", "towers", "plates", "elite_monsters",
            "wards_placed", "wards_killed", "first_blood"]

# Objetivos del detalle que NO son monstruos épicos. Todo lo demás que
# aparezca en `teams[].objectives` (dragon, baron, riftHerald, horde,
# atakhan, ...) se suma como monstruo épico.
_OBJETIVOS_NO_MONSTRUO = {"champion", "tower", "inhibitor"}


def _rival(team_id) -> int | None:
    return {100: 200, 200: 100}.get(team_id)


def _equipos_por_participante(participantes: list[dict]) -> dict[int, int]:
    return {p.get("participantId"): p.get("teamId") for p in participantes}


def _cuadro_del_minuto(frames: list[dict], corte_ms: int) -> dict | None:
    """El primer cuadro que alcanza el corte.

    Los cuadros no caen exacto en el minuto: el del 5 suele tener un
    `timestamp` de 300.0xx ms. El primero que llega al corte es la foto
    más cercana al minuto pedido sin mirar antes de tiempo.
    """
    for cuadro in frames:
        if (cuadro.get("timestamp") or 0) >= corte_ms:
            return cuadro
    return None


def contar_eventos(frames: list[dict], equipo_de: dict[int, int],
                   corte_ms: float) -> tuple[dict, tuple[int, int] | None]:
    """Cuenta los eventos hasta `corte_ms`, por equipo.

    Devuelve `(conteos, primera_sangre)`: `conteos[team][metrica]` y la
    primera sangre como `(team, timestamp_ms)`, o `None` si no hubo.

    Un asesinato se le anota al equipo de quien mató (`killerId`); cuando
    `killerId` es 0 mató una torre o un súbdito, y no suma para nadie,
    igual que en el marcador del juego. La primera sangre es el primer
    asesinato con un campeón como asesino.
    """
    metricas = ["kills", "towers", "plates", "elite_monsters",
                "wards_placed", "wards_killed"]
    conteos = {t: dict.fromkeys(metricas, 0) for t in EQUIPOS}
    primera: tuple[int, int] | None = None

    for cuadro in frames:
        for e in cuadro.get("events") or []:
            ts = e.get("timestamp") or 0
            if ts > corte_ms:
                continue
            tipo = e.get("type")
            metrica, team = None, None

            if tipo == "CHAMPION_KILL":
                metrica, team = "kills", equipo_de.get(e.get("killerId"))
                if team is not None and (primera is None or ts < primera[1]):
                    primera = (team, ts)
            elif tipo == "BUILDING_KILL":
                if e.get("buildingType") == "TOWER_BUILDING":
                    metrica, team = "towers", _rival(e.get("teamId"))
            elif tipo == "TURRET_PLATE_DESTROYED":
                metrica, team = "plates", _rival(e.get("teamId"))
            elif tipo == "ELITE_MONSTER_KILL":
                metrica, team = "elite_monsters", e.get("killerTeamId")
            elif tipo == "WARD_PLACED":
                metrica, team = "wards_placed", equipo_de.get(e.get("creatorId"))
            elif tipo == "WARD_KILL":
                metrica, team = "wards_killed", equipo_de.get(e.get("killerId"))

            if metrica is not None and team in conteos:
                conteos[team][metrica] += 1

    return conteos, primera


def estado_al_minuto(match_data: dict, timeline: dict, minuto: int) -> dict:
    """Partida + timeline crudos -> una fila de `schema.columnas_minuto`.

    Lanza `PartidaDescartada` si la partida no pasa las reglas de admisión
    del dataset principal, si terminó antes del minuto de corte, o si el
    timeline no llega a ese minuto. Una partida que terminó en el minuto 4
    no tiene "estado al minuto 5": meterla con ceros mentiría.
    """
    _, participantes, duracion = admitir(match_data)
    if duracion <= minuto * 60:
        raise PartidaDescartada(
            f"dura {duracion}s, termina antes del minuto {minuto}")

    corte = minuto * MS_POR_MINUTO
    frames = (timeline.get("info") or {}).get("frames") or []
    cuadro = _cuadro_del_minuto(frames, corte)
    if cuadro is None:
        raise PartidaDescartada(f"el timeline no llega al minuto {minuto}")

    equipo_de = _equipos_por_participante(participantes)
    conteos, primera = contar_eventos(frames, equipo_de, corte)

    foto = {t: {"gold": 0, "xp": 0, "cs": 0, "level": 0} for t in EQUIPOS}
    for pid, pf in (cuadro.get("participantFrames") or {}).items():
        team = equipo_de.get(int(pid))
        if team not in foto:
            continue
        foto[team]["gold"] += pf.get("totalGold") or 0
        foto[team]["xp"] += pf.get("xp") or 0
        foto[team]["cs"] += ((pf.get("minionsKilled") or 0)
                             + (pf.get("jungleMinionsKilled") or 0))
        foto[team]["level"] += pf.get("level") or 0

    s = f"_m{minuto}"
    fila = {"match_id": (match_data.get("metadata") or {}).get("matchId"),
            "game_duration_s": duracion}
    for m in schema.METRICAS_MINUTO:
        if m in foto[100]:
            a, b = foto[100][m], foto[200][m]
        else:
            a, b = conteos[100][m], conteos[200][m]
        if m == "level":
            # El nivel se promedia: "nivel medio del equipo" se lee mejor
            # que una suma de niveles, y la diferencia no cambia de sentido.
            a, b = round(a / 5, 2), round(b / 5, 2)
        fila[f"t1_{m}{s}"] = a
        fila[f"t2_{m}{s}"] = b
        fila[f"dif_{m}{s}"] = round(abs(a - b), 2)

    fila[f"t1_first_blood{s}"] = int(primera is not None and primera[0] == 100)
    fila[f"t2_first_blood{s}"] = int(primera is not None and primera[0] == 200)
    fila[f"first_blood_s{s}"] = (round(primera[1] / 1000, 1)
                                 if primera is not None else None)
    return fila


def chequeo_contra_partida(match_data: dict, timeline: dict) -> dict:
    """Recorre el timeline entero y lo compara con los totales finales.

    Devuelve `{chequeo: True | False | None}`: `None` cuando el detalle
    de la partida no trae el dato para comparar. Es la forma de verificar
    con datos reales la lectura que este módulo hace de cada evento, sin
    confiar en la memoria de nadie: si un conteo no coincide en ninguna
    partida, la lectura está mal; si no coincide en unas pocas, es ruido
    de la fuente y se declara.

    Contra qué se compara cada uno:

    * kills, torres, monstruos épicos y primera sangre → `teams[].objectives`
    * placas → `challenges.turretPlatesTaken` de cada jugador, sumado
    * wards → `wardsPlaced` / `wardsKilled` de cada jugador, sumado
    """
    info = match_data.get("info") or {}
    participantes = info.get("participants") or []
    equipo_de = _equipos_por_participante(participantes)
    frames = (timeline.get("info") or {}).get("frames") or []
    conteos, primera = contar_eventos(frames, equipo_de, float("inf"))

    objetivos = {t.get("teamId"): t.get("objectives") or {}
                 for t in info.get("teams") or []}

    def total_objetivo(team, clave):
        return ((objetivos.get(team) or {}).get(clave) or {}).get("kills")

    def total_jugadores(team, obtener):
        valores = [obtener(p) for p in participantes if p.get("teamId") == team]
        return None if any(v is None for v in valores) else sum(valores)

    esperado = {}
    for team in EQUIPOS:
        obj = objetivos.get(team) or {}
        monstruos = [v.get("kills") for k, v in obj.items()
                     if k not in _OBJETIVOS_NO_MONSTRUO]
        esperado[team] = {
            "kills": total_objetivo(team, "champion"),
            "towers": total_objetivo(team, "tower"),
            "elite_monsters": (None if not obj or None in monstruos
                               else sum(monstruos)),
            "plates": total_jugadores(
                team, lambda p: (p.get("challenges") or {}).get("turretPlatesTaken")),
            "wards_placed": total_jugadores(team, lambda p: p.get("wardsPlaced")),
            "wards_killed": total_jugadores(team, lambda p: p.get("wardsKilled")),
        }

    resultado = {}
    for metrica in CHEQUEOS:
        if metrica == "first_blood":
            primero = [t for t in EQUIPOS
                       if ((objetivos.get(t) or {}).get("champion") or {}).get("first")]
            if not objetivos:
                resultado[metrica] = None
            else:
                resultado[metrica] = (primero[0] if primero else None) == (
                    primera[0] if primera else None)
            continue
        if any(esperado[t][metrica] is None for t in EQUIPOS):
            resultado[metrica] = None
            continue
        resultado[metrica] = all(conteos[t][metrica] == esperado[t][metrica]
                                 for t in EQUIPOS)
    return resultado
