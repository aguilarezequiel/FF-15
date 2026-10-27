"""Tests del corte del timeline al minuto N.

No importan Airflow: `lol.timeline` es puro, así que se prueba con una
partida y un timeline sintéticos, armados con la forma de match-v5.
Corren con `astro dev pytest`, junto con los del DAG.
"""
import pytest

from lol import timeline
from lol.transform import PartidaDescartada

MIN = timeline.MS_POR_MINUTO


def _partida(duracion=1500):
    participantes = [{"participantId": i, "teamId": 100 if i <= 5 else 200,
                      "kills": 1 if i in (1, 2, 7) else 0,
                      "wardsPlaced": 1, "wardsKilled": 0,
                      "challenges": {"turretPlatesTaken": 1 if i == 1 else 0}}
                     for i in range(1, 11)]
    # objectives.champion.kills son las muertes del rival: el 200 suma la
    # ejecución del jugador 3, que no figura en los kills de ningún jugador
    objetivos = {
        100: {"champion": {"first": False, "kills": 2},
              "tower": {"first": True, "kills": 1},
              "inhibitor": {"first": False, "kills": 0},
              "dragon": {"first": True, "kills": 1}},
        200: {"champion": {"first": True, "kills": 2},
              "tower": {"first": False, "kills": 0},
              "inhibitor": {"first": False, "kills": 0},
              "dragon": {"first": False, "kills": 0}},
    }
    return {"metadata": {"matchId": "LA2_1"},
            "info": {"gameVersion": "16.10.1", "gameDuration": duracion,
                     "participants": participantes,
                     "teams": [{"teamId": t, "objectives": o}
                               for t, o in objetivos.items()]}}


def _cuadro(ts, oro_t1, oro_t2, eventos=()):
    pf = {str(i): {"totalGold": oro_t1 if i <= 5 else oro_t2, "xp": 100,
                   "minionsKilled": 10, "jungleMinionsKilled": 0,
                   "level": 3 if i <= 5 else 2}
          for i in range(1, 11)}
    return {"timestamp": ts, "participantFrames": pf, "events": list(eventos)}


def _timeline():
    wards = [{"type": "WARD_PLACED", "timestamp": 30_000, "creatorId": i}
             for i in range(1, 11)]
    return {"info": {"frames": [
        _cuadro(0, 500, 500, wards),
        _cuadro(3 * MIN + 20, 900, 800, [
            {"type": "CHAMPION_KILL", "timestamp": 200_000, "killerId": 7,
             "victimId": 2},
            {"type": "CHAMPION_KILL", "timestamp": 150_000, "killerId": 0,
             "victimId": 3},               # ejecutado por una torre: no suma
        ]),
        _cuadro(5 * MIN + 30, 1500, 1200, [
            {"type": "CHAMPION_KILL", "timestamp": 280_000, "killerId": 1,
             "victimId": 6},
            {"type": "TURRET_PLATE_DESTROYED", "timestamp": 290_000,
             "killerId": 1, "teamId": 200},  # placa del 200: punto del 100
        ]),
        _cuadro(10 * MIN + 10, 4000, 3000, [
            {"type": "CHAMPION_KILL", "timestamp": 400_000, "killerId": 2,
             "victimId": 8},               # después del corte
            {"type": "BUILDING_KILL", "timestamp": 500_000, "killerId": 1,
             "teamId": 200, "buildingType": "TOWER_BUILDING"},
            {"type": "ELITE_MONSTER_KILL", "timestamp": 550_000,
             "killerTeamId": 100, "monsterType": "DRAGON"},
        ]),
    ]}}


def test_toma_el_primer_cuadro_que_alcanza_el_corte():
    fila = timeline.estado_al_minuto(_partida(), _timeline(), 5)
    assert fila["t1_gold_m5"] == 1500 * 5
    assert fila["t2_gold_m5"] == 1200 * 5
    assert fila["dif_gold_m5"] == 300 * 5
    assert fila["t1_level_m5"] == 3
    assert fila["dif_level_m5"] == 1


def test_eventos_se_cortan_en_el_minuto():
    fila = timeline.estado_al_minuto(_partida(), _timeline(), 5)
    assert (fila["t1_kills_m5"], fila["t2_kills_m5"]) == (1, 1)
    assert (fila["t1_plates_m5"], fila["t2_plates_m5"]) == (1, 0)
    assert fila["t1_towers_m5"] == 0
    assert fila["t1_elite_monsters_m5"] == 0
    assert (fila["t1_wards_placed_m5"], fila["t2_wards_placed_m5"]) == (5, 5)


def test_primera_sangre_ignora_ejecuciones():
    fila = timeline.estado_al_minuto(_partida(), _timeline(), 5)
    assert fila["t2_first_blood_m5"] == 1
    assert fila["t1_first_blood_m5"] == 0
    assert fila["first_blood_s_m5"] == 200.0


def test_sin_primera_sangre_antes_del_corte_queda_vacio():
    fila = timeline.estado_al_minuto(_partida(), _timeline(), 3)
    assert fila["first_blood_s_m3"] is None
    assert fila["t1_first_blood_m3"] == fila["t2_first_blood_m3"] == 0


def test_partida_que_termina_antes_del_corte_queda_afuera():
    with pytest.raises(PartidaDescartada):
        timeline.estado_al_minuto(_partida(duracion=310), _timeline(), 10)


def test_chequeo_contra_partida_coincide():
    resultado = timeline.chequeo_contra_partida(_partida(), _timeline())
    assert resultado["towers"] is True
    assert resultado["plates"] is True
    assert resultado["elite_monsters"] is True
    assert resultado["wards_placed"] is True
    assert resultado["wards_killed"] is True
    assert resultado["kills"] is True
    assert resultado["first_blood"] is True


def test_chequeo_de_kills_compara_con_los_jugadores():
    """Los kills se comparan con los de los jugadores, no con objectives:
    si un jugador no tiene el kill que le da el timeline, salta."""
    partida = _partida()
    jugador_7 = partida["info"]["participants"][6]
    jugador_7["kills"] = 0
    assert timeline.chequeo_contra_partida(partida, _timeline())["kills"] is False


def test_chequeo_detecta_una_lectura_al_reves():
    """Si la torre se le anotara al dueño, el chequeo tiene que saltar."""
    partida = _partida()
    for t in partida["info"]["teams"]:
        t["objectives"]["tower"]["kills"] = 1 - t["objectives"]["tower"]["kills"]
    assert timeline.chequeo_contra_partida(partida, _timeline())["towers"] is False
