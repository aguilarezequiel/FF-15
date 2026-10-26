"""
### Dataset de partidas de League of Legends — Integrador 5K09-02

Construye el dataset del proyecto a partir de la **Riot Games API**, para
responder: *¿es posible predecir la duración de una partida de League of
Legends a partir de las características de los jugadores, de los campeones
de los equipos y las condiciones iniciales de la partida?*

Una fila es **una partida clasificatoria** (cola solo/duo 420) de la
Season 16. La clave es `match_id`. El objetivo es `game_duration_s`,
continuo en segundos: es un problema de **regresión**.

**Dos capas, y son tareas distintas en el grafo**, siguiendo el modelo
medallón:

* **Bronce** (`land_bronze`, y `land_timelines` en la rama del timeline)
  — las respuestas de la API tal como llegaron, comprimidas y particionadas
  por plataforma. Son las únicas tareas que bajan datos de la red. No
  interpretan nada. Guardan lo que hace falta para reconstruir una fila: el
  detalle de la partida, las entradas de liga y las maestrías de los 10
  jugadores, y la línea de tiempo de la partida.
* **Plata** (`refine_silver` + `consolidate`) — filas tipadas, una por
  partida, deduplicadas y validadas. **No toca la red**: lee del bronce.

La separación no es decorativa. Una partida que ya está en bronce **no se
vuelve a pedir nunca**, y la plata se reconstruye entera sobre todo el
bronce acumulado. De ahí salen las dos propiedades que la justifican:

* El dataset **crece corrida a corrida**. Con una development key no se
  juntan miles de partidas de una sentada, así que cada corrida suma al
  bronce y la plata se rehace sobre el total.
* Un bug en el parseo se arregla **sin volver a la fuente**: se corrige
  `refine_silver` y se reprocesa lo que ya está en disco.

Ojo con qué es idempotente y qué no, porque es la pregunta que se hace en
la entrega. Con el mismo bronce, la plata siempre da el mismo CSV: de
`refine_silver` para abajo todo es una función pura del disco. Lo que
cambia entre corridas es **cuánto** bronce hay, porque cada corrida sale a
buscar partidas que todavía no tiene.

La tercera capa —**oro**: features del modelo, agregados— no se construye
acá. Se arma en las Unidades 3 y 4 sobre esta misma plata.

**Una segunda rama: el estado de la partida al minuto N.** Las condiciones
iniciales solas predicen poco la duración (Entrega 3), así que el DAG baja
también la **línea de tiempo** de cada partida (`land_timelines`) y arma
un segundo dataset con cómo estaba la partida en el minuto de corte —5 por
defecto— (`refine_minuto` + `save_minuto`). Es un CSV aparte, unido al
principal por `match_id`: las 137 columnas de condiciones iniciales no
cambian. Las mismas reglas valen acá: el timeline crudo y completo va a
bronce, se pide una sola vez, y el corte en el minuto se hace en la plata.
Con `buscar_partidas_nuevas=False` el DAG no agranda el bronce y sólo
completa los timelines que falten: es el modo para un bronce que ya tiene
miles de partidas.

**Por qué `schedule=None`.** La development key de Riot vence cada 24 hs.
Un DAG programado corriendo sin nadie mirando fallaría todos los días
apenas venciera la key, y el ruido de esas fallas taparía las reales. Se
dispara a mano desde la interfaz, con la key recién renovada.

**Por qué las plataformas van en paralelo.** Riot aplica los rate limits
por región: cada plataforma tiene su propio balde por key. Seis
plataformas en paralelo, con un pool de keys, es lo que hace viable juntar
miles de partidas dentro de la ventana de 24 hs. Ojo con una sutileza:
`la2`, `la1`, `br1` y `na1` **comparten** el balde de match-v5 porque las
cuatro enrutan a `americas`; sí tienen baldes separados en league-v4 y
champion-mastery-v4.
"""
from __future__ import annotations

import gzip
import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pendulum
from airflow.sdk import Param, PokeReturnValue, dag, task
from airflow.task.trigger_rule import TriggerRule

from lol import ddragon, schema, timeline, transform
from lol.riot import (
    ALL_TIERS,
    PLATFORM_ROUTING,
    RiotClient,
    RiotKeysExhausted,
    resumen_liga,
    resumen_maestria,
)
from lol.seeds import iter_puuids

try:                                    # Airflow 3 expone BaseHook en el SDK
    from airflow.sdk import BaseHook
except ImportError:                     # pragma: no cover
    from airflow.hooks.base import BaseHook

log = logging.getLogger(__name__)

CONN_ID = "riot_api"

OUTPUT_DIR = Path("/usr/local/airflow/include/output")
BRONCE_DIR = OUTPUT_DIR / "bronze"
PLATA_DIR = OUTPUT_DIR / "silver"
PARTIAL_DIR = PLATA_DIR / "_parciales"
REPORTS_DIR = OUTPUT_DIR / "reports"

PLATAFORMAS = list(PLATFORM_ROUTING)

# Cada cuántas partidas se refresca el manifiesto de progreso. El payload
# crudo se escribe apenas llega —o sea, cada UNA— así que una tarea que se
# corta no pierde nada; esto es sólo para que el avance sea legible en los
# logs y para que el manifiesto quede razonablemente fresco.
CHECKPOINT_CADA = 10

# Cuántas partidas pedirle a cada jugador semilla. Más alto significa
# menos jugadores distintos y más partidas repetidas entre ellos.
PARTIDAS_POR_JUGADOR = 15

