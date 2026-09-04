# Riot Games API — referencia operativa

Portal: <https://developer.riotgames.com/apis>

## Contenido

- [Keys y rate limits](#keys-y-rate-limits)
- [Routing: platform vs región continental](#routing-platform-vs-región-continental)
- [Endpoints que usa el pipeline](#endpoints-que-usa-el-pipeline)
- [Data Dragon](#data-dragon)
- [El recorrido semilla → dataset](#el-recorrido-semilla--dataset)
- [Manejo de errores](#manejo-de-errores)
- [Trampas conocidas](#trampas-conocidas)

---

## Keys y rate limits

| Tipo de key | Límites | Vencimiento |
|---|---|---|
| **Development** | 20 req/s · 100 req/2 min | **Cada 24 hs** — hay que regenerarla en el portal |
| Personal | 20 req/s · 100 req/2 min | Sin vencimiento |
| Production | 500 req/10 s · 30.000 req/10 min | Sin vencimiento |

**Los límites se aplican por región.** Esto es la clave de todo el diseño de concurrencia: una misma key tiene un balde independiente por cada host. Puede seguir pegándole a `euw1` aunque esté en cooldown en `la2`.

**Este proyecto usa una Development key**, así que el pipeline tiene que:

- Leer la key (o la lista de keys) desde la Connection `riot_api`, nunca del código.
- Chequear temprano que la key sigue viva, y cortar limpio con un log claro si venció. Descubrirlo tres horas después de arrancar una corrida larga es el peor de los mundos.
- Hacer el pacing **proactivo** (esperar antes de disparar la request), no sólo reactivo al 429.

Header de autenticación: `{"X-Riot-Token": key}`. Nunca como query param.

### Pool de varias keys

El diseño acepta una lista de keys separadas por coma (una por integrante del grupo) en `conn_password`. El limitador lleva la contabilidad por par **(key, host)**: una `deque` de timestamps por ventana y un cooldown por host disparado por un 429 real. Se elige la primera key con cupo para ese host; si ninguna tiene, se duerme el mínimo necesario.

## Routing: platform vs región continental

Hay **dos familias de hosts** y confundirlas da 404:

| Familia | Hosts | Qué endpoints |
|---|---|---|
| **Platform** | `la2`, `la1`, `br1`, `na1`, `euw1`, `kr`, … | league-v4, summoner-v4, champion-mastery-v4 |
| **Región continental** | `americas`, `europe`, `asia` | **match-v5** |

| Platform | Región | Nombre |
|---|---|---|
| `la2` | `americas` | LAS |
| `la1` | `americas` | LAN |
| `br1` | `americas` | BR |
| `na1` | `americas` | NA |
| `euw1` | `europe` | EUW |
| `kr` | `asia` | KR |

**Consecuencia práctica para la concurrencia:** `la2`, `la1`, `br1` y `na1` **comparten** el balde de match-v5 (las cuatro son `americas`), pero tienen baldes **separados** en league-v4 y champion-mastery-v4. Paralelizar las 6 plataformas rinde mucho en los endpoints de plataforma y poco en match-v5.

## Endpoints que usa el pipeline

| # | Endpoint | Host | Para qué |
|---|---|---|---|
| A | `/lol/league/v4/{challenger\|grandmaster\|master}leagues/by-queue/RANKED_SOLO_5x5` | platform | Semilla, tiers apex. Devuelve un objeto con `entries`. |
| B | `/lol/league/v4/entries/RANKED_SOLO_5x5/{TIER}/{DIVISION}?page={n}` | platform | Semilla, IRON→DIAMOND. Devuelve una lista, paginada. |
| C | `/lol/summoner/v4/summoners/{summonerId}` | platform | Fallback para resolver puuid. Ruta deprecada; hoy league-v4 ya devuelve `puuid`. |
| D | `/lol/match/v5/matches/by-puuid/{puuid}/ids` + `{count, queue: 420, type: "ranked"}` | **región** | Ids de partidas clasificatorias del jugador. |
| E | `/lol/match/v5/matches/{matchId}` | **región** | El detalle completo de la partida. **Acá sale el target.** |
| F | `/lol/league/v4/entries/by-puuid/{puuid}` | platform | Tier, rank, LP, wins/losses del jugador. |
| G | `/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{championId}` | platform | Puntos de maestría del jugador con ese campeón. |

Tiers válidos: `IRON`, `BRONZE`, `SILVER`, `GOLD`, `PLATINUM`, `EMERALD`, `DIAMOND`, `MASTER`, `GRANDMASTER`, `CHALLENGER`. Divisiones `I`–`IV`, salvo los tres apex que no tienen división.

Cola **420** = Ranked Solo/Duo. Es la única que se recolecta.

## Data Dragon

CDN pública, **sin API key y sin rate limit**:

1. `https://ddragon.leagueoflegends.com/api/versions.json` → `versions[0]` es la más reciente.
2. `https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json`
3. `https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/summoner.json`

De `champion.json` se usan, por campeón: `key` (el id numérico, que es como viene en match-v5), `name`, `tags` (`Fighter`, `Tank`, `Mage`, `Assassin`, `Marksman`, `Support`), `info.{attack,defense,magic,difficulty}` y `stats.{hp,armor,attackrange}`.

Ids de hechizos de invocador que el esquema cuenta por equipo: **4** Flash · **12** Teleport · **14** Ignite. Smite (**11**) no se cuenta: el juego se lo impone al jungla, así que la columna daba 1 en toda partida (varianza cero) y se quitó.

## El recorrido semilla → dataset

```
por plataforma:
  por tier (IRON..CHALLENGER), por división, por página:
    A/B  → entries de la escalera            ← la SEMILLA
    por jugador:
      puuid = entry["puuid"]
      D  → ids de sus últimas partidas ranked
      por match_id no visto todavía:
        E  → detalle de la partida           → BRONCE
        filtros: gameVersion "16.*", duración ≥ 300 s,
                 exactamente 10 participantes, 5 por equipo
        por los 10 participantes:
          G  → maestría con su campeón       → BRONCE
          F  → entrada de liga               → BRONCE
```

`F` y `G` se cachean por puuid: un jugador aparece en varias partidas.

## Manejo de errores

| Código | Qué hacer |
|---|---|
| `200` | OK. |
| `429` | Leer el header `Retry-After` (default 5 s), poner esa key en cooldown **para ese host**, y seguir con otra key. |
| `403` | La key está vencida o es inválida. Sacarla del pool. Si se vacía el pool, fallar con un mensaje explícito de que hay que renovar la key. |
| `404` | Recurso inexistente. Devolver `None`, no reintentar. |
| `5xx` / timeout | Reintentar con backoff. |

## Trampas conocidas

Encontradas auditando el prototipo `../FF15`. Todas están corregidas en este proyecto; están acá para que no vuelvan a aparecer.

1. **`gameDuration` puede venir en milisegundos.** Riot cambió el criterio alrededor del parche 11.20: las partidas con `gameEndTimestamp` lo devuelven en segundos, las anteriores en milisegundos. Hay que chequear defensivamente: si el valor supera lo físicamente posible para una partida, dividir por 1000 y loguearlo.

2. **`teamPosition` puede venir vacío** (remakes, autofill). Si se asignan los roles buscando `TOP`/`JUNGLE`/`MIDDLE`/`BOTTOM`/`UTILITY` en orden y se mandan los sobrantes a los slots que quedan, el jugador termina etiquetado con un rol que no jugó, **en silencio**. Hay que dejar una columna bandera que lo registre, para poder filtrar esas filas después.

3. **Paginación de los tiers apex.** Los endpoints `challengerleagues`/`grandmasterleagues`/`masterleagues` **no aceptan `page`**: devuelven la liga entera. Si se los mete en un bucle de páginas, se re-pide la misma lista N veces gastando cuota al pedo.

4. **Memoizar también las partidas rechazadas.** Una partida que se descarga y se descarta (no es Season 16, dura menos de 300 s, es un remake) se vuelve a descargar cada vez que otro jugador semilla la vuelve a mencionar. Es el mayor desperdicio de cuota del prototipo: el detalle de partida es la respuesta más pesada de todas.

5. **`estimated_elo` es un proxy inventado, no un dato de Riot.** Riot no expone el MMR. La fórmula que se usa (ver `dataset-schema.md`) es una construcción del grupo. Hay que decirlo así en la defensa: es una variable derivada, no observada.

6. **Fuga temporal en `winrate` y `mastery_pts`.** Se consultan **hoy** (F y G), no al momento en que se jugó la partida. Para una partida de hace semanas son valores posteriores al hecho, lo cual tensiona el claim de "sólo variables pre-partida". La API no ofrece histórico, así que no se puede arreglar: se **declara** en el README y en la defensa.

7. **Campeones más nuevos que el snapshot de Data Dragon** devuelven `{}` al buscarlos por id, y contribuyen 0 a todos los agregados de composición sin avisar. Conviene loguear un warning cuando pasa.
