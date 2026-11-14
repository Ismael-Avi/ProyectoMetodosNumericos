"""Carga de una sesión y conversión de los valores crudos a unidades físicas (SI).

Cambios de unidades que se hacen aquí:
- Acelerómetro: LSB -> g -> m/s²     (dividir por LSB/g y multiplicar por 9,80665)
- Giroscopio:   LSB -> °/s -> rad/s  (dividir por LSB/(°/s) y pasar a radianes)
- Magnetómetro: LSB -> µT            (multiplicar por µT/LSB)
- Barómetro:    adc_T, adc_P -> °C, Pa   (fórmula de compensación, ver bmp280.py)
- Tiempo:       microsegundos desde el arranque del ESP32 -> segundos desde la primera
                muestra del IMU

Aquí NO se calibra ni se filtra: solo se cambian las unidades.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial import bmp280, formato

COLUMNAS_ACCEL = ["ax", "ay", "az"]
COLUMNAS_GYRO = ["gx", "gy", "gz"]
COLUMNAS_MAG = formato.COLUMNAS_MAG


@dataclass
class Sesion:
    """Una sesión en unidades físicas.

    imu:     seq, t_us, t_s, ax, ay, az (m/s²), gx, gy, gz (rad/s), mx, my, mz (µT; NaN en
             las filas donde el magnetómetro no tiene lectura nueva)
    baro:    seq, t_us, t_s, temperatura_C, presion_Pa
    eventos: t_us, t_s, evento
    t_s es el tiempo en segundos desde la primera muestra del IMU (la misma referencia en
    las tres tablas). t0_us es el t_us de esa primera muestra.
    """

    carpeta: Path
    meta: dict
    t0_us: int
    imu: pd.DataFrame
    baro: pd.DataFrame
    eventos: pd.DataFrame


# ---------------------------------------------------------------------------
# Conversiones (sirven con un número o con un arreglo)
# ---------------------------------------------------------------------------

def accel_crudo_a_ms2(crudo, rango_g):
    """Acelerómetro: de LSB a m/s².

    rango_g: rango configurado (2, 4, 8 o 16). Con ±4 g, 8192 LSB equivalen a 1 g.
    Se usa la gravedad estándar porque es la definición de la unidad "g", no la de Quito.
    """
    lsb_por_g = config.ACCEL_LSB_POR_G[rango_g]
    return crudo / lsb_por_g * config.G_ESTANDAR


def gyro_crudo_a_rads(crudo, rango_dps):
    """Giroscopio: de LSB a rad/s.

    rango_dps: rango configurado (250, 500, 1000 o 2000 °/s). Con ±500 °/s, 65,5 LSB
    equivalen a 1 °/s.
    """
    lsb_por_dps = config.GYRO_LSB_POR_DPS[rango_dps]
    return np.radians(crudo / lsb_por_dps)


def mag_crudo_a_uT(crudo, asa=None):
    """Magnetómetro: de LSB a µT (0,15 µT por LSB en modo de 16 bits).

    asa: ajuste de sensibilidad de fábrica del AK8963 para ese eje (entero de 0 a 255), o
    None si no se conoce. Según la hoja de datos, la lectura se corrige así:

        H_ajustado = H · ((asa − 128) / 256 + 1)

    Con asa = 128 el factor vale 1 (sin corrección). TODO: confirmar la fórmula en la hoja
    de datos del AK8963 (sección del registro ASAX).
    """
    factor = 1.0 if asa is None else factor_ajuste_ak8963(asa)
    return crudo * config.MAG_UT_POR_LSB * factor


def factor_ajuste_ak8963(asa):
    """Factor de corrección de sensibilidad del AK8963: (asa − 128)/256 + 1. Sin unidades."""
    return (asa - config.AK8963_ASA_CENTRO) / config.AK8963_ASA_DIVISOR + 1.0


def us_a_segundos(t_us, t0_us):
    """Tiempo: de microsegundos del ESP32 a segundos desde t0_us.

    Se resta primero (con enteros, sin pérdida) y después se pasa a segundos.
    """
    return (t_us - t0_us) * 1e-6


# ---------------------------------------------------------------------------
# Carga de la sesión
# ---------------------------------------------------------------------------

def _convertir_imu(cruda, t0_us):
    meta = cruda.meta
    imu = cruda.imu[["seq", "t_us"]].copy()
    imu["t_s"] = us_a_segundos(imu["t_us"], t0_us)
    for columna in COLUMNAS_ACCEL:
        imu[columna] = accel_crudo_a_ms2(cruda.imu[columna].astype(float), meta["accel_rango_g"])
    for columna in COLUMNAS_GYRO:
        imu[columna] = gyro_crudo_a_rads(cruda.imu[columna].astype(float), meta["gyro_rango_dps"])
    # Ajuste de sensibilidad del magnetómetro: el firmware lo guarda en meta.json; el
    # simulador no (entonces no se corrige nada).
    ajustes = meta.get("ak8963_asa") or [None, None, None]
    for columna, asa in zip(COLUMNAS_MAG, ajustes):
        # Las celdas vacías (<NA>) pasan a ser NaN ("no es un número").
        crudo = cruda.imu[columna].to_numpy(dtype=float, na_value=np.nan)
        imu[columna] = mag_crudo_a_uT(crudo, asa)
    return imu


def _convertir_baro(cruda, t0_us):
    baro = cruda.baro[["seq", "t_us"]].copy()
    baro["t_s"] = us_a_segundos(baro["t_us"], t0_us)
    temperatura_C, presion_Pa = bmp280.compensar(
        cruda.baro["adc_T"].to_numpy(dtype=float),
        cruda.baro["adc_P"].to_numpy(dtype=float),
        cruda.meta["bmp280_calib"],
    )
    baro["temperatura_C"] = temperatura_C
    baro["presion_Pa"] = presion_Pa
    return baro


def convertir_sesion(cruda):
    """Convierte una SesionCruda (valores crudos) en una Sesion (unidades físicas)."""
    if len(cruda.imu) == 0:
        raise formato.ErrorDeFormato(f"{formato.ARCHIVO_IMU} no tiene muestras")
    t0_us = int(cruda.imu["t_us"].iloc[0])

    eventos = cruda.eventos[["t_us"]].copy()
    eventos["t_s"] = us_a_segundos(eventos["t_us"], t0_us)
    eventos["evento"] = cruda.eventos["evento"]

    return Sesion(
        carpeta=cruda.carpeta,
        meta=cruda.meta,
        t0_us=t0_us,
        imu=_convertir_imu(cruda, t0_us),
        baro=_convertir_baro(cruda, t0_us),
        eventos=eventos,
    )


def cargar_sesion(carpeta):
    """Lee la carpeta de una sesión y la devuelve en unidades físicas."""
    return convertir_sesion(formato.leer_sesion_cruda(carpeta))