# Hilos que piden timelines dentro de cada región. Con un bucle secuencial
# el techo lo pone la latencia de cada request y no el cupo de las keys
# (ver la trampa 10 de references/riot-api.md); con cuatro hilos el que
# frena es el limitador del cliente, que es lo que corresponde.
HILOS_TIMELINE = 4


# --------------------------------------------------------------- bronce io

def _ruta_partida(platform: str, match_id: str) -> Path:
    return BRONCE_DIR / "matches" / f"plataforma={platform}" / f"{match_id}.json.gz"


def _ruta_perfil(platform: str, puuid: str, nombre: str) -> Path:
    return (BRONCE_DIR / "players" / f"plataforma={platform}"
            / f"puuid={puuid}" / f"{nombre}.json.gz")


def _ruta_descartadas(platform: str) -> Path:
    return BRONCE_DIR / "descartadas" / f"plataforma={platform}.txt"


def _ruta_timeline(platform: str, match_id: str) -> Path:
    return BRONCE_DIR / "timelines" / f"plataforma={platform}" / f"{match_id}.json.gz"


def _ruta_sin_timeline(platform: str) -> Path:
    return BRONCE_DIR / "descartadas" / f"sin_timeline_plataforma={platform}.txt"


def _leer_indice(ruta: Path) -> set[str]:
    if not ruta.exists():
        return set()
    return {linea.strip() for linea
            in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()}


def _ids_en_bronce(platform: str) -> list[str]:
    """Las partidas de la plataforma que ya están en bronce, ordenadas."""
    carpeta = BRONCE_DIR / "matches" / f"plataforma={platform}"
    return [r.name.removesuffix(".json.gz")
            for r in sorted(carpeta.glob("*.json.gz"))]


