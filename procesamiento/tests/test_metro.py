"""Pruebas de la etapa del metro: ruta sintética, herramientas numéricas, análisis de un
viaje simulado y bitácora."""

import numpy as np
import pandas as pd
import pytest

import config
from navinercial import bitacora, lectura, metro
from simulador import escenarios, generar


# ---------------------------------------------------------------------------
# Ruta sintética
# ---------------------------------------------------------------------------

def test_ruta_recta_y_cuarto_de_circulo():
    # 100 m hacia el este y después un cuarto de círculo de radio 100 m hacia la izquierda.
    ruta = escenarios.Ruta([(("recta", 100.0), ("curva", 100.0, 90.0))], [5.0], 0.0)
    largo_curva = 100.0 * np.pi / 2

    x, y, rumbo, curvatura = ruta.planta(np.array([0.0, 100.0, 100.0 + largo_curva]))
    h, _, _ = ruta.perfil(np.array([0.0, 100.0 + largo_curva]))

    np.testing.assert_allclose(x, [0.0, 100.0, 200.0], atol=1e-9)
    np.testing.assert_allclose(y, [0.0, 0.0, 100.0], atol=1e-9)
    assert rumbo[-1] == pytest.approx(np.pi / 2)
    assert curvatura[-1] == pytest.approx(1 / 100.0)
    np.testing.assert_allclose(h, [0.0, 5.0], atol=1e-12)


def test_viaje_de_vuelta_recorre_las_mismas_estaciones_al_reves():
    ida = escenarios.crear_metro(sentido=1).info["estaciones"]
    vuelta = escenarios.crear_metro(sentido=-1).info["estaciones"]

    assert [e["nombre"] for e in vuelta] == [e["nombre"] for e in ida][::-1]
    assert vuelta[0]["x_m"] == pytest.approx(ida[-1]["x_m"])
    assert vuelta[-1]["y_m"] == pytest.approx(ida[0]["y_m"], abs=1e-9)


def test_en_las_estaciones_del_metro_el_acelerometro_ideal_mide_g():
    escenario = escenarios.crear_metro()

    estado = escenario.estado(np.array([5.0, escenario.duracion_s - 5.0]))

    magnitud = np.linalg.norm(estado[["fx", "fy", "fz"]].to_numpy(), axis=1)
    np.testing.assert_allclose(magnitud, config.G_QUITO, atol=1e-9)
    np.testing.assert_allclose(estado["velocidad_ms"], 0.0, atol=1e-12)


# ---------------------------------------------------------------------------
# Herramientas numéricas
# ---------------------------------------------------------------------------

def test_diferencia_de_angulos_da_el_camino_corto():
    diferencia = metro.diferencia_de_angulos(np.radians(359.0), np.radians(1.0))

    assert np.degrees(diferencia) == pytest.approx(-2.0)


def test_promedio_movil_de_una_constante_y_de_una_recta():
    recta = np.arange(100, dtype=float)

    np.testing.assert_allclose(metro.promedio_movil(np.full(50, 3.0), 9), 3.0)
    # Lejos de los bordes, el promedio centrado de una recta es la misma recta.
    np.testing.assert_allclose(metro.promedio_movil(recta, 9)[10:-10], recta[10:-10])


def test_derivada_centrada_es_exacta_para_una_parabola():
    t = np.linspace(0.0, 2.0, 201)

    derivada = metro.derivada_centrada(t, t**2)

    np.testing.assert_allclose(derivada[1:-1], 2 * t[1:-1], atol=1e-10)


def test_geograficas_a_locales_un_grado_de_latitud():
    # Un grado de latitud mide R·π/180 ≈ 111,2 km en cualquier lugar de la Tierra.
    x, y = metro.geograficas_a_locales(1.0, -78.5, 0.0, -78.5)

    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(config.RADIO_TIERRA_M * np.pi / 180)


def test_gravedad_por_pendiente_en_una_subida_del_dos_por_ciento():
    # A 10 m/s por una subida con sen(θ) = 0,02 se suben 0,2 m cada segundo.
    t = np.linspace(0.0, 20.0, 4001)

    falsa = metro.gravedad_por_pendiente(t, 0.2 * t, np.full_like(t, 10.0))

    np.testing.assert_allclose(falsa, config.G_QUITO * 0.02, rtol=1e-9)


def test_ajustar_a_distancias_deja_cada_tramo_con_la_longitud_conocida():
    t = np.linspace(0.0, 40.0, 4001)
    paradas = [(0.0, 5.0), (15.0, 25.0), (35.0, 40.0)]
    velocidad = np.where((t > 5) & (t < 15), 10.0, 0.0) + np.where((t > 25) & (t < 35), 8.0, 0.0)

    ajustada, factores = metro.ajustar_a_distancias(t, velocidad, paradas, [110.0, 72.0])

    assert factores == pytest.approx([1.1, 0.9], rel=1e-2)
    assert np.max(ajustada) == pytest.approx(11.0, rel=1e-2)


