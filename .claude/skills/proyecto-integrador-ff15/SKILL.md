---
name: proyecto-integrador-ff15
description: Workflow completo del Proyecto Integrador de Ciencia de Datos (UTN FRM 2026, grupo 5K09-02) — un pipeline de Apache Airflow 3.3 sobre Astro Runtime que ingesta la Riot Games API para predecir la duración de partidas de League of Legends. Usar SIEMPRE que se trabaje en este repo: escribir o modificar DAGs, tocar include/lol/, cambiar el esquema del dataset, preparar una entrega, defender el dataset contra los 7 criterios de la cátedra, depurar una corrida de Airflow, manejar la API key de Riot, o responder "¿cómo hago X acá?". Activar también ante síntomas sin nombrar el proyecto — "el DAG no aparece en la UI", "me tira 429", "la key venció", "cuántas filas tengo", "cuál es la clave primaria", "esto es tidy?", "hay que subirlo a bronce o a plata" — y antes de cualquier decisión de diseño sobre el pipeline, porque la cátedra evalúa el POR QUÉ de cada tarea del grafo, no sólo que corra.
---

# Proyecto Integrador · Ciencia de Datos · UTN FRM 2026

## De qué se trata

**Pregunta del proyecto:** ¿Es posible predecir la duración de una partida de League of Legends a partir de las características de los jugadores, de los campeones de los equipos y las condiciones iniciales de la partida?

| | |
|---|---|
| Grupo | **5K09-02** · Comisión 5K09 |
| Fuente | **Riot Games API** (`developer.riotgames.com`) + Data Dragon CDN |
| Unidad de análisis | **Una partida clasificatoria** (cola 420) de LoL, Season 16 |
| Clave primaria | `match_id` (ej. `LA2_1617259431`) |
| Columna objetivo | `game_duration_s` — segundos, continua → **regresión** |
| Stack | Apache Airflow **3.3** sobre **Astro Runtime 3.3-4**, orquestado con Astro CLI |
| Repo | `github.com/aguilarezequiel/FF-15` |

El integrador vale el **50 % de la nota final** y son cuatro entregas encadenadas: cada una se apoya en la anterior. Lo que se construye acá en la Unidad 1 (la capa plata) es el insumo de la exploración, el modelado y la app de las Unidades 2, 3 y 4.

## Regla que manda sobre todas las demás

**No inventar nada.** Requisitos, columnas, fechas, criterios, umbrales: si no está en `Documentacion/`, en este skill, o no lo dijo el usuario explícitamente — preguntar. Un dato inventado en un proyecto que se defiende oralmente frente a un docente que pregunta a integrantes puntuales no es un atajo, es una trampa que se descubre en la defensa.

Cuando el alcance de un pedido admite dos lecturas que llevan a trabajo distinto, preguntar antes de escribir código.

## Cómo está organizado el repo

```
FF-15/
├── CLAUDE.md              · contexto permanente + reglas de trabajo
├── README.md              · el entregable escrito de cada entrega
├── Dockerfile             · FROM astrocrpublic.azurecr.io/runtime:3.3-4
├── requirements.txt       · paquetes de Python (tocar → astro dev restart)
├── packages.txt           · paquetes de sistema (apt), vacío
├── airflow_settings.yaml  · Connections/Variables locales — GITIGNOREADO, tiene la key
├── dags/lol_ingest.py     · la definición del flujo, y nada más
├── include/lol/           · toda la lógica pesada, SIN un solo import de Airflow
├── include/output/        · bronce, plata y entregables — gitignoreado
├── notebooks/             · el análisis de las Unidades 2+, una carpeta por entrega
├── docs/                  · documentación integral del proyecto (HTML fuente + PDF)
├── tests/                 · astro dev pytest
└── Documentacion/         · material de la cátedra (fuente de verdad de las consignas)
```

**Por qué `dags/` e `include/` están separados:** el `dag-processor` parsea `dags/` cada pocos segundos. Todo lo que sea lento de importar o pesado de ejecutar va en `include/` y se importa. Un `import pandas` en el tope de un archivo de `dags/` ralentiza el parseo de todo el proyecto.

