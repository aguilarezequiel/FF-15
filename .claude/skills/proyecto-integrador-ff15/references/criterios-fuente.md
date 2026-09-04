# Los 7 criterios de una buena fuente de datos

Fuente: `Documentacion/Criterios de una buena fuente de datos/` (Clase 1, Bloque 2) y el Kit de arranque, sección 4.

**Lo que cambió para la Entrega 1:** los mismos siete criterios que se usaron en agosto para *elegir* la fuente se usan ahora para *juzgar lo que produjo el pipeline*. En agosto la calidad del dato era responsabilidad de quien publicó la fuente. Ahora es nuestra.

## Punto de partida

Dos preguntas, en este orden y no al revés:

1. **¿Qué querés investigar?** Una pregunta acotada, sobre una unidad concreta.
2. **¿Qué fuente responde esa pregunta?**

Elegir el dataset primero e inventar la pregunta después lleva a proyectos mecánicos y desmotivadores.

---

## Bloque A · Los 4 eliminatorios

*"Sin esto no hay proyecto."* Si la fuente falla uno solo, no se insiste: se busca otra o se ajusta la pregunta.

### 01 · Datos tidy

Cada fila es una observación. Cada columna es una variable.

- ✗ **Wide:** `Persona | Enero | Febrero | Marzo`. "Mes" es una variable pero está escondida como nombre de columna.
- ✓ **Long:** `Persona | Mes | Valor`. Cada fila es una observación persona-mes.

### 02 · Unidad de análisis alineada con la pregunta

La unidad que representa cada fila tiene que coincidir con la unidad sobre la que se quieren sacar conclusiones. **La granularidad se decide desde la pregunta, no desde el dataset.**

- ✓ Pregunta sobre perfiles físicos por posición → dataset con un jugador por fila.
- ✗ Pregunta sobre por qué emigran las personas → dataset del Banco Mundial con país-año por fila. La unidad país no captura decisiones individuales.

### 03 · Algo modelable

En la Unidad 3 hay que construir un modelo. Basta con que se cumpla una de las dos:

- **Supervisado:** hay una variable que se quiere predecir a partir de las otras.
- **No supervisado:** se sospecha que hay grupos naturales escondidos.

Un listado de museos con dirección no tiene qué predecir ni grupos que descubrir — en U3 el proyecto se rompe.

### 04 · Descargable de forma automatizada

En la Unidad 1 hay que construir un pipeline que baje los datos sin intervención humana. Vale:

- Archivos por URL directa (un CSV o JSON en un endpoint público).
- **APIs REST públicas**, con o sin API key, siempre que se pueda automatizar.
- Páginas scrapeables con estructura estable — aun con Cloudflare o JS pesado, usando Playwright.

**No vale:** foto de una tabla en un PDF, sitios con captcha manual, bases privadas o pagas, apuntes propios.

---

## Bloque B · Los 3 facilitadores

*"Estos te hacen la vida más fácil."* No rompen el proyecto si fallan, pero lo complican. Cada uno tiene salida de emergencia si se pone más trabajo.

### 05 · Volumen suficiente

| Filas | Veredicto |
|---|---|
| < 1.000 | Insuficiente |
| 1.000 – 10.000 | Suficiente para arrancar |
| > 10.000 | Cómodo |

**Salida:** combinar con otra fuente por una clave común, o acotar el alcance del modelo.

### 06 · Varias columnas informativas

Al menos **5 columnas útiles**, con mezcla de tipos: numéricas, categóricas, fechas.

Contraejemplo: habitantes por localidad — una única columna útil, no hay features para modelar ni dimensiones para cruzar.

**Salida:** derivar variables nuevas desde las existentes (feature engineering), o combinar con otra fuente por una clave común.

### 07 · Documentación entendible

Hay que saber qué significa cada columna, sus unidades, su origen, y qué representa un valor faltante. Un CSV con `col_1, col_2, col_3` sin diccionario hace perder más tiempo adivinando que analizando.

**Salida:** reconstruir la documentación leyendo los datos y consultando la fuente original. Cuesta tiempo, pero se puede — no descarta la fuente por sí solo.

---

## Cómo se para nuestro proyecto contra los 7

| # | Criterio | Estado | Justificación |
|---|---|---|---|
| 1 | Tidy | **Con concesión declarada** | Una fila = una partida, que es la unidad de la pregunta. Pero los 10 jugadores están aplanados en 100 columnas `t1_top_*` … `t2_sup_*` en vez de estar en formato largo. Ver abajo. |
| 2 | Unidad alineada | ✓ | La pregunta es sobre la duración de **una partida**, y una fila es exactamente una partida. |
| 3 | Algo modelable | ✓ | Supervisado: regresión sobre `game_duration_s`. No supervisado: arquetipos de composición de equipo. |
| 4 | Descargable automatizado | ✓ | API REST oficial de Riot Games, con key, orquestada en Airflow. Cero intervención humana dentro del pipeline. |
| 5 | Volumen | ✓ | Objetivo parametrizable; el prototipo previo llegó a 20.020 partidas. |
| 6 | Columnas informativas | ✓ | 137 columnas: enteras, flotantes y categóricas (nombres de campeón). |
| 7 | Documentación | ✓ | Documentación oficial del Riot Developer Portal + Data Dragon. |

### La confesión de tidy, que hay que decir en voz alta

El dataset **no es del todo tidy**, y la consigna pide explícitamente declararlo en vez de esconderlo.

La observación natural más fina es *jugador-en-partida*: hay 10 por partida. Están aplanados en columnas (`t1_top_champ_id`, `t1_top_player_elo`, …, `t2_sup_champ_mastery_pts`) en lugar de ocupar 10 filas.

**Por qué es una concesión deliberada y no un descuido:** la unidad de análisis de la pregunta es la **partida**, no el jugador — se quiere predecir cuánto dura *una partida*. En formato largo habría 10 filas por partida y el target `game_duration_s` se repetiría idéntico en las 10, lo cual es peor: rompe la correspondencia una-fila-una-observación respecto de la pregunta, y obligaría a re-agregar antes de cada modelo.

Es exactamente el mismo tipo de concesión que hace la cátedra con `player_positions` en el dataset FIFA.
