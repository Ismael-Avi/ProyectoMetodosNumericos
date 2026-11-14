"""Pruebas del modelo de error del sensor y de la generación de sesiones."""

import dataclasses

import numpy as np
import pytest

import config
from navinercial import bmp280, formato
from simulador import escenarios, generar, modelo_sensor

LSB_POR_MS2 = config.ACCEL_LSB_POR_G[config.ACCEL_RANGO_G] / config.G_ESTANDAR


def _parametros_sin_perdidas(**cambios):
    """Parámetros por defecto, pero sin muestras perdidas (para contar filas con exactitud)."""
    parametros = modelo_sensor.ParametrosSimulacion(**cambios)
    parametros.tiempo.prob_muestra_perdida = 0.0
    return parametros


# ---------------------------------------------------------------------------
# Piezas del modelo
# ---------------------------------------------------------------------------

def test_sin_ruido_el_modelo_es_escala_por_real_mas_sesgo():
    parametros = modelo_sensor.ParametrosTriaxial(
        sesgo=(0.1, -0.2, 0.3), error_escala=(0.01, 0.0, -0.02), ruido_std=0.0, deriva_std=0.0)
    real = np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 9.77]])

    medido = modelo_sensor.medir_triaxial(real, parametros, 0.005, np.random.default_rng(0))

    assert medido[0] == pytest.approx([1.01 * 1.0 + 0.1, 2.0 - 0.2, 0.98 * 3.0 + 0.3])
    assert medido[1] == pytest.approx([0.1, -0.2, 0.98 * 9.77 + 0.3])


def test_desalineacion_mezcla_los_ejes():
    # El eje x del sensor "ve" un 1 % de lo que pasa en el eje y.
    desalineacion = ((1.0, 0.01, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    parametros = modelo_sensor.ParametrosTriaxial(
        sesgo=(0, 0, 0), error_escala=(0, 0, 0), ruido_std=0.0, deriva_std=0.0,
        desalineacion=desalineacion)
    real = np.array([[0.0, 10.0, 0.0]])

    medido = modelo_sensor.medir_triaxial(real, parametros, 0.005, np.random.default_rng(0))

    assert medido[0] == pytest.approx([0.1, 10.0, 0.0])


def test_cuantizar_redondea_y_satura():
    cuentas = modelo_sensor.cuantizar_int16(np.array([0.0, 1.4, 1.6, -1.6, 1e6, -1e6]), 1.0)

    assert list(cuentas) == [0, 1, 2, -2, 32767, -32768]


def test_paseo_aleatorio_crece_como_raiz_del_tiempo():
    """Con muchos paseos, la desviación estándar al final debe ser std · √t."""
    rng = np.random.default_rng(1)
    dt, n_pasos, std = 0.01, 1000, 0.5        # tiempo total: 10 s

    finales = [modelo_sensor.paseo_aleatorio((n_pasos,), dt, std, rng)[-1] for _ in range(2000)]

    assert np.std(finales) == pytest.approx(std * np.sqrt(10.0), rel=0.05)


def test_tiempos_tienen_la_frecuencia_real_y_el_jitter_pedidos():
    rng = np.random.default_rng(2)

    t = modelo_sensor.generar_tiempos_s(100.0, 199.96, 50.0, rng)
    intervalos = np.diff(t)

    assert len(t) == 19996
    assert 1.0 / intervalos.mean() == pytest.approx(199.96, rel=1e-5)
    # Cada intervalo es la diferencia de dos jitter independientes: su desviación es √2 · 50 µs.
    assert intervalos.std() == pytest.approx(np.sqrt(2) * 50e-6, rel=0.05)


def test_mascara_pierde_la_fraccion_esperada():
    conservadas = modelo_sensor.mascara_muestras_conservadas(
        200_000, 0.01, np.random.default_rng(3))

    assert conservadas[0]
    assert (~conservadas).mean() == pytest.approx(0.01, rel=0.1)


# ---------------------------------------------------------------------------
# Sesión completa
# ---------------------------------------------------------------------------

def test_reposo_simulado_tiene_el_sesgo_y_la_escala_esperados():
    """El promedio de cada eje en reposo debe ser (1 + escala) · real + sesgo, en LSB."""
    parametros = _parametros_sin_perdidas()
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=30.0), parametros)

    sesgo = np.array(parametros.acelerometro.sesgo)
    escala = 1.0 + np.array(parametros.acelerometro.error_escala)
    esperado_ms2 = escala * np.array([0.0, 0.0, config.G_QUITO]) + sesgo
    promedio_ms2 = sesion.imu[["ax", "ay", "az"]].mean().to_numpy() / LSB_POR_MS2

    # Con 6000 muestras, el error del promedio es ruido/√6000 ≈ 0,0004 m/s².
    assert promedio_ms2 == pytest.approx(esperado_ms2, abs=0.003)


