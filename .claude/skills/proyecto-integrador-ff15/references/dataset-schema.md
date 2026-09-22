# Esquema del dataset — 137 columnas

Definido en `include/lol/schema.py`, construido en `include/lol/transform.py`.

- **Unidad de observación:** una partida clasificatoria (cola 420) de LoL, Season 16.
- **Clave primaria:** `match_id`.
- **Columna objetivo:** `game_duration_s` — regresión.

Aritmética del ancho: `3 (match_id + game_duration_s + roles_inferidos) + (10 features × 5 posiciones × 2 equipos = 100) + (17 agregados × 2 equipos = 34) = 137`.

## Filtros de admisión

Una partida entra al dataset sólo si:

1. `info.gameVersion` empieza con `"16."` (Season 16).
2. Duración ≥ 300 segundos (descarta remakes).
3. Tiene exactamente 10 participantes.
4. 5 por `teamId` 100 y 5 por `teamId` 200.

## 1 · Identidad, target y calidad (3 columnas)

| Columna | Origen |
|---|---|
| `match_id` | Match-V5 `metadata.matchId`, ej. `LA2_1617259431` |
| `game_duration_s` | Match-V5 `info.gameDuration`, en segundos, **con chequeo defensivo ms→s** |
| `roles_inferidos` | **derivada**: cuántos de los 10 jugadores no traían `teamPosition` y se ubicaron en un slot libre (ver «Asignación de posiciones») |

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

## 3 · Agregados por equipo (34 columnas)

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

Los 10 hechizos de un equipo son los 5 `sum1` más los 5 `sum2`.

**No hay `_count_smite`.** El juego obliga al jungla a llevar Smite (`11`) y hay un jungla por equipo, así que valía 1 en toda partida real. Columna de varianza cero: no aporta a un modelo, se quitó del esquema.

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

La decisión de imputar con defaults en vez de dejar `NaN` es deliberada y hay que poder justificarla: un jugador sin ranked **es** un jugador de habilidad desconocida, y 1500 / 0.50 codifica "promedio, sin información". La Unidad 2 cerró esa discusión: la bandera `_es_unranked` **no hace falta** para predecir la duración. Las 615 partidas con jugadores imputados duran una mediana de 1.788 segundos contra 1.750 del resto —separación 0,067, zona roja—, así que la imputación con 1500 / 0,50 queda como está. Dos salvedades: el proxy para detectarla es imperfecto (`_player_elo == 1500` también le pasa a un SILVER III con 50 LP, así que hay que exigir además `_player_winrate == 0.50`), y la conclusión vale **para este objetivo**. `resumen_liga()` en `include/lol/riot.py` ya calcula `es_unranked`, pero `transform.py` no lo escribe al CSV: si alguna vez hace falta el dato exacto, es una columna de una línea.


## Qué columnas salen después de la Entrega 2, y con qué número

El esquema del pipeline **no cambió** —el CSV sigue teniendo las 137 columnas—, pero el análisis
exploratorio decidió cuáles de ellas no entran al modelo de la Unidad 3. Cada decisión tiene una
razón escrita en la tabla de candidatas de `notebooks/entrega-2/eda_entrega2.ipynb`. Las fichas
están numeradas según el orden del 22/9 (por importancia: H1 tanques, H2 maestría, H3 t1/t2,
H4 elo, H5 armadura, H6 winrate, H7 defensa, H8 flash):

| Columnas | Cuántas | Ficha | El número |
|---|---|---|---|
| `_player_winrate` | 10 | H6 | 0,711 con `player_elo` agregado; el elo conserva más señal contra el objetivo (−0,161 contra −0,120) y tiene un reparo de fuga menor |
| `_is_main` | 10 | H2 | con la escala correcta coincide 0,769 con la continua, y el umbral de 50.000 marca al 67,9 % de los jugadores |
| `_mains_count` | 2 | H2 | es la suma de los `_is_main` |
| `_avg_defense` y `_avg_magic` | 4 | H7 | η² 0,319 y 0,310 contra `_num_tanks` y `_num_mages` |
| `_total_base_armor` | 2 | H5 | −0,672 con `_avg_attackrange` y 0,529 con `_total_base_hp`: es el centro de dos redundancias |
| `_count_flash` | 2 | H8 | valor modal 0,838 y Pearson −0,014 |
| `_champ_name` | 10 | — | mapea 1 a 1 con `_champ_id` (173 y 173) |
| `_sum1` y `_sum2` | 20 | — | códigos guardados como enteros; su información ya está en los `_count_*` |
| `_rune_primary` | 10 | — | código, zona roja: es una etiqueta, no una magnitud |
| `_rune_sub` | 10 | — | código, zona roja, con 27 ceros que son faltantes disfrazados |
| `match_id` | 1 | — | es la clave, no una feature |
| `roles_inferidos` | 1 | — | vale 0 en el 99,91 % de las filas; queda para filtrar las 17 filas dudosas |

Son **82 columnas** que no entran como feature. Entran 54 —casi todas agregadas por partida o
sumadas entre equipos— y la restante es el objetivo.

Y dos transformaciones que hay que respetar al escribir el modelado:

- **`_champ_mastery_pts` entra en logaritmo aplicado por jugador *antes* de promediar.** No es lo
  mismo que el logaritmo del promedio: medido contra `mains_count`, el promedio del logaritmo da
  0,769 y el logaritmo del promedio 0,582.
- **Los agregados de equipo entran como suma `t1 + t2`, no por equipo** (H3). Los rótulos `t1` y
  `t2` son los `teamId` 100 y 200, que Riot asigna sin criterio: la diferencia entre la correlación
  de una mitad y la de la otra es 0,013 en promedio. De las 34 columnas quedan 24 tras los recortes
  de arriba, y se colapsan en **12 sumas**.

**El hallazgo de fondo, que hay que saber decir:** ninguna columna de condiciones iniciales predice
la duración. La más asociada al objetivo es `elo_partida` con Pearson −0,161, que explica el 2,6 %
de la varianza. Las cuatro fichas verdes miden **columnas entre sí**, no contra el objetivo.

## Lo que NO está en el dataset

- **Bans.** Excluidos a propósito.
- **Cualquier variable in-game o post-partida**: kills, oro, torres, deltas por minuto. El dataset es estrictamente de condiciones iniciales.
- `championLevel` de maestría: redundante con `championPoints`.
- Tier y rank como categóricas: redundantes con `_player_elo`.
- Duración en minutos: redundante con el target en segundos.

## Precedente

El prototipo `../FF15` produjo un esquema casi igual (138 columnas: sin `roles_inferidos`, con `t1_count_smite` / `t2_count_smite`) con **20.020 filas** en `data/processed/matches_season16.csv`.

Dos advertencias sobre ese archivo: contiene 36 filas con prefijo `EUN1`, una plataforma que ya no está en el código, así que **no es reproducible byte a byte** con la versión final del prototipo. Y no es el entregable de la Entrega 1 — el entregable tiene que salir de una corrida del pipeline nuevo.
