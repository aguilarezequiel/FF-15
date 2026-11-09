# Entregas del Integrador

Fuente: `Documentacion/Kit de arranque - Proyecto Integrador 2026.pdf` y la página del campus guardada en `Documentacion/Consignas de Entrega 1/`.

## Contenido

- [Calendario](#calendario)
- [Cómo funciona la evaluación](#cómo-funciona-la-evaluación)
- [Instrucciones para la Entrega 1 (verbatim)](#instrucciones-para-la-entrega-1-verbatim)
- [Instrucciones para la Entrega 2 (verbatim)](#instrucciones-para-la-entrega-2-verbatim)
- [La Entrega 3 (resumen de la consigna)](#la-entrega-3-resumen-de-la-consigna)
- [Errores de años anteriores](#errores-de-años-anteriores)

---

## Calendario

| Entrega | Fecha | Qué se presenta |
|---|---|---|
| Definición | 12/08 | Grupo, pregunta y fuente de datos |
| **1 · Ingeniería de datos** | **miércoles 9/9** | Pipeline automatizado que produce tu dataset |
| **2 · Análisis exploratorio** | **miércoles 23/9** | Exploración, hipótesis y hallazgos |
| **3 · Modelado** | **miércoles 28/10** | Objetivo predictivo, modelos comparados y métricas |
| 4 · Visualización e integración | 04/11 | Visualizaciones y aplicación funcionando |
| Exposición final | 18/11 | Proyecto completo y demo en vivo |
| Recuperación | 25/11 | Para los grupos que la necesiten |

> **Discrepancia de fechas, a favor del campus.** El PDF del Kit de arranque dice que la Entrega 1 es el **02/09** y que la Entrega 2 es el **16/09**. Las consignas del campus, más recientes, dicen **miércoles 9 de septiembre** y **miércoles 23 de septiembre**. Valen las del campus.

**La Entrega 2 ocupa la clase completa**, no una franja asignada: cada grupo pasa 20 minutos con el docente, en privado, sin audiencia de otros grupos.

**Franja del grupo 5K09-02: miércoles 9 de septiembre, 14:55 – 15:15.** Llegar cinco minutos antes con el entorno ya levantado. La franja empieza y termina a la hora que dice, y lo que no se llega a mostrar no se recupera.

El integrador vale el **50 % de la nota final**. Se aprueba con el 60 %. Hay una instancia de recuperación al final del cursado.

## Cómo funciona la evaluación

Cada grupo se reúne **en privado** con el docente, 20 minutos, sin audiencia de otros grupos. La **evaluación es individual**: las preguntas van dirigidas a integrantes puntuales, y la pregunta sobre el scraping puede caerle a quien escribió la transformación. Repartirse el trabajo está bien; desentenderse de la parte del otro, no.

Los TPs prácticos (sobre el dataset FIFA que provee la cátedra) son el entrenamiento: cada TP enseña la técnica con un caso controlado y la entrega del integrador siguiente pide aplicarla al dataset propio, que es más sucio y más ambiguo. Conviene hacer el TP antes de encarar la entrega correspondiente.

---

## Instrucciones para la Entrega 1 (verbatim)

> Esta entrega tiene una sola pregunta de fondo: **¿tenés un pipeline que produce tu dataset sin que nadie lo toque a mano?** Todo lo demás son formas de responderla.
>
> ### Qué tenés que traer
>
> Llegá con esto **ya funcionando**. Los 20 minutos son para mostrar y explicar, no para instalar ni para esperar que termine una descarga.
>
> | Qué | Detalle |
> |---|---|
> | **El entorno levantado** | Airflow corriendo en la notebook de alguien del grupo, con la interfaz abierta en el navegador. Prendelo antes de entrar. |
> | **Una corrida en verde** | Una ejecución completa y exitosa, ya hecha, visible en el historial. No la corras en el momento: si tu pipeline tarda cinco minutos, son cinco minutos de los veinte. |
> | **El CSV producido** | El archivo que generó esa corrida, abierto o listo para abrir. |
> | **El chequeo de calidad** | Los siete criterios verificados sobre tu salida, con los números a mano (ver más abajo). |
>
> ### Cómo se organizan los 20 minutos
>
> | Min. | Momento | Qué pasa |
> |---|---|---|
> | **0–2** | **De qué se trata** | La pregunta del proyecto en una frase, la fuente, y qué es una fila de tu dataset. Tres oraciones, sin filminas. |
> | **2–7** | **La corrida** | Mostrás la ejecución en verde en la interfaz y recorrés el grafo explicando qué hace cada tarea y por qué está donde está. |
> | **7–12** | **El dataset** | Abrís el CSV y lo defendés contra los siete criterios: cuántas filas, cuál es la clave, dónde hay nulos, cuál es la columna objetivo. |
> | **12–18** | **Preguntas dirigidas** | El docente pregunta, a **integrantes puntuales**, sobre cualquier parte de lo anterior. |
> | **18–20** | **Devolución** | Qué está bien, qué hay que corregir antes de la Entrega 2. |
>
> **La evaluación es individual.** Repartirse el trabajo está bien; desentenderse de la parte del otro, no. La pregunta sobre el scraping puede caerle a quien escribió la transformación. Con grupos de cuatro a siete personas esto pesa: no alcanza con que uno solo sepa todo.
>
> ### Qué es un buen dataset de salida
>
> Los siete criterios que usaste en la primera clase para elegir una fuente son los mismos que ahora usamos para **juzgar lo que produjo tu pipeline**. Cambió una sola cosa, y no es menor: en agosto la calidad del dato era responsabilidad de quien publicó la fuente. Ahora es tuya.
>
> #### Lo que se verifica con un número
>
> Estos los podés medir vos mismo antes de venir. Si tu CSV está cargado en un DataFrame llamado `df`:
>
> | Criterio | Qué tiene que dar | Cómo lo verificás |
> |---|---|---|
> | **Clave sin duplicados** | `True` | `df["tu_clave"].is_unique` |
> | **Volumen suficiente** | más de 1.000 filas | `len(df)` |
> | **Ancho suficiente** | 5 o más columnas útiles | `df.shape` |
> | **Mezcla de tipos** | numéricas, categóricas y fechas | `df.dtypes.value_counts()` |
> | **Nulos conocidos** | saber cuáles y por qué | `df.isna().mean().sort_values(ascending=False)` |
> | **Sin columnas vacías** | ninguna al 100 % de nulos | `df.columns[df.isna().all()]` |
>
> **La clave primaria es el criterio más importante**, y el que más se subestima. Es el test operativo de la unidad de análisis: si la clave repite, o la unidad está mal definida o el pipeline está duplicando filas. No existe un dataset con la clave limpia y la unidad equivocada.
>
> #### Lo que hay que saber explicar
>
> Esto no lo mide ningún script: se pregunta.
>
> - **«Una fila es un ___».** Completá la frase en una oración, y que coincida con la pregunta del proyecto. Si tu pregunta es sobre pacientes y una fila es una consulta médica, hay un problema.
> - **Cuál es la columna objetivo**, o qué estructura latente esperás encontrar. Señalá una columna concreta del CSV, no una idea.
> - **Por qué hay nulos donde hay nulos.** No pedimos cero nulos: eso no existe en datos reales. Pedimos que sepas cuáles tenés y qué significan.
> - **Qué pasa si lo corrés de nuevo.** ¿Sale el mismo archivo? Si no, ¿por qué?
> - **Dónde guardás el dato crudo.** ¿Queda en algún lado la respuesta de la API, el HTML o el archivo original, tal como llegó? Si mañana descubrís que venías interpretando mal una columna, ¿podés arreglarlo sin volver a la fuente? El dataset que entregás es la **capa plata**; la pregunta es si además tenés el **bronce**.
>
> ### Sobre «tidy», y una confesión
>
> Tidy significa: **cada fila una observación, cada columna una variable**. Suena simple hasta que lo aplicás a datos reales.
>
> **El dataset canónico de la cátedra no cumple del todo esa regla.** La columna `player_positions` guarda más de un valor en la misma celda —«CM, CDM»— en el 65 % de las filas, y `player_traits` en el 24 %.
>
> No es un descuido: es una **concesión deliberada**. Separarlo en columnas o en filas complicaría todo lo demás, y por eso el dataset trae además `best_position`, que sí tiene un solo valor y es la que se usa como objetivo en la Unidad 3.
>
> Si tu dataset tiene una concesión parecida, no la escondas: **explicala**. Un grupo que sabe dónde su dataset se aparta del ideal y por qué está mejor parado que uno que repite la definición de memoria.
>
> ### Cómo se aprueba
>
> El piso es el mismo para todos, más allá de si tu fuente es una API, un CSV que se descarga o una página que hay que scrapear:
>
> - Hay una **corrida completa en verde**, hecha por ustedes, visible en la interfaz.
> - El grupo sabe explicar **qué hace cada tarea** del pipeline y por qué está ahí.
> - El pipeline produce un **CSV que cumple los criterios medibles**.
> - El grupo sabe **defender las decisiones** de la lista de arriba.
> - **Las respuestas no vienen de una sola persona.**
>
> ### No hacer esto
>
> - **Llegar sin el entorno levantado.** Arrancar Airflow delante nuestro se lleva la mitad del tiempo, y es tiempo que no recuperás.
> - **Correr el pipeline en vivo.** Traé la corrida hecha. Si querés mostrar una ejecución en el momento, que sea sobre una muestra chica y además de la que ya está.
> - **Que hable uno solo.** Es el error más caro, porque las preguntas van dirigidas y la nota es individual.
>
> Si algo de tu pipeline no llegó a funcionar, **vení igual y decilo**. Un grupo que muestra un pipeline a medias y entiende dónde está trabado se lleva una devolución útil. Uno que no se presenta, no.

---

## Instrucciones para la Entrega 2 (verbatim)

> Entrega 2 · Análisis exploratorio. **Miércoles 23 de septiembre**, la clase completa. Cada grupo pasa 20 minutos con el docente, en privado. No hay audiencia de otros grupos.
>
> En la Entrega 1 la pregunta era si tenías un pipeline que produce tu dataset sin que nadie lo toque a mano. Ahora que el dataset existe, la pregunta es otra: **¿sabés qué tiene adentro, y podés defender con un número cada decisión que tomaste sobre él?**
>
> Es la entrega que decide con qué llegás a modelar. Todo lo que salga de acá — qué columnas entran, cuál es el objetivo, qué hay que transformar — es la materia prima de la Entrega 3.
>
> ### Qué tenés que traer
>
> Llegá con esto ya hecho. Los 20 minutos son para mostrar y explicar, no para correr celdas ni para esperar que termine un gráfico.
>
> | Qué | Detalle |
> |---|---|
> | **El notebook ejecutado** | De arriba a abajo, sin errores y con las salidas guardadas. Abierto antes de entrar. Si hay que correrlo delante nuestro, son minutos que no recuperás. |
> | **El perfil del dataset** | Filas, columnas, tipos, nulos, constantes, duplicados y la distribución de la variable objetivo. Los números a mano. |
> | **Cuatro fichas de hipótesis** | Con los seis campos, el número, la zona del semáforo y el gráfico. |
> | **La tabla de columnas candidatas** | Qué columnas le vas a dar al modelo, cuáles descartás y por qué. |
> | **Lo que te marcamos en la Entrega 1** | Resuelto, o con una explicación de por qué no se pudo. |
>
> ### Cómo se organizan los 20 minutos
>
> | Min. | Momento | Qué pasa |
> |---|---|---|
> | **0–2** | **Qué cambió** | Qué se corrigió del pipeline desde la Entrega 1, y si cambió algo de la pregunta del proyecto. Dos oraciones. |
> | **2–7** | **El perfil** | Recorrés el dataset: cuántas filas, cuál es la clave, dónde hay nulos y por qué, cuál es la columna objetivo y cómo está distribuida. |
> | **7–13** | **Dos hipótesis** | El docente elige **dos de tus cuatro fichas** y las recorrés enteras, desde la afirmación hasta la decisión. |
> | **13–18** | **Preguntas dirigidas** | El docente pregunta, a integrantes puntuales, sobre cualquier parte de lo anterior. |
> | **18–20** | **Devolución** | Qué está bien, qué hay que corregir antes de la Entrega 3. |
>
> La evaluación es individual. **La pregunta sobre una hipótesis puede caerle a quien hizo la limpieza.**
>
> ### Lo que se verifica con un número
>
> | Qué | Cómo lo verificás | Qué tenés que saber decir |
> |---|---|---|
> | Tamaño | `df.shape` | Cuántas filas y columnas, y qué es una fila. |
> | Tipos | `df.dtypes.value_counts()` | Si alguna numérica quedó como texto, y por qué. |
> | Nulos por columna | `df.isna().mean().sort_values(ascending=False)` | De dónde salen los faltantes de las tres columnas peores. |
> | Columnas sin información | `df.columns[df.nunique() <= 1]` | Cuáles son constantes y si se van. |
> | Duplicados de la clave | `df["tu_clave"].duplicated().sum()` | Que dé cero, o por qué no da cero. |
> | Distribución del objetivo | `df["objetivo"].value_counts(normalize=True)` | Si hay una clase que se come todo. |
> | Asimetría de las numéricas | `df.select_dtypes("number").skew().sort_values()` | Cuáles tienen cola larga y habría que transformar. |
>
> **La distribución del objetivo es el número más importante de esta entrega**, y el que más se pasa por alto. Si el 92 % de tus filas son de una sola clase, el modelo de la Unidad 3 arranca con un problema que conviene ver ahora y no en octubre.
>
> ### Las cuatro hipótesis
>
> Las mismas seis casillas del TP2, sobre tu dataset. Cuatro fichas, con estas condiciones:
>
> - Al menos **una de cada pregunta**: una que responda algo sobre tu dominio y una que decida sobre una columna del modelo.
> - Al menos **una refutada o inconclusa**. Cuatro hipótesis confirmadas suele querer decir que se eligieron cosas que ya se sabían.
> - Cada resultado con su **número y su zona**, no sólo con un gráfico.
> - Los movimientos justificados por lo que se ve en el gráfico, y **ninguna hipótesis con más de dos**.
>
> ### La tabla de columnas candidatas
>
> Es el entregable que se lleva la Entrega 3. Una fila por columna que estés pensando darle al modelo:
>
> | Columna | Qué mide | Zona | Decisión | ¿Existiría al predecir? |
> |---|---|---|---|---|
> | ejemplo_a | Antigüedad del cliente en meses | verde | Entra | Sí |
> | ejemplo_b | Motivo de la baja | verde | Sale | No — se completa después del hecho |
> | ejemplo_c | Monto facturado | amarillo | Entra en escala logarítmica | Sí |
>
> La última columna es el **chequeo de fuga**, y es la que más caro se paga si falta. Si la respuesta ya está adentro, no es una feature: es la respuesta escrita de otra forma, y el modelo va a dar buenísimo por el peor de los motivos.
>
> ### Lo que hay que saber explicar
>
> - Cuál es la variable objetivo y cómo está distribuida. **Señalá una columna concreta, no una idea.**
> - Por qué hay nulos donde hay nulos. Distinguí los **faltantes de verdad** de los **nulos estructurales**, que son los que tienen que estar vacíos.
> - Qué hipótesis te salió mal, y qué hiciste con eso.
> - Qué columna descartaste por fuga, y en qué momento se completa en la realidad.
> - Qué quedó inconcluso y qué haría falta para resolverlo.
>
> ### Cómo se aprueba
>
> - El notebook corre entero y las salidas están guardadas.
> - El grupo puede describir su dataset **con números, no con adjetivos**.
> - Las cuatro fichas están completas y **cada una termina en una decisión**.
> - La tabla de columnas candidatas existe y **cada fila pasó el chequeo de fuga**.
> - Las respuestas no vienen de una sola persona.
>
> ### Tres formas de perder los 20 minutos
>
> - **El EDA de checklist.** Veinte gráficos, ninguna conclusión. Un histograma por columna no es un análisis exploratorio: es un catálogo. Lo que se corrige es qué decidiste, no cuántas celdas corriste.
> - **Contestar con el gráfico.** «Se ve que hay diferencia» no es un resultado. Un gráfico no se compara contra nada; el número sí, y por eso es el que decide.
> - **Que hable uno solo.** Es el error más caro, porque las preguntas van dirigidas y la nota es individual.
>
> Si algo no te dio, vení igual y decilo.

> **El método completo** —semáforo, plantillas, movimientos, estilo— está en [`eda-hipotesis.md`](eda-hipotesis.md).

---

## La Entrega 3 (resumen de la consigna)

Fuente: `Documentacion/Consignas de Entrega 3/` (página del campus, modificada el 14/10/2026). El Kit decía 14/10; vale el campus: **miércoles 28 de octubre, la clase completa, 25 minutos por grupo** con el docente, en privado.

La pregunta: *«¿tenés un modelo que dice algo que los datos solos no decían, y podés explicar por qué es ese y no otro?»*. **El modelo que se elige acá es el que usa la aplicación de la Entrega 4.**

Con objetivo (nuestro caso), antes del primer modelo: la métrica declarada, el piso (`DummyRegressor`) con la misma validación, pedazos que imitan el uso (al azar si las filas son independientes; `GroupKFold` si se repiten por entidad; `TimeSeriesSplit` si hay tiempo), y todo adentro de un pipeline. La comparación: el simple primero (lineal), al menos dos familias más con media y desvío —**si el complejo no le gana al simple por más que el desvío, se queda el simple**—, el ajuste del elegido con la tabla completa, y las columnas que se probaron y no sirvieron. El final: medido **una vez** en el test, dónde se equivoca (real contra predicho y por tramo del objetivo) y en qué se apoya (coeficientes o permutación), con el chequeo de fuga de la columna que más pesa.

| Min. | Momento |
|---|---|
| 0–2 | Qué cambió (dos oraciones) |
| 2–7 | El planteo |
| 7–16 | El resultado |
| 16–22 | Preguntas dirigidas |
| 22–25 | Devolución |

Se aprueba si: el notebook corre entero con semilla y salidas; todo está en un pipeline; métrica declarada, piso medido, ≥ 3 modelos por validación cruzada con media y desvío, el elegido ajustado, el test mirado una vez y el final leído; el grupo dice qué probó y no anduvo; las respuestas no vienen de una sola persona. Tres formas de perder los 25 minutos: el número que da demasiado bien, el zoológico, que hable uno solo.

Cómo lo resolvimos: Parte IX de `docs/documentacion-proyecto.html` y `docs/guion-defensa-entrega3.pdf`.

### Las correcciones de la Entrega 3 (pedidas por el docente; resueltas el 9/11)

No hay consigna escrita en `Documentacion/`: las cuatro correcciones las transmitió el usuario. El criterio de fondo del docente: **un modelo útil para el jugador**.

1. **Clasificación**: en qué banda de 3 minutos termina la partida, sabiendo lo del minuto 10.
2. **Distribución del error con gráficos**, no sólo números.
3. **Probar el MSE**, o buscar una métrica mejor.
4. **Expresar bien el R²**.

Decisiones del grupo (no reabrir sin preguntar): **el problema pasa a ser de clasificación** y el modelo final es una **regresión logística** (la más simple, y da una probabilidad por banda: «62 % de que termine entre 24 y 33 minutos»); 12 bandas, de 3 min entre 15 y 45 más `<15` y `45+`; se comparan la versión sin pesos y la `balanced` contra el piso, y decide el **F1 macro**, con accuracy, ±1 banda, error en minutos y matriz de confusión al lado; el MSE y el R² se explican en una sección corta sobre la regresión de la E3; el notebook es **corto y con muchos gráficos** (estilo de las prácticas: curva de C, barras de error, matrices de confusión, métricas por banda, calibración, coeficientes, permutación). **Resultado**: queda la **sin pesos, `C=1`** (F1 macro 0,099 en el test, piso 0,025). En minutos casi no le gana al piso (38,0 % contra 37,0 % de partidas a menos de 3 minutos); lo que aporta son probabilidades calibradas que cambian de partida en partida (dice 56 %, pasa 56 %). `balanced` no le gana en F1, cae por debajo del piso en accuracy y rompe la calibración.

Notebook: `notebooks/entrega-4/correcciones_entrega3.ipynb` (no es la Entrega 4: la app no se empezó). Detalle: Parte X de `docs/documentacion-proyecto.html`.

## Errores de años anteriores

Del Kit de arranque, sección 5:

- **Datos ya agregados.** Promedios por provincia, totales por año. Perdiste la observación individual y con ella la posibilidad de modelar.
- **Sin variable objetivo ni estructura latente.** Un listado de museos con su dirección es información, no un problema de ciencia de datos. En la unidad 3 el proyecto se rompe.
- **Muy pocas filas.** Con 200 registros los modelos no aprenden y los gráficos cuentan anécdotas.
- **Una sola columna útil.** Sin features no hay modelo, y sin dimensiones no hay visualizaciones que cruzar.
- **Bajable solo a mano.** Un PDF con una tabla adentro, un sitio con captcha, una base privada. La unidad 1 pide un pipeline automatizado.
- **Fuente elegida por descarte, sin interés real.** Es el que más caro sale: son cuatro meses.

Y el error de gestión más común (sección 8): **trabajar el integrador la semana previa a cada entrega.** Cada entrega se apoya en la anterior, y llegar con lo mínimo a la Entrega 1 significa arrastrar un pipeline frágil hasta noviembre.

## Material que NO está en el repo

Estas páginas del campus están enlazadas pero su contenido no se descargó. Si hace falta, hay que pedírselo al usuario:

- **"Cómo se evalúa"** — notas, mínimos, rúbrica del integrador y recuperatorios.
- **"Consigna Trabajo Práctico 1"** — el TP sobre FIFA.
- **"Calendario y entregas"** — las 16 clases con sus fechas y parciales.