def test_cantidad_de_muestras_y_marcas_de_tiempo():
    parametros = _parametros_sin_perdidas()
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=20.0), parametros)

    assert len(sesion.imu) == int(20.0 * config.SIM_FS_IMU_REAL_HZ)
    assert len(sesion.baro) == int(20.0 * config.SIM_FS_BARO_REAL_HZ)
    assert list(sesion.imu["seq"]) == list(range(len(sesion.imu)))
    assert sesion.imu["t_us"].is_monotonic_increasing
    assert abs(sesion.imu["t_us"][0] - config.SIM_T_INICIAL_US) < 1000


def test_muestras_perdidas_dejan_saltos_en_seq():
    parametros = modelo_sensor.ParametrosSimulacion()
    parametros.tiempo.prob_muestra_perdida = 0.01
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=20.0), parametros)

    saltos = np.diff(sesion.imu["seq"])
    n_perdidas = int((saltos - 1).sum())

    assert n_perdidas > 10
    assert len(sesion.imu) + n_perdidas == sesion.imu["seq"].iloc[-1] + 1
    assert len(sesion.verdad) == len(sesion.imu)          # la verdad pierde las mismas filas
    assert list(sesion.verdad["seq"]) == list(sesion.imu["seq"])


def test_magnetometro_tiene_lectura_una_de_cada_dos_muestras():
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=5.0),
                                    _parametros_sin_perdidas())

    hay_lectura = sesion.imu["mx"].notna().to_numpy()

    assert hay_lectura[0::2].all()
    assert not hay_lectura[1::2].any()


def test_sin_magnetometro_las_columnas_quedan_vacias():
    parametros = _parametros_sin_perdidas(tiene_magnetometro=False)
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=5.0), parametros)

    assert sesion.meta["tiene_magnetometro"] is False
    assert sesion.meta["chip_whoami"] == config.WHOAMI_MPU6500
    assert sesion.imu[formato.COLUMNAS_MAG].isna().all().all()


def test_barometro_simulado_recupera_la_presion_verdadera():
    """Compensar los crudos del barómetro debe dar la presión verdadera más el ruido."""
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=60.0),
                                    _parametros_sin_perdidas())
    calib = sesion.meta["bmp280_calib"]

    temperatura, presion = bmp280.compensar(
        sesion.baro["adc_T"].to_numpy(), sesion.baro["adc_P"].to_numpy(), calib)
    error_presion = presion - sesion.verdad_baro["presion_Pa"].to_numpy()
    error_temperatura = temperatura - sesion.verdad_baro["temperatura_C"].to_numpy()

    assert abs(error_presion.mean()) < 0.2
    assert error_presion.std() == pytest.approx(config.SIM_BARO_RUIDO_PRESION_STD_PA, rel=0.15)
    assert abs(error_temperatura.mean()) < 0.002


def test_marea_barometrica_es_una_sinusoide_de_doce_horas():
    barometro = modelo_sensor.ParametrosBarometro(marea_amplitud_Pa=100.0, marea_fase_h=0.0)
    horas = np.array([0.0, 3.0, 6.0, 12.0])

    marea = modelo_sensor.marea_barometrica(horas, barometro)

    # Empieza en el máximo: baja A en 3 h, baja 2A en 6 h y vuelve al inicio en 12 h.
    assert marea == pytest.approx([0.0, -100.0, -200.0, 0.0], abs=1e-9)


