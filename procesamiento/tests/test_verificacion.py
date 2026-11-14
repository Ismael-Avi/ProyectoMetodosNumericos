"""Pruebas de la verificación: muestras perdidas, frecuencia real y jitter."""

import numpy as np
import pandas as pd
import pytest

import config
from navinercial import lectura, verificacion
from scripts import verificar_sesion
from simulador import escenarios, generar, modelo_sensor


def _muestreo_perfecto(n_muestras=2000, fs_hz=200.0):
    seq = np.arange(n_muestras)
    return seq, seq / fs_hz


def _tabla(seq, t_s):
    return pd.DataFrame({"seq": seq, "t_s": t_s})


# ---------------------------------------------------------------------------
# Muestras perdidas
# ---------------------------------------------------------------------------

def test_muestreo_perfecto_no_tiene_huecos():
    seq, t_s = _muestreo_perfecto()

    assert len(verificacion.buscar_huecos(seq, t_s)) == 0


def test_detecta_muestras_perdidas_con_su_posicion_y_cantidad():
    seq, t_s = _muestreo_perfecto()
    # Se pierden la muestra 100 y las muestras 500, 501 y 502.
    conservar = ~np.isin(seq, [100, 500, 501, 502])

    huecos = verificacion.buscar_huecos(seq[conservar], t_s[conservar])

    assert list(huecos["seq_anterior"]) == [99, 499]
    assert list(huecos["seq_siguiente"]) == [101, 503]
    assert list(huecos["perdidas_seq"]) == [1, 3]
    assert list(huecos["perdidas_tiempo"]) == [1, 3]
    assert huecos["intervalo_s"][1] == pytest.approx(4 / 200.0)


def test_detecta_un_salto_de_tiempo_aunque_seq_no_salte():
    """Si el firmware se detiene un momento y no aumenta seq, el reloj lo delata."""
    seq, t_s = _muestreo_perfecto()
    t_s = t_s.copy()
    t_s[300:] += 0.050           # pausa de 50 ms = 10 períodos de 5 ms

    huecos = verificacion.buscar_huecos(seq, t_s)

    assert len(huecos) == 1
    assert huecos["perdidas_seq"][0] == 0
    assert huecos["perdidas_tiempo"][0] == 10


def test_el_jitter_normal_no_se_confunde_con_un_hueco():
    rng = np.random.default_rng(0)
    seq, t_s = _muestreo_perfecto(n_muestras=50_000)
    t_s = t_s + rng.normal(0.0, 200e-6, len(t_s))     # jitter grande: 200 µs

    assert len(verificacion.buscar_huecos(seq, t_s)) == 0


# ---------------------------------------------------------------------------
# Frecuencia real e intervalo
# ---------------------------------------------------------------------------

def test_frecuencia_real_no_se_altera_por_muestras_perdidas():
    seq, t_s = _muestreo_perfecto(fs_hz=199.96)
    conservar = ~np.isin(seq, [100, 500, 501, 502])

    assert verificacion.frecuencia_real(seq[conservar], t_s[conservar]) == pytest.approx(199.96)


def test_frecuencia_al_inicio_y_al_final_cuando_el_reloj_cambia():
    """Primera mitad a 200 Hz y segunda mitad a 198 Hz."""
    t_rapido = np.arange(20_000) / 200.0                       # 100 s
    t_lento = t_rapido[-1] + np.arange(1, 19_801) / 198.0      # otros 100 s
    t_s = np.concatenate([t_rapido, t_lento])
    seq = np.arange(len(t_s))

    fs_inicio, fs_final, ventana = verificacion.frecuencia_inicio_y_final(seq, t_s, ventana_s=30.0)

    assert ventana == 30.0
    assert fs_inicio == pytest.approx(200.0, rel=1e-6)
    assert fs_final == pytest.approx(198.0, rel=1e-6)


def test_la_ventana_se_acorta_si_el_registro_es_corto():
    seq, t_s = _muestreo_perfecto(n_muestras=2001)             # 10 s

    _, _, ventana = verificacion.frecuencia_inicio_y_final(seq, t_s, ventana_s=60.0)

    assert ventana == pytest.approx(5.0)


def test_frecuencia_por_ventanas():
    seq, t_s = _muestreo_perfecto(n_muestras=20_000)           # 100 s

    centros, frecuencias = verificacion.frecuencia_por_ventanas(seq, t_s, ventana_s=10.0)

    assert len(centros) == 10
    assert centros[0] == pytest.approx(5.0)
    assert frecuencias == pytest.approx([200.0] * 10, rel=1e-3)


