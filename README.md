# FF-15 — Duración de partidas de League of Legends

**Proyecto Integrador · Ciencia de Datos · UTN FRM · Ingeniería en Sistemas de Información · 2026**
**Comisión 5K09 · Grupo 5K09-02**

> **¿Es posible predecir la duración de una partida de League of Legends a partir de las características de los jugadores, de los campeones de los equipos y las condiciones iniciales de la partida?**

Pipeline de Apache Airflow que construye el dataset del proyecto a partir de la **API oficial de Riot Games**, usando exclusivamente variables conocidas **antes de que la partida empiece**.

---

## El dataset en cuatro líneas

|  |  |
|---|---|
| **Una fila es** | una partida clasificatoria (cola solo/duo, 420) de League of Legends, Season 16 |
| **Clave primaria** | `match_id` — ej. `LA2_1617259431` |
| **Columna objetivo** | `game_duration_s` — segundos, continua → **regresión** |
| **Ancho** | 137 columnas |

---

## Arrancar

```bash
# 1. Conseguir una API key en https://developer.riotgames.com
#    (las development keys VENCEN CADA 24 HS)
cp airflow_settings.example.yaml airflow_settings.yaml
#    y pegar la key en conn_password

# 2. Levantar
astro dev start
```

Airflow queda en <http://localhost:8080> (usuario `admin`, contraseña `admin`). Desde ahí se dispara `lol_ingest` con **Trigger DAG w/ config**.

`airflow_settings.yaml` está en `.gitignore` porque contiene la key. Nunca se versiona, y la key no aparece en ningún `.py`.

## Parámetros de corrida

| Parámetro | Default | Qué hace |
|---|---|---|
| `partidas_objetivo` | 1500 | Cuántas partidas juntar en total. Se reparte en partes iguales entre las plataformas elegidas. La consigna pide más de 1.000 filas. |
| `plataformas` | las 6 | `la2`, `la1`, `br1`, `na1`, `euw1`, `kr`. Cada una tiene su propio cupo de rate limit por key, así que más plataformas es más rápido. |
| `tiers` | los 10 | De `IRON` a `CHALLENGER`. Se recorren en orden aleatorio para que una corrida cortada no quede sesgada hacia un rango. |
| `forzar` | `false` | Ignora el bronce ya bajado. Normalmente no hace falta. |

### Cómo se junta el volumen

Riot aplica los rate limits **por región y por key**: 20 req/s y 100 req/2 min en cada balde. El pipeline aprovecha las dos dimensiones:

- **Pool de keys.** `conn_password` acepta varias keys separadas por coma —una por integrante del grupo— y el cliente reparte las requests entre ellas.
- **Seis plataformas en paralelo.** Cada una golpea un host distinto, así que sus baldes son independientes en `league-v4` y `champion-mastery-v4`. (En `match-v5` sí comparten: `la2`, `la1`, `br1` y `na1` enrutan las cuatro a `americas`.)

La corrida está pensada para dejarse andando varias horas dentro de la ventana de 24 hs de la key. El payload crudo se escribe **apenas llega**, así que una corrida interrumpida no pierde nada: la siguiente reusa todo el bronce y sólo suma lo nuevo.

---

## Cómo está armado

```
wait_for_riot → check_key ─┬→ fetch_ddragon ──┐
                           │                  ├→ refine_silver[6] → consolidate → validate → save
                           └→ plan_plataformas → land_bronze[6] ───┘
```

| Tarea | Qué hace |
|---|---|
| `wait_for_riot` | **Sensor.** Espera a que Riot responda y confirma que la key sirve. Sondea cada 2 min hasta 30. Con `mode="reschedule"` libera el worker entre sondeos en vez de ocuparlo durmiendo. |
| `check_key` | **Short-circuit** con `ALL_DONE`. Si el sensor no consiguió respuesta, corta limpio y deja en el log que hay que renovar la key. Está arriba de todo a propósito: la corrida dura horas, y enterarse al final sería el peor resultado. |
| `fetch_ddragon` | **Bronce.** Catálogo de campeones y hechizos desde el CDN público, particionado por versión: los campeones cambian entre parches y una partida vieja tiene que poder reinterpretarse con el catálogo que le correspondía. |
| `plan_plataformas` | Reparte `partidas_objetivo` entre las plataformas elegidas. |
| `land_bronze` | **Una tarea por plataforma, y la única que toca la red.** Baja el detalle de la partida y los perfiles de los 10 jugadores, y los guarda crudos. |
| `refine_silver` | Una por plataforma, **sin red**. Del JSON crudo a las 137 columnas tipadas. |
| `consolidate` | Junta los parciales, deduplica por `match_id` y castea tipos. |
| `validate` | Chequeos duros —si alguno falla, el DAG falla— y escribe el reporte de calidad. |
| `save` | Escribe el entregable fechado con la corrida. |

