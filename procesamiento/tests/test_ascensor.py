"""Pruebas de la etapa del ascensor: barómetro, perfil de movimiento, correcciones, fusión,
predicción del error y análisis completo de un ascensor simulado corto."""

import numpy as np
import pytest

import config
from navinercial import ascensor, barometro, correcciones, fusion, lectura, prediccion_error
from simulador import escenarios, generar

ITINERARIO_CORTO = (0, 2, 1, 0)


# ---------------------------------------------------------------------------
# Fórmula barométrica
# ---------------------------------------------------------------------------

def test_altura_barometrica_ida_y_vuelta():
    alturas = np.array([-5.0, 0.0, 3.6, 15.1])

    presion = barometro.presion_a_altura(alturas, 72000.0, 20.0)
    recuperada = barometro.altura_barometrica(presion, 72000.0, 20.0)

    np.testing.assert_allclose(recuperada, alturas, atol=1e-9)


def test_en_quito_la_presion_baja_unos_8_pascales_por_metro():
    # P·M·g/(R·T) = 72000 · 0,0289644 · 9,77 / (8,314462618 · 293,15) = 8,36 Pa/m
    assert barometro.pascales_por_metro(72000.0, 20.0) == pytest.approx(8.36, abs=0.01)
    assert 72000.0 - barometro.presion_a_altura(1.0, 72000.0, 20.0) == pytest.approx(8.36, abs=0.01)


def test_misma_presion_que_la_referencia_es_altura_cero():
    assert barometro.altura_barometrica(72000.0, 72000.0, 15.0) == 0.0


# ---------------------------------------------------------------------------
# Perfil de movimiento y escenario
# ---------------------------------------------------------------------------