**Por qué `include/lol/` no importa Airflow:** para que se pueda testear con pytest plano y reusar tal cual en las Unidades 2–4, donde no hay un DAG alrededor. La frontera es dura: si un módulo de `include/lol/` necesita un `Variable.get()`, el valor se le pasa por parámetro desde la tarea.

## Ciclo de trabajo

```bash
astro dev start          # levanta todo; UI en localhost:8080 (admin/admin)
astro dev restart        # SÓLO si tocaste requirements.txt, packages.txt o Dockerfile
astro dev parse          # chequeo rápido de errores de parseo
astro dev pytest         # tests de integridad del DAG
astro dev logs -f        # logs de los contenedores
astro dev stop           # apaga sin borrar
```

El análisis vive en un entorno aparte, para no engordar la imagen de Airflow:

```bash
python -m venv .venv
.venv\Scripts\pip install -r notebooks/requirements.txt
.venv\Scripts\jupyter lab
# volver a ejecutar el notebook entero, con las salidas guardadas:
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace notebooks/entrega-2/eda_entrega2.ipynb
```

Editar un `.py` de `dags/` o de `include/` **no** necesita restart: el dag-processor lo recoge solo en unos segundos.

Después de cualquier cambio en un DAG: disparar desde la UI con el formulario de params, y **leer los logs de la tarea**, no sólo el color del cuadradito. Un `skipped` puede ser el comportamiento correcto (un short-circuit que cortó porque no había nada que hacer) o un bug silencioso, y sólo el log lo distingue.

## Reglas duras del código

Estas no son estilo, son cosas que rompen el pipeline o la nota si se ignoran:

- **Credenciales en Connection, nunca en el `.py`.** La key de Riot vive en la Connection `riot_api`. El apunte de la cátedra lo dice literal. Y hay antecedente concreto: el prototipo previo (`../FF15`) tiene 5 keys hardcodeadas pusheadas a un repo público.
- **Por XCom viajan metadatos, no datos.** Rutas, ids, banderas, conteos. Pasar filas por XCom satura la base de metadatos de Airflow. Los datos van a disco.
- **Nunca `ds`.** Sólo existe si el DAG tiene `schedule`. Usar siempre:
  ```python
  dag_run = context["dag_run"]
  momento = dag_run.logical_date or dag_run.run_after
  ds = momento.date().isoformat()
  ```
- **`import pandas` va adentro de la tarea**, no en el tope del módulo del DAG.
- **`logging` con `%s` diferido**, nunca `print()` ni f-strings en la llamada al log: `log.info("%s filas", n)`.
- **Bronce es append-only.** Una partida ya bajada no se vuelve a pedir jamás. La plata se reconstruye sobre **todo** el bronce acumulado, no sólo sobre lo que bajó la corrida actual: así el dataset crece corrida a corrida y un bug de parseo se arregla sin volver a la fuente.
- **Rutas absolutas del contenedor** (`Path("/usr/local/airflow/include/output")`), nunca relativas: Airflow fija su propio CWD.
- Cada tarea lleva **docstring que explica el porqué de la decisión de diseño**, no lo que hace el código. Se renderizan en la UI y son la chuleta de la defensa oral.

## Las capas (modelo medallón)

| Capa | Qué es | Dónde |
|---|---|---|
| **Bronce** | La respuesta de la API tal como llegó, sin interpretar. gzip, particionado en carpetas. | `include/output/bronze/` |
| **Plata** | Filas tipadas, una por partida, deduplicadas y validadas. **Es el entregable de la Entrega 1.** | `include/output/lol_AAAA-MM-DD.csv` |
| **Oro** | Features derivadas, agregados. **No se construye acá** — es de las Unidades 3 y 4. | — |

