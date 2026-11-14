"""Pruebas de la caracterización, el detector de quietud y la calibración de seis caras."""

import numpy as np
import pytest

import config
from navinercial import calibracion, lectura
from scripts import calibrar_seis_caras, caracterizar_reposo
from simulador import escenarios, generar


def _cargar_simulada(carpeta, escenario, parametros=None):
    """Simula un escenario, lo guarda en la carpeta y lo carga en unidades físicas."""
    simulada = generar.simular_sesion(escenario, parametros)
    generar.guardar_sesion_simulada(carpeta, simulada)
    return lectura.cargar_sesion(carpeta)


@pytest.fixture(scope="module")
def carpeta_seis_caras(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("seis_caras")
    _cargar_simulada(carpeta, escenarios.crear_seis_caras(duracion_cara_s=30.0))
    return carpeta


@pytest.fixture(scope="module")
def carpeta_reposo(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("reposo")
    _cargar_simulada(carpeta, escenarios.crear_reposo(duracion_s=120.0))
    return carpeta


# ---------------------------------------------------------------------------
# Caracterización en reposo
# ---------------------------------------------------------------------------

def test_ruido_por_diferencias_ignora_la_deriva_lenta():
    rng = np.random.default_rng(0)
    deriva = np.linspace(0.0, 50.0, 100_000)             # sube 50 unidades durante el registro
    senal = deriva + rng.normal(0.0, 1.3, len(deriva))

    assert np.std(senal) > 10.0                           # la desviación directa se infla
    assert calibracion.ruido_por_diferencias(senal) == pytest.approx(1.3, rel=0.02)


def test_caracterizacion_recupera_el_sesgo_del_giroscopio_y_el_ruido(carpeta_reposo):
    tabla = calibracion.caracterizar_reposo(lectura.cargar_sesion(carpeta_reposo))

    for i, columna in enumerate(lectura.COLUMNAS_GYRO):
        assert tabla.loc[columna, "media"] == pytest.approx(config.SIM_GYRO_SESGO_RADS[i], abs=1e-4)
        assert tabla.loc[columna, "ruido"] == pytest.approx(config.SIM_GYRO_RUIDO_STD_RADS, rel=0.05)
    for columna in lectura.COLUMNAS_ACCEL:
        assert tabla.loc[columna, "ruido"] == pytest.approx(config.SIM_ACCEL_RUIDO_STD_MS2, rel=0.05)
    assert tabla.loc["presion_Pa", "ruido"] == pytest.approx(
        config.SIM_BARO_RUIDO_PRESION_STD_PA, rel=0.1)


def test_desviacion_allan_del_ruido_blanco_baja_como_raiz_de_tau():
    rng = np.random.default_rng(1)
    fs, sigma = 200.0, 0.03
    ruido = rng.normal(0.0, sigma, 400_000)

    taus, desviaciones = calibracion.desviacion_allan(ruido, fs)

    # Para ruido blanco: σ(τ) = σ / √(número de muestras promediadas) = σ / √(τ · fs).
    esperadas = sigma / np.sqrt(taus * fs)
    cortos = taus < 20.0          # con τ largo hay pocos grupos y la estimación es imprecisa
    assert desviaciones[cortos] == pytest.approx(esperadas[cortos], rel=0.15)


# ---------------------------------------------------------------------------
# Detector de quietud
# ---------------------------------------------------------------------------

def test_en_reposo_el_detector_dice_quieto(carpeta_reposo):
    sesion = lectura.cargar_sesion(carpeta_reposo)

    quieto = calibracion.detectar_quietud(sesion.imu)

    assert quieto.mean() > 0.99


def test_en_seis_caras_el_detector_separa_caras_y_giros(carpeta_seis_caras):
    sesion = lectura.cargar_sesion(carpeta_seis_caras)

    quieto = calibracion.detectar_quietud(sesion.imu)
    tramos = calibracion.tramos_de_quietud(quieto, sesion.imu["t_s"].to_numpy(),
                                           duracion_minima_s=10.0)

    assert len(tramos) == 6
    for inicio, fin in tramos:
        duracion = sesion.imu["t_s"][fin - 1] - sesion.imu["t_s"][inicio]
        assert 28.0 < duracion < 32.0


def test_tramos_de_quietud_con_un_arreglo_pequeno():
    quieto = np.array([True, True, False, True, True, True, False, True])
    t_s = np.arange(len(quieto), dtype=float)

    assert calibracion.tramos_de_quietud(quieto, t_s) == [(0, 2), (3, 6), (7, 8)]
    assert calibracion.tramos_de_quietud(quieto, t_s, duracion_minima_s=2.0) == [(3, 6)]


# ---------------------------------------------------------------------------
# Calibración de seis caras
# ---------------------------------------------------------------------------

def test_nombre_de_cara():
    g = config.G_QUITO
    assert calibracion.nombre_de_cara(np.array([0.1, -0.2, 9.9])) == "+z"
    assert calibracion.nombre_de_cara(np.array([-9.6, 0.3, 0.1])) == "-x"
    # Inclinado 45°: ningún eje mide el 80 % de g.
    assert calibracion.nombre_de_cara(np.array([g * 0.707, g * 0.707, 0.0])) is None


def test_seis_caras_recupera_el_sesgo_y_la_escala_del_simulador(carpeta_seis_caras):
    sesion = lectura.cargar_sesion(carpeta_seis_caras)

    resultado, caras = calibracion.calibrar_seis_caras(sesion.imu)

    assert sorted(caras["cara"]) == sorted(escenarios.CARAS)
    escala_real = 1.0 + np.array(config.SIM_ACCEL_ERROR_ESCALA)
    # Tolerancias: unas 10 veces el error esperado del promedio (ruido/√n ≈ 0,0004 m/s²).
    assert resultado.sesgo_accel == pytest.approx(config.SIM_ACCEL_SESGO_MS2, abs=0.004)
    assert resultado.escala_accel == pytest.approx(escala_real, abs=0.0005)
    assert resultado.sesgo_gyro == pytest.approx(config.SIM_GYRO_SESGO_RADS, abs=1e-4)


def test_despues_de_calibrar_la_gravedad_mide_g_en_todas_las_caras(carpeta_seis_caras):
    sesion = lectura.cargar_sesion(carpeta_seis_caras)
    resultado, caras = calibracion.calibrar_seis_caras(sesion.imu)

    calibrada = calibracion.aplicar_calibracion(sesion, resultado)

    t = sesion.imu["t_s"].to_numpy()
    for _, cara in caras.iterrows():
        en_cara = (t >= cara["t_inicio_s"]) & (t <= cara["t_fin_s"])
        antes = calibracion.magnitud(sesion.imu[en_cara], lectura.COLUMNAS_ACCEL).mean()
        despues = calibracion.magnitud(calibrada.imu[en_cara], lectura.COLUMNAS_ACCEL).mean()
        assert abs(antes - config.G_QUITO) > 0.02, cara["cara"]      # sin calibrar no coincide
        assert despues == pytest.approx(config.G_QUITO, abs=0.005), cara["cara"]


def test_aplicar_calibracion_invierte_el_modelo_y_no_modifica_el_original(carpeta_reposo):
    sesion = lectura.cargar_sesion(carpeta_reposo)
    original = sesion.imu["az"].copy()
    resultado = calibracion.Calibracion(
        sesgo_accel=[0.0, 0.0, 0.25], escala_accel=[1.0, 1.0, 1.015],
        sesgo_gyro=[0.0, 0.0, 0.0], g=config.G_QUITO)

    calibrada = calibracion.aplicar_calibracion(sesion, resultado)

    assert calibrada.imu["az"].to_numpy() == pytest.approx((original.to_numpy() - 0.25) / 1.015)
    assert sesion.imu["az"].equals(original)
    assert calibrada.imu["az"].mean() == pytest.approx(config.G_QUITO, abs=0.005)


def test_si_falta_una_cara_da_un_error_claro(carpeta_reposo):
    sesion = lectura.cargar_sesion(carpeta_reposo)      # solo tiene la cara +z

    with pytest.raises(ValueError, match="Faltan"):
        calibracion.calibrar_seis_caras(sesion.imu)


def test_guardar_y_cargar_la_calibracion(tmp_path):
    resultado = calibracion.Calibracion([0.1, 0.2, 0.3], [1.01, 0.99, 1.0], [0.0, 0.0, 0.0],
                                        g=9.77, origen="prueba")

    ruta = calibracion.guardar_calibracion(resultado, tmp_path / "cal" / "calibracion.json")

    assert calibracion.cargar_calibracion(ruta) == resultado


def test_seis_caras_con_mesa_inclinada_sigue_recuperando_el_sesgo(tmp_path):
    """Una mesa inclinada 1 grado cambia la escala en cos(1°), pero casi no afecta al sesgo."""
    escenario = escenarios.crear_seis_caras(duracion_cara_s=30.0, alabeo_grados=1.0)
    sesion = _cargar_simulada(tmp_path, escenario)

    resultado, _ = calibracion.calibrar_seis_caras(sesion.imu)

    assert resultado.sesgo_accel == pytest.approx(config.SIM_ACCEL_SESGO_MS2, abs=0.004)


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

def test_script_de_reposo_guarda_reporte_y_graficas(carpeta_reposo, tmp_path):
    reporte = caracterizar_reposo.caracterizar_y_guardar(carpeta_reposo, tmp_path)

    assert "Detector de quietud" in reporte
    for nombre in ["reporte.txt", "ruido.png", "allan.png"]:
        assert (tmp_path / nombre).stat().st_size > 0, nombre


def test_script_de_seis_caras_guarda_calibracion_reporte_y_grafica(carpeta_seis_caras, tmp_path):
    ruta_json = tmp_path / "calibracion.json"

    reporte = calibrar_seis_caras.calibrar_y_guardar(carpeta_seis_caras, tmp_path, ruta_json)

    assert "Comparación con los valores que puso el simulador" in reporte
    assert calibracion.cargar_calibracion(ruta_json).g == config.G_QUITO
    for nombre in ["reporte.txt", "caras.png"]:
        assert (tmp_path / nombre).stat().st_size > 0, nombre
