# Esquema del dataset — 138 columnas

Definido en `include/lol/schema.py`, construido en `include/lol/transform.py`.

- **Unidad de observación:** una partida clasificatoria (cola 420) de LoL, Season 16.
- **Clave primaria:** `match_id`.
- **Columna objetivo:** `game_duration_s` — regresión.

Aritmética del ancho: `2 + (10 features × 5 posiciones × 2 equipos = 100) + (18 agregados × 2 equipos = 36) = 138`.

## Filtros de admisión

Una partida entra al dataset sólo si:

1. `info.gameVersion` empieza con `"16."` (Season 16).
2. Duración ≥ 300 segundos (descarta remakes).
3. Tiene exactamente 10 participantes.
4. 5 por `teamId` 100 y 5 por `teamId` 200.

## 1 · Identidad y target (2 columnas)

| Columna | Origen |
|---|---|
| `match_id` | Match-V5 `metadata.matchId`, ej. `LA2_1617259431` |
| `game_duration_s` | Match-V5 `info.gameDuration`, en segundos, **con chequeo defensivo ms→s** |

## 2 · Bloque por jugador (100 columnas)

Nomenclatura: `{t1|t2}_{top|jng|mid|bot|sup}_{feature}`.

| Sufijo | Origen | Notas |
|---|---|---|
| `_champ_id` | participante `championId` | entero |
| `_champ_name` | participante `championName`, con fallback al `name` de Data Dragon | **categórica** |
| `_sum1` | participante `summoner1Id` | id de hechizo |
| `_sum2` | participante `summoner2Id` | id de hechizo |
| `_rune_primary` | `perks.styles[0].style` | 0 si falta |
| `_rune_sub` | `perks.styles[1].style` | 0 si falta |
| `_player_elo` | **derivada** de League-V4 (F) | ver fórmula abajo |
| `_player_winrate` | League-V4: `round(wins / max(1, wins+losses), 4)` | default `0.50` si no hay entrada de solo-queue |
| `_champ_mastery_pts` | Champion-Mastery-V4 (G) `championPoints` | default `0` |
| `_is_main` | **derivada**: `1 if championPoints >= 50000 else 0` | umbral elegido por el grupo |

### Asignación de posiciones

Los participantes se ordenan haciendo match de `teamPosition` contra `["TOP","JUNGLE","MIDDLE","BOTTOM","UTILITY"]`, en ese orden, y se etiquetan `top, jng, mid, bot, sup`. Los que no matchean (remake, autofill, campo vacío) se ubican en los slots que quedan libres — y eso queda registrado en la columna bandera `roles_inferidos`, así las filas afectadas se pueden filtrar en la Unidad 2 en vez de contaminar el análisis en silencio.

### Fórmula de `_player_elo`

Riot **no expone el MMR**. Este es un proxy construido por el grupo, y hay que presentarlo como tal:

```python
estimated_elo = TIER_BASE_MMR[tier] + RANK_BONUS[rank] + int(leaguePoints * 0.5)
```

| Tier | Base | | División | Bonus |
|---|---|---|---|---|
| IRON | 800 | | IV | 0 |
| BRONZE | 1100 | | III | 75 |
| SILVER | 1400 | | II | 150 |
| GOLD | 1700 | | I | 225 |
| PLATINUM | 2000 | | | |
| EMERALD | 2300 | | | |
| DIAMOND | 2600 | | | |
| MASTER | 2900 | | | |
| GRANDMASTER | 3200 | | | |
| CHALLENGER | 3500 | | | |

Sólo se lee la entrada con `queueType == "RANKED_SOLO_5x5"`. Sin entrada: `elo = 1500`, `winrate = 0.50`.

## 3 · Agregados por equipo (36 columnas)

Nomenclatura: `{t1|t2}_{feature}`.

| Columna | Cómo se calcula |
|---|---|
| `_mains_count` | Suma de los 5 `_is_main` |
| `_num_tanks`, `_num_mages`, `_num_assassins`, `_num_marksmen`, `_num_fighters`, `_num_supports` | Cuántos de los 5 campeones tienen ese tag en Data Dragon. **No suman 5**: un campeón puede tener varios tags. |
| `_avg_attack`, `_avg_defense`, `_avg_magic`, `_avg_difficulty` | `round(sum(info.X) / 5, 2)` sobre Data Dragon |
| `_avg_attackrange` | `round(sum(stats.attackrange) / 5, 2)` |
| `_total_base_hp` | `sum(stats.hp)` — suma cruda, no promedio |
| `_total_base_armor` | `sum(stats.armor)` — suma cruda |
| `_count_teleport` | Cuántos `12` entre los 10 hechizos del equipo |
| `_count_ignite` | Cuántos `14` |
| `_count_flash` | Cuántos `4` |
| `_count_smite` | Cuántos `11` |

Los 10 hechizos de un equipo son los 5 `sum1` más los 5 `sum2`.

## Orden de las columnas en el CSV

`match_id`, `game_duration_s`, todo el equipo 1 (las 5 posiciones en orden top/jng/mid/bot/sup, después los agregados de t1), todo el equipo 2 igual.

## Nulos: dónde y por qué

Esto es lo que hay que saber contestar en la defensa:

| Situación | Qué pasa |
|---|---|
| Jugador sin entrada de RANKED_SOLO_5x5 (unranked, o sólo juega flex) | `_player_elo = 1500`, `_player_winrate = 0.50` — valores por defecto, no nulos |
| Jugador que nunca jugó ese campeón | `_champ_mastery_pts = 0`, `_is_main = 0` |
| `perks` ausente en el payload | `_rune_primary` / `_rune_sub` en `0` |
| Campeón más nuevo que el snapshot de Data Dragon | Aporta 0 a todos los agregados de composición del equipo. Se loguea un warning. |

La decisión de imputar con defaults en vez de dejar `NaN` es deliberada y hay que poder justificarla: un jugador sin ranked **es** un jugador de habilidad desconocida, y 1500 / 0.50 codifica "promedio, sin información". Vale la pena discutir en la Unidad 2 si conviene agregar una bandera `_es_unranked` en vez de esconder el caso dentro del valor.

## Lo que NO está en el dataset

- **Bans.** Excluidos a propósito.
- **Cualquier variable in-game o post-partida**: kills, oro, torres, deltas por minuto. El dataset es estrictamente de condiciones iniciales.
- `championLevel` de maestría: redundante con `championPoints`.
- Tier y rank como categóricas: redundantes con `_player_elo`.
- Duración en minutos: redundante con el target en segundos.

## Precedente

El prototipo `../FF15` produjo este mismo esquema con **20.020 filas** en `data/processed/matches_season16.csv`.

Dos advertencias sobre ese archivo: contiene 36 filas con prefijo `EUN1`, una plataforma que ya no está en el código, así que **no es reproducible byte a byte** con la versión final del prototipo. Y no es el entregable de la Entrega 1 — el entregable tiene que salir de una corrida del pipeline nuevo.
