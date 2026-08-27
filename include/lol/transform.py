"""
Del payload crudo de match-v5 a una fila del esquema.

Todo lo de este módulo es **puro**: no toca la red ni el disco. Recibe el
JSON tal como lo guardó la capa bronce más los perfiles de los jugadores
(también de bronce) y devuelve un diccionario con las columnas del
esquema. Esa pureza es lo que permite corregir un error de parseo y
reprocesar todo el bronce sin volver a gastar una sola request.
"""
from __future__ import annotations

import logging

from lol import ddragon, schema

log = logging.getLogger(__name__)


class PartidaDescartada(Exception):
    """La partida no cumple las reglas de admisión del dataset."""


def normalizar_duracion(bruto) -> int:
    """`gameDuration` a segundos.

    Riot cambió el criterio alrededor del parche 11.20: las partidas con
    `gameEndTimestamp` lo devuelven en segundos y las anteriores en
    milisegundos. Mezclar las dos unidades en la misma columna arruinaría
    el target sin que nada falle, que es la peor clase de bug. Como
    ninguna partida dura cinco horas y media, un valor por encima de ese
    techo sólo puede ser milisegundos.
    """
    valor = int(bruto or 0)
    if valor > schema.DURACION_MAXIMA_PLAUSIBLE_S:
        log.info("gameDuration=%s parece venir en ms; se convierte a s.",
                 valor)
        valor = valor // 1000
    return valor


def admitir(match_data: dict) -> tuple[dict, list[dict], int]:
    """Aplica las reglas de admisión. Lanza `PartidaDescartada` si no pasa.

    Devuelve `(info, participantes, duracion_s)` para no volver a
    desarmar el payload en el llamador.
    """
    info = match_data.get("info") or {}

    version = info.get("gameVersion") or ""
    if not version.startswith(schema.SEASON_PREFIX):
        raise PartidaDescartada(f"no es Season 16 (gameVersion={version!r})")

    duracion = normalizar_duracion(info.get("gameDuration"))
    if duracion < schema.DURACION_MINIMA_S:
        raise PartidaDescartada(f"dura {duracion}s, parece un remake")

    participantes = info.get("participants") or []
    if len(participantes) != 10:
        raise PartidaDescartada(
            f"tiene {len(participantes)} participantes, no 10")

    for team_id in (100, 200):
        n = sum(1 for p in participantes if p.get("teamId") == team_id)
        if n != 5:
            raise PartidaDescartada(
                f"el equipo {team_id} tiene {n} jugadores, no 5")

    return info, participantes, duracion


def ordenar_por_rol(participantes: list[dict]) -> tuple[list[dict], int]:
    """Ordena los 5 de un equipo en top/jng/mid/bot/sup.

    Devuelve también **cuántos** quedaron sin emparejar. `teamPosition`
    puede venir vacío en remakes y en partidas con autofill; en ese caso
    el jugador se coloca igual en el slot que sobre —descartar la partida
    entera sería peor— pero el conteo viaja hasta la columna
    `roles_inferidos`, así esas filas se pueden filtrar más adelante en
    vez de arrastrar una etiqueta silenciosamente equivocada.
    """
    ordenados: list[dict] = []
    pendientes = list(participantes)

    for pos in schema.TEAM_POSITIONS:
        encontrado = next(
            (p for p in pendientes if p.get("teamPosition") == pos), None)
        if encontrado is not None:
            ordenados.append(encontrado)
            pendientes.remove(encontrado)

    inferidos = len(pendientes)
    ordenados.extend(pendientes)
    return ordenados[:5], inferidos


