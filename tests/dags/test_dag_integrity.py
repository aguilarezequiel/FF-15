"""Chequeos de integridad del DAG y del esquema.

Corren con `astro dev pytest`, dentro del contenedor.
"""
from airflow.models import DagBag

from lol import schema, transform

TAREAS_ESPERADAS = {
    "wait_for_riot", "check_key", "fetch_ddragon", "plan_plataformas",
    "land_bronze", "refine_silver", "consolidate", "validate", "save",
    "plan_timelines", "land_timelines", "refine_minuto", "save_minuto",
}


def _dagbag():
    return DagBag(include_examples=False)


def _dag():
    """El DAG desde el diccionario en memoria del DagBag.

    No se usa `DagBag.get_dag()`: en Airflow 3 esa función consulta la
    tabla `dag` de la metadata DB, que no existe en el contexto de
    pytest. `.dags` es el resultado del parseo, que es justo lo que estos
    tests quieren verificar.
    """
    dag = _dagbag().dags.get("lol_ingest")
    assert dag is not None, "lol_ingest no se registró"
    return dag


def test_sin_errores_de_import():
    dagbag = _dagbag()
    assert not dagbag.import_errors, f"errores de import: {dagbag.import_errors}"


def test_dag_registrado():
    assert set(_dagbag().dag_ids) == {"lol_ingest"}


def test_tareas_del_grafo():
    faltan = TAREAS_ESPERADAS - set(_dag().task_dict)
    assert not faltan, f"faltan tareas: {faltan}"


def test_corre_a_demanda():
    """A demanda y no programado: la development key vence cada 24 hs."""
    assert _dag().schedule is None


def test_no_hace_catchup():
    assert _dag().catchup is False


# --- el esquema ------------------------------------------------------------

def test_ancho_del_esquema():
    """138 del prototipo + roles_inferidos (+1) - los dos count_smite (-2)."""
    assert len(schema.COLUMNS) == 137
    assert len(set(schema.COLUMNS)) == len(schema.COLUMNS)


def test_particion_de_tipos():
    """Cada columna cae en exactamente un grupo de tipo."""
    grupos = schema.ENTEROS + schema.FLOTANTES + schema.TEXTO
    assert sorted(grupos) == sorted(schema.COLUMNS)


def test_clave_y_target_estan():
    assert "match_id" in schema.COLUMNS
    assert "game_duration_s" in schema.COLUMNS


def test_ancho_del_dataset_al_minuto():
    """Clave + objetivo + 10 métricas x (t1, t2, dif) + 3 de primera sangre."""
    cols = schema.columnas_minuto(5)
    assert len(cols) == 35
    assert len(set(cols)) == len(cols)
    assert cols[:2] == ["match_id", "game_duration_s"]
    assert set(schema.columnas_minuto(10)).isdisjoint(cols[2:])


# --- las trampas conocidas de la fuente ------------------------------------

def test_duracion_en_milisegundos_se_normaliza():
    """Riot devuelve gameDuration en ms en partidas anteriores al 11.20."""
    assert transform.normalizar_duracion(1_800_000) == 1800
    assert transform.normalizar_duracion(1800) == 1800


def test_roles_sin_teamposition_se_cuentan():
    """Un teamPosition vacío no puede etiquetar mal en silencio."""
    parts = [{"teamPosition": p} for p in schema.TEAM_POSITIONS]
    _, inferidos = transform.ordenar_por_rol(parts)
    assert inferidos == 0

    parts[2]["teamPosition"] = ""
    _, inferidos = transform.ordenar_por_rol(parts)
    assert inferidos == 1