### Las capas

| Capa | Qué es | Dónde |
|---|---|---|
| **Bronce** | Las respuestas de la API tal como llegaron. gzip, particionado por plataforma. | `include/output/bronze/` |
| **Plata** | Filas tipadas, una por partida, deduplicadas y validadas. **Es el entregable.** | `include/output/lol_AAAA-MM-DD.csv` |
| **Oro** | Features del modelo, agregados. **No se construye acá** — es de las Unidades 3 y 4. | — |

```
include/output/bronze/
├── ddragon/version=16.16.1/{champion,summoner}.json.gz
├── matches/plataforma=la2/LA2_1617259431.json.gz
├── players/plataforma=la2/puuid=.../{liga.json.gz, maestria_875.json.gz}
└── descartadas/plataforma=la2.txt
```

La separación no es decorativa:

- Una partida que ya está en bronce **no se vuelve a pedir nunca**, ni en esta corrida ni en las que vengan.
- `refine_silver` reprocesa **todo el bronce acumulado**, no sólo lo que bajó la corrida actual. Por eso el dataset **crece corrida a corrida**: con una development key no se juntan miles de partidas de una sentada.
- Un bug en el parseo se corrige **sin volver a la fuente**: se arregla `refine_silver` y se reprocesa lo que ya está en disco.
- El bronce guarda **las tres respuestas** que hacen falta para reconstruir una fila —partida, liga y maestría— así la capa plata queda 100 % offline.
- Una corrida que se corta a la mitad no pierde nada: dejó su bronce en disco y la siguiente lo levanta.

---

## El chequeo de calidad

Cada corrida deja el reporte en `include/output/reports/calidad.md`, con los seis números que pide la consigna ya calculados:

```python
df["match_id"].is_unique                        # True — el criterio que más pesa
len(df)                                         # > 1.000
df.shape                                        # (n, 137)
df.dtypes.value_counts()                        # Int64, float64 y object
df.isna().mean().sort_values(ascending=False)
df.columns[df.isna().all()]                     # vacío
```

`validate` además hace fallar el DAG si la clave repite, si falta una columna obligatoria, si aparece una columna 100 % nula o si el target se sale del rango plausible. **No se publica un dataset roto.**

---

## Las decisiones que hay que poder defender

### Por qué hay nulos donde hay nulos

No hay nulos en las columnas obligatorias — `validate` lo garantiza. Donde la fuente no tiene el dato, se imputa con un valor que significa algo, en vez de dejar un hueco:

| Situación | Qué queda | Por qué |
|---|---|---|
| Jugador sin entrada de solo/duo (unranked, o sólo juega flex) | `player_elo = 1500`, `player_winrate = 0.50` | Codifica "habilidad desconocida, asumimos promedio". |
| Jugador que nunca jugó ese campeón | `champ_mastery_pts = 0`, `is_main = 0` | Es literalmente cierto: tiene cero puntos. |
| `perks` ausente en el payload | `rune_primary = rune_sub = 0` | 0 no es un id de rama válido, así que es distinguible. |
| Campeón más nuevo que el snapshot de Data Dragon | Aporta 0 a los agregados de composición | Se emite un warning en el log. |

Es una decisión discutible y está abierta: en la Unidad 2 vale la pena evaluar si conviene una bandera `es_unranked` explícita en lugar de esconder el caso dentro del valor.

### Qué pasa si lo corrés de nuevo

**No sale el mismo archivo: sale uno más grande.** Y es a propósito.

Hay que separar dos cosas que se confunden fácil:

- **De `refine_silver` para abajo, el pipeline es una función pura del disco.** Con el mismo bronce, produce siempre exactamente el mismo CSV. Ahí sí es idempotente.
- **`land_bronze` es acumulativo.** Cada corrida sale a buscar partidas que todavía no tiene, hasta llenar su cuota. Las que ya están no se vuelven a pedir, pero sí se suman las nuevas.

