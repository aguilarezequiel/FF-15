"""
Construye la aplicación de la Entrega 4: app/index.html, una sola página con todo adentro.

    .venv\\Scripts\\python app/build_app.py                    # con los CSV congelados (los del notebook)
    .venv\\Scripts\\python app/build_app.py --desde-pipeline   # con lo último que dejó el DAG en include/output/

Hace, en orden, lo mismo que notebooks/entrega-4/correcciones_entrega3.ipynb para el ancho de
6 minutos: las mismas clases, la misma partición, los mismos cinco pedazos y SEMILLA = 42. Entrena
la regresión logística sin pesos (el modelo final que eligió el grupo), mide lo que muestra la app
y escribe los gráficos de Altair y la fórmula del modelo adentro de la página.

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


def armar(modelo):
    """El pipeline de la E3 con el minuto 10: derivar, imputar y escalar, codificar, y el modelo al final."""
    derivar = FeatureUnion([("partida", ColumnasDePartida()), ("diferencias", DiferenciasEntreEquipos()),
                            ("minuto", EstadoAlMinuto(10))],
                           verbose_feature_names_out=False).set_output(transform="pandas")
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
                "±1 banda test": 0.843, "dice ventana": 0.666, "pasa ventana": 0.663}


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
COLORES_BANDA = ["#9CC3FF", "#4F7CF7", "#8A5CF5", "#D94FB0", "#F2716B", "#F5A453", "#F7DC7B"]
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
    else:
        ruta_df = buscar("lol_2*.csv", RAIZ / "notebooks" / "entrega-2" / "datos")
        ruta_min = buscar("lol_min10_*.csv", RAIZ / "notebooks" / "entrega-3" / "datos")
    log.info("Datos: %s y %s", ruta_df.name, ruta_min.name)
    return pd.read_csv(ruta_df), pd.read_csv(ruta_min), ruta_df.name, ruta_min.name


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

    df, min10, nombre_df, nombre_min = cargar(args.desde_pipeline)

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

    # ── Elegir el modelo (notebook, Sección 2), sólo el ancho de 6 minutos ──
    scorers = {"F1 macro": "f1_macro", "accuracy": "accuracy", "±1 banda": make_scorer(a_una_banda)}
    piso_cv = cross_validate(armar(DummyClassifier(strategy="prior")), X10, yb, cv=cv, scoring=scorers, n_jobs=-1)
    busquedas = {n: GridSearchCV(armar(LogisticRegression(max_iter=3000, class_weight=w)), {"modelo__C": GRILLA_C},
                                 cv=cv, scoring=scorers, refit="F1 macro", n_jobs=-1).fit(X10, yb)
                 for n, w in {"sin pesos": None, "balanced": "balanced"}.items()}
    final = busquedas["sin pesos"].best_estimator_
    C_final = busquedas["sin pesos"].best_params_["modelo__C"]
    piso = armar(DummyClassifier(strategy="prior")).fit(X10, yb)

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

    chequeo = {"C": C_final, "F1 test": round(m_final["F1"], 3), "F1 piso test": round(m_piso["F1"], 3),
               "accuracy test": round(m_final["accuracy"], 3), "±1 banda test": round(m_final["±1"], 3),
               "dice ventana": round(dice_te.mean(), 3), "pasa ventana": round(pasa_te.mean(), 3)}
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
    P_tr = cross_val_predict(armar(LogisticRegression(max_iter=3000, C=C_final)), X10, yb, cv=cv,
                             method="predict_proba", n_jobs=-1)

    # ─────────────────────────────────────────────────────────────────────
    # Los números de la página
    # ─────────────────────────────────────────────────────────────────────
    minutos_df = df["game_duration_s"] / 60
    banda_df = pd.Series(np.array(BANDAS)[banda_de(df["game_duration_s"])], index=df.index)
    en_15 = int(((df["game_duration_s"] >= 900) & (df["game_duration_s"] < 960)).sum())
    en_14 = int(((df["game_duration_s"] >= 840) & (df["game_duration_s"] < 900)).sum())
    parte_21_33 = minutos_df.between(21, 33, inclusive="left").mean()
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
    nota = alt.Chart(pd.DataFrame({"x": [15], "y": [en_15], "t": [f"min 15: se habilita el «ff» · {num(en_15)} partidas"]})) \
        .mark_text(align="right", dx=-8, dy=4, color=CREMA, fontSize=12.5, fontWeight=600).encode(x="x:Q", y="y:Q", text="t:N")
    specs["g-datos"] = (barras + regla + nota).properties(
        width=820, height=300,
        title=alt.Title(f"Cuánto duraron las {num(len(df))} partidas",
                        subtitle=["Cada barra es un minuto de duración; el color, la banda de 6 minutos en la que cae.",
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

    # El modelo: la calibración de la ventana de 12 minutos en el test
    cortes = np.linspace(0, 1, 11)
    cal = pd.DataFrame({"dice": dice_te, "pasa": pasa_te}).groupby(pd.cut(dice_te, cortes), observed=True) \
        .agg(dice=("dice", "mean"), pasa=("pasa", "mean"), partidas=("pasa", "size")).reset_index(drop=True)
    cal = cal[cal["partidas"] >= 20].assign(quien="el modelo")
    cal_piso = pd.DataFrame({"dice": [dice_piso.mean()], "pasa": [pasa_piso.mean()], "partidas": [len(dice_piso)],
                             "quien": ["el piso (dice siempre lo mismo)"]})
    cal_todo = pd.concat([cal, cal_piso])
    cal_todo["dice_txt"], cal_todo["pasa_txt"] = cal_todo["dice"].map(pct), cal_todo["pasa"].map(pct)
    esc_cal = alt.Scale(domain=[0.3, 0.9], zero=False, clamp=True)
    diag = alt.Chart(pd.DataFrame({"x": [0.3, 0.9], "y": [0.3, 0.9]})).mark_line(color=GRIS, strokeDash=[5, 5]) \
        .encode(x=alt.X("x:Q", scale=esc_cal), y=alt.Y("y:Q", scale=esc_cal))
    diag_txt = alt.Chart(pd.DataFrame({"x": [0.86], "y": [0.86], "t": ["calibración perfecta"]})) \
        .mark_text(color=GRIS, angle=315, dy=-10, fontSize=11.5).encode(
            x=alt.X("x:Q", scale=esc_cal), y=alt.Y("y:Q", scale=esc_cal), text="t:N")
    escala_quien = alt.Scale(domain=["el modelo", "el piso (dice siempre lo mismo)"], range=[ORO, PISO_COLOR])
    base_cal = alt.Chart(cal_todo).encode(
        x=alt.X("dice:Q", title="probabilidad que el modelo le da a su ventana", scale=esc_cal,
                axis=alt.Axis(format="%")),
        y=alt.Y("pasa:Q", title="frecuencia con que la partida termina ahí", scale=esc_cal,
                axis=alt.Axis(format="%")),
        color=alt.Color("quien:N", scale=escala_quien, legend=alt.Legend(title=None, orient="top", labelLimit=320)),
        tooltip=[alt.Tooltip("quien:N", title=" "), alt.Tooltip("dice_txt:N", title="dice"),
                 alt.Tooltip("pasa_txt:N", title="pasa"), alt.Tooltip("partidas:Q", title="partidas", format=",")])
    linea_cal = base_cal.transform_filter("datum.quien == 'el modelo'").mark_line(strokeWidth=2.5)
    puntos_cal = base_cal.mark_point(filled=True, opacity=1).encode(
        size=alt.Size("partidas:Q", scale=alt.Scale(range=[40, 600]), legend=None))
    specs["g-modelo"] = (diag + diag_txt + linea_cal + puntos_cal).properties(
        width=460, height=400,
        title=alt.Title("Cuando dice «p %», pasa más o menos el p % de las veces",
                        subtitle=[f"Las {num(len(te))} partidas del test, agrupadas por la probabilidad que el modelo le dio",
                                  "a su ventana de 12 minutos (tramos de 10 puntos con 20 partidas o más)."])).to_dict()

    # ── Explorá: cada partida, con lo que dijo un modelo que no la vio ──
    P_todo = np.vstack([P_tr, P_te])
    idx = list(tr) + list(te)
    ini_todo, dice_todo = ventana_de(P_todo)
    real_todo = np.concatenate([yb.to_numpy(), real_te])
    ex = pd.DataFrame({
        "match_id": d10.loc[idx, "match_id"].to_numpy(),
        "servidor": d10.loc[idx, "match_id"].str.split("_").str[0].to_numpy(),
        "grupo": grupo.loc[idx].astype(str).to_numpy(),
        "elo": derivadas.loc[idx, "elo_partida"].round().astype(int).to_numpy(),
        "duracion": (d10.loc[idx, "game_duration_s"] / 60).round(1).to_numpy(),
        "banda_real": np.array(BANDAS)[real_todo],
        "dif_oro": d10.loc[idx, "dif_gold_m10"].astype(int).to_numpy(),
        "dif_kills": d10.loc[idx, "dif_kills_m10"].astype(int).to_numpy(),
        "ventana": [texto_ventana(i, largo=False) for i in ini_todo],
        "vi": ini_todo,
        "p_ventana": dice_todo.round(3),
        "acierta": ((real_todo >= ini_todo) & (real_todo <= ini_todo + 1)).astype(int),
        "conjunto": ["validación cruzada"] * len(tr) + ["test"] * len(te)})
    for k in range(K):
        ex[f"p{k}"] = P_todo[:, k].round(3)
    ex["acierta_txt"] = np.where(ex["acierta"] == 1, "sí", "no")
    ejemplo_click = ex.loc[ex["conjunto"] == "test"].sort_values("p_ventana").iloc[len(te) // 2]["match_id"]

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
            alt.Tooltip("acierta_txt:N", title="¿acertó?"), alt.Tooltip("dif_oro:Q", title="dif. de oro al min 10", format=","),
            alt.Tooltip("dif_kills:Q", title="dif. de asesinatos al min 10"), alt.Tooltip("conjunto:N", title="predicha en")]
    nube = alt.Chart(ex).mark_circle(size=14).encode(
        x=alt.X("dif_oro:Q", title="diferencia de oro entre los equipos al minuto 10", axis=alt.Axis(format=",d")),
        y=alt.Y("duracion:Q", title="duración real (minutos)", scale=alt.Scale(domain=[5, 67])),
        color=alt.Color("banda_real:N", scale=ESCALA_BANDA, sort=BANDAS,
                        legend=alt.Legend(title="banda real (clic para resaltar)", orient="top", columns=7, symbolOpacity=1)),
        opacity=alt.condition(sel_banda, alt.value(0.55), alt.value(0.04)),
        tooltip=tips).add_params(p_srv, p_elo, p_conf, sel_banda, sel_click).transform_filter(filtro).properties(
        width=470, height=420, title=alt.Title("Las partidas que llegan al minuto 10",
                                               subtitle="Pasá el mouse para ver qué dijo el modelo; hacé clic para abrir una."))
    elegido = alt.Chart(ex).mark_circle(size=140, fill=None, stroke=ORO, strokeWidth=2.5).encode(
        x="dif_oro:Q", y="duracion:Q").transform_filter(sel_click)
    cuenta = alt.Chart(ex).transform_filter(filtro).mark_bar(cornerRadiusEnd=3, height=16).encode(
        y=alt.Y("banda_real:N", sort=BANDAS, title=None, scale=alt.Scale(domain=BANDAS)),
        x=alt.X("count():Q", title="partidas"),
        color=alt.Color("banda_real:N", scale=ESCALA_BANDA, legend=None),
        tooltip=[alt.Tooltip("banda_real:N", title="banda real"), alt.Tooltip("count():Q", title="partidas", format=",")]) \
        .properties(width=250, height=alt.Step(20), title=alt.Title("Dónde terminaron", subtitle="las partidas que quedan con los filtros"))
    acierto = alt.Chart(ex).transform_filter(filtro).transform_aggregate(
        n="count()", a="mean(acierta)").transform_calculate(
        t="format(datum.n, ',') + ' partidas · el modelo acertó la ventana en el ' + format(datum.a, '.0%')").mark_text(
        align="left", color=ORO, fontSize=13, fontWeight=600).encode(x=alt.value(0), y=alt.value(8), text="t:N") \
        .properties(width=250, height=18)
    detalle = alt.Chart(ex).transform_filter(sel_click).transform_fold(
        [f"p{k}" for k in range(K)], as_=["clave", "p"]).transform_calculate(
        k="toNumber(replace(datum.clave, 'p', ''))", banda=f"{json.dumps(BANDAS)}[toNumber(replace(datum.clave, 'p', ''))]",
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
    specs["g-explora"] = alt.hconcat(nube + elegido, alt.vconcat(acierto, cuenta, det, spacing=18), spacing=28) \
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
        CSV_DF=html.escape(nombre_df), CSV_MIN=html.escape(nombre_min),
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
        T_COEF=t_coef, T_IMP=t_imp, T_RES=t_res,
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
