# FF-15 · Proyecto Integrador de Ciencia de Datos

**UTN FRM · Ingeniería en Sistemas de Información · 2° cuatrimestre 2026 · Comisión 5K09 · Grupo 5K09-02**

> **Pregunta del proyecto:** ¿Es posible predecir la duración de una partida de League of Legends a partir de las características de los jugadores, de los campeones de los equipos y las condiciones iniciales de la partida?

| | |
|---|---|
| Fuente | Riot Games API (`developer.riotgames.com`) + Data Dragon CDN |
| Unidad de análisis | Una partida clasificatoria (cola 420), Season 16 |
| Clave primaria | `match_id` |
| Columna objetivo | `game_duration_s` — segundos. Hasta la E3, regresión; desde las correcciones de la E3, el modelo final predice **la banda de 3 minutos** en la que termina → clasificación |
| Datasets | `lol_AAAA-MM-DD.csv` — condiciones iniciales, 137 columnas · `lol_minN_AAAA-MM-DD.csv` — estado de la partida al minuto N (timeline de match-v5), 35 columnas. Se unen por `match_id` |
| Stack | Apache Airflow 3.3 · Astro Runtime 3.3-4 · Astro CLI · Docker |
| Entrega 1 | miércoles 9/9, franja 14:55 – 15:15 — **presentada** |
| Entrega 2 | miércoles 23/9, la clase completa · 20 min con el docente, en privado — **presentada** |
| Entrega 3 | miércoles 28/10 · 25 min con el docente, en privado — **presentada** · modelo final: `Ridge(alpha=100)` con las 137 columnas + el estado al **minuto 10** (decisión del grupo, 27/10). Es el que usa la app de la Entrega 4 |
| Correcciones de la E3 | pedidas por el docente; hechas el 9/11 en `notebooks/entrega-4/correcciones_entrega3.ipynb`. **El modelo final pasa a ser una regresión logística sin pesos** (`C=1`) que predice la banda de 3 min y da una probabilidad por banda (decisión del grupo). Es el que usaría la app de la E4, que no se empezó |

---

## Cómo trabajar en este repo

### 1. Preguntar antes de tocar

**Antes de agregar o modificar cualquier cosa del proyecto, preguntar.** Vale para columnas del dataset, tareas del DAG, dependencias, parámetros, umbrales, estructura de carpetas y textos del README.

Cuando el alcance de un pedido admite dos lecturas que llevan a trabajo distinto, no elegir una y seguir: preguntar cuál.

### 2. No inventar

Requisitos, columnas, fechas, criterios de evaluación, umbrales, nombres de endpoints. Si no está en `Documentacion/`, en la skill del proyecto, o no lo dijo el usuario explícitamente — **preguntar, no asumir**.

Esto no es formalismo: el proyecto se defiende oralmente, con preguntas dirigidas a integrantes puntuales. Un dato inventado se descubre en la defensa y la nota es individual.

### 3. Mantener la documentación viva

Después de todo cambio aceptado, evaluar en el mismo movimiento si quedó desactualizado o incompleto:

- **`docs/documentacion-proyecto.html`** → el documento integral que lee todo el grupo. **Es el más importante de los tres.** Ver la regla detallada abajo.
- **este `CLAUDE.md`** → actualizarlo;
- **la skill `.claude/skills/proyecto-integrador-ff15/`** → corregir la referencia que corresponda, o ampliarla si el cambio introdujo conocimiento nuevo que valga la pena conservar.

Si el cambio no afecta a ninguno de los tres, decirlo explícitamente en vez de saltearlo en silencio. Una documentación que describe un proyecto que ya no existe da respuestas con confianza y están mal.

### 4. La documentación integral es incremental, no acumulativa

`docs/documentacion-proyecto.html` es la memoria completa del proyecto: qué hace, por qué está hecho así, cómo se ejecuta y cómo se defiende. El grupo lo lee para entender todo el proyecto, y de ahí salen las respuestas de la defensa oral.

**Ante cada avance relevante — una tarea nueva, una columna que se agrega o se quita, una decisión de diseño que cambia, un bug corregido, un número que se vuelve a medir — hay que actualizarlo en el mismo movimiento:**

