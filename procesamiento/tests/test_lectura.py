"""Pruebas de la lectura: conversión de valores crudos a unidades físicas."""

import numpy as np
import pandas as pd
import pytest

import config
from navinercial import formato, lectura
from simulador import escenarios, generar, modelo_sensor


def test_acelerometro_8192_lsb_es_un_g_estandar():
    assert lectura.accel_crudo_a_ms2(8192, rango_g=4) == pytest.approx(9.80665)
    assert lectura.accel_crudo_a_ms2(-4096, rango_g=4) == pytest.approx(-9.80665 / 2)
    assert lectura.accel_crudo_a_ms2(16384, rango_g=2) == pytest.approx(9.80665)


def test_giroscopio_65_5_lsb_es_un_grado_por_segundo():
    assert lectura.gyro_crudo_a_rads(65.5, rango_dps=500) == pytest.approx(np.pi / 180)
    assert lectura.gyro_crudo_a_rads(131 * 90, rango_dps=250) == pytest.approx(np.pi / 2)


def test_magnetometro_015_microteslas_por_lsb():
    assert lectura.mag_crudo_a_uT(100) == pytest.approx(15.0)


def test_tiempo_en_segundos_desde_la_primera_muestra():
    # 5 400 000 000 µs = 90 min: no cabe en 32 bits, pero la resta con enteros es exacta.
    t_us = np.array([5_400_000_000, 5_400_005_000], dtype=np.int64)

    t_s = lectura.us_a_segundos(t_us, t0_us=5_400_000_000)

    assert list(t_s) == pytest.approx([0.0, 0.005], abs=1e-12)


def _sesion_cruda_pequena(tmp_path):
    imu = pd.DataFrame({
        "seq": [0, 1, 2], "t_us": [2_000_000, 2_005_000, 2_010_000],
        "ax": [0, 0, 0], "ay": [0, 0, 0], "az": [8192, 8192, 8192],
        "gx": [131, 0, 0], "gy": [0, 0, 0], "gz": [0, 0, 0],
        "mx": [100, None, 200], "my": [0, None, 0], "mz": [0, None, 0],
    })
    baro = pd.DataFrame({"seq": [0], "t_us": [2_001_000],
                         "adc_T": [519888], "adc_P": [415148]})
    eventos = pd.DataFrame({"t_us": [2_007_500], "evento": [formato.EVENTO_BOTON]})
    formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)
    return tmp_path


def test_cargar_sesion_convierte_todas_las_tablas(tmp_path):
    sesion = lectura.cargar_sesion(_sesion_cruda_pequena(tmp_path))

    assert sesion.t0_us == 2_000_000
    assert list(sesion.imu["t_s"]) == pytest.approx([0.0, 0.005, 0.010])
    assert list(sesion.imu["az"]) == pytest.approx([9.80665] * 3)
    assert sesion.imu["gx"][0] == pytest.approx(np.radians(131 / 65.5))
    # Magnetómetro: 100 LSB = 15 µT, y la celda vacía queda como NaN.
    assert sesion.imu["mx"][0] == pytest.approx(15.0)
    assert np.isnan(sesion.imu["mx"][1])
    assert sesion.imu["mx"][2] == pytest.approx(30.0)
    # Barómetro: el ejemplo de la hoja de datos.
    assert sesion.baro["temperatura_C"][0] == pytest.approx(25.08, abs=0.005)
    assert sesion.baro["presion_Pa"][0] == pytest.approx(100653.27, abs=0.02)
    # Todas las tablas usan la misma referencia de tiempo.
    assert sesion.baro["t_s"][0] == pytest.approx(0.001)
    assert sesion.eventos["t_s"][0] == pytest.approx(0.0075)


def test_sesion_simulada_en_reposo_da_valores_fisicos_razonables(tmp_path):
    parametros = modelo_sensor.ParametrosSimulacion()
    simulada = generar.simular_sesion(escenarios.crear_reposo(duracion_s=20.0), parametros)
    generar.guardar_sesion_simulada(tmp_path, simulada)

    sesion = lectura.cargar_sesion(tmp_path)

    # Eje z: (1 + escala) · g + sesgo, con los valores que puso el simulador.
    esperado_az = (1 + config.SIM_ACCEL_ERROR_ESCALA[2]) * config.G_QUITO + config.SIM_ACCEL_SESGO_MS2[2]
    assert sesion.imu["az"].mean() == pytest.approx(esperado_az, abs=0.005)
    assert sesion.imu["gx"].mean() == pytest.approx(config.SIM_GYRO_SESGO_RADS[0], abs=2e-4)
    assert sesion.baro["presion_Pa"].mean() == pytest.approx(config.SIM_BARO_PRESION_BASE_PA, abs=1.0)
    assert sesion.baro["temperatura_C"].mean() == pytest.approx(
        config.SIM_BARO_TEMPERATURA_BASE_C, abs=0.01)


def test_sesion_sin_magnetometro_se_carga_con_nan(tmp_path):
    parametros = modelo_sensor.ParametrosSimulacion(tiene_magnetometro=False)
    simulada = generar.simular_sesion(escenarios.crear_reposo(duracion_s=2.0), parametros)
    generar.guardar_sesion_simulada(tmp_path, simulada)

    sesion = lectura.cargar_sesion(tmp_path)

    assert sesion.imu[lectura.COLUMNAS_MAG].isna().all().all()
    assert sesion.imu["az"].notna().all()


def test_ajuste_de_sensibilidad_del_magnetometro():
    # asa = 128 no cambia nada; asa = 192 aumenta 25 %: (192 - 128)/256 + 1 = 1,25.
    assert lectura.factor_ajuste_ak8963(128) == pytest.approx(1.0)
    assert lectura.factor_ajuste_ak8963(192) == pytest.approx(1.25)
    assert lectura.mag_crudo_a_uT(100, asa=192) == pytest.approx(100 * 0.15 * 1.25)


def test_cargar_sesion_aplica_ak8963_asa_si_esta_en_meta(tmp_path):
    cruda = formato.leer_sesion_cruda(_sesion_cruda_pequena(tmp_path))
    sin_ajuste = lectura.convertir_sesion(cruda)
    cruda.meta["ak8963_asa"] = [192, 128, 64]

    con_ajuste = lectura.convertir_sesion(cruda)

    for columna, factor in zip(["mx", "my", "mz"], [1.25, 1.0, 0.75]):
        np.testing.assert_allclose(con_ajuste.imu[columna], sin_ajuste.imu[columna] * factor)