def test_estadisticas_del_intervalo_miden_el_jitter():
    rng = np.random.default_rng(1)
    seq, t_s = _muestreo_perfecto(n_muestras=100_000)
    t_s = t_s + rng.normal(0.0, 50e-6, len(t_s))

    estadisticas = verificacion.estadisticas_intervalo(seq, t_s)

    assert estadisticas["media_us"] == pytest.approx(5000.0, abs=1.0)
    # El intervalo es la diferencia de dos jitter independientes: desviación √2 · 50 µs.
    assert estadisticas["std_us"] == pytest.approx(np.sqrt(2) * 50.0, rel=0.03)
    assert estadisticas["min_us"] < 5000.0 < estadisticas["max_us"]


def test_los_huecos_no_cuentan_en_las_estadisticas_del_intervalo():
    seq, t_s = _muestreo_perfecto()
    conservar = ~np.isin(seq, [100, 500, 501, 502])

    estadisticas = verificacion.estadisticas_intervalo(seq[conservar], t_s[conservar])

    assert estadisticas["max_us"] == pytest.approx(5000.0)


def test_verificar_tabla_cuenta_seq_y_tiempo_que_no_aumentan():
    seq, t_s = _muestreo_perfecto()
    seq = seq.copy()
    t_s = t_s.copy()
    seq[1000:] -= 1000            # el contador se reinicia a mitad del registro
    t_s[1500] = t_s[1499]         # una marca de tiempo repetida

    resultado = verificacion.verificar_tabla("imu", _tabla(seq, t_s), 200.0)

    assert resultado.n_seq_no_creciente == 1
    assert resultado.n_tiempo_no_creciente == 1


# ---------------------------------------------------------------------------
# Sesión simulada completa
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sesion_con_perdidas(tmp_path_factory):
    """Reposo de 3 minutos con bastantes muestras perdidas, guardado y vuelto a cargar."""
    carpeta = tmp_path_factory.mktemp("sesion")
    parametros = modelo_sensor.ParametrosSimulacion()
    parametros.tiempo.prob_muestra_perdida = 1e-3
    simulada = generar.simular_sesion(escenarios.crear_reposo(duracion_s=180.0), parametros)
    generar.guardar_sesion_simulada(carpeta, simulada)
    return carpeta, simulada


def test_verificacion_encuentra_exactamente_las_perdidas_del_simulador(sesion_con_perdidas):
    carpeta, simulada = sesion_con_perdidas
    n_generadas = int(180.0 * config.SIM_FS_IMU_REAL_HZ)
    n_perdidas = n_generadas - len(simulada.imu)

    resultado = verificacion.verificar_sesion(lectura.cargar_sesion(carpeta))["imu"]

    assert n_perdidas > 10
    # La última muestra también pudo perderse, y esa no deja hueco.
    assert resultado.n_perdidas_seq in (n_perdidas, n_perdidas - 1)
    assert resultado.n_perdidas_tiempo == resultado.n_perdidas_seq


def test_verificacion_mide_la_frecuencia_real_y_no_la_nominal(sesion_con_perdidas):
    carpeta, _ = sesion_con_perdidas

    resultados = verificacion.verificar_sesion(lectura.cargar_sesion(carpeta))

    imu, baro = resultados["imu"], resultados["baro"]
    assert imu.fs_nominal_hz == 200
    assert imu.fs_media_hz == pytest.approx(config.SIM_FS_IMU_REAL_HZ, abs=0.002)
    assert imu.fs_inicio_hz == pytest.approx(config.SIM_FS_IMU_REAL_HZ, abs=0.005)
    assert imu.fs_final_hz == pytest.approx(config.SIM_FS_IMU_REAL_HZ, abs=0.005)
    assert baro.fs_media_hz == pytest.approx(config.SIM_FS_BARO_REAL_HZ, abs=0.002)
    assert imu.intervalo["std_us"] == pytest.approx(np.sqrt(2) * config.SIM_JITTER_STD_US, rel=0.05)


def test_reporte_menciona_lo_importante(sesion_con_perdidas):
    carpeta, _ = sesion_con_perdidas
    sesion = lectura.cargar_sesion(carpeta)
    resultados = verificacion.verificar_sesion(sesion)

    reporte = verificacion.texto_reporte(sesion, resultados)

    assert "Frecuencia real al inicio" in reporte
    assert "Frecuencia real al final" in reporte
    assert f"Muestras perdidas según seq:    {resultados['imu'].n_perdidas_seq}" in reporte
    assert "Sin muestras perdidas: NO CUMPLE" in reporte


def test_el_script_guarda_el_reporte_y_las_graficas(sesion_con_perdidas, tmp_path):
    carpeta, _ = sesion_con_perdidas

    verificar_sesion.verificar_y_guardar(carpeta, tmp_path)

    for nombre in ["reporte.txt", "intervalos.png", "frecuencia.png", "senales.png"]:
        assert (tmp_path / nombre).stat().st_size > 0, nombre