- **Agregar** lo nuevo, en la parte que corresponda.
- **Borrar** lo que dejó de ser cierto. Esto es tan importante como agregar: un documento que sólo crece termina afirmando cosas contradictorias, y como está escrito con seguridad, se le cree.
- **Reflejar el cambio en todas las partes afectadas.** Una columna nueva toca la parte IV (el módulo), la parte V (el esquema) y probablemente la VII (la defensa). Buscar todas las menciones antes de dar el cambio por hecho.
- **Actualizar el bloque «Estado a la fecha de esta versión»** del principio, que es lo primero que lee alguien que vuelve al documento.

Después de editar el HTML, regenerar el PDF:

```bash
python docs/generar_pdf.py
```

**Verificar antes de dar por cerrado un cambio:** los números que aparecen en el documento (cantidad de columnas, líneas por archivo, partidas en bronce, filas del CSV, mediciones de rendimiento) tienen que coincidir con la realidad del repo. No arrastrar un número viejo: medirlo de nuevo.

---

## Reglas técnicas que no se negocian

Están explicadas con su porqué en `.claude/skills/proyecto-integrador-ff15/SKILL.md` y en `references/airflow-catedra.md`. El resumen:

- **Credenciales en la Connection `riot_api`, jamás en el `.py`.** Ni en un default, ni en un comentario, ni "temporalmente".
- `airflow_settings.yaml` está gitignoreado porque contiene la key. Se versiona `airflow_settings.example.yaml`.
- **Por XCom viajan rutas y metadatos, no datos.** Los datos van a disco.
- **Nunca `ds`**: `dag_run.logical_date or dag_run.run_after`.
- `import pandas` va **dentro** de la tarea, no en el tope del módulo del DAG.
- `logging` con `%s` diferido. Nunca `print()`.
- `include/lol/` no importa Airflow. Ni una línea.
- **Bronce es append-only**: lo ya bajado no se vuelve a pedir.
- **El timeline va entero al bronce**; el corte en el minuto se hace en la plata (`minuto_corte`). Cambiar de minuto no pide nada a Riot.
- **El dataset al minuto N es aparte.** Nada del timeline entra en las 137 columnas de condiciones iniciales: cambia la pregunta, y mezclarlo la escondería.
- Rutas absolutas del contenedor (`/usr/local/airflow/...`), nunca relativas.
- Cada tarea con docstring que explica **por qué** está donde está. Se renderiza en la UI y es la chuleta de la defensa.

## Estructura

```
dags/lol_ingest.py    · el flujo, y nada más
include/lol/          · toda la lógica pesada, testeable sin Airflow
include/output/       · bronce, plata y entregables (gitignoreado)
notebooks/            · el análisis de las Unidades 2+, una carpeta por entrega
tests/                · astro dev pytest
docs/                 · la documentación integral del proyecto (HTML + PDF)
Documentacion/        · material de la cátedra — fuente de verdad de las consignas
.claude/skills/       · la skill del proyecto, versionada para todo el grupo
```

El notebook de análisis corre en un **venv aparte** (`notebooks/requirements.txt`),
no en la imagen de Astro: son dos entornos con dos propósitos. Detalles en
`notebooks/README.md`.

## Comandos

```bash
astro dev start      # UI en localhost:8081 (admin/admin)
astro dev restart    # sólo si tocaste requirements.txt, packages.txt o Dockerfile
astro dev parse      # chequeo de parseo
astro dev pytest     # tests de integridad
astro dev logs -f
```

Para completar los timelines de un bronce que ya existe sin agrandarlo: disparar `lol_ingest` con
`buscar_partidas_nuevas=false`. Después, leer el chequeo de eventos de
`include/output/reports/calidad_minutoN.md` antes de modelar con esos datos. El CSV del minuto se
copia a `notebooks/entrega-3/datos/` y se versiona, como el CSV congelado de la E2.

El venv del análisis necesita **Python 3.12 o más nuevo** (`numpy==2.5.2` no se instala con 3.11); con el lanzador de Windows: `py -3.14 -m venv .venv`.

```bash
python -m venv .venv                                    # el entorno del análisis
.venv\Scripts\pip install -r notebooks/requirements.txt
.venv\Scripts\jupyter lab
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace notebooks/entrega-2/eda_entrega2.ipynb
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace notebooks/entrega-3/modelado_entrega3.ipynb
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 notebooks/entrega-4/correcciones_entrega3.ipynb
python docs/generar_pdf.py guion-defensa-entrega3.html   # el guion de la defensa de la E3
```

