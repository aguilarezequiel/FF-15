# El método de EDA e hipótesis de la cátedra

Fuente: `Documentacion/Consignas de Entrega 2/`. La teórica está en
`2026 - EDA.pdf`; el aparato metodológico completo —semáforo, casillas,
plantillas, movimientos— está en `Hipotesis_sobre_el_canonico.ipynb`, que **es
el TP2** al que la consigna se refiere cuando dice «las mismas seis casillas del
TP2». No hay ningún otro archivo de TP2 en el repo.

## Contenido

- [Las seis fases del EDA](#las-seis-fases-del-eda)
- [Las dos preguntas](#las-dos-preguntas)
- [La regla del orden](#la-regla-del-orden)
- [Las tres plantillas y sus medidas](#las-tres-plantillas-y-sus-medidas)
- [El semáforo](#el-semáforo)
- [Los tres movimientos y el tope de dos](#los-tres-movimientos-y-el-tope-de-dos)
- [Las seis casillas de una ficha](#las-seis-casillas-de-una-ficha)
- [El chequeo de fuga](#el-chequeo-de-fuga)
- [Estilo de la cátedra](#estilo-de-la-cátedra)

---

## Las seis fases del EDA

El notebook de EDA de la cátedra las recorre en este orden, y dice explícitamente
que son «las mismas seis fases que define la teórica».

| # | Fase | Objetivo, textual del PDF |
|---|---|---|
| 1 | Inspección inicial | «construir un mapa mental del dataset antes de entrar en detalles» |
| 2 | Análisis univariado | «detectar comportamientos atípicos en un análisis aislado de cada variable» |
| 3 | Análisis bivariado | «estudiar relaciones entre dos variables» |
| 4 | Análisis de calidad | «definir estrategias de limpieza y preparación para el modelado» |
| 5 | Análisis temporal | «detectar patrones dinámicos que no se ven en un análisis estático» |
| 6 | Generación de hipótesis | «El EDA no solo responde preguntas, sino que ayuda a formular nuevas» |

**La fase 5 puede no aplicar, y decirlo es parte del análisis.** La cátedra lo
plantea así: «Antes de buscarlos hay que preguntarse algo más básico: ¿este
dataset tiene dimensión temporal? No todos la tienen, y reconocerlo también es
parte del análisis exploratorio». En FF-15 no aplica: ninguna de las 137
columnas es una fecha.

La fase 6 no cierra con un resumen: «termina en **preguntas mejores que las del
principio**».

## Las dos preguntas

> «**Qué queremos responder** es la pregunta de negocio. Termina en una
> conclusión. **Qué queremos predecir** es la de modelado. Termina en una
> decisión sobre qué columnas usar.»

La consigna exige al menos una ficha de cada tipo.

## La regla del orden

> «La afirmación y lo que esperás ver se escriben **antes** de correr la medida.
> Podés usar todo lo que ya sabías, pero no el resultado que estás por calcular.
> Si al releer tu hipótesis se nota que la escribiste después de mirar el
> gráfico, no estás poniendo a prueba nada: estás describiendo lo que viste.»

Y la tesis de fondo:

> «Una hipótesis no se contesta con un gráfico: se contesta con **un número**, y
> el gráfico explica ese número. Un gráfico no se compara contra nada.»

## Las tres plantillas y sus medidas

> «La forma trae su medida. Ese es todo el truco: si sabés en qué plantilla cae
> tu hipótesis, ya sabés qué número tenés que calcular, y no lo elegís después
> de ver cuál te conviene.»

| Forma | Se escribe | Medida |
|---|---|---|
| Comparación | «X difiere entre A y B» | separación estandarizada, o η² con varios grupos |
| Asociación | «X se mueve junto con Y» | Pearson y Spearman |
| Composición | «C está sobrerrepresentada en G» | proporción del grupo contra la global |

Las tres funciones, **verbatim** del notebook de la cátedra:

```python
def separacion(x, y):
    """Distancia entre dos muestras, en desviaciones estándar."""
    x, y = x.dropna(), y.dropna()
    return abs(x.mean() - y.mean()) / np.sqrt((x.std() ** 2 + y.std() ** 2) / 2)


def eta2(numerica, categoria):
    """Proporción de la varianza de la numérica que explica la categoría."""
    g = numerica.groupby(categoria)
    m = numerica.mean()
    return (g.count() * (g.mean() - m) ** 2).sum() / ((numerica - m) ** 2).sum()


def asociacion(x, y):
    """Pearson, Spearman y la brecha entre ambos."""
    p, s = x.corr(y), x.corr(y, method="spearman")
    return pd.Series({"pearson": p, "spearman": s, "brecha": s - p}).round(3)
```

`separacion` es Cohen's d con desvío combinado, pero **la cátedra nunca la llama
así**: el nombre de cátedra es *separación estandarizada*. Del mismo modo, no
enseña Cramér's V, Cliff's delta ni odds ratio. El vocabulario es: separación,
η² o razón de correlación, Pearson, Spearman, brecha, proporción.

**La composición no tiene función ni cortes**: se compara una proporción dentro
del grupo contra la global, y se interpreta cualitativamente.

**Nada de p-values ni tests de significancia**, y está justificado:

> «con 18.936 filas casi cualquier diferencia da estadísticamente significativa.
> [...] Pero real no es lo mismo que importante.»

**`scipy` hace falta igual aunque no se importe**: `Series.corr(method="spearman")`
delega en `scipy.stats.spearmanr`.

## El semáforo

`rojo` si `|v| < bajo`; `verde` si `|v| > alto`; `amarillo` en el medio, bordes
incluidos. **Siempre sobre el valor absoluto**: el signo se lee aparte, así que
una correlación de −0,818 es verde y negativa.

| Medida | rojo | amarillo | verde |
|---|---|---|---|
| separación | < 0,2 | 0,2 – 0,8 | > 0,8 |
| η² | < 0,05 | 0,05 – 0,25 | > 0,25 |
| correlación | < 0,2 | 0,2 – 0,6 | > 0,6 |
| brecha (Spearman − Pearson) | < 0,05 | 0,05 – 0,15 | > 0,15 |

```python
CORTES = {"separacion": (0.2, 0.8), "eta2": (0.05, 0.25),
          "correlacion": (0.2, 0.6), "brecha": (0.05, 0.15)}


def semaforo(valor, medida):
    """Devuelve la zona en la que cae el valor, según la medida usada."""
    bajo, alto = CORTES[medida]
    v = abs(valor)
    return "rojo" if v < bajo else "verde" if v > alto else "amarillo"
```

Justificación de cada corte, textual: separación 0,2 y 0,8 son «los cortes
convencionales de tamaño de efecto» —con 0,2 las distribuciones se superponen en
el 92 % de su área, con 0,8 en el 69 %—; η² se lee directo como proporción de
varianza explicada; correlación es «la misma lógica que la separación, en la
escala de −1 a 1». La brecha es invención de la cátedra: «Sirve para esta
materia; **no la cites como si fuera una regla establecida**».

**La brecha es un detector de curvatura**: cuando Spearman supera a Pearson, la
relación existe y es ordenada pero no es recta.

## Los tres movimientos y el tope de dos

> «**Verde** y **rojo** terminan la hipótesis. **Amarillo** es el único que
> habilita seguir, y seguir quiere decir hacer un **movimiento**.»

| Movimiento | Cuándo se usa (lo dice el gráfico) |
|---|---|
| Partir la población | el gráfico muestra grupos que se comportan distinto |
| Controlar una tercera variable | la relación observada contradice algo que sabemos cierto |
| Cambiar la escala | la brecha entre Spearman y Pearson es grande |

> «El movimiento **no se elige a ojo ni se prueban los tres a ver cuál da
> mejor**: se elige mirando el gráfico. Y hay un tope de **dos movimientos por
> hipótesis**: si después del segundo el número sigue amarillo, la conclusión es
> *inconclusa*. Sin tope, partiendo el dataset lo suficiente cualquier hipótesis
> termina confirmada.»

Los tres veredictos se escriben con esas palabras: **confirmada**, **refutada**,
**inconclusa**. Y «escribir *inconclusa* es más honesto que forzar un veredicto».

Dos observaciones que la cátedra remarca y conviene reusar:

- **Un movimiento que empeora el resultado es información**: dice que la
  variable que controlaste no estaba tapando nada.
- Insistir sobre un rojo es **cazar resultados**: «con suficientes recortes
  siempre aparece un subgrupo donde el efecto existe, y no significa nada».

## Las seis casillas de una ficha

> «Cada hipótesis se resuelve completando seis campos, y son los mismos seis que
> pide el TP: la **afirmación**, **qué espero ver** antes de mirar, la **medida**
> y el **gráfico**, el **resultado** con su zona, el **movimiento** que hice si
> dio amarillo, y **qué hago con eso**.»

Los rótulos exactos, en negrita, tal como los escribe:

1. `**Afirmación.**`
2. `**Qué espero ver.**`
3. `**Por qué esta medida.**` (o `**Por qué estas medidas.**` si la afirmación
   tiene dos partes)
4. `**Resultado.**` — variantes: `**Resultado parcial.**`,
   `**Resultado tras el movimiento.**`, `**Resultado tras los dos movimientos.**`
5. `**Movimiento 1: <nombre>.**` / `**Movimiento 2: <nombre>.**`
6. `**Qué hago con eso.**`

Y un campo intermedio que aparece siempre que hay gráfico: `**Qué se ve.**`, que
es la lectura del gráfico y lo que justifica el movimiento.

La tabla resumen final lleva seis columnas —`hipótesis | pregunta | plantilla |
medida | zona | decisión`— y en «medida» va **la trayectoria del número**
(`0.054 → 0.077 → 0.066`), no sólo el valor final.

## El chequeo de fuga

> «Antes de darle una columna al modelo, preguntate si esa columna existiría en
> el momento de predecir. Si la respuesta ya está adentro, no es una feature: es
> la respuesta escrita de otra forma, y el modelo va a dar buenísimo por el peor
> de los motivos.»

> «Una columna que es demasiado buena para ser cierta casi nunca es cierta.»

La **tabla de columnas candidatas** tiene cinco columnas exactas:
`Columna | Qué mide | Zona | Decisión | ¿Existiría al predecir?`
y la decisión admite tres verbos: **entra**, **sale**, **se transforma** (por
ejemplo «entra en escala logarítmica»).

## Estilo de la cátedra

- Sólo `pandas`, `numpy` y `matplotlib`. **Sin seaborn, sin `plt.style.use`, sin
  `sns.set`.**
- Dos colores y nada más: **`#009086`** primario, **`#B5402C`** secundario.
  Matrices de correlación con `cmap="RdBu", vmin=-1, vmax=1`.
- **Ni un `print()`** en todo el material: las salidas son `pd.Series` o
  `pd.DataFrame`, casi siempre con `.round(3)`.
- Ritmo de tres celdas: markdown que explica el concepto y anticipa qué se va a
  mirar → celda de código corta con **un comentario de una línea** que dice qué
  se pregunta, no qué hace el código → markdown que interpreta el número.
- Títulos de sección **declarativos, no rótulos**: «Duplicados: primero hay que
  elegir la clave», no «Duplicados».
- Nombres de funciones y variables **en castellano**, constantes en MAYÚSCULAS,
  docstring de una línea.
- Cada conclusión cita el número, **con coma decimal en la prosa**. Negrita para
  la idea que hay que llevarse, no para los términos técnicos.
- Tamaños: panel simple `figsize=(6.5, 4.5)`, dos paneles `(13, 3.8)`, cinco
  paneles `(15, 3.2)`, boxplot de muchas categorías `(12, 4)` con `rot=90`.
  Scatter con mucha data siempre `s=3, alpha=.15`. Siempre `plt.tight_layout()`
  y `plt.show()`.
- Toda transformación va seguida de **un chequeo de que no rompió nada**.

## Las tres formas de perder la defensa

De `consigna.md`, textual:

- **El EDA de checklist.** «Veinte gráficos, ninguna conclusión. Un histograma
  por columna no es un análisis exploratorio: es un catálogo.»
- **Contestar con el gráfico.** «"Se ve que hay diferencia" no es un resultado.»
- **Que hable uno solo.** «Es el error más caro, porque las preguntas van
  dirigidas y la nota es individual.»
