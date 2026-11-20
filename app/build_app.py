"""
Construye la aplicación de la Entrega 4: app/index.html, una sola página con todo adentro.

    .venv\\Scripts\\python app/build_app.py                    # con los CSV congelados (los del notebook)
    .venv\\Scripts\\python app/build_app.py --desde-pipeline   # con lo último que dejó el DAG en include/output/

Hace, en orden, lo mismo que notebooks/entrega-4/correcciones_entrega3.ipynb para el ancho de
6 minutos: las mismas clases, la misma partición, los mismos cinco pedazos y SEMILLA = 42. Entrena
la regresión logística sin pesos (el modelo final que eligió el grupo) y, como la Sección 9 del
notebook, la misma logística antes de jugar y al minuto 5, para comparar los tres momentos. Mide lo
que muestra la app y escribe los gráficos de Altair y la fórmula del modelo adentro de la página.

Con los CSV congelados, antes de escribir nada compara sus números con los que quedaron guardados
en el notebook: si no coinciden, corta. Lo que muestra la app tiene que ser lo que da el notebook.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import urllib.request
from pathlib import Path
from string import Template

import altair as alt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    mean_absolute_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    KFold,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

log = logging.getLogger("build_app")

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "app"
SEMILLA = 42

# ─────────────────────────────────────────────────────────────────────────────
# 1 · Las clases y el pipeline: copiados sin cambios del notebook (Sección 0)
# ─────────────────────────────────────────────────────────────────────────────
POS = ["top", "jng", "mid", "bot", "sup"]
EQUIPOS = ["t1", "t2"]
AGG = ["mains_count", "num_tanks", "num_mages", "num_assassins", "num_marksmen", "num_fighters",
       "num_supports", "avg_attack", "avg_defense", "avg_magic", "avg_difficulty", "avg_attackrange",
       "total_base_hp", "total_base_armor", "count_teleport", "count_ignite", "count_flash"]
SUMAS = ["num_tanks", "num_mages", "num_assassins", "num_marksmen", "num_fighters", "num_supports",
         "avg_attack", "avg_difficulty", "avg_attackrange", "total_base_hp", "count_teleport", "count_ignite"]
METRICAS_MINUTO = ["gold", "xp", "cs", "level", "kills", "towers", "elite_monsters"]


def de_jugador(feature, equipos=EQUIPOS):
    """Los nombres de las columnas de una feature de jugador, para los equipos pedidos."""
    return [f"{e}_{p}_{feature}" for e in equipos for p in POS]


def por_equipo(X, equipo):
    """Elo, winrate y log-maestría medios de los cinco jugadores de un equipo."""
    return pd.DataFrame({
        "elo": X[de_jugador("player_elo", [equipo])].mean(axis=1),
        "winrate": X[de_jugador("player_winrate", [equipo])].mean(axis=1),
        "logmastery": np.log1p(X[de_jugador("champ_mastery_pts", [equipo])]).mean(axis=1)}, index=X.index)


class DiferenciasEntreEquipos(BaseEstimator, TransformerMixin):
    """Cuánto se separan los dos equipos en cada columna conocida antes de jugar: |t1 - t2|."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        t1, t2 = por_equipo(X, "t1"), por_equipo(X, "t2")
        nuevas = {f"dif_{a}": (X[f"t1_{a}"] - X[f"t2_{a}"]).abs() for a in AGG}
        nuevas |= {f"dif_{k}": (t1[k] - t2[k]).abs() for k in t1.columns}
        return pd.DataFrame(nuevas, index=X.index)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"dif_{a}" for a in AGG] + ["dif_elo", "dif_winrate", "dif_logmastery"])