La consigna pregunta literalmente *"¿dónde guardás el dato crudo? El dataset que entregás es la capa plata; la pregunta es si además tenés el bronce."* Por eso el bronce guarda **todas** las respuestas crudas — partidas, entradas de liga, maestrías y Data Dragon — no sólo las partidas. Con eso, la plata se reconstruye 100 % offline.

## Antes de cada entrega

Correr este checklist. Los primeros seis son numéricos y se miden solos; los demás se preguntan en la defensa.

```python
df["match_id"].is_unique                        # True — el criterio más importante
len(df)                                         # > 1.000
df.shape                                        # ≥ 5 columnas útiles
df.dtypes.value_counts()                        # numéricas + categóricas + fechas
df.isna().mean().sort_values(ascending=False)   # saber cuáles y por qué
df.columns[df.isna().all()]                     # vacío
```

Y tener listas las respuestas a: qué es una fila, cuál es la columna objetivo, por qué hay nulos donde hay, qué pasa si lo corrés de nuevo, dónde está el bronce, y **dónde el dataset se aparta de tidy y por qué**. Esa última la cátedra la pide explícitamente y premia que se declare en vez de esconderse.

Detalle logístico que cuesta caro olvidar: se llega con el entorno **ya levantado** y con una **corrida en verde ya hecha**. Arrancar Airflow o correr el pipeline en vivo se come la mitad de los 20 minutos.

## Referencias

Leerlas cuando la tarea lo pida — no hace falta cargarlas todas de entrada.

| Archivo | Cuándo leerlo |
|---|---|
| `references/entregas.md` | Al preparar una entrega. Texto **verbatim** de la consigna de la Entrega 1, fechas de las cuatro entregas, cómo se aprueba. |
| `references/criterios-fuente.md` | Al defender el dataset o al discutir si algo cumple. Los 7 criterios verbatim. |
| `references/airflow-catedra.md` | Antes de escribir o tocar un DAG. Imports de Airflow 3, argumentos del `@dag`, mapeo dinámico, sensores, branching, errores frecuentes. |
| `references/riot-api.md` | Al tocar `include/lol/riot.py`, `seeds.py` o `ddragon.py`. Endpoints, routing, rate limits, rotación de keys y las trampas conocidas. |
| `references/dataset-schema.md` | Al tocar `schema.py` o `transform.py`, o al explicar una columna. Las 137 columnas y cómo se deriva cada una. |
| `references/eda-hipotesis.md` | Al escribir análisis, hipótesis o gráficos. El semáforo con sus cortes, las seis casillas, las tres plantillas, los tres movimientos, el chequeo de fuga y el estilo de la cátedra. |

## Mantener esto vivo

Cuando cambie algo del proyecto — una columna, una tarea, una decisión de diseño, una fecha — actualizar **en el mismo movimiento** los tres lugares donde vive el conocimiento del proyecto:

| Dónde | Qué se actualiza |
|---|---|
| **`docs/documentacion-proyecto.html`** | El documento integral que lee todo el grupo. Es el más importante. Después: `python docs/generar_pdf.py`. |
| `CLAUDE.md` | El contexto y las reglas de trabajo. |
| Esta skill y sus `references/` | El conocimiento reusable. |

La regla del documento integral es que es **incremental, no acumulativo**: se agrega lo nuevo y se **borra lo que dejó de ser cierto**. Borrar pesa tanto como agregar — un documento que sólo crece termina afirmando cosas contradictorias, y como está escrito con seguridad, se le cree.

Un cambio suele tocar varias partes a la vez: una columna nueva aparece en la parte IV (el módulo), en la V (el esquema) y probablemente en la VII (la defensa). Buscar todas las menciones antes de dar el cambio por hecho, y actualizar el bloque «Estado a la fecha de esta versión» del principio.

Y verificar los números: cantidad de columnas, líneas por archivo, partidas en bronce, filas del CSV, mediciones de rendimiento. No arrastrar un número viejo — medirlo de nuevo.

Una documentación que describe un proyecto que ya no existe es peor que no tenerla: da respuestas con confianza y están mal.