def escribir_json(destino: Path, data) -> None:
    """Escribe comprimido y de forma atómica.

    El temporal + rename evita que una tarea cortada a mitad de escritura
    deje un archivo truncado que después reviente el parseo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(destino)


def leer_json(ruta: Path):
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        return json.load(f)


def api_keys() -> list[str]:
    """Las keys, desde la Connection. Nunca desde el código.

    Acepta una o varias separadas por coma —una por integrante del grupo—
    porque el límite de Riot es por key y por región: más keys, más cupo.
    """
    conn = BaseHook.get_connection(CONN_ID)
    crudo = conn.password or ""
    keys = [k.strip() for k in crudo.split(",") if k.strip()]
    if not keys:
        raise ValueError(
            f"La Connection `{CONN_ID}` no tiene ninguna API key en el campo "
            "password. Copiá airflow_settings.example.yaml a "
            "airflow_settings.yaml, completala y hacé `astro dev restart`.")
    return keys


@dag(
    dag_id="lol_ingest",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    # Una tarea por plataforma, las seis a la vez: cada una golpea un host
    # distinto en los endpoints de plataforma.
    max_active_tasks=6,
    tags=["ciencia-de-datos", "unidad-1", "integrador", "5K09-02"],
    doc_md=__doc__,
    params={
        "partidas_objetivo": Param(
            1500, type="integer", minimum=10, maximum=100_000,
            title="Partidas objetivo",
            description=("Cuántas partidas juntar en total en esta corrida. "
                         "Se reparte en partes iguales entre las plataformas "
                         "elegidas. La consigna pide más de 1.000 filas."),
        ),
        "plataformas": Param(
            PLATAFORMAS, type="array",
            title="Plataformas",
            description=("Servidores a recorrer. Cada uno tiene su propio "
                         "cupo de rate limit por key, así que más "
                         "plataformas es más rápido."),
        ),
        "tiers": Param(
            ALL_TIERS, type="array",
            title="Tiers a muestrear",
            description=("Rangos de la escalera de los que salen los "
                         "jugadores semilla. Se recorren en orden aleatorio "
                         "para que una corrida cortada no quede sesgada."),
        ),
        "forzar": Param(
            False, type="boolean",
            title="Forzar la descarga",
            description=("Ignora el bronce ya bajado y vuelve a pedir todo. "
                         "Normalmente no hace falta: el bronce es "
                         "append-only."),
        ),
        "buscar_partidas_nuevas": Param(
            True, type="boolean",
            title="Buscar partidas nuevas",
            description=("Con False no se agranda el bronce: land_bronze no "
                         "pide partidas, sólo se bajan las líneas de tiempo "
                         "que falten para las partidas que ya están en disco "
                         "y se rehacen los dos datasets. Es el modo para "
                         "completar un bronce grande."),
        ),
        "minuto_corte": Param(
            5, type="integer", minimum=1, maximum=60,
            title="Minuto de corte",
            description=("En qué minuto se mira el estado de la partida "
                         "para el dataset del timeline. Cambiarlo no pide "
                         "nada a Riot: el timeline completo ya está en "
                         "bronce."),
        ),
    },
)
def lol_ingest():

    # ------------------------------------------------------------------ 1
    @task.sensor(poke_interval=120, timeout=1800, mode="reschedule",
                 soft_fail=True)
    def wait_for_riot() -> PokeReturnValue:
        """Espera a que la API responda y confirma que la key sirve.

        Un sensor sirve para esperar algo que está **fuera del control del
        DAG**. Con `mode="reschedule"` la tarea libera el worker entre
        sondeos en vez de ocuparlo durmiendo, y con `soft_fail=True`
        termina en `skipped` y no en `failed`: que Riot no responda no es
        un error de nuestro pipeline.

        Que esto esté arriba de todo es deliberado. La corrida real puede
        durar horas; enterarse de que la key venció recién al final sería
        el peor resultado posible.

        Hay dos fallas distintas y el sensor no las trata igual, porque no
        se resuelven igual:

        * **Riot no responde** — un corte pasa. Se sondea media hora antes
          de darlo por perdido: no tiene sentido tirar una corrida por
          diez minutos de indisponibilidad.
        * **La key no sirve** (401/403) — esperar no arregla nada. Se
          termina en el acto y se dice qué hacer. Media hora sondeando con
          una key vencida es media hora tirada.
        """
        try:
            cliente = RiotClient(api_keys())
        except RiotKeysExhausted as e:
            return PokeReturnValue(is_done=True,
                                   xcom_value={"ok": False,
                                               "motivo": str(e)})
        except Exception as e:
            # Un sensor nunca debe romper por una excepción inesperada:
            # su trabajo es reintentar.
            log.warning("No se pudo armar el cliente: %s", e)
            return PokeReturnValue(is_done=False)

        try:
            responde = cliente.ping()
        except RiotKeysExhausted as e:
            # Ninguna key del pool sirve. Cortar ya, no seguir sondeando.
            return PokeReturnValue(is_done=True,
                                   xcom_value={"ok": False,
                                               "motivo": str(e)})

        if responde:
            log.info("Riot responde y la key es válida.")
            return PokeReturnValue(is_done=True, xcom_value={"ok": True})

        log.warning("Riot no responde todavía. Reintento en 2 min.")
        return PokeReturnValue(is_done=False)

    # ------------------------------------------------------------------ 2
    @task.short_circuit(trigger_rule=TriggerRule.ALL_DONE)
    def check_key(**context) -> bool:
        """Corta la corrida si el sensor nunca consiguió respuesta.

        Corre con `ALL_DONE` porque la tarea de arriba puede haber quedado
        en `skipped`, que es justamente el caso que tiene que manejar: con
        la regla por defecto, `ALL_SUCCESS`, no se ejecutaría nunca cuando
        más falta hace.

        Devolver `False` deja todo lo de abajo en `skipped` y la corrida
        termina bien. No pasó nada porque no se podía hacer nada.
        """
        estado = context["ti"].xcom_pull(task_ids="wait_for_riot")
        if estado and estado.get("ok"):
            return True
        if estado and estado.get("motivo"):
            log.error("%s", estado["motivo"])
            return False
        log.error(
            "Riot no respondió en 30 minutos, o la API key está vencida. "
            "Las development keys duran 24 hs: regenerala en "
            "https://developer.riotgames.com, actualizá la Connection "
            "`riot_api` y volvé a disparar el DAG.")
        return False

    # ------------------------------------------------------------------ 3
    @task(retries=2, retry_delay=pendulum.duration(seconds=30))
    def fetch_ddragon() -> str:
        """**Bronce.** Metadatos de campeones y hechizos, crudos.

        Data Dragon es un CDN público: no pide key ni tiene rate limit,
        así que va aparte del cliente con pool. Se guarda particionado por
        versión porque los campeones cambian entre parches, y una partida
        vieja tiene que poder reinterpretarse con el catálogo que
        correspondía.
        """
        version = ddragon.latest_version()
        base = BRONCE_DIR / "ddragon" / f"version={version}"

        champs_path = base / "champion.json.gz"
        spells_path = base / "summoner.json.gz"

        if champs_path.exists() and spells_path.exists():
            log.info("Data Dragon %s ya está en bronce. No se re-pide.",
                     version)
            return version

        escribir_json(champs_path, ddragon.fetch_champions(version))
        escribir_json(spells_path, ddragon.fetch_spells(version))
        log.info("Data Dragon %s guardado en bronce.", version)
        return version

    # ------------------------------------------------------------------ 4
    @task
    def plan_plataformas(**context) -> list[dict]:
        """Reparte el objetivo entre las plataformas elegidas.

        Airflow corre cada tarea mapeada en su propio proceso, así que no
        existe el contador compartido en memoria que tendría un script
        monolítico. La cuota se reparte por adelantado y se deduplica al
        final: el total puede quedar apenas por debajo del objetivo si dos
        plataformas se cruzaron con la misma partida, cosa rara porque
        cada `match_id` lleva el prefijo de su región.
        """
        params = context["params"]
        plataformas = [p for p in params["plataformas"] if p in PLATFORM_ROUTING]
        if not plataformas:
            raise ValueError(
                f"Ninguna plataforma válida en {params['plataformas']!r}. "
                f"Opciones: {sorted(PLATFORM_ROUTING)}")

        cuota = math.ceil(params["partidas_objetivo"] / len(plataformas))
        trabajos = [{
            "platform": p,
            "region": PLATFORM_ROUTING[p]["region"],
            "nombre": PLATFORM_ROUTING[p]["name"],
            "cuota": cuota,
            "tiers": params["tiers"],
            "forzar": params["forzar"],
            "buscar": params["buscar_partidas_nuevas"],
        } for p in plataformas]

        log.info("Objetivo %s partidas · %s plataformas · cuota %s c/u",
                 params["partidas_objetivo"], len(plataformas), cuota)
        return trabajos

    # ------------------------------------------------------------------ 5
    @task(map_index_template="{{ task.op_kwargs['trabajo']['nombre'] }}",
          retries=1, retry_delay=pendulum.duration(minutes=2),
          execution_timeout=pendulum.duration(hours=20))
    def land_bronze(trabajo: dict) -> dict:
        """**Capa bronce**: guarda las respuestas crudas, sin interpretarlas.

        Junto con `land_timelines`, son las únicas tareas del DAG que bajan
        datos de la red. No parsea, no limpia, no valida: deja el JSON tal
        como vino y anota dónde quedó.

        La regla del bronce es **append-only**: una partida ya bajada no
        se vuelve a pedir jamás, ni en esta corrida ni en las que vengan.
        Cada corrida sale a buscar partidas nuevas hasta llenar su cuota,
        y lo que ya está en disco se cuenta sin gastar una request.

        Se guardan también las partidas **descartadas** —las que no son de
        Season 16, las que duran menos de cinco minutos, los remakes— en
        un índice aparte. No guardarlas es el mayor desperdicio de cuota
        posible: el detalle de partida es la respuesta más pesada de
        todas, y sin el índice se vuelve a bajar cada vez que otro jugador
        semilla la menciona.

        El `execution_timeout` de 20 hs está calibrado contra la ventana
        de vida de una development key.

        Con `buscar_partidas_nuevas=False` la tarea no toca la red y
        termina en el acto: el bronce queda como está y la corrida sólo
        completa timelines. Sigue en el grafo igual, para que la plata y
        la rama del timeline no cambien de forma según el modo.
        """
        platform = trabajo["platform"]
        region = trabajo["region"]
        cuota = trabajo["cuota"]
        forzar = trabajo["forzar"]

        if not trabajo.get("buscar", True):
            log.info("%s · buscar_partidas_nuevas=False: no se piden "
                     "partidas. Bronce actual: %s partidas.",
                     trabajo["nombre"], len(_ids_en_bronce(platform)))
            return {"platform": platform, "nombre": trabajo["nombre"],
                    "matches": [], "nuevas": 0, "reusadas": 0, "pedidas": 0}

        cliente = RiotClient(api_keys())

        ruta_descartes = _ruta_descartadas(platform)
        descartadas: set[str] = set()
        if ruta_descartes.exists() and not forzar:
            descartadas = {
                linea.strip() for linea
                in ruta_descartes.read_text(encoding="utf-8").splitlines()
                if linea.strip()}

        landeadas: list[str] = []
        nuevas = reusadas = descartes_nuevos = 0

        def perfil_de(participante: dict, owner_key: str | None) -> None:
            """Baja liga y maestría de un jugador, si no están en bronce.

            `owner_key` es la key que trajo el detalle de esta partida:
            los `puuid` de los participantes vienen encriptados para ella,
            no para la que semilló al jugador ni para ninguna otra del
            pool. Ver `RiotClient._request`.
            """
            puuid = participante.get("puuid")
            cid = participante.get("championId")
            if not puuid:
                return

            p_liga = _ruta_perfil(platform, puuid, "liga")
            if not p_liga.exists() or forzar:
                escribir_json(p_liga, cliente.league_by_puuid(
                    platform, puuid, owner_key=owner_key))

            p_mast = _ruta_perfil(platform, puuid, f"maestria_{cid}")
            if not p_mast.exists() or forzar:
                escribir_json(p_mast, cliente.mastery(
                    platform, puuid, cid, owner_key=owner_key))

        for puuid, _tier, owner_key in iter_puuids(cliente, platform,
                                                   trabajo["tiers"]):
            if len(landeadas) >= cuota:
                break

            for match_id in cliente.match_ids(region, puuid,
                                              count=PARTIDAS_POR_JUGADOR,
                                              owner_key=owner_key):
                if len(landeadas) >= cuota:
                    break
                if match_id in descartadas:
                    continue

                destino = _ruta_partida(platform, match_id)
                if destino.exists() and not forzar:
                    if match_id not in landeadas:
                        landeadas.append(match_id)
                        reusadas += 1
                    continue

                datos, match_key = cliente.match(region, match_id)
                if datos is None:
                    continue

                # Se filtra ANTES de gastar 20 requests en los perfiles de
                # los 10 jugadores de una partida que igual se va a tirar.
                try:
                    _, participantes, _ = transform.admitir(datos)
                except transform.PartidaDescartada as e:
                    descartadas.add(match_id)
                    descartes_nuevos += 1
                    log.debug("%s descartada: %s", match_id, e)
                    continue

                escribir_json(destino, datos)

                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(
                        lambda p: perfil_de(p, match_key), participantes))

                landeadas.append(match_id)
                nuevas += 1

                if len(landeadas) % CHECKPOINT_CADA == 0:
                    _guardar_manifiesto(platform, landeadas,
                                        descartadas, ruta_descartes)
                    log.info("%s · %s/%s partidas en bronce "
                             "(%s nuevas, %s reusadas, %s descartadas) · "
                             "%s requests a Riot",
                             trabajo["nombre"], len(landeadas), cuota,
                             nuevas, reusadas, descartes_nuevos,
                             cliente.pedidas)

        _guardar_manifiesto(platform, landeadas, descartadas, ruta_descartes)
        log.info("%s · FIN · %s partidas en bronce (%s nuevas, %s reusadas, "
                 "%s descartadas nuevas) · %s requests a Riot",
                 trabajo["nombre"], len(landeadas), nuevas, reusadas,
                 descartes_nuevos, cliente.pedidas)

        # Por XCom viajan metadatos, no datos: una lista de ids y conteos.
        # Los payloads pesan megabytes y viven en disco.
        return {"platform": platform, "nombre": trabajo["nombre"],
                "matches": landeadas, "nuevas": nuevas,
                "reusadas": reusadas, "pedidas": cliente.pedidas}

    # ------------------------------------------------------------------ 6
    @task(map_index_template="{{ task.op_kwargs['lote']['nombre'] }}")
    def refine_silver(lote: dict, version: str) -> str:
        """**Capa plata**: del JSON crudo a filas tipadas, una por partida.

        **No toca la red.** Todo lo que necesita ya está en bronce: el
        detalle de la partida, las entradas de liga y las maestrías. Esa
        es la propiedad que hace valiosa la separación: esta tarea se
        puede correr cien veces mientras se depura el parseo y Riot ni se
        entera.

        Procesa **todo el bronce de la plataforma**, no sólo lo que bajó
        esta corrida. Es lo que hace que el dataset se acumule: con una
        development key no se llegan a juntar miles de partidas de una
        sentada, así que cada corrida suma al bronce y la plata se
        reconstruye entera sobre el total. Como efecto secundario, una
        corrida que se cortó después de dejar bronce en disco no pierde
        nada: la siguiente lo levanta igual.
        """
        import pandas as pd

        platform = lote["platform"]
        base = BRONCE_DIR / "ddragon" / f"version={version}"
        campeones = ddragon.index_champions(leer_json(base / "champion.json.gz"))

        rutas = sorted(
            (BRONCE_DIR / "matches" / f"plataforma={platform}").glob("*.json.gz"))

        filas, descartes = [], 0
        for ruta in rutas:
            match_id = ruta.name.removesuffix(".json.gz")
            datos = leer_json(ruta)

            perfiles = {}
            for p in (datos.get("info") or {}).get("participants", []):
                puuid, cid = p.get("puuid"), p.get("championId")
                p_liga = _ruta_perfil(platform, puuid, "liga")
                p_mast = _ruta_perfil(platform, puuid, f"maestria_{cid}")
                perfiles[puuid] = {
                    "liga": resumen_liga(
                        leer_json(p_liga) if p_liga.exists() else None),
                    "maestria": resumen_maestria(
                        leer_json(p_mast) if p_mast.exists() else None),
                }

            try:
                filas.append(transform.to_row(datos, campeones, perfiles))
            except transform.PartidaDescartada as e:
                descartes += 1
                log.debug("%s descartada en plata: %s", match_id, e)

        PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
        destino = PARTIAL_DIR / f"plataforma_{platform}.csv"
        pd.DataFrame(filas, columns=schema.COLUMNS).to_csv(destino,
                                                           index=False)
        log.info("%s · %s filas de plata desde %s partidas de bronce "
                 "(%s bajadas en esta corrida, %s descartadas) -> %s",
                 lote["nombre"], len(filas), len(rutas),
                 len(lote["matches"]), descartes, destino.name)
        return str(destino)

    # ------------------------------------------------------------------ 7
    @task
    def consolidate(rutas: list[str]) -> str:
        """Junta los parciales, deduplica por `match_id` y castea tipos.

        Sigue siendo plata: una fila por partida, sin agregar nada nuevo.
        La deduplicación acá es lo que sostiene la promesa de que la clave
        primaria es única, que es el criterio que más pesa en la entrega.
        """
        import pandas as pd

        partes = [pd.read_csv(r, low_memory=False) for r in rutas if r]
        partes = [p for p in partes if len(p)]
        if not partes:
            raise ValueError(
                "Ninguna plataforma produjo filas. Revisá los logs de "
                "land_bronze: lo más probable es que la key esté vencida.")

        df = pd.concat(partes, ignore_index=True)[schema.COLUMNS]
        antes = len(df)
        df = df.drop_duplicates("match_id").reset_index(drop=True)
        log.info("%s filas, %s tras deduplicar por match_id", antes, len(df))

        for c in schema.ENTEROS:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        for c in schema.FLOTANTES:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        destino = OUTPUT_DIR / "_consolidado.csv"
        df.to_csv(destino, index=False)
        return str(destino)

    # ------------------------------------------------------------------ 8
    @task
    def validate(ruta: str) -> str:
        """Chequeos duros + el reporte de calidad de la consigna.

        Si algún chequeo falla, el DAG falla: no se publica un dataset
        roto. Y de paso deja escritos, en un archivo, los seis números que
        la cátedra pide tener a mano en la defensa — para no calcularlos
        a las apuradas cinco minutos antes.
        """
        import pandas as pd

        df = pd.read_csv(ruta, low_memory=False)
        problemas = []

        if list(df.columns) != schema.COLUMNS:
            faltan = set(schema.COLUMNS) - set(df.columns)
            sobran = set(df.columns) - set(schema.COLUMNS)
            problemas.append(
                f"columnas distintas (faltan {faltan}, sobran {sobran})")
        if not df["match_id"].is_unique:
            n = int(df["match_id"].duplicated().sum())
            problemas.append(f"{n} match_id repetidos")
        for c in schema.OBLIGATORIAS:
            if c in df.columns and df[c].isna().any():
                problemas.append(f"{c} tiene {int(df[c].isna().sum())} nulos")
        if "game_duration_s" in df.columns and not df["game_duration_s"].between(
                schema.DURACION_MINIMA_S,
                schema.DURACION_MAXIMA_PLAUSIBLE_S).all():
            problemas.append("game_duration_s fuera del rango plausible")
        vacias = list(df.columns[df.isna().all()])
        if vacias:
            problemas.append(f"columnas 100% nulas: {vacias}")

        if problemas:
            raise ValueError(
                "Validación fallida:\n  - " + "\n  - ".join(problemas))

        _escribir_reporte(df)

        log.info("Validación OK: %s filas x %s columnas. Clave única: %s. "
                 "Duración media: %.0f s",
                 len(df), len(df.columns), df["match_id"].is_unique,
                 df["game_duration_s"].mean())
        if len(df) <= 1000:
            log.warning("ATENCIÓN: %s filas. La consigna pide más de 1.000. "
                        "Volvé a disparar el DAG: el bronce ya bajado se "
                        "reusa, así que la próxima corrida sólo suma.",
                        len(df))
        return ruta

    # ------------------------------------------------------------------ 9
    @task
    def save(ruta: str, **context) -> str:
        """Escribe el entregable, fechado con la corrida.

        La fecha sale del DagRun y no de `ds`: `ds` sólo existe cuando el
        DAG tiene schedule, y éste corre a demanda. Es un tropiezo clásico
        al pasar de Airflow 2 a 3.
        """
        import shutil

        dag_run = context["dag_run"]
        momento = dag_run.logical_date or dag_run.run_after
        ds = momento.date().isoformat()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        destino = OUTPUT_DIR / f"lol_{ds}.csv"
        shutil.copy(ruta, destino)
        log.info("Dataset escrito en %s", destino)
        return str(destino)

    # ----------------------------------------------------------------- 10
    @task
    def plan_timelines(lotes: list[dict], **context) -> list[dict]:
        """Agrupa las plataformas por **región continental**.

        El timeline vive en match-v5, que se pide al host de la región
        (`americas`, `europe`, `asia`) y no al de la plataforma. Cada
        tarea mapeada corre en su propio proceso con su propio limitador:
        si las cuatro plataformas de `americas` pidieran timelines por
        separado, cada una creería tener el cupo entero del host y entre
        las cuatro lo pasarían cuatro veces, a fuerza de 429. Con una
        tarea por región, un solo limitador lleva la cuenta exacta.

        Recibe la salida de `land_bronze` para correr **después** de que
        el bronce de partidas esté completo: no se le puede pedir el
        timeline a una partida que todavía no se bajó.
        """
        params = context["params"]
        por_region: dict[str, list[str]] = {}
        for lote in lotes:
            region = PLATFORM_ROUTING[lote["platform"]]["region"]
            por_region.setdefault(region, []).append(lote["platform"])

        trabajos = [{"region": region, "plataformas": sorted(plataformas),
                     "minuto": params["minuto_corte"],
                     "forzar": params["forzar"]}
                    for region, plataformas in sorted(por_region.items())]
        log.info("Timelines por región: %s",
                 {t["region"]: t["plataformas"] for t in trabajos})
        return trabajos

    # ----------------------------------------------------------------- 11
    @task(map_index_template="{{ task.op_kwargs['trabajo']['region'] }}",
          retries=1, retry_delay=pendulum.duration(minutes=2),
          execution_timeout=pendulum.duration(hours=20))
    def land_timelines(trabajo: dict) -> dict:
        """**Capa bronce**: la línea de tiempo cruda de cada partida.

        Recorre **todo el bronce de partidas** de la región, no sólo lo
        que bajó esta corrida: así un bronce juntado antes de que existiera
        esta tarea se completa solo, sin volver a pedir las partidas.

        Las mismas reglas que `land_bronze`. Se guarda el timeline entero,
        tal como llega, y no recortado al minuto de corte: recortarlo
        obligaría a volver a pedir 19.000 timelines el día que se quiera
        el minuto 10. Es append-only: un timeline que ya está en disco no
        se vuelve a pedir. Y si Riot contesta 404 —no tiene esa línea de
        tiempo— se anota en un índice aparte para no preguntar de nuevo.
        Un fallo transitorio, en cambio, no se anota: se reintenta en la
        próxima corrida.

        Los timelines se piden con varios hilos dentro de la región (ver
        `HILOS_TIMELINE`); el limitador del cliente es compartido entre
        hilos, así que el ritmo lo sigue poniendo el cupo de las keys.
        """
        region = trabajo["region"]
        forzar = trabajo["forzar"]

        sin_timeline = {p: (set() if forzar else _leer_indice(_ruta_sin_timeline(p)))
                        for p in trabajo["plataformas"]}
        pendientes = [
            (p, mid) for p in trabajo["plataformas"] for mid in _ids_en_bronce(p)
            if mid not in sin_timeline[p]
            and (forzar or not _ruta_timeline(p, mid).exists())]
        log.info("%s · %s timelines por bajar en %s", region,
                 len(pendientes), trabajo["plataformas"])

        def guardar_indices() -> None:
            for p, ids in sin_timeline.items():
                ruta = _ruta_sin_timeline(p)
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text("\n".join(sorted(ids)), encoding="utf-8")

        conteo = {"nuevos": 0, "no_existen": 0, "fallidos": 0}
        if not pendientes:
            return {**trabajo, **conteo, "pedidas": 0}

        cliente = RiotClient(api_keys())

        def bajar(par: tuple[str, str]) -> str:
            platform, match_id = par
            datos, no_existe = cliente.timeline(region, match_id)
            if datos is not None:
                escribir_json(_ruta_timeline(platform, match_id), datos)
                return "nuevos"
            return "no_existen" if no_existe else "fallidos"

        try:
            with ThreadPoolExecutor(max_workers=HILOS_TIMELINE) as pool:
                for i, (par, res) in enumerate(
                        zip(pendientes, pool.map(bajar, pendientes),
                            strict=True), 1):
                    conteo[res] += 1
                    if res == "no_existen":
                        sin_timeline[par[0]].add(par[1])
                    if i % (CHECKPOINT_CADA * 10) == 0:
                        guardar_indices()
                        log.info("%s · %s/%s timelines (%s nuevos, %s sin "
                                 "timeline en Riot, %s fallidos) · %s "
                                 "requests", region, i, len(pendientes),
                                 conteo["nuevos"], conteo["no_existen"],
                                 conteo["fallidos"], cliente.pedidas)
        finally:
            # Si las keys vencen a mitad de camino la tarea falla, pero lo
            # ya bajado está en disco y el índice de 404 no se pierde.
            guardar_indices()

        log.info("%s · FIN · %s timelines nuevos, %s sin timeline en Riot, "
                 "%s fallidos · %s requests a Riot", region, conteo["nuevos"],
                 conteo["no_existen"], conteo["fallidos"], cliente.pedidas)
        return {**trabajo, **conteo, "pedidas": cliente.pedidas}

    # ----------------------------------------------------------------- 12
    @task(map_index_template="{{ task.op_kwargs['lote']['region'] }}")
    def refine_minuto(lote: dict) -> dict:
        """**Capa plata** del timeline: el estado de la partida al minuto N.

        No toca la red: lee la partida y su timeline del bronce y corta en
        el minuto de corte. Por eso cambiar el minuto es barato: es volver
        a correr esta tarea, no volver a pedirle nada a Riot.

        Además corre `timeline.chequeo_contra_partida` sobre cada partida:
        cuenta los eventos de la partida **entera** y los compara con los
        totales que trae el detalle (kills, torres, placas, monstruos,
        wards, primera sangre). Es la prueba, con datos reales, de que los
        eventos se están leyendo bien. El resultado viaja por XCom —son
        catorce números, no datos— y `save_minuto` lo deja en el reporte.
        """
        import pandas as pd

        minuto = lote["minuto"]
        filas, sin_tl, descartes = [], 0, 0
        chequeo = {c: {"coinciden": 0, "comparadas": 0}
                   for c in timeline.CHEQUEOS}

        for platform in lote["plataformas"]:
            for match_id in _ids_en_bronce(platform):
                ruta_tl = _ruta_timeline(platform, match_id)
                if not ruta_tl.exists():
                    sin_tl += 1
                    continue
                datos = leer_json(_ruta_partida(platform, match_id))
                linea = leer_json(ruta_tl)
                try:
                    filas.append(timeline.estado_al_minuto(datos, linea, minuto))
                except transform.PartidaDescartada as e:
                    descartes += 1
                    log.debug("%s fuera del dataset del minuto: %s",
                              match_id, e)
                    continue
                for c, ok in timeline.chequeo_contra_partida(datos, linea).items():
                    if ok is not None:
                        chequeo[c]["comparadas"] += 1
                        chequeo[c]["coinciden"] += int(ok)

        PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
        destino = PARTIAL_DIR / f"minuto{minuto}_{lote['region']}.csv"
        pd.DataFrame(filas, columns=schema.columnas_minuto(minuto)).to_csv(
            destino, index=False)
        log.info("%s · %s filas al minuto %s (%s partidas sin timeline, %s "
                 "fuera por durar menos) -> %s", lote["region"], len(filas),
                 minuto, sin_tl, descartes, destino.name)
        return {"region": lote["region"], "minuto": minuto,
                "ruta": str(destino), "filas": len(filas),
                "sin_timeline": sin_tl, "descartadas": descartes,
                "chequeo": chequeo}

    # ----------------------------------------------------------------- 13
    @task
    def save_minuto(lotes: list[dict], **context) -> str:
        """Junta las regiones, valida y escribe el dataset al minuto N.

        Hace en una sola tarea lo que la rama principal reparte en tres
        (`consolidate`, `validate`, `save`): este dataset tiene 35
        columnas de tipos conocidos y no necesita el casteo de la plata
        principal. Los chequeos duros son los mismos —columnas exactas,
        clave única, nada vacío fuera de la columna que puede estarlo— y
        si falla uno, falla el DAG.

        El reporte que deja incluye el chequeo contra el detalle de la
        partida: si una métrica no coincide nunca, el problema es cómo se
        lee el evento y no la fuente, y eso tiene que verse antes de
        modelar con ella.
        """
        import pandas as pd

        lotes = list(lotes)
        minuto = lotes[0]["minuto"]
        columnas = schema.columnas_minuto(minuto)

        partes = [pd.read_csv(lote["ruta"]) for lote in lotes
                  if lote["filas"]]
        if not partes:
            raise ValueError(
                f"Ninguna región produjo filas al minuto {minuto}. Revisá "
                "los logs de land_timelines: lo más probable es que no se "
                "haya bajado ningún timeline (key vencida).")
        df = pd.concat(partes, ignore_index=True)
        df = df.drop_duplicates("match_id").reset_index(drop=True)

        problemas = []
        if list(df.columns) != columnas:
            problemas.append("las columnas no son las de schema.columnas_minuto")
        if not df["match_id"].is_unique:
            problemas.append("match_id repetidos")
        obligatorias = [c for c in columnas
                        if c not in schema.nulables_minuto(minuto)]
        con_nulos = [c for c in obligatorias if df[c].isna().any()]
        if con_nulos:
            problemas.append(f"nulos en {con_nulos}")
        if problemas:
            raise ValueError(
                "Validación fallida:\n  - " + "\n  - ".join(problemas))

        chequeo = {c: {"coinciden": 0, "comparadas": 0}
                   for c in timeline.CHEQUEOS}
        for lote in lotes:
            for c, v in lote["chequeo"].items():
                chequeo[c]["coinciden"] += v["coinciden"]
                chequeo[c]["comparadas"] += v["comparadas"]
        for c, v in chequeo.items():
            if v["comparadas"] and v["coinciden"] < v["comparadas"]:
                log.warning("Chequeo %s: coincide en %s de %s partidas.",
                            c, v["coinciden"], v["comparadas"])

        _escribir_reporte_minuto(df, minuto, lotes, chequeo)

        dag_run = context["dag_run"]
        momento = dag_run.logical_date or dag_run.run_after
        ds = momento.date().isoformat()

        destino = OUTPUT_DIR / f"lol_min{minuto}_{ds}.csv"
        df.to_csv(destino, index=False)
        log.info("Dataset al minuto %s: %s filas x %s columnas -> %s",
                 minuto, len(df), len(df.columns), destino)
        return str(destino)

    # --------------------------------------------------------------- grafo
    espera = wait_for_riot()
    sigue = check_key()
    version = fetch_ddragon()
    plan = plan_plataformas()

    bronces = land_bronze.expand(trabajo=plan)
    parciales = refine_silver.partial(version=version).expand(lote=bronces)

    # El único lugar donde hacen falta dependencias a mano: estas tareas no
    # se pasan datos entre sí, sólo ordenan el flujo.
    espera >> sigue >> [version, plan]

    save(validate(consolidate(parciales)))

    # La rama del timeline arranca cuando el bronce de partidas está
    # completo y no depende de la plata principal: si una falla, la otra
    # igual entrega su dataset.
    lineas = land_timelines.expand(trabajo=plan_timelines(bronces))
    save_minuto(refine_minuto.expand(lote=lineas))


# ------------------------------------------------------------------ helpers

def _guardar_manifiesto(platform: str, landeadas: list[str],
                        descartadas: set[str], ruta_descartes: Path) -> None:
    """Refresca el índice de descartadas y el manifiesto de progreso."""
    ruta_descartes.parent.mkdir(parents=True, exist_ok=True)
    ruta_descartes.write_text("\n".join(sorted(descartadas)),
                              encoding="utf-8")
    manifiesto = BRONCE_DIR / "matches" / f"plataforma={platform}" / "_manifiesto.txt"
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    manifiesto.write_text("\n".join(landeadas), encoding="utf-8")


def _escribir_reporte(df) -> None:
    """Deja en disco los seis números que pide la consigna."""
    nulos = df.isna().mean().sort_values(ascending=False)
    con_nulos = nulos[nulos > 0]

    lineas = [
        "# Chequeo de calidad del dataset",
        "",
        f"Filas: **{len(df)}** · Columnas: **{len(df.columns)}**",
        "",
        "| Criterio | Qué tiene que dar | Resultado |",
        "|---|---|---|",
        f"| Clave sin duplicados | True | **{df['match_id'].is_unique}** |",
        f"| Volumen suficiente | > 1.000 filas | **{len(df)}** |",
        f"| Ancho suficiente | >= 5 columnas | **{df.shape[1]}** |",
        ("| Sin columnas vacías | ninguna al 100% | "
         f"**{list(df.columns[df.isna().all()]) or 'ninguna'}** |"),
        "",
        "## Mezcla de tipos",
        "",
        "```",
        str(df.dtypes.value_counts()),
        "```",
        "",
        "## Nulos por columna (sólo las que tienen)",
        "",
        "```",
        str(con_nulos) if len(con_nulos) else "Ninguna columna tiene nulos.",
        "```",
        "",
        "## La columna objetivo",
        "",
        "```",
        str(df["game_duration_s"].describe()),
        "```",
        "",
        "## Calidad de la asignación de roles",
        "",
        ("Partidas con al menos un rol inferido (`teamPosition` vacío en "
         f"la fuente): **{int((df['roles_inferidos'] > 0).sum())}** de "
         f"{len(df)}."),
        "",
        ("Esas filas conservan todos sus datos; lo único incierto es a qué "
         "carril se asignó cada jugador. Se pueden filtrar con "
         "`df[df.roles_inferidos == 0]`."),
    ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    destino = REPORTS_DIR / "calidad.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    log.info("Reporte de calidad en %s", destino)


def _escribir_reporte_minuto(df, minuto: int, lotes: list[dict],
                             chequeo: dict) -> None:
    """El reporte del dataset al minuto N, con el chequeo de los eventos."""
    nulos = df.isna().mean()
    con_nulos = nulos[nulos > 0]

    lineas = [
        f"# Chequeo del dataset al minuto {minuto}",
        "",
        f"Filas: **{len(df)}** · Columnas: **{len(df.columns)}** · "
        f"Clave única: **{df['match_id'].is_unique}**",
        "",
        "## Cuántas partidas del bronce quedaron afuera, y por qué",
        "",
        "| Región | Filas | Sin timeline en bronce | Terminan antes del corte |",
        "|---|---|---|---|",
    ]
    lineas += [f"| {lote['region']} | {lote['filas']} | "
               f"{lote['sin_timeline']} | {lote['descartadas']} |"
               for lote in lotes]
    lineas += [
        "",
        "## Los eventos contra el detalle de la partida",
        "",
        ("Cada evento se cuenta sobre la partida **entera** y se compara con "
         "el total que trae el detalle (`teams[].objectives` y los campos "
         "de cada jugador). Si una métrica no coincide casi nunca, el evento "
         "se está leyendo mal y esa métrica no se usa hasta corregirlo."),
        "",
        "| Métrica | Coinciden | Comparadas | % |",
        "|---|---|---|---|",
    ]
    for c, v in chequeo.items():
        pct = (f"{100 * v['coinciden'] / v['comparadas']:.1f}"
               if v["comparadas"] else "—")
        lineas.append(f"| {c} | {v['coinciden']} | {v['comparadas']} | {pct} |")
    lineas += [
        "",
        "## Nulos",
        "",
        "```",
        str(con_nulos) if len(con_nulos) else "Ninguna columna tiene nulos.",
        "```",
        "",
        (f"`first_blood_s_m{minuto}` vacío = no hubo primera sangre antes del "
         f"minuto {minuto}. No es un dato perdido."),
    ]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    destino = REPORTS_DIR / f"calidad_minuto{minuto}.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    log.info("Reporte del minuto %s en %s", minuto, destino)


lol_ingest()