class ColumnasDePartida(BaseEstimator, TransformerMixin):
    """Las columnas por partida que dejó la tabla de candidatas de la Entrega 2."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        nuevas = pd.DataFrame({f"suma_{a}": X[f"t1_{a}"] + X[f"t2_{a}"] for a in SUMAS}, index=X.index)
        nuevas["elo_partida"] = X[de_jugador("player_elo")].mean(axis=1)
        nuevas["logmastery_partida"] = np.log1p(X[de_jugador("champ_mastery_pts")]).mean(axis=1)
        nuevas["plataforma"] = X["match_id"].str.split("_").str[0]
        return nuevas

    def get_feature_names_out(self, input_features=None):
        return np.array([f"suma_{a}" for a in SUMAS] + ["elo_partida", "logmastery_partida", "plataforma"])


class EstadoAlMinuto(BaseEstimator, TransformerMixin):
    """Del CSV del minuto N: cuánto se separan los equipos (|t1 - t2|) y el total de la partida (t1 + t2)."""

    def __init__(self, minuto=10):
        self.minuto = minuto

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        s = f"_m{self.minuto}"
        nuevas = {f"suma_{m}{s}": X[f"t1_{m}{s}"] + X[f"t2_{m}{s}"] for m in METRICAS_MINUTO}
        nuevas |= {f"dif_{m}{s}": X[f"dif_{m}{s}"] for m in METRICAS_MINUTO}
        return pd.DataFrame(nuevas, index=X.index)

    def get_feature_names_out(self, input_features=None):
        s = f"_m{self.minuto}"
        return np.array([f"suma_{m}{s}" for m in METRICAS_MINUTO] + [f"dif_{m}{s}" for m in METRICAS_MINUTO])


def armar(modelo, minuto=10):
    """El pipeline de la E3: derivar, imputar y escalar, codificar, y el modelo al final.

    minuto=10 es el del modelo final. Con minuto=5 usa el estado al minuto 5, y con minuto=None sólo lo
    que se sabe antes de jugar (Sección 9 del notebook).
    """
    partes = [("partida", ColumnasDePartida()), ("diferencias", DiferenciasEntreEquipos())]
    if minuto is not None:
        partes.append(("minuto", EstadoAlMinuto(minuto)))
    derivar = FeatureUnion(partes, verbose_feature_names_out=False).set_output(transform="pandas")
    preparar = ColumnTransformer([
        ("numericas", Pipeline([("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())]),
         make_column_selector(dtype_include="number")),
        ("categoricas", OneHotEncoder(handle_unknown="ignore"), make_column_selector(dtype_exclude="number"))],
        verbose_feature_names_out=False)
    return Pipeline([("derivar", derivar), ("preparar", preparar), ("modelo", modelo)])


# ─────────────────────────────────────────────────────────────────────────────
# 2 · Las bandas de 6 minutos y las métricas (Secciones 1 a 3 del notebook)
# ─────────────────────────────────────────────────────────────────────────────
CORTES = [0, 15, 21, 27, 33, 39, 45, np.inf]
BANDAS = ["<15", "15-21", "21-27", "27-33", "33-39", "39-45", "45+"]
K = len(BANDAS)
VENTANA = 2  # al jugador: las 2 bandas consecutivas más probables (12 minutos)
GRUPOS = ["Hierro–Oro", "Platino–Diamante", "Master–Challenger"]  # noqa: RUF001 (raya y menos tipográficos)
GRILLA_C = [0.001, 0.01, 0.1, 1, 10]

# Lo que quedó guardado en el notebook (Secciones 2, 3 y 5) para el ancho de 6 minutos.
# Con los CSV congelados, la app tiene que dar exactamente esto.
DEL_NOTEBOOK = {"C": 10, "F1 test": 0.159, "F1 piso test": 0.076, "accuracy test": 0.369,
                "±1 banda test": 0.843, "dice ventana": 0.666, "pasa ventana": 0.663,
                # Sección 9: la misma logística antes de jugar y al minuto 5
                "C antes de jugar": 10, "F1 test antes de jugar": 0.111,
                "C minuto 5": 10, "F1 test minuto 5": 0.133}

# Los tres momentos en los que se predice (Sección 9 del notebook): las mismas partidas, otras columnas
MOMENTOS = {"antes de jugar": None, "minuto 5": 5, "minuto 10": 10}
CORTO = {"antes de jugar": "antes", "minuto 5": "m5", "minuto 10": "m10"}


def banda_de(segundos):
    """El número de banda (0 = la más corta) de una duración en segundos."""
    return pd.cut(segundos / 60, CORTES, right=False, labels=False).astype(int)


def a_una_banda(real, pred):
    """Proporción de partidas cuya banda predicha está a lo sumo a una de la real."""
    return np.mean(np.abs(np.asarray(real) - np.asarray(pred)) <= 1)


def sumas_ventana(P, n=VENTANA):
    """Para cada partida (fila de P), la probabilidad sumada de cada ventana de n bandas consecutivas."""
    return np.stack([P[:, i:i + n].sum(axis=1) for i in range(P.shape[1] - n + 1)], axis=1)


def texto_ventana(i, largo=True):
    """La ventana que empieza en la banda i, como se le dice al jugador."""
    ini, fin = CORTES[i], CORTES[i + VENTANA]
    if i == 0:
        return f"antes del minuto {fin}" if largo else f"<{fin} min"
    if np.isinf(fin):
        return f"después del minuto {ini}" if largo else f"{ini}+ min"
    return f"entre los minutos {ini} y {fin}" if largo else f"{ini}–{fin} min"  # noqa: RUF001 (raya y menos tipográficos)


# ─────────────────────────────────────────────────────────────────────────────
# 3 · Cómo se escriben los números en la página
# ─────────────────────────────────────────────────────────────────────────────
def num(x, dec=0):
    """Un número a la manera argentina: 19.145 · 0,159."""
    return f"{x:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".").replace("-", "−")  # noqa: RUF001 (raya y menos tipográficos)


def pct(x, dec=1):
    return f"{num(100 * x, dec)} %"


def tabla(encabezado, filas, clase=""):
    """Una tabla HTML. Las celdas ya vienen como texto."""
    th = "".join(f"<th>{h}</th>" for h in encabezado)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f'<div class="tabla {clase}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


NOMBRES = {
    "num_tanks": "tanques", "num_mages": "magos", "num_assassins": "asesinos", "num_marksmen": "tiradores",
    "num_fighters": "luchadores", "num_supports": "soportes", "avg_attack": "ataque medio",
    "avg_difficulty": "dificultad media", "avg_attackrange": "alcance medio", "total_base_hp": "vida base",
    "count_teleport": "Teleport", "count_ignite": "Ignite", "mains_count": "mains", "avg_defense": "defensa media",
    "avg_magic": "magia media", "total_base_armor": "armadura base", "count_flash": "Flash",
    "elo": "elo", "winrate": "winrate", "logmastery": "log-maestría",
    "gold": "oro", "xp": "experiencia", "cs": "súbditos", "level": "nivel", "kills": "asesinatos",
    "towers": "torres", "elite_monsters": "monstruos épicos"}


def legible(col):
    """El nombre de una columna derivada, en castellano."""
    if col == "elo_partida":
        return "elo medio de la partida"
    if col == "logmastery_partida":
        return "log-maestría media"
    minuto = col.endswith("_m10")
    base = col.removesuffix("_m10")
    tipo, _, resto = base.partition("_")
    nombre = NOMBRES.get(resto, resto)
    if minuto:
        return f"{'diferencia de' if tipo == 'dif' else 'total de'} {nombre} al minuto 10"
    return f"{'diferencia de' if tipo == 'dif' else ''} {nombre}{' en la partida' if tipo == 'suma' else ''}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# 4 · La identidad visual: los mismos colores significan lo mismo en toda la app
# ─────────────────────────────────────────────────────────────────────────────
PANEL, CREMA, GRIS, LINEA = "#0E1A2E", "#F0E6D2", "#A09B8C", "#24344F"
ORO = "#C8AA6E"        # lo que dice el modelo
HEXTECH = "#0AC8B9"    # lo que se sabe al minuto 10
PIZARRA = "#6E7F99"    # lo que se sabe antes de jugar
PISO_COLOR = "#8C8C8C"  # el piso
MINUTO5 = "#3CA3A9"    # lo que se sabe al minuto 5: entre el gris azulado y el turquesa
COLOR_MOMENTO = {"antes de jugar": PIZARRA, "minuto 5": MINUTO5, "minuto 10": HEXTECH}
ESCALA_MOMENTO = alt.Scale(domain=list(MOMENTOS), range=list(COLOR_MOMENTO.values()))
# Las bandas son ordinales: un degradé de un solo azul, de claro (la más corta) a oscuro (la más larga).
# Pasos parejos en OKLCH (L de 0,97 a 0,54, tono 262); el más oscuro tiene contraste >= 3:1 con el panel
COLORES_BANDA = ["#EAF6FF", "#C9DEFF", "#A9C7FD", "#89AFF6", "#6A98ED", "#4B7FE4", "#2A66DB"]
ESCALA_BANDA = alt.Scale(domain=BANDAS, range=COLORES_BANDA)
FUENTE = "Inter, Segoe UI, Helvetica, Arial, sans-serif"


@alt.theme.register("ff15", enable=True)
def tema():
    return alt.theme.ThemeConfig({"config": {
        "background": PANEL, "font": FUENTE, "padding": 10,
        "view": {"stroke": None, "continuousWidth": 560, "continuousHeight": 320},
        "axis": {"domainColor": "#3A4B66", "gridColor": LINEA, "tickColor": "#3A4B66", "labelColor": GRIS,
                 "titleColor": GRIS, "labelFontSize": 12.5, "titleFontSize": 12.5, "titleFontWeight": "normal"},
        "legend": {"labelColor": CREMA, "titleColor": GRIS, "labelFontSize": 12.5, "titleFontSize": 12.5,
                   "titleFontWeight": "normal"},
        "title": {"color": CREMA, "subtitleColor": GRIS, "fontSize": 16, "subtitleFontSize": 12.5, "anchor": "start",
                  "font": FUENTE, "fontWeight": 600, "offset": 12},
        "text": {"color": CREMA, "font": FUENTE},
        "header": {"labelColor": CREMA, "titleColor": GRIS}}})


alt.data_transformers.disable_max_rows()


# ─────────────────────────────────────────────────────────────────────────────
# 5 · Los datos
# ─────────────────────────────────────────────────────────────────────────────
def buscar(patron, carpeta):
    """El CSV más reciente que cumple el patrón en una carpeta."""
    candidatos = sorted(carpeta.glob(patron))
    if not candidatos:
        raise SystemExit(f"No hay ningún {patron} en {carpeta}")
    return candidatos[-1]


def cargar(desde_pipeline):
    if desde_pipeline:
        salida = RAIZ / "include" / "output"
        ruta_df, ruta_min = buscar("lol_2*.csv", salida), buscar("lol_min10_*.csv", salida)
        ruta_min5 = buscar("lol_min5_*.csv", salida)
    else:
        ruta_df = buscar("lol_2*.csv", RAIZ / "notebooks" / "entrega-2" / "datos")
        ruta_min = buscar("lol_min10_*.csv", RAIZ / "notebooks" / "entrega-3" / "datos")
        ruta_min5 = buscar("lol_min5_*.csv", RAIZ / "notebooks" / "entrega-3" / "datos")
    log.info("Datos: %s, %s y %s", ruta_df.name, ruta_min.name, ruta_min5.name)
    return (pd.read_csv(ruta_df), pd.read_csv(ruta_min), pd.read_csv(ruta_min5), ruta_df.name, ruta_min.name,
            ruta_min5.name)


def version_ddragon():
    """La versión más reciente de Data Dragon, para los íconos de los campeones. Si no hay red, sin íconos."""
    try:
        with urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json", timeout=10) as r:
            return json.load(r)[0]
    except Exception as e:
        log.warning("Sin versión de Data Dragon (%s): la app sale sin íconos de campeones", e)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--desde-pipeline", action="store_true",
                        help="leer lo último que dejó el DAG en include/output/ en vez de los CSV congelados")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    df, min10, min5, nombre_df, nombre_min, nombre_min5 = cargar(args.desde_pipeline)

    # La partición de la E3 (notebook, Sección 0)
    grupo = pd.cut(df[de_jugador("player_elo")].mean(axis=1), [-np.inf, 2000, 2900, np.inf], right=False,
                   labels=GRUPOS)
    X_train, X_test = train_test_split(df.drop(columns=["game_duration_s"]), test_size=0.2,
                                       stratify=grupo, random_state=SEMILLA)
    d10 = df.join(min10.drop(columns="game_duration_s").set_index("match_id"), on="match_id", how="inner")
    tr, te = X_train.index.intersection(d10.index), X_test.index.intersection(d10.index)
    X10, y10 = d10.loc[tr].drop(columns="game_duration_s"), d10.loc[tr, "game_duration_s"]
    X10_te, y10_te = d10.loc[te].drop(columns="game_duration_s"), d10.loc[te, "game_duration_s"]
    cv = KFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    yb, yb_te = banda_de(y10), banda_de(y10_te)
    minuto_tipico = (y10.groupby(yb).median() / 60).reindex(range(K)).to_numpy()
    log.info("Partidas: %d en total, %d llegan al minuto 10 (%d train, %d test)", len(df), len(d10), len(X10),
             len(X10_te))
    # Sección 9: el estado al minuto 5, sobre las mismas partidas (todas las que llegan al 10 llegan al 5)
    d_mom = d10.join(min5.drop(columns="game_duration_s").set_index("match_id"), on="match_id", how="left")
    assert d_mom[[f"dif_{m}_m5" for m in METRICAS_MINUTO]].notna().all().all()
    Xm, Xm_te = d_mom.loc[tr].drop(columns="game_duration_s"), d_mom.loc[te].drop(columns="game_duration_s")

    # ── Elegir el modelo (notebook, Sección 2), sólo el ancho de 6 minutos ──
    scorers = {"F1 macro": "f1_macro", "accuracy": "accuracy", "±1 banda": make_scorer(a_una_banda)}
    piso_cv = cross_validate(armar(DummyClassifier(strategy="prior")), X10, yb, cv=cv, scoring=scorers, n_jobs=-1)
    busquedas = {n: GridSearchCV(armar(LogisticRegression(max_iter=3000, class_weight=w)), {"modelo__C": GRILLA_C},
                                 cv=cv, scoring=scorers, refit="F1 macro", n_jobs=-1).fit(X10, yb)
                 for n, w in {"sin pesos": None, "balanced": "balanced"}.items()}
    final = busquedas["sin pesos"].best_estimator_
    C_final = busquedas["sin pesos"].best_params_["modelo__C"]
    piso = armar(DummyClassifier(strategy="prior")).fit(X10, yb)
    # Los otros dos momentos, cada uno con su C (el del minuto 10 es el final)
    busq_mom = {n: GridSearchCV(armar(LogisticRegression(max_iter=3000), minuto=m), {"modelo__C": GRILLA_C}, cv=cv,
                                scoring=scorers, refit="F1 macro", n_jobs=-1).fit(Xm, yb)
                for n, m in MOMENTOS.items() if m != 10} | {"minuto 10": busquedas["sin pesos"]}

    # ── El test, una sola vez (Sección 3) ──
    P_te, P_piso = final.predict_proba(X10_te), piso.predict_proba(X10_te)
    pred_te, pred_piso = P_te.argmax(axis=1), P_piso.argmax(axis=1)

    def resumen(pred):
        err = np.abs(minuto_tipico[pred] - y10_te.to_numpy() / 60)
        return {"F1": f1_score(yb_te, pred, average="macro", labels=range(K), zero_division=0),
                "accuracy": accuracy_score(yb_te, pred), "±1": a_una_banda(yb_te, pred),
                "≤3": (err <= 3).mean(), "error medio": err.mean()}

    m_final, m_piso = resumen(pred_te), resumen(pred_piso)

    # ── Lo que vería el jugador: la ventana de 12 minutos, y si está calibrada (Sección 5) ──
    def ventana_de(P):
        s = sumas_ventana(P)
        ini = s.argmax(axis=1)
        return ini, s.max(axis=1)

    real_te = yb_te.to_numpy()
    ini_te, dice_te = ventana_de(P_te)
    pasa_te = (real_te >= ini_te) & (real_te <= ini_te + VENTANA - 1)
    ini_piso, dice_piso = ventana_de(P_piso)
    pasa_piso = (real_te >= ini_piso) & (real_te <= ini_piso + VENTANA - 1)
    tercio = pd.qcut(dice_te, 3, labels=["el tercio en que dice menos", "el tercio del medio", "el tercio en que dice más"])
    resolucion = {t: (dice_te[np.asarray(tercio == t)].min(), dice_te[np.asarray(tercio == t)].max(),
                      pasa_te[np.asarray(tercio == t)].mean()) for t in tercio.categories}

    # Los tres momentos en el test (Sección 9): la ventana, las métricas y la matriz de cada uno
    P_mom = {n: b.best_estimator_.predict_proba(Xm_te) for n, b in busq_mom.items()}
    assert np.allclose(P_mom["minuto 10"], P_te)
    m_mom, cm_mom = {}, {}
    for n, P in P_mom.items():
        b = busq_mom[n]
        ini, dice = ventana_de(P)
        m_mom[n] = resumen(P.argmax(axis=1)) | {
            "dice": dice.mean(), "pasa": ((real_te >= ini) & (real_te <= ini + VENTANA - 1)).mean(),
            "contesta": len(np.unique(P.argmax(axis=1))), "C": b.best_params_["modelo__C"],
            "F1 cv": b.cv_results_["mean_test_F1 macro"][b.best_index_],
            "F1 cv desvío": b.cv_results_["std_test_F1 macro"][b.best_index_]}
        cm_mom[n] = confusion_matrix(yb_te, P.argmax(axis=1), labels=range(K))

    chequeo = {"C": C_final, "F1 test": round(m_final["F1"], 3), "F1 piso test": round(m_piso["F1"], 3),
               "accuracy test": round(m_final["accuracy"], 3), "±1 banda test": round(m_final["±1"], 3),
               "dice ventana": round(dice_te.mean(), 3), "pasa ventana": round(pasa_te.mean(), 3)}
    for n in ["antes de jugar", "minuto 5"]:
        chequeo |= {f"C {n}": m_mom[n]["C"], f"F1 test {n}": round(m_mom[n]["F1"], 3)}
    log.info("Chequeo contra el notebook: %s", chequeo)
    if not args.desde_pipeline and chequeo != DEL_NOTEBOOK:
        raise SystemExit(f"La app no coincide con el notebook.\n  app:      {chequeo}\n  notebook: {DEL_NOTEBOOK}")

    # ── Dónde se equivoca y en qué se apoya (Secciones 4 y 6) ──
    cm = confusion_matrix(yb_te, pred_te, labels=range(K))
    p_b, r_b, f_b, s_b = precision_recall_fscore_support(yb_te, pred_te, labels=range(K), zero_division=0)
    nombres = final[:-1].get_feature_names_out()
    coef = pd.DataFrame(final[-1].coef_, index=BANDAS, columns=nombres)
    Z_te = final["derivar"].transform(X10_te)
    pi = permutation_importance(final[1:], Z_te, yb_te, scoring="f1_macro", n_repeats=10, random_state=SEMILLA,
                                n_jobs=-1)
    importancia = pd.Series(pi.importances_mean, index=Z_te.columns).sort_values(ascending=False)

    # El Ridge de la E3, para el «qué cambió» (Sección 7 del notebook)
    ridge = armar(Ridge(alpha=100)).fit(X10, y10)
    pr = ridge.predict(X10_te)
    mae_ridge, r2_ridge = mean_absolute_error(y10_te, pr), r2_score(y10_te, pr)

    # ── Las predicciones para explorar: cada partida, con un modelo que no la vio ──
    # Las de entrenamiento salen de la validación cruzada (los mismos cinco pedazos, C del final);
    # las del test, del modelo final.
    P_tr_mom = {n: cross_val_predict(armar(LogisticRegression(max_iter=3000, C=m_mom[n]["C"]), minuto=m), Xm, yb,
                                     cv=cv, method="predict_proba", n_jobs=-1)
                for n, m in MOMENTOS.items()}

    # ─────────────────────────────────────────────────────────────────────
    # Los números de la página
    # ─────────────────────────────────────────────────────────────────────
    minutos_df = df["game_duration_s"] / 60
    banda_df = pd.Series(np.array(BANDAS)[banda_de(df["game_duration_s"])], index=df.index)
    en_15 = int(((df["game_duration_s"] >= 900) & (df["game_duration_s"] < 960)).sum())
    en_14 = int(((df["game_duration_s"] >= 840) & (df["game_duration_s"] < 900)).sum())
    parte_21_33 = minutos_df.between(21, 33, inclusive="left").mean()
    n_lt15 = int((df["game_duration_s"] < 900).sum())
    plataformas = df["match_id"].str.split("_").str[0]

    derivadas = armar(LogisticRegression())["derivar"].fit_transform(d10.drop(columns="game_duration_s"))
    derivadas_df = ColumnasDePartida().transform(df)  # sin el minuto: las 19.145, como en la Entrega 2
    numericas = [c for c in derivadas.columns if c != "plataforma"]
    corr = pd.DataFrame({
        "columna": numericas,
        "r": [derivadas[c].corr(d10["game_duration_s"]) for c in numericas]})
    corr["familia"] = np.where(corr["columna"].str.endswith("_m10"), "al minuto 10", "antes de jugar")
    corr["nombre"] = corr["columna"].map(legible)
    corr["abs_r"] = corr["r"].abs()
    r_elo_e2 = derivadas_df["elo_partida"].corr(df["game_duration_s"])
    mejor_antes = corr[corr.familia == "antes de jugar"].sort_values("abs_r", ascending=False).iloc[0]
    mejor_min = corr[corr.familia == "al minuto 10"].sort_values("abs_r", ascending=False).iloc[0]

    # ─────────────────────────────────────────────────────────────────────
    # Los gráficos
    # ─────────────────────────────────────────────────────────────────────
    specs = {}

    # Los datos: la duración de las 19.145 partidas, minuto a minuto, pintada por banda
    d1 = pd.DataFrame({"minutos": minutos_df.round(3), "banda": banda_df})
    bin1 = alt.Bin(step=1, extent=[5, 67])
    barras = alt.Chart(d1).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("minutos:Q", bin=bin1, title="duración de la partida (minutos)", axis=alt.Axis(values=list(range(5, 70, 5)))),
        y=alt.Y("count():Q", title="partidas"),
        color=alt.Color("banda:N", scale=ESCALA_BANDA, sort=BANDAS,
                        legend=alt.Legend(title="banda de 6 minutos", orient="top", direction="horizontal")),
        tooltip=[alt.Tooltip("minutos:Q", bin=bin1, title="minuto"), alt.Tooltip("banda:N", title="banda"),
                 alt.Tooltip("count():Q", title="partidas", format=",")])
    regla = alt.Chart(pd.DataFrame({"x": [15]})).mark_rule(color=CREMA, strokeDash=[4, 4]).encode(x="x:Q")
    nota = alt.Chart(pd.DataFrame({"x": [15], "t": ["min 15: el «ff»"]})) \
        .mark_text(align="left", baseline="top", dx=6, color=CREMA, fontSize=12.5, fontWeight=600) \
        .encode(x="x:Q", y=alt.value(8), text="t:N")
    # Antes del 15: las partidas que pueden terminar antes porque alguien se fue y la rendición se habilitó antes
    zona15 = alt.Chart(pd.DataFrame({"a": [5], "b": [15]}))
    franja15 = zona15.mark_rect(color=CREMA, opacity=0.06).encode(x="a:Q", x2="b:Q")
    nota15 = alt.Chart(pd.DataFrame({"x": [5.4], "t": [f"antes del 15:\n{num(n_lt15)} partidas ({pct(n_lt15 / len(df))})\n"
                                                         "si alguien se va,\nla rendición se\nhabilita antes"]})) \
        .mark_text(align="left", baseline="top", lineBreak="\n", color=CREMA, fontSize=11.5, lineHeight=15) \
        .encode(x="x:Q", y=alt.value(8), text="t:N")
    specs["g-datos"] = (franja15 + barras + regla + nota + nota15).properties(
        width=820, height=300,
        title=alt.Title(f"Cuánto duraron las {num(len(df))} partidas",
                        subtitle=["Cada barra es un minuto de duración; el color, la banda de 6 minutos en la que cae (más oscuro, más larga).",
                                  "Del minuto 14 al 15 terminan " + num(en_14) + " partidas; del 15 al 16, " + num(en_15) + "."])).to_dict()

    # Lo que encontramos: la correlación de cada columna derivada con la duración
    top = pd.concat([corr[corr.familia == "antes de jugar"].nlargest(8, "abs_r"),
                     corr[corr.familia == "al minuto 10"].nlargest(8, "abs_r")]).sort_values("abs_r", ascending=False)
    top["r_txt"] = top["r"].map(lambda v: num(v, 3))
    zona = alt.Chart(pd.DataFrame({"a": [0], "b": [0.2], "t": ["zona roja del semáforo (|r| < 0,2)"]}))
    franja = zona.mark_rect(color="#B5402C", opacity=0.13).encode(x="a:Q", x2="b:Q")
    franja_txt = zona.mark_text(align="left", baseline="bottom", dx=4, dy=-4, color="#E08A7A", fontSize=11.5) \
        .encode(x="a:Q", y=alt.value(0), text="t:N")
    barras_r = alt.Chart(top).mark_bar(cornerRadiusEnd=3, height=14).encode(
        x=alt.X("abs_r:Q", title="|correlación de Pearson con la duración|", scale=alt.Scale(domain=[0, 0.35])),
        y=alt.Y("nombre:N", sort=list(top["nombre"]), title=None, axis=alt.Axis(labelLimit=260)),
        color=alt.Color("familia:N", scale=alt.Scale(domain=["antes de jugar", "al minuto 10"], range=[PIZARRA, HEXTECH]),
                        legend=alt.Legend(title="lo que se sabe", orient="bottom")),
        tooltip=[alt.Tooltip("nombre:N", title="columna"), alt.Tooltip("columna:N", title="en el código"),
                 alt.Tooltip("r_txt:N", title="Pearson"), alt.Tooltip("familia:N", title="cuándo se sabe")])
    texto_r = barras_r.mark_text(align="left", dx=4, color=CREMA, fontSize=11.5).encode(text="r_txt:N", color=alt.value(CREMA))
    specs["g-hallazgo"] = (franja + franja_txt + barras_r + texto_r).properties(
        width=560, height=alt.Step(20),
        title=alt.Title("Las 8 columnas más asociadas a la duración, de cada lado",
                        subtitle=[f"Sobre las {num(len(d10))} partidas que llegan al minuto 10. El signo está en el tooltip:",
                                  "todas las fuertes son negativas (más diferencia, partida más corta)."])).to_dict()

    # ── Antes, a los 5 y a los 10: el mismo modelo, según cuándo se predice (Sección 9 del notebook) ──
    ORDEN_MOM = list(MOMENTOS)
    PISO_TXT = "piso (siempre la más común)"

    # El F1 macro del test, una barra por momento, con el piso como regla
    d_f1 = pd.DataFrame({"momento": ORDEN_MOM, "F1": [m_mom[n]["F1"] for n in ORDEN_MOM]})
    d_f1["F1_txt"] = d_f1["F1"].map(lambda v: num(v, 3))
    barras_f1 = alt.Chart(d_f1).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, width=70).encode(
        x=alt.X("momento:N", sort=ORDEN_MOM, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13)),
        y=alt.Y("F1:Q", title="F1 macro en el test (de 0 a 1)", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("momento:N", scale=ESCALA_MOMENTO, legend=None),
        tooltip=[alt.Tooltip("momento:N", title="cuándo predice"), alt.Tooltip("F1_txt:N", title="F1 macro")])
    txt_f1 = barras_f1.mark_text(dy=-10, fontSize=14, fontWeight=600, color=CREMA).encode(
        text="F1_txt:N", color=alt.value(CREMA))
    piso_f1 = alt.Chart(pd.DataFrame({"y": [m_piso["F1"]], "t": [f"piso: {num(m_piso['F1'], 3)}"]}))
    regla_f1 = piso_f1.mark_rule(color=PISO_COLOR, strokeDash=[5, 4], strokeWidth=2).encode(y="y:Q")
    regla_f1_txt = piso_f1.mark_text(align="center", dy=-7, color=GRIS, fontSize=12).encode(
        y="y:Q", x=alt.value(187), text="t:N")
    specs["g-f1"] = (barras_f1 + txt_f1 + regla_f1 + regla_f1_txt).properties(
        width=560, height=280,
        title=alt.Title("El F1 macro sube con cada minuto de partida, pero queda bajo",
                        subtitle=[f"La misma logística, entrenada con lo que se sabe en cada momento. Las mismas {num(len(te))} partidas del test.",
                                  "El F1 macro va de 0 a 1: el promedio, sin pesos, del F1 de cada una de las 7 bandas."])).to_dict()

    # Las otras métricas, con el piso al lado
    filas_met = []
    nombres_met = {"accuracy": "banda exacta (accuracy)", "±1": "a una banda o menos (±6 min)",
                   "pasa": "la ventana de 12 min acierta"}
    for quien, mm in [(PISO_TXT, m_piso | {"pasa": pasa_piso.mean()})] + [(n, m_mom[n]) for n in ORDEN_MOM]:
        for k, nombre in nombres_met.items():
            filas_met.append({"quien": quien, "metrica": nombre, "valor": mm[k], "txt": pct(mm[k], 1)})
    d_met = pd.DataFrame(filas_met)
    orden_quien = [PISO_TXT, *ORDEN_MOM]
    esc_quien = alt.Scale(domain=orden_quien, range=[PISO_COLOR, *COLOR_MOMENTO.values()])
    base_met = alt.Chart().encode(
        x=alt.X("quien:N", sort=orden_quien, title=None, axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("valor:Q", title="partidas del test", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("quien:N", scale=esc_quien, sort=orden_quien,
                        legend=alt.Legend(title=None, orient="top", direction="horizontal", labelLimit=260)),
        tooltip=[alt.Tooltip("quien:N", title="modelo"), alt.Tooltip("metrica:N", title="métrica"),
                 alt.Tooltip("txt:N", title="valor")])
    capa_met = alt.layer(base_met.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width=34),
                         base_met.mark_text(dy=-8, fontSize=11.5, color=CREMA).encode(
                             text="txt:N", color=alt.value(CREMA)), data=d_met)
    specs["g-metricas"] = capa_met.properties(width=230, height=250).facet(
        column=alt.Column("metrica:N", sort=list(nombres_met.values()), title=None,
                          header=alt.Header(labelFontSize=13, labelFontWeight=600)),
        spacing=24).properties(
        title=alt.Title("Las otras métricas casi no se mueven: todos rondan al piso",
                        subtitle="Banda exacta, a una banda de distancia y la ventana de 12 minutos que vería el jugador.")).to_dict()

    # Qué contesta cada modelo, contra dónde terminaron de verdad
    real_cuenta = np.bincount(real_te, minlength=K)
    filas_c = []
    for n in ORDEN_MOM:
        dijo = np.bincount(P_mom[n].argmax(axis=1), minlength=K)
        filas_c += [{"momento": n, "banda": BANDAS[k], "contesta": int(dijo[k]), "real": int(real_cuenta[k])}
                    for k in range(K)]
    d_c = pd.DataFrame(filas_c)
    base_c = alt.Chart().encode(x=alt.X("banda:N", sort=BANDAS, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=11)))
    barras_c = base_c.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width=22).encode(
        y=alt.Y("contesta:Q", title="partidas del test"),
        color=alt.Color("banda:N", scale=ESCALA_BANDA, sort=BANDAS, legend=None),
        tooltip=[alt.Tooltip("momento:N", title="modelo"), alt.Tooltip("banda:N"),
                 alt.Tooltip("contesta:Q", title="veces que la contesta", format=","),
                 alt.Tooltip("real:Q", title="partidas que terminan ahí", format=",")])
    marca_real = base_c.mark_tick(color=CREMA, thickness=3, size=30).encode(
        y="real:Q", tooltip=[alt.Tooltip("banda:N"), alt.Tooltip("real:Q", title="partidas que terminan ahí", format=",")])
    specs["g-contesta"] = alt.layer(barras_c, marca_real, data=d_c).properties(width=250, height=230).facet(
        column=alt.Column("momento:N", sort=ORDEN_MOM, title=None,
                          header=alt.Header(labelFontSize=13, labelFontWeight=600)), spacing=22).properties(
        title=alt.Title("Los tres contestan casi siempre el centro",
                        subtitle=["Las barras: cuántas veces contesta cada banda cada modelo. La raya clara: cuántas partidas",
                                  "terminan de verdad en esa banda. Si el modelo acertara, la barra llegaría a la raya."])).to_dict()

    # La matriz de confusión, normalizada por fila, una por momento
    filas_m = []
    for n in ORDEN_MOM:
        cmn_n = cm_mom[n] / cm_mom[n].sum(axis=1, keepdims=True)
        filas_m += [{"momento": n, "real": BANDAS[i], "dijo": BANDAS[j], "p": float(cmn_n[i, j]),
                     "n": int(cm_mom[n][i, j]), "total": int(cm_mom[n][i].sum())} for i in range(K) for j in range(K)]
    d_m = pd.DataFrame(filas_m)
    d_m["txt"] = d_m["p"].map(lambda v: f"{round(100 * v)}" if v >= 0.005 else "")
    base_m = alt.Chart().encode(
        x=alt.X("dijo:N", sort=BANDAS, title="banda que dijo el modelo", axis=alt.Axis(labelAngle=-45, labelFontSize=11)),
        y=alt.Y("real:N", sort=BANDAS, title="banda real", axis=alt.Axis(labelFontSize=11)))
    celdas = base_m.mark_rect(stroke=PANEL, strokeWidth=2).encode(
        color=alt.Color("p:Q", scale=alt.Scale(domain=[0, 1], range=["#13213A", ORO]),
                        legend=alt.Legend(title="% de la fila", format="%", orient="right", gradientLength=160)),
        tooltip=[alt.Tooltip("momento:N", title="modelo"), alt.Tooltip("real:N", title="banda real"),
                 alt.Tooltip("dijo:N", title="dijo"), alt.Tooltip("p:Q", title="% de la fila", format=".1%"),
                 alt.Tooltip("n:Q", title="partidas", format=","), alt.Tooltip("total:Q", title="de", format=",")])
    num_m = base_m.mark_text(fontSize=10.5).encode(
        text="txt:N", color=alt.condition("datum.p > 0.5", alt.value(PANEL), alt.value(CREMA)))
    specs["g-matriz"] = alt.layer(celdas, num_m, data=d_m).properties(width=alt.Step(30), height=alt.Step(30)).facet(
        column=alt.Column("momento:N", sort=ORDEN_MOM, title=None,
                          header=alt.Header(labelFontSize=13, labelFontWeight=600)), spacing=18).properties(
        title=alt.Title("De cada banda real, a dónde la manda cada modelo",
                        subtitle=["Cada fila suma 100 %; el número es el porcentaje. Antes de jugar, casi todo va a 27-33;",
                                  "al minuto 10, las partidas cortas empiezan a ir a 15-21 y 21-27."])).to_dict()

    # Lo predicho contra lo real: cada banda predicha pasada a su minuto típico, con la recta y = x
    rng = np.random.default_rng(SEMILLA)
    sacudida = rng.uniform(-1.2, 1.2, len(te))  # separa los puntos que caen en la misma banda; no es parte del modelo
    real_min = (y10_te / 60).to_numpy()
    paneles = []
    for n in ORDEN_MOM:
        pr_n = minuto_tipico[P_mom[n].argmax(axis=1)]
        d_p = pd.DataFrame({"real": real_min.round(2), "predicho": (pr_n + sacudida).round(2), "tipico": pr_n.round(1),
                            "banda": np.array(BANDAS)[P_mom[n].argmax(axis=1)], "momento": n})
        diag_p = alt.Chart(pd.DataFrame({"x": [10, 60], "y": [10, 60]})).mark_line(
            color=GRIS, strokeDash=[5, 5]).encode(x="x:Q", y="y:Q")
        puntos_p = alt.Chart(d_p).mark_circle(size=10, opacity=0.35, color=COLOR_MOMENTO[n]).encode(
            x=alt.X("real:Q", title="duración real (min)", scale=alt.Scale(domain=[10, 60], clamp=True)),
            y=alt.Y("predicho:Q", title="lo que predice (min)" if n == ORDEN_MOM[0] else None,
                    scale=alt.Scale(domain=[10, 60], clamp=True)),
            tooltip=[alt.Tooltip("real:Q", title="duró (min)", format=".1f"), alt.Tooltip("banda:N", title="dijo"),
                     alt.Tooltip("tipico:Q", title="minuto típico de esa banda", format=".1f")])
        paneles.append((diag_p + puntos_p).properties(width=250, height=250, title=alt.Title(n, fontSize=13.5)))
    specs["g-predicho"] = alt.hconcat(*paneles, spacing=20).properties(
        title=alt.Title("Si acertara, los puntos caerían sobre la diagonal: quedan en franjas planas",
                        subtitle=["Cada punto es una partida del test: en x, lo que duró; en y, el minuto típico (la mediana) de la banda",
                                  "que dijo el modelo, con una sacudida de ±1,2 min para que no se tapen. La diagonal es y = x."])).to_dict()

    # El modelo: la calibración de la ventana de 12 minutos en el test, un panel por momento
    cortes = np.linspace(0, 1, 11)
    esc_cal = alt.Scale(domain=[0.3, 0.9], zero=False, clamp=True)
    escala_quien = alt.Scale(domain=["el modelo", "el piso (dice siempre lo mismo)"], range=[ORO, PISO_COLOR])
    paneles_cal = []
    for n in ORDEN_MOM:
        ini_n, dice_n = ventana_de(P_mom[n])
        pasa_n = (real_te >= ini_n) & (real_te <= ini_n + VENTANA - 1)
        cal = pd.DataFrame({"dice": dice_n, "pasa": pasa_n}).groupby(pd.cut(dice_n, cortes), observed=True) \
            .agg(dice=("dice", "mean"), pasa=("pasa", "mean"), partidas=("pasa", "size")).reset_index(drop=True)
        cal = cal[cal["partidas"] >= 20].assign(quien="el modelo")
        cal_piso = pd.DataFrame({"dice": [dice_piso.mean()], "pasa": [pasa_piso.mean()], "partidas": [len(dice_piso)],
                                 "quien": ["el piso (dice siempre lo mismo)"]})
        cal_todo = pd.concat([cal, cal_piso])
        cal_todo["dice_txt"], cal_todo["pasa_txt"] = cal_todo["dice"].map(pct), cal_todo["pasa"].map(pct)
        diag = alt.Chart(pd.DataFrame({"x": [0.3, 0.9], "y": [0.3, 0.9]})).mark_line(color=GRIS, strokeDash=[5, 5]) \
            .encode(x=alt.X("x:Q", scale=esc_cal), y=alt.Y("y:Q", scale=esc_cal))
        base_cal = alt.Chart(cal_todo).encode(
            x=alt.X("dice:Q", title="probabilidad que le da a su ventana", scale=esc_cal,
                    axis=alt.Axis(format="%", values=[0.3, 0.5, 0.7, 0.9])),
            y=alt.Y("pasa:Q", title="frecuencia con que termina ahí" if n == ORDEN_MOM[0] else None, scale=esc_cal,
                    axis=alt.Axis(format="%")),
            color=alt.Color("quien:N", scale=escala_quien, legend=alt.Legend(title=None, orient="top", labelLimit=320)),
            tooltip=[alt.Tooltip("quien:N", title=" "), alt.Tooltip("dice_txt:N", title="dice"),
                     alt.Tooltip("pasa_txt:N", title="pasa"), alt.Tooltip("partidas:Q", title="partidas", format=",")])
        linea_cal = base_cal.transform_filter("datum.quien == 'el modelo'").mark_line(strokeWidth=2.5)
        puntos_cal = base_cal.mark_point(filled=True, opacity=1).encode(
            size=alt.Size("partidas:Q", scale=alt.Scale(range=[30, 400]), legend=None))
        resumen_cal = alt.Chart(pd.DataFrame({"t": [f"dice {pct(dice_n.mean(), 1)} · pasa {pct(pasa_n.mean(), 1)}"]})) \
            .mark_text(align="left", color=CREMA, fontSize=12).encode(x=alt.value(4), y=alt.value(10), text="t:N")
        paneles_cal.append((diag + linea_cal + puntos_cal + resumen_cal).properties(
            width=250, height=250, title=alt.Title(n, fontSize=13.5)))
    specs["g-modelo"] = alt.hconcat(*paneles_cal, spacing=20).properties(
        title=alt.Title("Cuando dice «p %», pasa más o menos el p % de las veces, en los tres momentos",
                        subtitle=[f"Las {num(len(te))} partidas del test, agrupadas por la probabilidad que el modelo le dio a su ventana",
                                  "de 12 minutos (tramos de 10 puntos con 20 partidas o más). La diagonal es la calibración perfecta."])).to_dict()

    # ── Explorá: cada partida, con lo que dijo un modelo que no la vio, para los tres momentos ──
    # Las de entrenamiento salen de la validación cruzada; las del test, del modelo de cada momento
    idx = list(tr) + list(te)
    real_todo = np.concatenate([yb.to_numpy(), real_te])
    ex = pd.DataFrame({
        "match_id": d10.loc[idx, "match_id"].to_numpy(),
        "servidor": d10.loc[idx, "match_id"].str.split("_").str[0].to_numpy(),
        "grupo": grupo.loc[idx].astype(str).to_numpy(),
        "elo": derivadas.loc[idx, "elo_partida"].round().astype(int).to_numpy(),
        "duracion": (d10.loc[idx, "game_duration_s"] / 60).round(1).to_numpy(),
        "banda_real": np.array(BANDAS)[real_todo], "bi": real_todo,
        "cj": [0] * len(tr) + [1] * len(te)})  # 1 = test
    for m in METRICAS_MINUTO:
        v = d10.loc[idx, f"dif_{m}_m10"]
        ex[f"dif_{m}"] = v.round(2).to_numpy() if m == "level" else v.round().astype(int).to_numpy()
    # Para que la página no pese de más, las 7 probabilidades de cada modelo van juntas, en milésimos:
    # «12,30,...». La ventana, su probabilidad y si acertó se calculan adentro del gráfico
    for n in ORDEN_MOM:
        c = CORTO[n]
        P_todo = np.vstack([P_tr_mom[n], P_mom[n]])
        ex[f"vi_{c}"] = ventana_de(P_todo)[0]
        ex[f"pp_{c}"] = [",".join(map(str, fila)) for fila in np.rint(P_todo * 1000).astype(int)]
    dice_m10 = ventana_de(np.vstack([P_tr_mom["minuto 10"], P_mom["minuto 10"]]))[1]
    arriba70 = {}
    for n in ORDEN_MOM:
        P_mil = np.rint(np.vstack([P_tr_mom[n], P_mom[n]]) * 1000) / 1000
        arriba70[n] = int((ventana_de(P_mil)[1] >= 0.70 - 1e-9).sum())
    ejemplo_click = ex.loc[ex["cj"] == 1].assign(d=dice_m10[ex["cj"].to_numpy() == 1]).sort_values("d")         .iloc[len(te) // 2]["match_id"]
    textos_ventana = json.dumps([texto_ventana(i, largo=False) for i in range(K - 1)], ensure_ascii=False)

    # El eje x lo elige el usuario: las 7 diferencias al minuto 10 y el elo medio
    EJES = {f"dif_{m}": f"Diferencia de {NOMBRES[m]} al minuto 10" for m in METRICAS_MINUTO} | {"elo": "Elo medio de la partida"}
    titulo_eje = " : ".join(f"eje == '{k}' ? '{v.lower() if k != 'elo' else v}'" for k, v in EJES.items()) + " : ''"
    p_eje = alt.param(name="eje", value="dif_gold", bind=alt.binding_select(
        options=list(EJES), labels=list(EJES.values()), name="Eje x ", element="#c-eje"))
    p_mod = alt.param(name="modelo", value="m10", bind=alt.binding_select(
        options=[CORTO[n] for n in ORDEN_MOM], labels=["Antes de jugar", "Al minuto 5", "Al minuto 10"],
        name="Lo que dijo el modelo ", element="#c-modelo"))
    # Las columnas del modelo elegido, con nombres fijos para el resto de los gráficos
    paso1 = dict(x="datum[eje]", vi="datum['vi_' + modelo]", pp="split(datum['pp_' + modelo], ',')",
                 conjunto="datum.cj == 1 ? 'test' : 'validación cruzada'")
    paso2 = dict(p_ventana="(toNumber(datum.pp[datum.vi]) + toNumber(datum.pp[datum.vi + 1])) / 1000",
                 ventana=f"{textos_ventana}[datum.vi]",
                 acierta="datum.bi >= datum.vi && datum.bi <= datum.vi + 1 ? 1 : 0")
    paso3 = dict(acierta_txt="datum.acierta == 1 ? 'sí' : 'no'")

    def del_modelo(chart):
        """Las columnas del modelo elegido, con nombres fijos para el resto de los gráficos."""
        return chart.transform_calculate(**paso1).transform_calculate(**paso2).transform_calculate(**paso3)

    srv = sorted(ex["servidor"].unique())
    p_srv = alt.param(name="srv", value=None, bind=alt.binding_select(options=[None, *srv], labels=["Todos", *srv],
                                                                      name="Servidor ", element="#c-srv"))
    p_elo = alt.param(name="elo", value=None, bind=alt.binding_radio(options=[None, *GRUPOS], labels=["Todos", *GRUPOS],
                                                                     name="Elo ", element="#c-elo"))
    p_conf = alt.param(name="conf", value=0.4, bind=alt.binding_range(min=0.4, max=0.85, step=0.01,
                                                                       name="Probabilidad mínima de la ventana (0,40 = 40 %) ", element="#c-conf"))
    sel_banda = alt.selection_point(name="leyenda", fields=["banda_real"], bind="legend")
    # empty=False: un clic en el vacío deja la selección vacía, y entonces no se resalta ninguna partida
    sel_click = alt.selection_point(name="clic", fields=["match_id"], on="click", value=[{"match_id": ejemplo_click}],
                                    clear=False, empty=False)
    filtro = "(srv == null || datum.servidor == srv) && (elo == null || datum.grupo == elo) && datum.p_ventana >= conf"
    tips = [alt.Tooltip("match_id:N", title="partida"), alt.Tooltip("servidor:N"), alt.Tooltip("grupo:N", title="elo"),
            alt.Tooltip("duracion:Q", title="duró (min)", format=".1f"), alt.Tooltip("banda_real:N", title="banda real"),
            alt.Tooltip("ventana:N", title="el modelo dijo"), alt.Tooltip("p_ventana:Q", title="con probabilidad", format=".0%"),
            alt.Tooltip("acierta_txt:N", title="¿acertó?"), alt.Tooltip("x:Q", title="valor en el eje x", format=",~f"),
            alt.Tooltip("dif_gold:Q", title="dif. de oro al min 10", format=","),
            alt.Tooltip("dif_kills:Q", title="dif. de asesinatos al min 10"), alt.Tooltip("conjunto:N", title="predicha en")]
    nube = del_modelo(alt.Chart(ex)).mark_circle(size=14).encode(
        x=alt.X("x:Q", title=" ", axis=alt.Axis(format=",~f", titlePadding=14), scale=alt.Scale(zero=False)),
        y=alt.Y("duracion:Q", title="duración real (minutos)", scale=alt.Scale(domain=[5, 67])),
        color=alt.Color("banda_real:N", scale=ESCALA_BANDA, sort=BANDAS,
                        legend=alt.Legend(title="banda real (clic para resaltar)", orient="top", columns=7, symbolOpacity=1)),
        opacity=alt.condition(sel_banda, alt.value(0.6), alt.value(0.04)),
        tooltip=tips).add_params(p_eje, p_mod, p_srv, p_elo, p_conf, sel_banda, sel_click).transform_filter(filtro).properties(
        width=470, height=420, title=alt.Title("Las partidas que llegan al minuto 10",
                                               subtitle="Pasá el mouse para ver qué dijo el modelo; hacé clic para abrir una."))
    # El título del eje x cambia con el selector: va como texto, debajo del eje
    eje_txt = alt.Chart(pd.DataFrame({"a": [0]})).transform_calculate(t=titulo_eje).mark_text(
        color=GRIS, fontSize=12.5, baseline="bottom").encode(x=alt.value(235), y=alt.value(420 + 46), text="t:N")
    elegido = alt.Chart(ex).transform_calculate(x="datum[eje]").mark_circle(
        size=140, fill=None, stroke=ORO, strokeWidth=2.5).encode(x="x:Q", y="duracion:Q").transform_filter(sel_click)
    cuenta = del_modelo(alt.Chart(ex)).transform_filter(filtro).mark_bar(
        cornerRadiusEnd=3, height=16).encode(
        y=alt.Y("banda_real:N", sort=BANDAS, title=None, scale=alt.Scale(domain=BANDAS)),
        x=alt.X("count():Q", title="partidas"),
        color=alt.Color("banda_real:N", scale=ESCALA_BANDA, legend=None),
        tooltip=[alt.Tooltip("banda_real:N", title="banda real"), alt.Tooltip("count():Q", title="partidas", format=",")]) \
        .properties(width=250, height=alt.Step(20), title=alt.Title("Dónde terminaron", subtitle="las partidas que quedan con los filtros"))
    acierto = del_modelo(alt.Chart(ex)).transform_filter(filtro).transform_aggregate(
        n="count()", a="mean(acierta)").transform_calculate(
        t="format(datum.n, ',') + ' partidas · acertó la ventana en el ' + format(datum.a, '.0%')").mark_text(
        align="left", color=ORO, fontSize=13, fontWeight=600).encode(x=alt.value(0), y=alt.value(8), text="t:N") \
        .properties(width=250, height=18)
    detalle = del_modelo(alt.Chart(ex).transform_filter(sel_click)).transform_calculate(
        **{f"q{k}": f"toNumber(datum.pp[{k}]) / 1000" for k in range(K)}).transform_fold(
        [f"q{k}" for k in range(K)], as_=["clave", "p"]).transform_calculate(
        k="toNumber(replace(datum.clave, 'q', ''))", banda=f"{json.dumps(BANDAS)}[toNumber(replace(datum.clave, 'q', ''))]",
        en_ventana="datum.k >= datum.vi && datum.k <= datum.vi + 1",
        titulo="datum.match_id + ' · duró ' + format(datum.duracion, '.1f') + ' min'")
    det_barras = detalle.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width=24).encode(
        x=alt.X("banda:N", sort=BANDAS, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=11)),
        y=alt.Y("p:Q", title="probabilidad", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 0.8])),
        color=alt.Color("banda:N", scale=ESCALA_BANDA, legend=None),
        tooltip=[alt.Tooltip("banda:N"), alt.Tooltip("p:Q", title="probabilidad", format=".1%")])
    # La ventana que se le mostraría al jugador: un borde dorado, en una capa aparte
    det_borde = detalle.transform_filter("datum.en_ventana").mark_bar(
        filled=False, stroke=ORO, strokeWidth=2.5, width=28).encode(x=alt.X("banda:N", sort=BANDAS), y="p:Q")
    det_txt = detalle.mark_text(dy=-8, fontSize=11, color=CREMA).encode(
        x=alt.X("banda:N", sort=BANDAS), y="p:Q", text=alt.Text("p:Q", format=".0%"))
    det_titulo = detalle.transform_filter("datum.k == 0").mark_text(align="left", fontSize=12.5, color=CREMA,
                                                                     fontWeight=600).encode(
        x=alt.value(0), y=alt.value(-14), text="titulo:N")
    det = (det_barras + det_borde + det_txt + det_titulo).properties(
        width=250, height=170, title=alt.Title("La partida elegida", subtitle="probabilidad de cada banda; en dorado, la ventana"))
    specs["g-explora"] = alt.hconcat(nube + elegido + eje_txt, alt.vconcat(acierto, cuenta, det, spacing=18), spacing=28) \
        .resolve_scale(color="shared").to_dict()

    # ── Probá el modelo: la fórmula de la logística, adentro del gráfico ──
    prep = final.named_steps["preparar"]
    num_cols = list(prep.transformers_[0][2])
    escalar = prep.named_transformers_["numericas"].named_steps["escalar"]
    media, desvio = dict(zip(num_cols, escalar.mean_, strict=True)), dict(zip(num_cols, escalar.scale_, strict=True))
    W, b0 = final[-1].coef_, final[-1].intercept_
    deslizadores = ["elo_partida"] + [f"dif_{m}_m10" for m in METRICAS_MINUTO] + [f"suma_{m}_m10" for m in METRICAS_MINUTO]
    j_desl = [list(nombres).index(c) for c in deslizadores]
    j_plat = {c.removeprefix("plataforma_"): list(nombres).index(c) for c in nombres if c.startswith("plataforma_")}
    j_fijas = [j for j, c in enumerate(nombres) if c not in deslizadores and not c.startswith("plataforma_")]
    der_tr = final["derivar"].transform(X10)
    pasos = {"elo_partida": 10, "gold": 100, "xp": 100, "cs": 1, "level": 0.1, "kills": 1, "towers": 1,
             "elite_monsters": 1}

    def paso(c):
        return pasos["elo_partida"] if c == "elo_partida" else pasos[c.removeprefix("dif_").removeprefix("suma_").removesuffix("_m10")]

    rango = {c: (float(np.floor(der_tr[c].min() / paso(c)) * paso(c)), float(np.ceil(der_tr[c].max() / paso(c)) * paso(c)))
             for c in deslizadores}

    # Las partidas de ejemplo: dos del test por banda (una sola en <15), al azar con la semilla
    Zfull_te = pd.DataFrame(prep.transform(Z_te), index=te, columns=nombres)
    der_te = Z_te
    ejemplos_idx = []
    for k in [3, 1, 5, 2, 4, 6, 0]:  # la primera, una partida típica; la de <15, al final
        cand = yb_te[(yb_te == k) & der_te[deslizadores].notna().all(axis=1)]
        ejemplos_idx += list(cand.sample(1 if k == 0 else 2, random_state=SEMILLA).index)
    filas_proba, ejemplos = [], []
    for n_ej, i in enumerate(ejemplos_idx):
        z = Zfull_te.loc[i].to_numpy()
        base = b0 + W[:, j_fijas] @ z[j_fijas]
        # Verificación: la fórmula de la página, con los valores reales de la partida, da lo mismo que sklearn
        logit = base.copy()
        for j, c in zip(j_desl, deslizadores, strict=True):
            logit += W[:, j] * (der_te.loc[i, c] - media[c]) / desvio[c]
        plat_i = der_te.loc[i, "plataforma"]
        logit += W[:, j_plat[plat_i]]
        p_formula = np.exp(logit - logit.max()) / np.exp(logit - logit.max()).sum()
        p_sk = final.predict_proba(X10_te.loc[[i]])[0]
        assert np.allclose(p_formula, p_sk, atol=1e-9), f"La fórmula de la página no coincide con sklearn en {i}"
        pid = f"e{n_ej}"
        for k in range(K):
            fila = {"partida": pid, "k": k, "banda": BANDAS[k], "base": round(float(base[k]), 10),
                    "texto": texto_ventana(k) if k < K - 1 else ""}
            fila |= {f"w_{c}": round(float(W[k, j] / desvio[c]), 10) for j, c in zip(j_desl, deslizadores, strict=True)}
            fila |= {f"wp_{p}": round(float(W[k, j]), 10) for p, j in j_plat.items()}
            filas_proba.append(fila)
        fila_df = d10.loc[i]
        ejemplos.append({
            "id": pid, "match_id": fila_df["match_id"], "servidor": plat_i,
            "grupo": str(grupo.loc[i]), "duracion": round(float(fila_df["game_duration_s"]) / 60, 1),
            "banda": BANDAS[int(yb_te.loc[i])],
            "valores": {c: round(float(der_te.loc[i, c]), 2) for c in deslizadores},
            "azul": [fila_df[f"t1_{p}_champ_name"] for p in POS], "rojo": [fila_df[f"t2_{p}_champ_name"] for p in POS],
            "proba": [round(float(v), 4) for v in p_sk]})
    centrado = " + ".join(f"datum.w_{c} * ({c} - {float(media[c])!r})" for c in deslizadores)
    z_expr = f"datum.base + {centrado} + datum['wp_' + srv_p]"
    params_probar = [alt.param(name="partida", value=ejemplos[0]["id"]),
                     alt.param(name="srv_p", value=ejemplos[0]["servidor"],
                               bind=alt.binding_select(options=sorted(j_plat), name="Servidor ", element="#s-srv_p"))]
    etiquetas = {"elo_partida": "Elo medio de la partida"}
    for m in METRICAS_MINUTO:
        etiquetas[f"dif_{m}_m10"] = f"Diferencia de {NOMBRES[m]}"
        etiquetas[f"suma_{m}_m10"] = f"Total de {NOMBRES[m]}"
    for c in deslizadores:
        lo, hi = rango[c]
        params_probar.append(alt.param(name=c, value=ejemplos[0]["valores"][c], bind=alt.binding_range(
            min=lo, max=hi, step=paso(c), name=etiquetas[c] + " ", element=f"#s-{c}")))
    proba_base = alt.Chart(pd.DataFrame(filas_proba)).transform_filter("datum.partida == partida").transform_calculate(
        z=z_expr).transform_joinaggregate(zmax="max(z)").transform_calculate(e="exp(datum.z - datum.zmax)") \
        .transform_joinaggregate(suma="sum(e)").transform_calculate(p="datum.e / datum.suma") \
        .transform_window(p_sig="lead(p)", sort=[alt.SortField("k")]) \
        .transform_calculate(par=f"datum.k == {K - 1} ? -1 : datum.p + datum.p_sig") \
        .transform_joinaggregate(parmax="max(par)").transform_calculate(inicio="datum.par == datum.parmax ? 1 : 0") \
        .transform_window(inicio_prev="lag(inicio)", sort=[alt.SortField("k")]) \
        .transform_calculate(en_ventana="datum.inicio == 1 || datum.inicio_prev == 1")
    pb_barras = proba_base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, width=40).encode(
        x=alt.X("banda:N", sort=BANDAS, title="banda de duración (minutos)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("p:Q", title="probabilidad según el modelo", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("banda:N", scale=ESCALA_BANDA, legend=None),
        tooltip=[alt.Tooltip("banda:N"), alt.Tooltip("p:Q", title="probabilidad", format=".1%")])
    pb_borde = proba_base.transform_filter("datum.en_ventana").mark_bar(
        filled=False, stroke=ORO, strokeWidth=3, width=46).encode(x=alt.X("banda:N", sort=BANDAS), y="p:Q")
    pb_txt = proba_base.mark_text(dy=-9, fontSize=13, color=CREMA).encode(
        x=alt.X("banda:N", sort=BANDAS), y="p:Q", text=alt.Text("p:Q", format=".0%"))
    pb_frase = proba_base.transform_filter("datum.inicio == 1").transform_calculate(
        t="format(datum.par, '.0%') + ' de que termine ' + datum.texto").mark_text(
        align="left", fontSize=22, fontWeight=700, color=ORO).encode(x=alt.value(0), y=alt.value(-26), text="t:N")
    specs["g-probar"] = (pb_barras + pb_borde + pb_txt + pb_frase).add_params(*params_probar).properties(
        width=430, height=330, padding={"top": 44, "left": 10, "right": 10, "bottom": 10}).to_dict()

    # ─────────────────────────────────────────────────────────────────────
    # Las tablas de los «Cómo lo sabemos»
    # ─────────────────────────────────────────────────────────────────────
    def fila_cv(nombre, r, i=None):
        g = (lambda m: r[f"mean_test_{m}"][i]) if i is not None else (lambda m: r[f"test_{m}"].mean())
        s = (lambda m: r[f"std_test_{m}"][i]) if i is not None else (lambda m: r[f"test_{m}"].std())
        return [nombre, f"{num(g('F1 macro'), 3)} ± {num(s('F1 macro'), 3)}", pct(g("accuracy")), pct(g("±1 banda"))]

    comp = [fila_cv("Piso (dice siempre la banda más frecuente)", piso_cv)]
    for n, bq in busquedas.items():
        comp.append(fila_cv(f"Logística {n} (C = {num(bq.best_params_['modelo__C'], 3).rstrip('0').rstrip(',')})",
                            bq.cv_results_, bq.best_index_))
    t_comp = tabla(["Modelo", "F1 macro (media ± desvío)", "Accuracy", "±1 banda"], comp)

    grilla = []
    for n, bq in busquedas.items():
        r = bq.cv_results_
        for i, c in enumerate(GRILLA_C):
            grilla.append([num(c, 3).rstrip("0").rstrip(","), n,
                           f"{num(r['mean_test_F1 macro'][i], 3)} ± {num(r['std_test_F1 macro'][i], 3)}",
                           pct(r["mean_test_accuracy"][i])])
    t_grilla = tabla(["C", "Pesos", "F1 macro", "Accuracy"], grilla)

    t_test = tabla(["", "El modelo (logística sin pesos)", "El piso"], [
        ["F1 macro", f"<b>{num(m_final['F1'], 3)}</b>", num(m_piso["F1"], 3)],
        ["Accuracy (banda exacta)", pct(m_final["accuracy"]), pct(m_piso["accuracy"])],
        ["A una banda o menos (±6 min)", pct(m_final["±1"]), pct(m_piso["±1"])],
        ["A menos de 3 minutos de lo real", pct(m_final["≤3"]), pct(m_piso["≤3"])],
        ["Error medio, en minutos", num(m_final["error medio"], 3), num(m_piso["error medio"], 3)],
        ["La ventana de 12 min: dice / pasa", f"{pct(dice_te.mean())} / {pct(pasa_te.mean())}",
         f"{pct(dice_piso.mean())} / {pct(pasa_piso.mean())}"]])

    t_bandas = tabla(["Banda", "Precisión", "Recall", "F1", "Partidas en el test", "Veces que la contesta"],
                     [[BANDAS[k], num(p_b[k], 2), num(r_b[k], 2), num(f_b[k], 2), num(s_b[k]), num(cm[:, k].sum())]
                      for k in range(K)])
    cmn = cm / cm.sum(axis=1, keepdims=True)
    t_cm = tabla(["Real \\ dijo", *BANDAS],
                 [[f"<b>{BANDAS[k]}</b>"] + [f'<span class="{"diag" if k == j else ""}">{pct(cmn[k, j], 0)}</span>'
                                             for j in range(K)] for k in range(K)], clase="chica")
    t_coef = tabla(["Columna", *BANDAS],
                   [[legible(c)] + [num(coef.loc[b, c], 2) for b in BANDAS] for c in ["elo_partida", "dif_gold_m10"]],
                   clase="chica")
    t_imp = tabla(["Columna", "Cuánto baja el F1 macro al desordenarla"],
                  [[legible(c) if c != "plataforma" else "servidor (plataforma)", num(v, 4)] for c, v in importancia.head(6).items()])
    t_res = tabla(["Partidas del test, por lo que dice", "Dice entre", "Acierta"],
                  [[t, f"{pct(lo, 0)} y {pct(hi, 0)}", pct(a)] for t, (lo, hi, a) in resolucion.items()])

    def c_txt(c):
        return num(c, 3).rstrip("0").rstrip(",")

    t_mom = tabla(["", "El piso", *[n.capitalize() for n in ORDEN_MOM]], [
        ["C elegido (validación cruzada)", "—", *[c_txt(m_mom[n]["C"]) for n in ORDEN_MOM]],
        ["F1 macro, validación cruzada", "—", *[f"{num(m_mom[n]['F1 cv'], 3)} ± {num(m_mom[n]['F1 cv desvío'], 3)}"
                                               for n in ORDEN_MOM]],
        ["<b>F1 macro, test</b>", num(m_piso["F1"], 3), *[f"<b>{num(m_mom[n]['F1'], 3)}</b>" for n in ORDEN_MOM]],
        ["Accuracy (banda exacta)", pct(m_piso["accuracy"]), *[pct(m_mom[n]["accuracy"]) for n in ORDEN_MOM]],
        ["A una banda o menos", pct(m_piso["±1"]), *[pct(m_mom[n]["±1"]) for n in ORDEN_MOM]],
        ["Error medio, en minutos", num(m_piso["error medio"], 2), *[num(m_mom[n]["error medio"], 2) for n in ORDEN_MOM]],
        ["La ventana de 12 min: dice / pasa", f"{pct(dice_piso.mean())} / {pct(pasa_piso.mean())}",
         *[f"{pct(m_mom[n]['dice'])} / {pct(m_mom[n]['pasa'])}" for n in ORDEN_MOM]],
        ["Bandas que llega a contestar", "1 de 7", *[f"{m_mom[n]['contesta']} de 7" for n in ORDEN_MOM]]])

    filtros = tabla(["Paso", "Partidas", "Qué se hizo"], [
        ["Bajadas al bronce", num(len(df) + 1651),
         "Cada partida clasificatoria (cola 420) de los jugadores de la escalera de seis servidores, tal como la devuelve Riot."],
        ["Pasan los filtros de admisión", num(len(df)),
         "Se descartan 1.651: de otra temporada, remakes (menos de 5 minutos) o sin 10 jugadores en dos equipos de 5. "
         "Quedan anotadas para no volver a pedirlas."],
        ["Llegan al minuto 10", num(len(d10)),
         f"Salen las {num(len(df) - len(d10))} que terminan antes: no tienen estado al minuto 10 que mirar."],
        ["Entrenamiento (80 %)", num(len(X10)), "Todo lo que se elige —modelo, pesos, C— se elige acá, con validación cruzada de 5 pedazos."],
        ["Test (20 %, estratificado por elo)", num(len(X10_te)), "Separado antes de mirar nada, y usado una sola vez."]])

    por_srv = plataformas.value_counts()
    txt_srv = " · ".join(f"{s} {num(v)}" for s, v in por_srv.items())

    # ─────────────────────────────────────────────────────────────────────
    # La página
    # ─────────────────────────────────────────────────────────────────────
    version = version_ddragon()
    valores = dict(
        TITULO="FF-15 · ¿Cuánto dura tu partida?",
        N_PARTIDAS=num(len(df)), N_MIN10=num(len(d10)), N_TEST=num(len(te)), N_TRAIN=num(len(tr)),
        N_SERVIDORES=str(plataformas.nunique()), TXT_SRV=txt_srv,
        CSV_DF=html.escape(nombre_df), CSV_MIN=html.escape(nombre_min), CSV_MIN5=html.escape(nombre_min5),
        N_LT15=num(n_lt15), PCT_LT15=pct(n_lt15 / len(df)),
        F1_ANTES=num(m_mom["antes de jugar"]["F1"], 3), F1_M5=num(m_mom["minuto 5"]["F1"], 3),
        ACC_ANTES=pct(m_mom["antes de jugar"]["accuracy"]), ACC_M5=pct(m_mom["minuto 5"]["accuracy"]),
        MAS1_PISO=pct(m_piso["±1"]), MAS1_ANTES=pct(m_mom["antes de jugar"]["±1"]), MAS1=pct(m_final["±1"]),
        PASA_ANTES=pct(m_mom["antes de jugar"]["pasa"]), PASA_PISO=pct(pasa_piso.mean()),
        CONTESTA_ANTES=str(m_mom["antes de jugar"]["contesta"]),
        N70_ANTES=num(arriba70["antes de jugar"]), N70_M10=num(arriba70["minuto 10"]),
        CM_ANTES_CENTRO=pct(cm_mom["antes de jugar"][:, 3].sum() / cm_mom["antes de jugar"].sum(), 0),
        CM_M10_CENTRO=pct(cm_mom["minuto 10"][:, 3].sum() / cm_mom["minuto 10"].sum(), 0),
        R2_ELO=pct(r_elo_e2 ** 2), R_ELO=num(r_elo_e2, 3),
        F1=num(m_final["F1"], 3), F1_PISO=num(m_piso["F1"], 3),
        DICE=pct(dice_te.mean()), PASA=pct(pasa_te.mean()), DICE0=pct(dice_te.mean(), 0), PASA0=pct(pasa_te.mean(), 0),
        DICE_PISO=pct(dice_piso.mean(), 0),
        EN_15=num(en_15), EN_14=num(en_14), PARTE_21_33=pct(parte_21_33, 0),
        R_MIN=num(mejor_min["r"], 3), NOMBRE_MIN=html.escape(mejor_min["nombre"]),
        R_ANTES=num(mejor_antes["r"], 3), NOMBRE_ANTES=html.escape(mejor_antes["nombre"]),
        ACC=pct(m_final["accuracy"]), ACC_PISO=pct(m_piso["accuracy"]),
        LE3=pct(m_final["≤3"]), LE3_PISO=pct(m_piso["≤3"]),
        ERR=num(m_final["error medio"], 3), ERR_PISO=num(m_piso["error medio"], 3),
        C_FINAL=num(C_final), MAE_RIDGE=num(mae_ridge, 1), R2_RIDGE=num(r2_ridge, 3),
        RES_BAJO=pct(resolucion["el tercio en que dice menos"][2]), RES_ALTO=pct(resolucion["el tercio en que dice más"][2]),
        CONTESTA=str(int((cm.sum(axis=0) > 0).sum())),
        T_FILTROS=filtros, T_COMP=t_comp, T_GRILLA=t_grilla, T_TEST=t_test, T_BANDAS=t_bandas, T_CM=t_cm,
        T_COEF=t_coef, T_IMP=t_imp, T_RES=t_res, T_MOM=t_mom,
        SPECS=json.dumps(specs, ensure_ascii=False, separators=(",", ":")),
        EJEMPLOS=json.dumps(ejemplos, ensure_ascii=False),
        DDRAGON=json.dumps(version), BANDAS_JSON=json.dumps(BANDAS, ensure_ascii=False),
        NUM_DESL=json.dumps(deslizadores),
    )
    pagina = Template((APP / "plantilla.html").read_text(encoding="utf-8")).substitute(valores)
    destino = APP / "index.html"
    destino.write_text(pagina, encoding="utf-8")
    log.info("Escrita %s (%.1f MB)", destino.relative_to(RAIZ), destino.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