def _bloque_equipo(participantes: list[dict], prefijo: str,
                   campeones: dict[int, dict],
                   perfiles: dict[str, dict]) -> tuple[dict, int]:
    """Las 50 columnas de jugador + las 18 de agregados, para un equipo."""
    ordenados, inferidos = ordenar_por_rol(participantes)
    bloque: dict = {}

    for pos, p in zip(schema.POSICIONES, ordenados, strict=False):
        puuid = p.get("puuid")
        cid = p.get("championId")
        meta = campeones.get(cid)
        if meta is None:
            log.warning("Campeón %s desconocido para el snapshot de Data "
                        "Dragon: aporta 0 a los agregados de composición.",
                        cid)
            meta = {}

        perfil = perfiles.get(puuid) or {}
        liga = perfil.get("liga") or {}
        maestria = perfil.get("maestria") or {}

        estilos = (p.get("perks") or {}).get("styles") or []

        bloque[f"{prefijo}_{pos}_champ_id"] = cid
        bloque[f"{prefijo}_{pos}_champ_name"] = (
            p.get("championName") or meta.get("name") or "Unknown")
        bloque[f"{prefijo}_{pos}_sum1"] = p.get("summoner1Id")
        bloque[f"{prefijo}_{pos}_sum2"] = p.get("summoner2Id")
        bloque[f"{prefijo}_{pos}_rune_primary"] = (
            estilos[0].get("style") if len(estilos) > 0 else 0)
        bloque[f"{prefijo}_{pos}_rune_sub"] = (
            estilos[1].get("style") if len(estilos) > 1 else 0)
        bloque[f"{prefijo}_{pos}_player_elo"] = liga.get("estimated_elo")
        bloque[f"{prefijo}_{pos}_player_winrate"] = liga.get("winrate")
        bloque[f"{prefijo}_{pos}_champ_mastery_pts"] = maestria.get(
            "championPoints")
        bloque[f"{prefijo}_{pos}_is_main"] = maestria.get("is_main")

    # --- agregados de composición -----------------------------------------
    metas = [campeones.get(bloque[f"{prefijo}_{pos}_champ_id"], {})
             for pos in schema.POSICIONES]

    bloque[f"{prefijo}_mains_count"] = sum(
        bloque[f"{prefijo}_{pos}_is_main"] or 0 for pos in schema.POSICIONES)

    # Un campeón puede tener varios tags, así que estos seis NO suman 5.
    for tag in ddragon.TAGS:
        clave = f"{prefijo}_num_{tag.lower()}s"
        if tag == "Marksman":
            clave = f"{prefijo}_num_marksmen"
        bloque[clave] = sum(1 for m in metas if tag in (m.get("tags") or []))

    for campo in ["attack", "defense", "magic", "difficulty", "attackrange"]:
        total = sum(m.get(campo, 0) or 0 for m in metas)
        bloque[f"{prefijo}_avg_{campo}"] = round(total / 5.0, 2)

    bloque[f"{prefijo}_total_base_hp"] = sum(
        m.get("hp", 0) or 0 for m in metas)
    bloque[f"{prefijo}_total_base_armor"] = sum(
        m.get("armor", 0) or 0 for m in metas)

    hechizos = ([bloque[f"{prefijo}_{pos}_sum1"] for pos in schema.POSICIONES]
                + [bloque[f"{prefijo}_{pos}_sum2"]
                   for pos in schema.POSICIONES])
    bloque[f"{prefijo}_count_teleport"] = hechizos.count(ddragon.SPELL_TELEPORT)
    bloque[f"{prefijo}_count_ignite"] = hechizos.count(ddragon.SPELL_IGNITE)
    bloque[f"{prefijo}_count_flash"] = hechizos.count(ddragon.SPELL_FLASH)
    bloque[f"{prefijo}_count_smite"] = hechizos.count(ddragon.SPELL_SMITE)

    return bloque, inferidos


def to_row(match_data: dict, campeones: dict[int, dict],
           perfiles: dict[str, dict]) -> dict:
    """Payload crudo + metadatos + perfiles -> una fila del esquema.

    `perfiles` mapea puuid -> {"liga": resumen_liga(...),
                               "maestria": resumen_maestria(...)}
    y sale de la capa bronce, no de la red.
    """
    _, participantes, duracion = admitir(match_data)

    fila = {c: None for c in schema.COLUMNS}
    fila["match_id"] = (match_data.get("metadata") or {}).get("matchId")
    fila["game_duration_s"] = duracion

    t1 = [p for p in participantes if p.get("teamId") == 100]
    t2 = [p for p in participantes if p.get("teamId") == 200]

    bloque1, inf1 = _bloque_equipo(t1, "t1", campeones, perfiles)
    bloque2, inf2 = _bloque_equipo(t2, "t2", campeones, perfiles)

    fila.update(bloque1)
    fila.update(bloque2)
    fila["roles_inferidos"] = inf1 + inf2

    return fila
