"""
Esquema canónico del dataset — Ciencia de Datos, UTN FRM 2026.

Unidad de observación: **una partida clasificatoria** (cola solo/duo) de
League of Legends, Season 16. Clave: `match_id`. Objetivo: `game_duration_s`.

Decisiones tomadas, y por qué:

  * NO entran bans, ni nada in-game o post-partida (kills, oro, torres,
    deltas por minuto). El dataset es estrictamente de condiciones
    iniciales: si entrara una variable observada durante la partida, la
    predicción de la duración dejaría de tener sentido.
  * NO entra `championLevel` de maestría: es una función escalonada de
    `championPoints`, que ya está.
  * NO entran tier ni rank como categóricas: son la entrada de la fórmula
    de `player_elo`, que ya los resume en un número ordenable.
  * NO entra la duración en minutos: sería el target dividido por 60.
  * SÍ entra `roles_inferidos`, que el prototipo previo no tenía. Cuando
    `teamPosition` viene vacío (remakes, autofill), al jugador se le
    asigna igual un slot libre para no perder la fila — pero eso queda
    contado acá, así que en la Unidad 2 se pueden filtrar esas filas en
    lugar de arrastrar una etiqueta silenciosamente equivocada.

Los 10 jugadores están aplanados en columnas en vez de estar en formato
largo. Es una concesión deliberada a tidy y hay que declararla: la unidad
de la pregunta es la partida, y en formato largo el target se repetiría
idéntico en las 10 filas de cada partida.
"""
from __future__ import annotations

EQUIPOS = ["t1", "t2"]
POSICIONES = ["top", "jng", "mid", "bot", "sup"]

# El orden en que match-v5 nombra las posiciones, para el emparejamiento.
TEAM_POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

IDENTIDAD = ["match_id"]
TARGET = ["game_duration_s"]
CALIDAD = ["roles_inferidos"]

# Las 10 features de cada jugador, en el orden en que salen al CSV.
FEATURES_JUGADOR = [
    "champ_id", "champ_name", "sum1", "sum2",
    "rune_primary", "rune_sub",
    "player_elo", "player_winrate", "champ_mastery_pts", "is_main",
]

# Los 17 agregados de cada equipo.
#
# NO entra `count_smite`: el juego obliga al jungla a llevar Smite y hay un
# jungla por equipo, así que vale 1 en toda partida real. Es una columna de
# varianza cero —no aporta nada a un modelo— y se quitó por eso.
FEATURES_EQUIPO = [
    "mains_count",
    "num_tanks", "num_mages", "num_assassins",
    "num_marksmen", "num_fighters", "num_supports",
    "avg_attack", "avg_defense", "avg_magic", "avg_difficulty",
    "avg_attackrange",
    "total_base_hp", "total_base_armor",
    "count_teleport", "count_ignite", "count_flash",
]


def columnas_equipo(prefijo: str) -> list[str]:
    """Las 50 columnas de jugador + 17 de equipo, para t1 o t2."""
    cols = [f"{prefijo}_{pos}_{f}"
            for pos in POSICIONES for f in FEATURES_JUGADOR]
    cols += [f"{prefijo}_{f}" for f in FEATURES_EQUIPO]
    return cols


COLUMNS = (IDENTIDAD + TARGET + CALIDAD
           + columnas_equipo("t1") + columnas_equipo("t2"))

# --- tipos, para validar y para castear al final --------------------------

# Todo lo que es entero. `champ_name` es la única categórica de texto y
# `player_winrate` la única flotante junto con los promedios.
FLOTANTES = (
    [f"{eq}_{pos}_player_winrate" for eq in EQUIPOS for pos in POSICIONES]
    + [f"{eq}_avg_{m}" for eq in EQUIPOS
       for m in ["attack", "defense", "magic", "difficulty", "attackrange"]]
)

TEXTO = [f"{eq}_{pos}_champ_name" for eq in EQUIPOS for pos in POSICIONES] \
        + ["match_id"]

ENTEROS = [c for c in COLUMNS if c not in FLOTANTES and c not in TEXTO]

# Columnas sin las cuales la fila no sirve para nada.
OBLIGATORIAS = ["match_id", "game_duration_s"] + [
    f"{eq}_{pos}_champ_id" for eq in EQUIPOS for pos in POSICIONES
]

# --- reglas de admisión de una partida ------------------------------------

SEASON_PREFIX = "16."
DURACION_MINIMA_S = 300          # descarta remakes
DURACION_MAXIMA_PLAUSIBLE_S = 20_000   # ~5,5 hs: nada dura tanto


def es_ancho_esperado(n: int) -> bool:
    return n == len(COLUMNS)