# ---------------------------------------------------------------------------
# Análisis de un viaje simulado
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def viaje(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("metro")
    escenario = escenarios.crear_metro()
    simulada = generar.simular_sesion(escenario)
    generar.guardar_sesion_simulada(carpeta, simulada)
    info = escenario.info
    inicio = info["estaciones"][0]
    analisis = metro.analizar(lectura.cargar_sesion(carpeta), info["rumbo_inicial_rad"],
                              inicio["x_m"], inicio["y_m"], info["longitudes_tramos_m"])
    return analisis, simulada.verdad, info


def test_encuentra_la_orientacion_del_dispositivo(viaje):
    analisis, _, _ = viaje

    # El dispositivo está girado +10°, así que "adelante" queda a −10° de su eje x.
    assert analisis.montaje_grados == pytest.approx(-config.SIM_METRO_MONTAJE_GRADOS, abs=1.5)


def test_rumbo_por_giroscopio_sigue_las_curvas(viaje):
    analisis, verdad, _ = viaje

    error = metro.diferencia_de_angulos(analisis.rumbo_rad, verdad["rumbo_rad"].to_numpy())

    assert np.degrees(np.max(np.abs(error))) < 1.5


def test_magnetometro_perturbado_se_detecta_como_no_confiable(viaje):
    analisis, _, _ = viaje

    assert analisis.magnetometro is not None
    assert not analisis.magnetometro["confiable"]


def test_distancia_de_cada_tramo_con_zupt(viaje):
    analisis, _, info = viaje
    nombres = [e["nombre"] for e in info["estaciones"]]

    tabla = metro.tabla_de_tramos(analisis, nombres, info["longitudes_tramos_m"])

    # Sin calibrar queda el error de escala del eje x (1 %): hasta unos 12 m en 1200 m.
    assert np.max(np.abs(tabla[f"error: {metro.ZUPT_BARO}"])) < 20.0
    assert np.max(np.abs(tabla[f"error: {metro.AJUSTADO}"])) < 1e-6
    assert tabla["velocidad_max_ms"].max() == pytest.approx(config.SIM_METRO_VELOCIDAD_MAX_MS, rel=0.03)


def test_el_barometro_mejora_la_velocidad_y_el_zupt_la_posicion(viaje):
    analisis, verdad, _ = viaje

    def error_de_velocidad(nombre):
        return np.sqrt(np.mean((analisis.velocidad[nombre] - verdad["velocidad_ms"])**2))

    def error_final(nombre):
        return float(np.hypot(analisis.x_m[nombre][-1] - verdad["x_m"].iloc[-1],
                              analisis.y_m[nombre][-1] - verdad["y_m"].iloc[-1]))

    assert error_de_velocidad(metro.ZUPT_BARO) < error_de_velocidad(metro.ZUPT)
    assert error_final(metro.ZUPT) < error_final(metro.SIN_ZUPT)
    assert error_final(metro.AJUSTADO) < 30.0


def test_combinar_viajes_junta_el_mismo_tramo_en_los_dos_sentidos():
    columna = f"distancia: {metro.ZUPT_BARO}"
    ida = pd.DataFrame({"desde": ["A", "B"], "hasta": ["B", "C"], columna: [800.0, 930.0],
                        "duracion_s": [78.0, 84.0], "velocidad_max_ms": [20.0, 20.0]})
    vuelta = pd.DataFrame({"desde": ["C", "B"], "hasta": ["B", "A"], columna: [934.0, 802.0],
                           "duracion_s": [84.0, 78.0], "velocidad_max_ms": [20.0, 20.0]})

    combinado = metro.combinar_viajes({"ida": ida, "vuelta": vuelta})

    assert list(combinado.index) == ["A – B", "B – C"]
    assert combinado.loc["A – B", "distancia_media_m"] == pytest.approx(801.0)
    assert combinado.loc["A – B", "dispersion_m"] == pytest.approx(np.sqrt(2.0))


# ---------------------------------------------------------------------------
# Bitácora
# ---------------------------------------------------------------------------

def test_resultados_de_movimiento():
    t = np.linspace(0.0, 40.0, 8001)
    paradas = [(0.0, 5.0), (15.0, 25.0), (35.0, 40.0)]
    velocidad = np.where((t > 5) & (t < 15), 2.0, 0.0) - np.where((t > 25) & (t < 35), 1.0, 0.0)

    resultados = bitacora.resultados_de_movimiento(t, velocidad, paradas)

    assert resultados["desplazamiento_m"] == pytest.approx(30.0, abs=0.05)   # 20 m + 10 m
    assert resultados["velocidad_max_ms"] == pytest.approx(2.0)
    assert resultados["duracion_tramos_s"] == "10.0 10.0"


def test_actualizar_bitacora_no_borra_lo_escrito_a_mano(tmp_path):
    ruta = tmp_path / "bitacora.csv"
    bitacora.actualizar_bitacora("sesion_001", "ascensor", {"duracion_s": 460.2}, ruta)
    tabla = bitacora.leer_bitacora(ruta)
    tabla.loc[0, "lugar"] = "Edificio de aulas"          # lo que escribiría el grupo
    tabla.to_csv(ruta, index=False)

    bitacora.actualizar_bitacora("sesion_001", "ascensor", {"velocidad_max_ms": 1.5}, ruta)
    bitacora.actualizar_bitacora("sesion_002", "metro", {"duracion_s": 458.3}, ruta)

    tabla = bitacora.leer_bitacora(ruta)
    assert list(tabla["sesion"]) == ["sesion_001", "sesion_002"]
    assert tabla.loc[0, "lugar"] == "Edificio de aulas"
    assert tabla.loc[0, "duracion_s"] == "460.2"
    assert tabla.loc[0, "velocidad_max_ms"] == "1.5"


def test_bitacora_rechaza_columnas_que_no_son_automaticas(tmp_path):
    with pytest.raises(ValueError, match="automática"):
        bitacora.actualizar_bitacora("sesion_001", "reposo", {"lugar": "x"}, tmp_path / "b.csv")


def test_las_sesiones_simuladas_van_a_otra_bitacora():
    assert bitacora.archivo_de_bitacora({"firmware_version": "simulador"}) == bitacora.ARCHIVO_BITACORA_SIMULADA
    assert bitacora.archivo_de_bitacora({"firmware_version": "0.1.0"}) == bitacora.ARCHIVO_BITACORA
