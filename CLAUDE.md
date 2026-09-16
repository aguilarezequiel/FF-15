# FF-15 · Proyecto Integrador de Ciencia de Datos

**UTN FRM · Ingeniería en Sistemas de Información · 2° cuatrimestre 2026 · Comisión 5K09 · Grupo 5K09-02**

> **Pregunta del proyecto:** ¿Es posible predecir la duración de una partida de League of Legends a partir de las características de los jugadores, de los campeones de los equipos y las condiciones iniciales de la partida?

| | |
|---|---|
| Fuente | Riot Games API (`developer.riotgames.com`) + Data Dragon CDN |
| Unidad de análisis | Una partida clasificatoria (cola 420), Season 16 |
| Clave primaria | `match_id` |
| Columna objetivo | `game_duration_s` — segundos, continua → regresión |
| Stack | Apache Airflow 3.3 · Astro Runtime 3.3-4 · Astro CLI · Docker |
| Entrega 1 | miércoles 9/9, franja 14:55 – 15:15 — **presentada** |
| Entrega 2 | miércoles 23/9, la clase completa · 20 min con el docente, en privado |

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

```bash
python -m venv .venv                                    # el entorno del análisis
.venv\Scripts\pip install -r notebooks/requirements.txt
.venv\Scripts\jupyter lab
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace notebooks/entrega-2/eda_entrega2.ipynb
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