## Antes de cada entrega

```python
df["match_id"].is_unique                        # True
len(df)                                         # > 1.000
df.shape
df.dtypes.value_counts()
df.isna().mean().sort_values(ascending=False)
df.columns[df.isna().all()]                     # vacío
```

Y tener listas las respuestas a: qué es una fila, cuál es la columna objetivo, por qué hay nulos donde hay, qué pasa si se corre de nuevo, dónde está el bronce, y dónde el dataset se aparta de tidy.

### Y para la Entrega 2, además

El notebook tiene que estar **ejecutado, con las salidas guardadas y sin una sola celda en error**. Se verifica corriéndolo entero, no abriéndolo:

```bash
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace notebooks/entrega-2/eda_entrega2.ipynb
```

Los siete números que la consigna mide sola: `df.shape`, `df.dtypes.value_counts()`, `df.isna().mean()`, `df.columns[df.nunique() <= 1]`, duplicados de la clave, distribución del objetivo y `skew()` ordenado.

Y lo que no mide ningún script: cuál es la variable objetivo y cómo está distribuida, por qué hay nulos donde hay, **qué hipótesis salió mal y qué se hizo con eso**, qué columna se descartó por fuga y en qué momento se completa en la realidad, y qué quedó inconcluso.

El método —el semáforo con sus cortes, las seis casillas de una ficha, las tres plantillas, los tres movimientos con tope de dos, el chequeo de fuga— está en `.claude/skills/proyecto-integrador-ff15/references/eda-hipotesis.md`. **Los cortes no se inventan ni se ajustan**: son los de la cátedra.

## Contexto útil

- `../airflow-fifa` — proyecto de la cátedra. Se imita el estilo, **no** sus partes desactualizadas (tests rotos, README viejo); están listadas en `references/airflow-catedra.md`.
- `../FF15` — prototipo previo del grupo, funcional pero sin Airflow. Sirve como referencia de la lógica de extracción. **Tiene API keys hardcodeadas y pusheadas a un repo público**: no copiar ese patrón, y no reutilizar esas keys.

### Y para la Entrega 3

El notebook `notebooks/entrega-3/modelado_entrega3.ipynb` se verifica corriéndolo entero (comando de arriba): sin celdas en error, con las salidas guardadas y `SEMILLA = 42`. Lee el CSV de condiciones iniciales con el patrón `lol_2*.csv` (en `entrega-3/datos/` también hay `lol_min*`); en Colab, los cuatro CSV van en `datos/`.

Lo que no se toca sin preguntar: la partición del test (20 %, estratificada por grupo de elo, separada una vez), la regla de la cátedra para elegir (el complejo gana sólo por más que el desvío), y las columnas del minuto que quedaron fuera (placas, wards y primera sangre: ver V.8 y IX.6 del documento integral). El detalle completo está en la Parte IX; el reparto de la defensa, en `docs/guion-defensa-entrega3.pdf`.

### Y para las correcciones de la Entrega 3

`notebooks/entrega-4/correcciones_entrega3.ipynb` usa las mismas clases, la misma partición y los mismos pedazos de la E3, con la banda de 3 minutos como objetivo. No copia CSV: lee `entrega-2/datos/` y `entrega-3/datos/`. Se ejecuta en unos veinte segundos. Al cerrar el kernel en Windows puede aparecer un `KeyError` de `joblib_memmapping_folder`: es la limpieza de joblib, no una celda en error.

Decisiones del grupo que no se reabren sin preguntar: el problema es de **clasificación** (la banda de 3 min en la que termina la partida); 12 bandas, de 3 min entre 15 y 45 más `<15` y `45+`; el modelo final es la **regresión logística sin pesos, `C=1`** (la más simple y la que da probabilidades por banda; `balanced` se probó y se descartó); decide el F1 macro, con accuracy, ±1 banda, error en minutos y matriz de confusión al lado; al jugador se le muestra la probabilidad de su ventana de 3 bandas. El MSE y el R² sólo se explican, sobre la regresión de la E3. El notebook es corto a propósito: hay poco tiempo para mostrarlo. Detalle en la Parte X del documento integral.