O sea: el bronce crece, y la plata se rehace entera sobre el total. Es la única forma de llegar a un volumen grande con una development key que se limita a 100 requests cada 2 minutos por región y vence cada 24 horas. Si se quisiera congelar el dataset, alcanza con no volver a correr `land_bronze` y reprocesar el bronce tal como está.

### Dónde el dataset se aparta de *tidy*

**No es del todo tidy, y es a propósito.**

La observación más fina que hay acá es *jugador-en-partida*: son 10 por partida. Están aplanados en 100 columnas (`t1_top_champ_id` … `t2_sup_is_main`) en lugar de ocupar 10 filas.

Es una concesión deliberada, no un descuido. La unidad de análisis de la pregunta es **la partida**: se quiere predecir cuánto dura *una partida*. En formato largo habría 10 filas por partida con el target `game_duration_s` repetido idéntico en las 10, lo cual rompe la correspondencia una-fila-una-observación justo respecto de la pregunta que importa, y obligaría a re-agregar antes de cada modelo.

Es el mismo tipo de concesión que hace el dataset canónico de la cátedra con `player_positions`.

### `player_elo` es una variable derivada, no un dato de Riot

Riot **no expone el MMR**. `player_elo` es un proxy construido por el grupo:

```python
estimated_elo = TIER_BASE_MMR[tier] + RANK_BONUS[rank] + int(leaguePoints * 0.5)
```

con `IRON=800 … CHALLENGER=3500` y `IV=0, III=75, II=150, I=225`. Convierte una escala ordinal (tier + división + LP) en un número comparable. Los coeficientes son una elección del grupo, no una medición.

### Una limitación que no podemos resolver, y la decimos

`player_winrate` y `champ_mastery_pts` se consultan **en el momento de la recolección**, no en el momento en que se jugó la partida. Para una partida de hace semanas, son valores *posteriores* al hecho.

Eso tensiona el claim de "sólo variables pre-partida": hay una fuga temporal acotada. La API de Riot no expone winrate ni maestría históricos, así que **no se puede arreglar** con esta fuente. Lo que sí se puede es acotarlo —recolectar partidas recientes reduce la ventana— y declararlo, que es lo que hacemos acá.

### `roles_inferidos`: la columna que el prototipo no tenía

`teamPosition` puede venir vacío en remakes y en partidas con autofill. En ese caso el jugador se coloca igual en el carril que quede libre, para no perder la fila entera — pero **cuántos** jugadores quedaron así se cuenta en `roles_inferidos`. Filas con `roles_inferidos > 0` tienen todos sus datos correctos; lo único incierto es la etiqueta de carril. Se filtran con `df[df.roles_inferidos == 0]`.

Sin esta columna el error existía igual, pero era invisible.

---

## Probar

```bash
astro dev pytest    # integridad del DAG, esquema y trampas conocidas de la fuente
astro dev parse     # chequeo de parseo
ruff check .        # estilo
```

## Documentación completa

Para entender el proyecto entero —la teoría de la materia, el recorrido archivo por archivo,
la guía de ejecución y la preparación de la defensa— está
**[`docs/documentacion-proyecto.pdf`](docs/documentacion-proyecto.pdf)** (58 páginas).

Se edita en `docs/documentacion-proyecto.html` y se regenera con `python docs/generar_pdf.py`.
Es un documento vivo: cada avance del proyecto se refleja ahí, agregando lo nuevo y borrando
lo que dejó de ser cierto.

## Estructura

```
dags/lol_ingest.py    · el flujo, y nada más
include/lol/          · toda la lógica pesada, sin un solo import de Airflow
  ├── riot.py         · cliente, pool de keys y limitador por (key, host)
  ├── ddragon.py      · catálogo de campeones y hechizos
  ├── seeds.py        · recorrido de la escalera → puuids
  ├── schema.py       · las 137 columnas, tipos y reglas de admisión
  └── transform.py    · payload crudo → fila (puro)
include/output/       · bronce, plata y entregables (gitignoreado)
tests/                · astro dev pytest
Documentacion/        · material de la cátedra
```

`include/lol/` no importa Airflow en ninguna línea: así se testea con pytest plano y se reusa tal cual en las Unidades 2, 3 y 4, donde no hay un DAG alrededor.

## Nota sobre la fuente

Los datos son de la API oficial de Riot Games, bajo su política de desarrollador. El uso es didáctico. El pipeline respeta los límites publicados (20 req/s, 100 req/2 min por key y por región) con un limitador proactivo, y sólo consulta endpoints públicos de partidas clasificatorias.
