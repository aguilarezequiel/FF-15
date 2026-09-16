# notebooks/

El análisis de las Unidades 2 y siguientes. Una carpeta por entrega.

```
notebooks/
├── requirements.txt          · el stack de análisis, con versiones exactas
└── entrega-2/
    ├── eda_entrega2.ipynb    · el entregable de la Entrega 2, ya ejecutado
    └── datos/
        └── lol_2026-09-06.csv  · 19.145 × 137, la corrida del 5–6/9
```

## Por qué el CSV está versionado acá

`include/output/` está gitignoreado, así que el dataset que produce el pipeline
no viaja por git. El notebook tiene que correr **de arriba a abajo en la máquina
de cualquiera del grupo**, sin levantar Airflow, y los números que se defienden
tienen que estar clavados a un archivo concreto. Por eso la corrida que se
presenta viaja congelada al lado del notebook.

Son 11 MB. Es el precio de que el análisis sea reproducible y de que la defensa
no dependa de que alguien tenga Docker prendido.

## Por qué un venv aparte y no la imagen de Airflow

El pipeline necesita `pandas` y `requests`. El análisis necesita además
matplotlib, scipy y todo Jupyter. Meter eso en `requirements.txt` engordaría la
imagen del contenedor y obligaría a `astro dev restart` cada vez que se toque
una versión del análisis. Son dos entornos con dos propósitos, y se mantienen
separados.

## Poner en marcha

Desde la raíz del repo:

```bash
python -m venv .venv
.venv\Scripts\pip install -r notebooks/requirements.txt
.venv\Scripts\jupyter lab
```

`.venv/` está gitignoreado.

## Volver a ejecutarlo entero

La consigna de la Entrega 2 exige que el notebook esté **ejecutado y con las
salidas guardadas**. Para regenerarlas sin abrir Jupyter:

```bash
.venv\Scripts\jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=900 notebooks/entrega-2/eda_entrega2.ipynb
```

Tarda alrededor de un minuto. Si alguna celda falla, `nbconvert` corta y
devuelve error, así que un exit code 0 es la garantía de que el notebook corre
entero.

## Las versiones están pinneadas a propósito

`notebooks/requirements.txt` fija versiones exactas, no `>=`. Entre pandas 2 y
pandas 3 cambia el dtype de las columnas de texto —`object` pasa a ser
`StringDtype`— y el perfil del dataset que se defiende en la entrega tiene que
coincidir con la salida que quedó guardada en el `.ipynb`.

`scipy` no se importa en ninguna celda y hace falta igual: el helper
`asociacion()` de la cátedra llama a `Series.corr(method="spearman")`, y pandas
delega ese cálculo en `scipy.stats.spearmanr`.

No hay `seaborn`: la cátedra usa matplotlib crudo, sin `sns.set` ni
`plt.style.use`, con dos colores fijos (`#009086` y `#B5402C`).
