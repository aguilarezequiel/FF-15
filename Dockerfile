FROM astrocrpublic.azurecr.io/runtime:3.3-4

# El código del proyecto vive en include/lol y se importa como `lol`.
ENV PYTHONPATH="/usr/local/airflow/include:${PYTHONPATH}"