def test_marea_con_amplitud_cero_no_cambia_la_presion():
    barometro = modelo_sensor.ParametrosBarometro(marea_amplitud_Pa=0.0)

    assert np.all(modelo_sensor.marea_barometrica(np.linspace(0, 24, 50), barometro) == 0.0)


def test_la_presion_verdadera_incluye_la_marea():
    """Sin tendencia ni paseo aleatorio, la presión verdadera es la base más la marea."""
    parametros = modelo_sensor.ParametrosSimulacion()
    parametros.barometro.deriva_clima_Pa_por_hora = 0.0
    parametros.barometro.paseo_clima_std = 0.0
    parametros.barometro.marea_amplitud_Pa = 100.0
    t_s = np.array([0.0, 6 * 3600.0])

    _, verdad_baro = modelo_sensor.simular_barometro(
        t_s, parametros, config.BMP280_CALIB_EJEMPLO, np.random.default_rng(0))

    base = config.SIM_BARO_PRESION_BASE_PA
    assert list(verdad_baro["presion_Pa"]) == pytest.approx([base, base - 200.0])


def test_la_misma_semilla_da_los_mismos_datos_y_otra_semilla_no():
    escenario = escenarios.crear_reposo(duracion_s=5.0)

    sesion_a = generar.simular_sesion(escenario, modelo_sensor.ParametrosSimulacion(semilla=1))
    sesion_b = generar.simular_sesion(escenario, modelo_sensor.ParametrosSimulacion(semilla=1))
    sesion_c = generar.simular_sesion(escenario, modelo_sensor.ParametrosSimulacion(semilla=2))

    assert sesion_a.imu.equals(sesion_b.imu)
    assert sesion_a.baro.equals(sesion_b.baro)
    assert not sesion_a.imu.equals(sesion_c.imu)


def test_seis_caras_simulado_no_satura_y_la_verdad_esta_alineada():
    escenario = escenarios.crear_seis_caras(duracion_cara_s=5.0, duracion_giro_s=2.0)
    sesion = generar.simular_sesion(escenario, _parametros_sin_perdidas())

    crudos = sesion.imu[["ax", "ay", "az", "gx", "gy", "gz"]]
    assert crudos.max().max() < formato.INT16_MAX
    assert crudos.min().min() > formato.INT16_MIN

    # En la cara "-x" el acelerómetro debe medir cerca de -g en el eje x.
    en_cara = (sesion.verdad["tramo"] == "-x").to_numpy()
    ax_ms2 = sesion.imu["ax"][en_cara].mean() / LSB_POR_MS2
    assert ax_ms2 == pytest.approx(-config.G_QUITO, abs=0.3)


def test_guardar_y_leer_una_sesion_simulada(tmp_path):
    sesion = generar.simular_sesion(escenarios.crear_reposo(duracion_s=5.0))

    generar.guardar_sesion_simulada(tmp_path, sesion)
    leida = formato.leer_sesion_cruda(tmp_path)

    assert leida.meta == sesion.meta
    assert len(leida.imu) == len(sesion.imu)
    assert list(leida.imu["az"]) == list(sesion.imu["az"])
    assert len(leida.eventos) == 0
    for nombre in [generar.ARCHIVO_VERDAD, generar.ARCHIVO_VERDAD_BARO,
                   generar.ARCHIVO_VERDAD_PARAMETROS]:
        assert (tmp_path / nombre).is_file()


def test_los_parametros_se_pueden_guardar_como_json():
    import json

    texto = json.dumps(dataclasses.asdict(modelo_sensor.ParametrosSimulacion()))

    assert json.loads(texto)["acelerometro"]["sesgo"] == list(config.SIM_ACCEL_SESGO_MS2)