def test_perfil_empieza_y_termina_en_reposo_y_recorre_la_distancia():
    _, duracion = escenarios.duracion_del_perfil(9.3, 1.5, 3.0)
    t = np.array([0.0, duracion])

    posicion, velocidad, aceleracion = escenarios.perfil_de_movimiento(t, 9.3, 1.5, 3.0)

    np.testing.assert_allclose(posicion, [0.0, 9.3], atol=1e-12)
    np.testing.assert_allclose(velocidad, [0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(aceleracion, [0.0, 0.0], atol=1e-12)


def test_perfil_velocidad_es_la_derivada_de_la_posicion():
    _, duracion = escenarios.duracion_del_perfil(9.3, 1.5, 3.0)
    t = np.linspace(0.0, duracion, 20001)

    posicion, velocidad, aceleracion = escenarios.perfil_de_movimiento(t, 9.3, 1.5, 3.0)

    np.testing.assert_allclose(np.gradient(posicion, t)[1:-1], velocidad[1:-1], atol=1e-5)
    np.testing.assert_allclose(np.gradient(velocidad, t)[1:-1], aceleracion[1:-1], atol=1e-5)
    assert np.max(velocidad) == pytest.approx(1.5)


def test_perfil_corto_no_alcanza_la_velocidad_maxima():
    velocidad_crucero, duracion = escenarios.duracion_del_perfil(3.0, 1.5, 3.0)

    assert velocidad_crucero == pytest.approx(1.0)      # 3 m / 3 s
    assert duracion == pytest.approx(6.0)               # solo arranque y frenado


def test_escenario_del_ascensor_para_en_los_pisos_del_itinerario():
    escenario = escenarios.crear_ascensor(itinerario=ITINERARIO_CORTO)
    paradas = correcciones.paradas_por_eventos(
        escenario.tiempos_eventos_s, 0.0, escenario.duracion_s)
    t_medio = np.array([(inicio + fin) / 2 for inicio, fin in paradas])

    estado = escenario.estado(t_medio)

    esperadas = np.array(config.SIM_ASCENSOR_ALTURAS_PISOS_M)[list(ITINERARIO_CORTO)]
    np.testing.assert_allclose(estado["altura_m"], esperadas, atol=1e-12)
    np.testing.assert_allclose(estado["velocidad_z_ms"], 0.0, atol=1e-12)
    # En reposo el acelerómetro ideal mide g, aunque el dispositivo esté inclinado.
    magnitud = np.linalg.norm(estado[["fx", "fy", "fz"]].to_numpy(), axis=1)
    np.testing.assert_allclose(magnitud, config.G_QUITO, atol=1e-12)
    assert len(escenario.tiempos_eventos_s) == 2 * (len(ITINERARIO_CORTO) - 1)


# ---------------------------------------------------------------------------
# Correcciones
# ---------------------------------------------------------------------------

def test_paradas_por_eventos():
    paradas = correcciones.paradas_por_eventos([10.0, 20.0, 30.0, 45.0], 0.0, 60.0, margen_s=0.5)

    assert paradas == [(0.0, 9.5), (20.5, 29.5), (45.5, 60.0)]


def test_cantidad_impar_de_pulsaciones_da_error():
    with pytest.raises(ValueError, match="par"):
        correcciones.paradas_por_eventos([10.0, 20.0, 30.0], 0.0, 60.0)


def test_restar_sesgo_por_paradas_quita_un_sesgo_constante():
    t = np.linspace(0.0, 60.0, 6001)
    paradas = [(0.0, 10.0), (20.0, 30.0), (50.0, 60.0)]
    real = np.where((t > 12) & (t < 14), 0.5, 0.0)       # un "arranque" entre dos paradas

    corregida, sesgo = correcciones.restar_sesgo_por_paradas(t, real + 0.2, paradas)

    np.testing.assert_allclose(corregida, real, atol=1e-12)
    np.testing.assert_allclose(sesgo, 0.2, atol=1e-12)


def test_zupt_quita_una_deriva_lineal_de_la_velocidad():
    t = np.linspace(0.0, 60.0, 6001)
    paradas = [(0.0, 10.0), (20.0, 30.0), (50.0, 60.0)]
    real = np.where((t > 10) & (t < 20), np.sin(np.pi * (t - 10) / 10), 0.0)   # 0 en las paradas
    en_parada = correcciones.mascara_de_paradas(t, paradas)
    # Error: cero hasta t = 10 y después crece en línea recta (lo que da un sesgo constante).
    error = np.where(t > 10, 0.03 * (t - 10), 0.0)

    corregida = correcciones.aplicar_zupt(t, real + error, paradas)

    np.testing.assert_allclose(corregida[en_parada], 0.0, atol=1e-12)
    np.testing.assert_allclose(corregida, real, atol=1e-9)


def test_factor_por_distancia_conocida():
    assert correcciones.factor_por_distancia_conocida(1030.0, 1000.0) == pytest.approx(1000 / 1030)
    with pytest.raises(ValueError):
        correcciones.factor_por_distancia_conocida(0.0, 1000.0)


# ---------------------------------------------------------------------------
# Fusión
# ---------------------------------------------------------------------------

def test_alinear_mediciones_pone_cada_medicion_una_sola_vez():
    t = np.arange(10) * 0.005

    alineado = fusion.alinear_mediciones(t, np.array([0.011, 0.031]), np.array([5.0, 7.0]))

    assert np.count_nonzero(~np.isnan(alineado)) == 2
    assert alineado[3] == 5.0 and alineado[7] == 7.0


def test_kalman_sin_mediciones_es_la_cinematica():
    # Aceleración constante de 1 m/s² durante 2 s: v = t, h = t²/2.
    t = np.linspace(0.0, 2.0, 401)

    altura, velocidad, std = fusion.kalman_altura(t, np.ones_like(t))

    assert velocidad[-1] == pytest.approx(2.0)
    assert altura[-1] == pytest.approx(2.0)
    assert std[-1] > std[0]            # sin mediciones, la incertidumbre crece


def _subida_con_sesgo():
    """Subida suave de 10 m, medida con un acelerómetro con sesgo y un barómetro exacto."""
    t = np.linspace(0.0, 60.0, 12001)
    posicion, _, aceleracion = escenarios.perfil_de_movimiento(t - 5.0, 10.0, 1.5, 3.0)
    return t, posicion, aceleracion + 0.05


def test_complementario_no_deriva_aunque_el_acelerometro_tenga_sesgo():
    t, posicion, aceleracion_con_sesgo = _subida_con_sesgo()

    altura, _ = fusion.filtro_complementario(t, aceleracion_con_sesgo, posicion, tau_s=3.0)

    # Solo integrando, un sesgo de 0,05 m/s² daría ½·0,05·60² = 90 m de error.
    assert np.max(np.abs(altura - posicion)) < 0.6


def test_kalman_con_barometro_no_deriva_y_con_zupt_tampoco():
    t, posicion, aceleracion_con_sesgo = _subida_con_sesgo()
    baro = fusion.alinear_mediciones(t, t[::8], posicion[::8])
    en_parada = (t < 4.5) | (t > 20.0)

    con_baro, _, _ = fusion.kalman_altura(t, aceleracion_con_sesgo, altura_baro=baro)
    con_zupt, velocidad, _ = fusion.kalman_altura(t, aceleracion_con_sesgo, en_parada=en_parada)

    # El sesgo deja un error fijo (el filtro no lo conoce), pero no crece: sin barómetro
    # serían 90 m.
    assert np.max(np.abs(con_baro - posicion)) < 1.0
    assert abs(velocidad[-1]) < 0.01
    assert abs(con_zupt[-1] - 10.0) < 6.0     # sin barómetro queda el error del tramo en movimiento


# ---------------------------------------------------------------------------
# Predicción del error
# ---------------------------------------------------------------------------

def test_formulas_de_prediccion():
    assert prediccion_error.error_posicion_por_sesgo(0.1, 10.0) == pytest.approx(5.0)
    assert prediccion_error.error_velocidad_por_sesgo(0.1, 10.0) == pytest.approx(1.0)
    assert prediccion_error.std_velocidad_por_ruido(0.03, 0.005, 20.0) == pytest.approx(
        0.03 * np.sqrt(0.1))
    assert prediccion_error.error_posicion_por_escala(0.015, 10.0) == pytest.approx(0.15)
    assert prediccion_error.std_altura_barometro(1.3, 8.36) == pytest.approx(0.1555, abs=1e-3)


def test_prediccion_del_ruido_coincide_con_una_simulacion():
    # 2000 integraciones dobles de ruido blanco durante 20 s a 200 Hz.
    rng = np.random.default_rng(config.SEMILLA_POR_DEFECTO)
    dt, n, sigma = 0.005, 4000, 0.03
    ruido = rng.normal(0.0, sigma, (2000, n))
    velocidad = np.cumsum(ruido, axis=1) * dt
    posicion = np.cumsum(velocidad, axis=1) * dt

    assert np.std(velocidad[:, -1]) == pytest.approx(
        prediccion_error.std_velocidad_por_ruido(sigma, dt, n * dt), rel=0.06)
    assert np.std(posicion[:, -1]) == pytest.approx(
        prediccion_error.std_posicion_por_ruido(sigma, dt, n * dt), rel=0.06)


# ---------------------------------------------------------------------------
# Análisis completo de un ascensor simulado corto
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ascensor_corto(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("ascensor")
    escenario = escenarios.crear_ascensor(itinerario=ITINERARIO_CORTO)
    simulada = generar.simular_sesion(escenario)
    generar.guardar_sesion_simulada(carpeta, simulada)
    analisis = ascensor.analizar(lectura.cargar_sesion(carpeta))
    alturas = np.array(config.SIM_ASCENSOR_ALTURAS_PISOS_M)
    return analisis, simulada.verdad["altura_m"].to_numpy(), alturas


def test_analisis_mide_la_gravedad_y_la_inclinacion(ascensor_corto):
    analisis, _, _ = ascensor_corto

    # Sin calibrar, el sensor simulado mide de más (sesgo y escala del eje z).
    assert analisis.gravedad_medida == pytest.approx(config.G_QUITO, abs=0.5)
    # Inclinación simulada: alabeo 1,5° y cabeceo −1° -> unos 1,8° respecto a la vertical.
    assert analisis.inclinacion_grados == pytest.approx(1.8, abs=0.5)


def test_zupt_y_barometro_recuperan_el_desplazamiento_de_cada_recorrido(ascensor_corto):
    analisis, _, alturas = ascensor_corto
    referencia = alturas[list(ITINERARIO_CORTO)]

    tabla = ascensor.tabla_de_recorridos(analisis, referencia)

    # Sin calibrar queda el error de escala del eje z (1,5 % de 6,45 m ≈ 0,10 m).
    assert ascensor.raiz_cuadratica_media(tabla[ascensor.CON_ZUPT]) < 0.20
    assert ascensor.raiz_cuadratica_media(tabla[ascensor.BAROMETRO]) < 0.15
    assert ascensor.raiz_cuadratica_media(tabla[ascensor.KALMAN_BARO_ZUPT]) < 0.15


def test_las_correcciones_mejoran_la_altura(ascensor_corto):
    analisis, verdad, _ = ascensor_corto

    def error(nombre):
        return ascensor.raiz_cuadratica_media(analisis.altura[nombre] - verdad)

    assert error(ascensor.CON_ZUPT) < error(ascensor.SESGO_INICIAL) < error(ascensor.SIN_CORRECCIONES)
    assert error(ascensor.KALMAN_BARO_ZUPT) < 0.5


def test_asignar_pisos_recupera_el_itinerario(ascensor_corto):
    analisis, _, alturas = ascensor_corto
    h_paradas = ascensor.alturas_en_paradas(
        analisis.t_s, analisis.altura[ascensor.KALMAN_BARO_ZUPT], analisis.paradas)

    assert ascensor.asignar_pisos(h_paradas, alturas) == list(ITINERARIO_CORTO)


def test_cruce_de_pisos_coincide_con_la_verdad(ascensor_corto):
    analisis, verdad, alturas = ascensor_corto
    t, paradas = analisis.t_s, analisis.paradas
    estimada = analisis.altura[ascensor.KALMAN_BARO_ZUPT]

    cruces = ascensor.cruces_de_pisos(t, estimada, paradas, alturas, ITINERARIO_CORTO)
    reales = ascensor.cruces_de_pisos(t, verdad, paradas, alturas, ITINERARIO_CORTO)

    # Solo el primer recorrido (0 -> 2) pasa frente a un piso intermedio (el 1).
    assert list(cruces["piso"]) == [1]
    assert cruces["t_biseccion_s"].iloc[0] == pytest.approx(reales["t_biseccion_s"].iloc[0], abs=0.3)
    assert cruces["iteraciones_biseccion"].iloc[0] > 10
