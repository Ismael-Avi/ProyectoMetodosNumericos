"""Modelo de error de los sensores: convierte el movimiento verdadero en lecturas crudas.

Modelo de cada eje del acelerómetro y del giroscopio:

    medido = (1 + error_escala) · real + sesgo + deriva(t) + ruido

- sesgo: valor constante que el sensor suma siempre.
- error_escala: el sensor mide un poco de más o de menos (0,01 = 1 % de más).
- deriva(t): el sesgo cambia lentamente; se modela como un paseo aleatorio.
- ruido: ruido blanco gaussiano, distinto en cada muestra.
- desalineación (opcional): los ejes del sensor no son exactamente perpendiculares, así que
  cada eje "ve" una pequeña parte de los otros. Se aplica una matriz de 3x3 al valor real.

Después se pasa a unidades del sensor (LSB), se redondea a entero (cuantización) y se
recorta al rango de int16 (saturación).

Todos los valores por defecto son SINTÉTICOS y están en config.py.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from navinercial import barometro, bmp280, formato
from simulador import escenarios


@dataclass
class ParametrosTriaxial:
    """Errores de un sensor de tres ejes. Unidades: m/s² (acelerómetro) o rad/s (giroscopio)."""

    sesgo: tuple            # un valor por eje
    error_escala: tuple     # un valor por eje, sin unidades
    ruido_std: float        # desviación estándar del ruido blanco
    deriva_std: float       # paseo aleatorio del sesgo, en unidades/√s (0 = sin deriva)
    desalineacion: tuple = None   # matriz 3x3 cercana a la identidad (None = sin desalineación)


@dataclass
class ParametrosMagnetometro:
    sesgo_uT: tuple = config.SIM_MAG_SESGO_UT
    ruido_std_uT: float = config.SIM_MAG_RUIDO_STD_UT
    fs_hz: float = config.FS_MAG_NOMINAL_HZ


@dataclass
class ParametrosBarometro:
    presion_base_Pa: float = config.SIM_BARO_PRESION_BASE_PA
    temperatura_base_C: float = config.SIM_BARO_TEMPERATURA_BASE_C
    ruido_presion_std_Pa: float = config.SIM_BARO_RUIDO_PRESION_STD_PA
    ruido_temperatura_std_C: float = config.SIM_BARO_RUIDO_TEMPERATURA_STD_C
    deriva_clima_Pa_por_hora: float = config.SIM_BARO_DERIVA_CLIMA_PA_POR_HORA
    paseo_clima_std: float = config.SIM_BARO_PASEO_CLIMA_STD            # Pa/√s
    deriva_temperatura_C_por_hora: float = config.SIM_BARO_DERIVA_TEMPERATURA_C_POR_HORA
    marea_amplitud_Pa: float = config.SIM_BARO_MAREA_AMPLITUD_PA        # 0 = sin marea
    marea_periodo_h: float = config.SIM_BARO_MAREA_PERIODO_H
    marea_fase_h: float = config.SIM_BARO_MAREA_FASE_H


@dataclass
class ParametrosTiempo:
    t_inicial_us: int = config.SIM_T_INICIAL_US
    jitter_std_us: float = config.SIM_JITTER_STD_US
    prob_muestra_perdida: float = config.SIM_PROB_MUESTRA_PERDIDA
    fs_imu_real_hz: float = config.SIM_FS_IMU_REAL_HZ
    fs_baro_real_hz: float = config.SIM_FS_BARO_REAL_HZ


def _acelerometro_por_defecto():
    return ParametrosTriaxial(
        sesgo=config.SIM_ACCEL_SESGO_MS2,
        error_escala=config.SIM_ACCEL_ERROR_ESCALA,
        ruido_std=config.SIM_ACCEL_RUIDO_STD_MS2,
        deriva_std=config.SIM_ACCEL_DERIVA_STD,
    )


def _giroscopio_por_defecto():
    return ParametrosTriaxial(
        sesgo=config.SIM_GYRO_SESGO_RADS,
        error_escala=config.SIM_GYRO_ERROR_ESCALA,
        ruido_std=config.SIM_GYRO_RUIDO_STD_RADS,
        deriva_std=config.SIM_GYRO_DERIVA_STD,
    )


@dataclass
class ParametrosSimulacion:
    """Todos los parámetros de una simulación. Con la misma semilla se obtienen los mismos datos."""

    semilla: int = config.SEMILLA_POR_DEFECTO
    tiene_magnetometro: bool = True
    acelerometro: ParametrosTriaxial = field(default_factory=_acelerometro_por_defecto)
    giroscopio: ParametrosTriaxial = field(default_factory=_giroscopio_por_defecto)
    magnetometro: ParametrosMagnetometro = field(default_factory=ParametrosMagnetometro)
    barometro: ParametrosBarometro = field(default_factory=ParametrosBarometro)
    tiempo: ParametrosTiempo = field(default_factory=ParametrosTiempo)


# ---------------------------------------------------------------------------
# Piezas del modelo
# ---------------------------------------------------------------------------

def generar_tiempos_s(duracion_s, fs_real_hz, jitter_std_us, rng):
    """Instantes de muestreo, en segundos desde el inicio del registro.

    La muestra k se toma en t_k = k / fs_real + jitter_k, con jitter gaussiano. El jitter
    representa que el ESP32 no lee el sensor exactamente cada período; la marca de tiempo sí
    registra el instante en que se leyó.
    """
    n_muestras = int(math.floor(duracion_s * fs_real_hz))
    t_ideal = np.arange(n_muestras) / fs_real_hz
    jitter_s = rng.normal(0.0, jitter_std_us * 1e-6, n_muestras)
    return t_ideal + jitter_s


def paseo_aleatorio(forma, dt_s, std_por_raiz_s, rng):
    """Paseo aleatorio: suma acumulada de pasos gaussianos independientes.

    Cada paso tiene desviación estándar std_por_raiz_s · √dt, de modo que después de un
    tiempo t la desviación estándar del paseo es std_por_raiz_s · √t.

    forma: (n_muestras,) o (n_muestras, 3). Devuelve un arreglo con esa forma.
    """
    pasos = rng.normal(0.0, std_por_raiz_s * math.sqrt(dt_s), forma)
    return np.cumsum(pasos, axis=0)


def medir_triaxial(real, parametros, dt_s, rng):
    """Aplica el modelo de error a una señal de tres ejes (arreglo de n x 3).

    medido = (1 + error_escala) · (D · real) + sesgo + deriva(t) + ruido
    Devuelve el valor medido en las mismas unidades físicas que la entrada.
    """
    if parametros.desalineacion is not None:
        real = real @ np.array(parametros.desalineacion).T   # D · real, fila por fila
    escala = 1.0 + np.array(parametros.error_escala)
    deriva = paseo_aleatorio(real.shape, dt_s, parametros.deriva_std, rng)
    ruido = rng.normal(0.0, parametros.ruido_std, real.shape)
    return escala * real + np.array(parametros.sesgo) + deriva + ruido


def cuantizar_int16(valor_fisico, lsb_por_unidad):
    """Pasa de unidades físicas al entero de 16 bits que entregaría el sensor.

    Cuantización: se redondea al entero más cercano (se pierde lo que sea menor que 1 LSB).
    Saturación: lo que no cabe en int16 se recorta a -32768 o 32767.
    """
    cuentas = np.rint(valor_fisico * lsb_por_unidad)
    return np.clip(cuentas, formato.INT16_MIN, formato.INT16_MAX).astype(np.int64)


def mascara_muestras_conservadas(n_muestras, prob_perdida, rng):
    """Arreglo de True/False: False en las muestras que el dispositivo "perdió".

    Cada muestra se pierde con probabilidad prob_perdida, de forma independiente. La primera
    muestra nunca se pierde.
    """
    conservadas = rng.random(n_muestras) >= prob_perdida
    conservadas[0] = True
    return conservadas


# ---------------------------------------------------------------------------
# Sensores completos
# ---------------------------------------------------------------------------

def _simular_magnetometro(seq, campo_real_uT, parametros, rng):
    """Lecturas crudas del magnetómetro, con celdas vacías donde no hay lectura nueva.

    El magnetómetro muestrea más lento que el acelerómetro: solo hay lectura nueva cada
    "paso" muestras (con 200 Hz y 100 Hz, una de cada dos).
    """
    p = parametros.magnetometro
    medido = campo_real_uT + np.array(p.sesgo_uT) + rng.normal(0.0, p.ruido_std_uT, campo_real_uT.shape)
    cuentas = cuantizar_int16(medido, 1.0 / config.MAG_UT_POR_LSB).astype(float)

    paso = round(config.FS_IMU_NOMINAL_HZ / p.fs_hz)
    hay_lectura = (seq % paso == 0) & parametros.tiene_magnetometro
    cuentas[~hay_lectura] = np.nan   # NaN = celda vacía
    return cuentas


def simular_imu(t_s, estado, parametros, rng):
    """Tabla imu.csv (todas las muestras, sin quitar las perdidas) a partir del estado verdadero.

    t_s: instantes de muestreo en segundos desde el inicio del registro.
    estado: tabla que devuelve Escenario.estado(t_s).
    """
    dt_s = 1.0 / config.FS_IMU_NOMINAL_HZ
    fuerza = estado[escenarios.COLUMNAS_FUERZA].to_numpy()
    velocidad_angular = estado[escenarios.COLUMNAS_VELOCIDAD_ANGULAR].to_numpy()
    campo = estado[escenarios.COLUMNAS_CAMPO].to_numpy()

    accel_ms2 = medir_triaxial(fuerza, parametros.acelerometro, dt_s, rng)
    gyro_rads = medir_triaxial(velocidad_angular, parametros.giroscopio, dt_s, rng)

    # Cambio de unidades: m/s² -> g -> LSB   y   rad/s -> °/s -> LSB.
    accel_lsb_por_ms2 = config.ACCEL_LSB_POR_G[config.ACCEL_RANGO_G] / config.G_ESTANDAR
    gyro_lsb_por_rads = config.GYRO_LSB_POR_DPS[config.GYRO_RANGO_DPS] * math.degrees(1.0)

    seq = np.arange(len(t_s))
    imu = pd.DataFrame({"seq": seq, "t_us": _a_microsegundos(t_s, parametros)})
    imu[["ax", "ay", "az"]] = cuantizar_int16(accel_ms2, accel_lsb_por_ms2)
    imu[["gx", "gy", "gz"]] = cuantizar_int16(gyro_rads, gyro_lsb_por_rads)
    imu[formato.COLUMNAS_MAG] = _simular_magnetometro(seq, campo, parametros, rng)
    return imu


def marea_barometrica(horas, parametros_barometro):
    """Cambio de presión por la marea barométrica semidiurna, en Pa.

    marea(t) = A · [cos(2π · (t + fase) / T) − cos(2π · fase / T)]

    A: amplitud en Pa; T: período (12 h); fase: horas transcurridas desde el último máximo
    de presión cuando empieza el registro. Se resta el valor inicial para que la marea valga
    cero en t = 0, es decir, para que la presión base sea la presión al empezar el registro.

    horas: tiempo desde el inicio del registro, en horas (número o arreglo).
    """
    p = parametros_barometro
    angulo = 2 * np.pi * (horas + p.marea_fase_h) / p.marea_periodo_h
    angulo_inicial = 2 * np.pi * p.marea_fase_h / p.marea_periodo_h
    return p.marea_amplitud_Pa * (np.cos(angulo) - np.cos(angulo_inicial))


def simular_barometro(t_s, parametros, calib, rng, altura_m=None):
    """Tabla baro.csv (todas las muestras) y la presión y temperatura verdaderas.

    Presión verdadera = presión base + deriva lenta por el clima (tendencia lineal + marea
    barométrica + paseo aleatorio).
    El sensor le suma ruido y entrega los valores crudos adc_T y adc_P, que se obtienen
    invirtiendo numéricamente la fórmula de compensación del BMP280 (ver bmp280.py).

    altura_m: altura del dispositivo sobre el punto de partida en cada instante (None = 0).
    Al subir, la presión baja según la fórmula barométrica (navinercial/barometro.py), con
    la temperatura verdadera del aire.

    Devuelve (tabla baro, tabla verdad_baro).
    """
    p = parametros.barometro
    n = len(t_s)
    horas = t_s / 3600.0
    dt_s = 1.0 / config.FS_BARO_NOMINAL_HZ

    clima = (p.deriva_clima_Pa_por_hora * horas
             + marea_barometrica(horas, p)
             + paseo_aleatorio((n,), dt_s, p.paseo_clima_std, rng))
    temperatura_real = p.temperatura_base_C + p.deriva_temperatura_C_por_hora * horas
    if altura_m is None:
        altura_m = np.zeros(n)
    presion_real = barometro.presion_a_altura(
        altura_m, p.presion_base_Pa, temperatura_real) + clima

    presion_medida = presion_real + rng.normal(0.0, p.ruido_presion_std_Pa, n)
    temperatura_medida = temperatura_real + rng.normal(0.0, p.ruido_temperatura_std_C, n)

    adc_T = [bmp280.temperatura_a_adc(float(T), calib) for T in temperatura_medida]
    adc_P = [bmp280.presion_a_adc(float(P), aT, calib) for P, aT in zip(presion_medida, adc_T)]

    seq = np.arange(n)
    t_us = _a_microsegundos(t_s, parametros)
    baro = pd.DataFrame({"seq": seq, "t_us": t_us, "adc_T": adc_T, "adc_P": adc_P})
    verdad_baro = pd.DataFrame({"seq": seq, "t_us": t_us,
                                "presion_Pa": presion_real, "temperatura_C": temperatura_real})
    return baro, verdad_baro


def _a_microsegundos(t_s, parametros):
    """Marca de tiempo del ESP32: microsegundos (enteros) desde que se encendió."""
    return parametros.tiempo.t_inicial_us + np.rint(np.asarray(t_s) * 1e6).astype(np.int64)
