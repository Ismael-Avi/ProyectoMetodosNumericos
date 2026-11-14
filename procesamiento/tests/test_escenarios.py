"""Pruebas de los escenarios: el movimiento verdadero debe tener sentido físico."""

import numpy as np
import pytest

import config
from simulador import escenarios

G = config.G_QUITO


def _magnitud(estado, columnas):
    return np.linalg.norm(estado[columnas].to_numpy(), axis=1)


def test_reposo_mide_g_hacia_arriba_y_no_gira():
    escenario = escenarios.crear_reposo(duracion_s=10.0)

    estado = escenario.estado(np.linspace(0, 10, 50))

    assert np.allclose(estado[["fx", "fy"]], 0.0)
    assert np.allclose(estado["fz"], G)
    assert np.allclose(estado[escenarios.COLUMNAS_VELOCIDAD_ANGULAR], 0.0)


def test_reposo_inclinado_reparte_la_gravedad_pero_conserva_su_magnitud():
    escenario = escenarios.crear_reposo(duracion_s=10.0, alabeo_grados=2.0, cabeceo_grados=-3.0)

    estado = escenario.estado(np.array([0.0, 5.0]))

    assert abs(estado["fx"][0]) > 0.1          # ya no es cero
    assert estado["fz"][0] < G                 # el eje z ve un poco menos
    assert np.allclose(_magnitud(estado, escenarios.COLUMNAS_FUERZA), G)


def test_seis_caras_cada_cara_mide_mas_o_menos_g_en_su_eje():
    escenario = escenarios.crear_seis_caras(duracion_cara_s=10.0, duracion_giro_s=2.0)
    estado = escenario.estado(np.arange(0, escenario.duracion_s, 0.05))

    for cara in escenarios.CARAS:
        signo = 1.0 if cara[0] == "+" else -1.0
        eje = cara[1]
        esperado = {"fx": 0.0, "fy": 0.0, "fz": 0.0}
        esperado["f" + eje] = signo * G

        filas = estado[estado["tramo"] == cara]

        assert len(filas) > 100, cara
        for columna, valor in esperado.items():
            assert np.allclose(filas[columna], valor, atol=1e-9), (cara, columna)


def test_seis_caras_la_magnitud_de_la_gravedad_no_cambia_al_girar():
    escenario = escenarios.crear_seis_caras(duracion_cara_s=10.0, duracion_giro_s=2.0)

    estado = escenario.estado(np.arange(0, escenario.duracion_s, 0.01))

    assert np.allclose(_magnitud(estado, escenarios.COLUMNAS_FUERZA), G)
    assert np.allclose(_magnitud(estado, escenarios.COLUMNAS_CAMPO),
                       np.linalg.norm(config.SIM_MAG_CAMPO_MUNDO_UT))


def test_seis_caras_solo_gira_durante_los_giros():
    escenario = escenarios.crear_seis_caras(duracion_cara_s=10.0, duracion_giro_s=2.0)
    estado = escenario.estado(np.arange(0, escenario.duracion_s, 0.01))

    rapidez = _magnitud(estado, escenarios.COLUMNAS_VELOCIDAD_ANGULAR)
    en_giro = (estado["tramo"] == "giro").to_numpy()

    assert np.all(rapidez[~en_giro] == 0.0)
    assert rapidez[en_giro].max() > 0.5


def test_integrar_la_velocidad_angular_del_primer_giro_da_180_grados():
    dt = 0.001
    escenario = escenarios.crear_seis_caras(duracion_cara_s=10.0, duracion_giro_s=2.0)
    t = np.arange(10.0, 12.0 + dt, dt)          # el primer giro va de t = 10 s a t = 12 s

    wx = escenario.estado(t)["wx"].to_numpy()
    angulo = np.sum(wx) * dt                    # integral aproximada de la velocidad angular

    assert np.degrees(angulo) == pytest.approx(180.0, abs=0.01)


def test_duracion_total_de_seis_caras():
    escenario = escenarios.crear_seis_caras(duracion_cara_s=60.0, duracion_giro_s=5.0)

    assert escenario.duracion_s == 6 * 60.0 + 5 * 5.0
