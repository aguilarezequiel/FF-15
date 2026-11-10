# Entregas del Integrador

Fuente: `Documentacion/Kit de arranque - Proyecto Integrador 2026.pdf` y las páginas del campus guardadas en `Documentacion/Consignas de Entrega N/`. La de la Entrega 4 (instructivo, app de ejemplo, teórica y práctica de Altair) está en `Documentacion/Consignas de Entrega 4/`, con el instructivo en texto en `consigna.md`.

## Contenido

- [Calendario](#calendario)
- [Cómo funciona la evaluación](#cómo-funciona-la-evaluación)
- [Instrucciones para la Entrega 1 (verbatim)](#instrucciones-para-la-entrega-1-verbatim)
- [Instrucciones para la Entrega 2 (verbatim)](#instrucciones-para-la-entrega-2-verbatim)
- [La Entrega 3 (resumen de la consigna)](#la-entrega-3-resumen-de-la-consigna)
- [La Entrega 4 (resumen de la consigna)](#la-entrega-4-resumen-de-la-consigna)
- [Errores de años anteriores](#errores-de-años-anteriores)

---

## Calendario

| Entrega | Fecha | Qué se presenta |
|---|---|---|
| Definición | 12/08 | Grupo, pregunta y fuente de datos |
| **1 · Ingeniería de datos** | **miércoles 9/9** | Pipeline automatizado que produce tu dataset |
| **2 · Análisis exploratorio** | **miércoles 23/9** | Exploración, hipótesis y hallazgos |
| **3 · Modelado** | **miércoles 28/10** | Objetivo predictivo, modelos comparados y métricas |
| **4 · Visualización y app** | **miércoles 11/11** | Aplicación web publicada en una URL pública que cuenta el proyecto y deja usarlo |
| Exposición final | 25/11 | Proyecto completo y demo en vivo, con la misma app de la E4 |
| Recuperación | sin fecha confirmada | El Kit decía 25/11, que el instructivo de la E4 ahora le da a la exposición final |

> **Discrepancia de fechas, a favor del campus.** El PDF del Kit de arranque dice que la Entrega 1 es el **02/09** y que la Entrega 2 es el **16/09**. Las consignas del campus, más recientes, dicen **miércoles 9 de septiembre** y **miércoles 23 de septiembre**. Valen las del campus. Lo mismo con la E4: el Kit decía **04/11** y la exposición final **18/11**; el instructivo de la E4 (`Documentacion/Consignas de Entrega 4/`) dice **miércoles 11 de noviembre** y **25 de noviembre**.

**Franja del grupo 5K09-02 en la Entrega 4: miércoles 11 de noviembre, 14:55 – 15:20** (25 minutos). Llegar cinco minutos antes con la aplicación ya abierta en su URL pública y el repositorio a mano.

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

1. **Clasificación**: en qué banda de minutos termina la partida, sabiendo lo del minuto 10.
2. **Distribución del error con gráficos**, no sólo números.
3. **Probar el MSE**, o buscar una métrica mejor.
4. **Expresar bien el R²**.

Decisiones del grupo (no reabrir sin preguntar): **el problema pasa a ser de clasificación** y el modelo es una **regresión logística** (la más simple, y da una probabilidad por banda: «79 % de que termine entre 21 y 33 minutos»). La primera versión (9/11) usaba 12 bandas de 3 min; **el 10/11 se reemplazaron por dos anchos**: 6 min (`<15, 15-21, 21-27, 27-33, 33-39, 39-45, 45+`) y 9 min (`<15, 15-24, 24-33, 33-42, 42+`), y **quedan dos modelos finales**. En cada ancho se comparan la versión sin pesos y la `balanced` contra el piso, y decide el **F1 macro**, con accuracy, ±1 banda (en los dos anchos: ±6 y ±9 min), error en minutos y matriz de confusión al lado. Al jugador: con 6 min, la ventana de 2 bandas (12 min); con 9 min, la banda más probable. El MSE y el R² se explican sobre la regresión de la E3 y se grafican (predicho contra real, con la recta y = x) para el Ridge y los dos clasificadores, pasando cada banda a su minuto típico. Cada gráfico del notebook tiene una fila por ancho. **Resultado**: los dos finales son la **sin pesos**: `C=10` con 6 min (F1 macro 0,159 en el test, piso 0,076) y `C=1` con 9 min (0,221, piso 0,137). Con 9 min la regla de la cátedra elegía la `balanced` (le ganaba por 0,0098 en F1 cv, con desvío 0,0072), y **el grupo la descartó**: en el test empata en F1, su accuracy (27,3 %) queda muy debajo del piso (52,2 %), erra 9,5 min en promedio y rompe la calibración. En minutos ninguno le gana casi al piso (37,5 y 38,0 % de partidas a menos de 3 min contra 36,5 y 37,0 %; R² pasado a minutos 0,042 y 0,046, contra 0,129 del Ridge); lo que aportan son probabilidades calibradas que cambian de partida en partida (6 min: dice 66,6 %, pasa 66,3 %; 9 min: dice 53,9 %, pasa 54,4 %). El notebook los compara sin elegir; **el 10/11 el grupo eligió el de 6 minutos para la app** de la Entrega 4.

Notebook: `notebooks/entrega-4/correcciones_entrega3.ipynb` (no es la Entrega 4: la app está en `app/`). Detalle: Parte X de `docs/documentacion-proyecto.html`.

## La Entrega 4 (resumen de la consigna)

Consigna completa en `Documentacion/Consignas de Entrega 4/` (instructivo en `consigna.md`; también la app de ejemplo de la cátedra, la teórica y la práctica de Altair). **Miércoles 11/11, 25 min en privado, franja del 5K09-02: 14:55 – 15:20.** Se entrega la versión final del proyecto: **una aplicación web publicada en una URL**, la misma de la exposición final del 25/11.

- **Forma de copa de martini.** Portada: la pregunta, la idea central en una oración con sujeto y verbo, y tres números. Tallo (lo guía el autor): «Los datos», «Lo que encontramos» y «El modelo», cada una con un **título que afirma**, un gráfico que lo prueba y un desplegable **«Cómo lo sabemos»** cerrado por defecto. Copa (la maneja el usuario): «Explorá» (panorama, al menos dos controles que cambian el gráfico, detalle a pedido con lo que dijo el modelo) y «Probá el modelo» (un caso nuevo, con probabilidad si es clasificación; no se pueden cargar valores que el modelo nunca vio, o la app avisa).
- **Gráficos con Altair**, legibles componente por componente; colores, categorías y escalas con el mismo significado en toda la app.
- **Dónde corre**: HTML en GitHub Pages (la fórmula del modelo escrita en la página) o Streamlit Community Cloud.
- **El proyecto integrado**: repo en GitHub con README; un script que toma los datos del pipeline, entrena con la misma semilla y genera la app; lo que muestra la app coincide con el notebook.
- **Los 25 minutos**: 0–2 qué cambió · 2–10 el tallo · 10–15 la copa (el docente toma el mouse) · 15–22 preguntas dirigidas · 22–25 devolución.
- **Se pregunta**: por qué cada título afirma lo que afirma; un gráfico componente por componente; una decisión de diseño que cambió; qué toca cada control; cómo llega el modelo a la app y qué pasa con un caso raro; cómo se regenera la app.

**Lo que hizo el grupo (10/11)**: `app/build_app.py` → `app/index.html`, HTML en GitHub Pages con la logística de 6 minutos. El script repite el modelado del notebook de las correcciones y **verifica siete números contra él** (corta si no coinciden). «Probá» parte de una partida real del test y mueve servidor, elo y las 7 métricas del minuto 10. Identidad visual propia (estética de LoL), no una copia del ejemplo. Publicada en https://aguilarezequiel.github.io/FF-15/ (el repo es público desde el 10/11; sólo queda el workflow `pages.yml`). Detalle: Parte XI de `docs/documentacion-proyecto.html`.

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
