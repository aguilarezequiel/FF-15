# Convenciones de Airflow de la cátedra

Fuente: `Documentacion/Intro a Airflow/` (Airflow **3.3** · Astro Runtime **3.3-4**) y el proyecto de referencia `../airflow-fifa`.

## Contenido

- [El stack y por qué](#el-stack-y-por-qué)
- [Migración Airflow 2 → 3](#migración-airflow-2--3)
- [Anatomía de un DAG](#anatomía-de-un-dag)
- [Operadores, hooks y funciones propias](#operadores-hooks-y-funciones-propias)
- [Connections](#connections)
- [Contexto de ejecución](#contexto-de-ejecución)
- [XCom](#xcom)
- [Mapeo dinámico](#mapeo-dinámico)
- [Control de flujo](#control-de-flujo)
- [Params](#params)
- [Idempotencia](#idempotencia)
- [Comandos de Astro CLI](#comandos-de-astro-cli)
- [Errores frecuentes](#errores-frecuentes)
- [Trampas del proyecto de referencia](#trampas-del-proyecto-de-referencia)

---

## El stack y por qué

- **Astro Runtime** es una imagen de Docker con Airflow ya armado y probado. **Astro CLI** es la herramienta que levanta esa imagen localmente. `astro dev start` no es un comando de Airflow: es de Astro. Se podría correr Airflow sin ninguna de las dos; se usa Astro porque ahorra una tarde de configuración.
- **Procesos de Airflow 3:** `dag-processor` (lee los `.py` de `dags/` y registra lo que encuentra — en Airflow 2 vivía dentro del scheduler), `scheduler` (decide qué tarea está lista), `api-server` (interfaz web y API — en Airflow 2 se llamaba `webserver`), `triggerer` (esperas asincrónicas), metadata DB. Ningún proceso le habla directo a otro.
- **Providers:** de fábrica vienen sólo `apache-airflow-providers-standard` y `apache-airflow-providers-common-sql`. El resto se agrega a `requirements.txt` y después `astro dev restart`.
- **Plugins:** en esta materia no se escribe ninguno. El código reusable va en `include/` y se importa vía `PYTHONPATH`.

> *"Antes de escribir código para hablar con tu fuente, fijate si hay un provider que ya lo resuelva."*

## Migración Airflow 2 → 3

Casi todo lo que se googlea está escrito para Airflow 2. Esta tabla es la traducción:

| Airflow 2 | Airflow 3 |
|---|---|
| `from airflow.decorators import dag, task` | `from airflow.sdk import dag, task` |
| `from airflow.operators.python import PythonOperator` | `from airflow.providers.standard.operators.python import ...` |
| `from airflow.operators.bash import BashOperator` | `from airflow.providers.standard.operators.bash import ...` |
| `from airflow.operators.dummy import DummyOperator` | `EmptyOperator` (el módulo `dummy` ya no existe) |
| `from airflow.utils.trigger_rule import TriggerRule` | `from airflow.task.trigger_rule import TriggerRule` |
| `schedule_interval=...` | `schedule=...` |
| `context["execution_date"]` | `context["logical_date"]` |
| `context["prev_ds"]`, `context["next_ds"]`, `context["conf"]` | ya no existen |
| `Variable.get(k, default_var=None)` | `Variable.get(k, default=None)` |
| servicio `webserver` | servicio `api-server` |
| el scheduler parsea los DAGs | lo hace el `dag-processor`, aparte |

Import completo del Task SDK que se usa acá:
```python
from airflow.sdk import Param, PokeReturnValue, Variable, dag, task
from airflow.task.trigger_rule import TriggerRule
```

## Anatomía de un DAG

Esqueleto, en este orden:

```python
"""
### Título en Markdown

Docstring largo que explica el diseño. Se pasa como doc_md y se renderiza
en la UI, así que es la chuleta de la defensa oral.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, task

from lol import schema          # first-party, desde include/

log = logging.getLogger(__name__)

OUTPUT_DIR = Path("/usr/local/airflow/include/output")


@dag(
    dag_id="lol_ingest",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    max_active_tasks=6,
    tags=["ciencia-de-datos", "unidad-1", "integrador", "5K09-02"],
    doc_md=__doc__,
    params={...},
)
def lol_ingest():
    ...

lol_ingest()   # SIN ESTA LÍNEA el DAG no aparece en la UI
```

**Argumentos del `@dag`, en este orden:** `dag_id` (igual al nombre del archivo), `schedule` (`None` = a demanda; `"@daily"`, `"0 8 * * *"`), `start_date`, `catchup=False`, `max_active_tasks` (sólo si importa la concurrencia), `tags`, `doc_md=__doc__`, `params`.

**No hay `default_args`** en el proyecto de la cátedra. Los reintentos se ponen por tarea, y sólo en las que tocan la red:

```python
@task(retries=2, retry_delay=pendulum.duration(seconds=30))
```

Se usa `pendulum.duration`, no `datetime.timedelta`.

## Operadores, hooks y funciones propias

Tres formas, y cuándo va cada una:

| Forma | Cuándo |
|---|---|
| Operador prefabricado (`HttpOperator`) | La acción es estándar y alguien ya la resolvió bien. |
| `@task` + hook (`HttpHook`) | Necesitás lógica propia pero querés reusar la conexión y el manejo de errores. |
| `@task` pelado | No hay sistema externo: transformar, validar, guardar. |

Detalle del `HttpOperator`: `response_filter` es la función que decide qué parte de la respuesta sobrevive. El objeto `Response` entero no es serializable y no se puede guardar en XCom.

## Connections

```yaml
# airflow_settings.yaml — Astro CLI las carga solas al hacer astro dev start
airflow:
  connections:
    - conn_id: riot_api
      conn_type: http
      conn_host: api.riotgames.com
      conn_schema: https
      conn_password: RGAPI-...
```

> *"Si tu fuente pide API key, token o usuario y contraseña, esa credencial va en una Connection, nunca en el `.py`."*

**Consecuencia para este repo:** como nuestro `airflow_settings.yaml` contiene la key, va **gitignoreado**, y se versiona un `airflow_settings.example.yaml` sin el secreto. (En `airflow-fifa` el archivo sí se versiona, pero porque su única conexión es la PokéAPI, que es pública y no tiene secreto — la diferencia está comentada en su `.gitignore`.)

## Contexto de ejecución

```python
@task
def guardar(**context):
    params  = context["params"]
    ti      = context["ti"]
    dag_run = context["dag_run"]
```

**Cuidado con `ds`.** Sólo existe cuando el DAG tiene `schedule` y por lo tanto intervalo de datos. La forma robusta, que anda siempre:

```python
dag_run = context["dag_run"]
momento = dag_run.logical_date or dag_run.run_after
ds = momento.date().isoformat()
```

## XCom

Por XCom viajan **metadatos, no datos**: rutas, identificadores, banderas, conteos.

La regla nace de un número concreto: en el proyecto de la cátedra, pasar las 345 páginas de HTML por XCom serían 260 MB en la metadata DB; en disco comprimidas ocupan 16,5 MB. Es de los errores más comunes al empezar con la herramienta.

## Mapeo dinámico

```python
ligas    = discover_leagues()                  # devuelve N diccionarios
bronces  = land_bronze.expand(league=ligas)    # crea N instancias
parciales = refine_silver.expand(lote=bronces) # se encadena directo
```

Para que el grafo se lea solo en la UI:

```python
@task(map_index_template="{{ task.op_kwargs['league']['league_name'] }}")
```

El paralelismo se limita con `max_active_tasks` en el `@dag`.

## Control de flujo

```python
# Sensor: espera algo FUERA del control del DAG.
# reschedule libera el worker entre sondeos en vez de ocuparlo durmiendo.
# soft_fail deja la tarea en skipped, no en failed: no responder no es un
# error del pipeline, es una condición que sabemos manejar.
@task.sensor(poke_interval=300, timeout=1800, mode="reschedule", soft_fail=True)
def wait_for_source(**context) -> PokeReturnValue:
    return PokeReturnValue(is_done=True, xcom_value=meta)

# Branch: elige el camino en tiempo de ejecución, devolviendo el task_id.
# ALL_DONE porque la tarea de arriba puede haber quedado en skipped, que es
# justamente el caso que tiene que manejar. Con ALL_SUCCESS nunca correría
# cuando más falta hace.
@task.branch(trigger_rule=TriggerRule.ALL_DONE)
def check_source(**context) -> str: ...

# Short-circuit: si devuelve False, todo lo de abajo queda en skipped y la
# corrida termina BIEN. No pasó nada porque no había nada que hacer.
@task.short_circuit
def has_new_snapshot(**context) -> bool: ...

# La tarea que junta dos ramas mutuamente excluyentes.
@task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
def validate(desde_a, desde_b): ...
```

Las dependencias se declaran implícitamente por el flujo de datos entre funciones. El `>>` explícito se usa **sólo** para las aristas de control que no llevan datos, con un comentario que lo diga.

**Diseñar la degradación:** *"si el dato es el mismo, reintentá en silencio; si el dato es distinto, hacelo visible."* Por eso los reintentos de red viven adentro del cliente y no aparecen en el grafo, pero una rama que usa datos más viejos sí es una tarea visible.

## Params

```python
params={
    "partidas_objetivo": Param(
        1500, type="integer", minimum=1,
        title="Partidas objetivo",
        description="Cuántas partidas nuevas juntar en esta corrida.",
    ),
    "modo": Param("subset", enum=["subset", "full"], title="...", description="..."),
    "forzar": Param(False, type="boolean", title="...", description="..."),
    "roster": Param(None, type=["null", "integer"], title="...", description="..."),
}
```

`title` y `description` siempre, en castellano: el formulario de disparo tiene que explicarse solo. Disparar desde la UI con "Trigger DAG w/ config" es la forma recomendada de correr los DAGs de la materia.

## Idempotencia

La misma corrida sobre la misma entrada produce la misma salida. En la práctica: la salida se nombra de forma determinista (`lol_AAAA-MM-DD.csv`), la capa cruda es append-only, y lo ya bajado no se vuelve a pedir.

## Comandos de Astro CLI

```bash
astro dev start      # levanta; UI en localhost:8080, admin/admin
astro dev stop
astro dev restart    # SÓLO si tocaste requirements.txt, packages.txt o Dockerfile
astro dev kill
astro dev ps
astro dev parse
astro dev pytest
astro dev logs -f
astro dev bash --scheduler
astro dev run dags test <dag_id> 2026-08-18 --conf '{"modo":"subset"}'
```

**Espacio en disco:** imagen base ~1,5 GB + Postgres ~0,45 GB. Con 6–8 GB libres alcanza cómodo. (Nuestro Dockerfile no instala Chromium, así que somos más livianos que `airflow-fifa`.)

## Errores frecuentes

| Síntoma | Causa |
|---|---|
| El DAG no aparece en la UI | El dag-processor escanea cada tanto. Si persiste, es error de parseo (banner rojo). **Causa más común: falta la llamada a la función al final del archivo.** |
| `ModuleNotFoundError` al importar un operador | Falta el provider en `requirements.txt` + `astro dev restart`. |
| Tareas clavadas en `queued` | El scheduler se cayó. Mirar los logs del contenedor scheduler. |
| `KeyError: 'ds'` | El DAG no tiene schedule. Sacar la fecha del DagRun. |
| `PermissionError` al escribir en `include/` | El contenedor corre como usuario `astro`. En Linux/WSL: `chmod -R 777 include/output`. |
| Todo se cuelga sin mensaje | Fijarse el espacio en disco. |

## Trampas del proyecto de referencia

`../airflow-fifa` es el modelo a imitar en estilo, pero tiene partes desactualizadas. **Copiar las convenciones, no los errores:**

1. `tests/dags/test_dag_integrity.py` está viejo y **falla**: espera una tarea `scrape_league` que fue refactorizada en `land_bronze` + `refine_silver`. `astro dev pytest` no pasa en ese proyecto tal como está.
2. El grafo ASCII y la tabla de tareas del README también quedaron viejos: no mencionan bronce/plata. El docstring del DAG es la verdad actual.
3. El docstring de `save()` dice "este corre a demanda" mientras el DAG tiene `schedule="@daily"`. El idiom `logical_date or run_after` sigue siendo correcto igual.
4. El comentario de cabecera de `airflow_settings.yaml` dice que está gitignoreado, pero el `.gitignore` explícitamente **no** lo ignora y explica por qué. Manda el `.gitignore`.
