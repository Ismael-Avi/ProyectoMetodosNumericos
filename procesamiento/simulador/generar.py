"""Genera sesiones simuladas en el formato del dispositivo.

Uso (desde la carpeta procesamiento/):

    python -m simulador.generar                         # todos los escenarios disponibles
    python -m simulador.generar --escenario seis_caras
    python -m simulador.generar --escenario reposo --duracion-reposo-min 10
    python -m simulador.generar --sin-magnetometro --semilla 7

Cada sesión se guarda en datos/simulados/sesion_YYYYMMDD_HHMMSS/ con los cuatro archivos
del dispositivo (meta.json, imu.csv, baro.csv, eventos.csv) y tres archivos extra que el
dispositivo real NO escribe, con la "verdad" de la simulación:

    verdad.csv              lo que mediría un sensor perfecto en cada muestra del IMU
    verdad_baro.csv         presión y temperatura verdaderas en cada muestra del barómetro
    verdad_parametros.json  sesgos, escalas, ruidos y semilla que usó el simulador
"""

import argparse
import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial import formato
from simulador import escenarios, modelo_sensor

ARCHIVO_VERDAD = "verdad.csv"
ARCHIVO_VERDAD_BARO = "verdad_baro.csv"
ARCHIVO_VERDAD_PARAMETROS = "verdad_parametros.json"

# Fecha y hora FICTICIAS de cada sesión simulada. Son fijas para que la carpeta de cada
# escenario se llame siempre igual y los scripts la encuentren.
FECHAS_SIMULADAS = {
    "reposo": datetime(2026, 1, 1, 8, 0, 0),
    "seis_caras": datetime(2026, 1, 1, 10, 0, 0),
}


@dataclass
class SesionSimulada:
    """Resultado de una simulación: los archivos del dispositivo más la verdad."""

    meta: dict
    imu: pd.DataFrame
    baro: pd.DataFrame
    eventos: pd.DataFrame
    verdad: pd.DataFrame
    verdad_baro: pd.DataFrame
    parametros: modelo_sensor.ParametrosSimulacion


def simular_sesion(escenario, parametros=None):
    """Simula el registro completo de un escenario.

    Pasos: (1) instantes de muestreo con jitter, (2) estado verdadero en esos instantes,
    (3) modelo de error de cada sensor, (4) quitar las muestras "perdidas".
    """
    if parametros is None:
        parametros = modelo_sensor.ParametrosSimulacion()
    rng = np.random.default_rng(parametros.semilla)
    tiempo = parametros.tiempo
    meta = formato.crear_meta(
        tiene_magnetometro=parametros.tiene_magnetometro,
        notas=f"SIMULADO: escenario {escenario.nombre}, semilla {parametros.semilla}",
    )

    # Sensor inercial.
    t_imu = modelo_sensor.generar_tiempos_s(
        escenario.duracion_s, tiempo.fs_imu_real_hz, tiempo.jitter_std_us, rng)
    estado = escenario.estado(t_imu)
    imu = modelo_sensor.simular_imu(t_imu, estado, parametros, rng)
    verdad = pd.concat([imu[["seq", "t_us"]], estado], axis=1)

    # Barómetro (tiene su propio contador de muestras y su propia frecuencia).
    t_baro = modelo_sensor.generar_tiempos_s(
        escenario.duracion_s, tiempo.fs_baro_real_hz, tiempo.jitter_std_us, rng)
    baro, verdad_baro = modelo_sensor.simular_barometro(
        t_baro, parametros, meta["bmp280_calib"], rng)

    # Muestras perdidas: se quitan las mismas filas de los datos y de la verdad.
    conservar_imu = modelo_sensor.mascara_muestras_conservadas(
        len(imu), tiempo.prob_muestra_perdida, rng)
    conservar_baro = modelo_sensor.mascara_muestras_conservadas(
        len(baro), tiempo.prob_muestra_perdida, rng)

    return SesionSimulada(
        meta=meta,
        imu=imu[conservar_imu].reset_index(drop=True),
        baro=baro[conservar_baro].reset_index(drop=True),
        eventos=_tabla_de_eventos(escenario, parametros),
        verdad=verdad[conservar_imu].reset_index(drop=True),
        verdad_baro=verdad_baro[conservar_baro].reset_index(drop=True),
        parametros=parametros,
    )


def _tabla_de_eventos(escenario, parametros):
    """Tabla eventos.csv con una pulsación del botón por cada instante del escenario."""
    t_s = np.array(escenario.tiempos_eventos_s, dtype=float)
    t_us = parametros.tiempo.t_inicial_us + np.rint(t_s * 1e6).astype(np.int64)
    return pd.DataFrame({"t_us": t_us, "evento": formato.EVENTO_BOTON})


def guardar_sesion_simulada(carpeta, sesion):
    """Escribe en la carpeta los archivos del dispositivo y los archivos de verdad."""
    carpeta = Path(carpeta)
    formato.escribir_sesion(carpeta, sesion.meta, sesion.imu, sesion.baro, sesion.eventos)

    # Seis cifras significativas bastan para la verdad y el archivo pesa mucho menos.
    sesion.verdad.to_csv(carpeta / ARCHIVO_VERDAD, index=False, float_format="%.6g")
    sesion.verdad_baro.to_csv(carpeta / ARCHIVO_VERDAD_BARO, index=False, float_format="%.9g")
    with open(carpeta / ARCHIVO_VERDAD_PARAMETROS, "w", encoding="utf-8") as archivo:
        json.dump(dataclasses.asdict(sesion.parametros), archivo, indent=2)


def carpeta_de_escenario(nombre_escenario, carpeta_base=config.CARPETA_DATOS_SIMULADOS):
    """Carpeta donde se guarda la sesión simulada de un escenario."""
    nombre = formato.nombre_carpeta_sesion(FECHAS_SIMULADAS[nombre_escenario])
    return Path(carpeta_base) / nombre


def _crear_escenario(nombre, argumentos):
    if nombre == "reposo":
        return escenarios.crear_reposo(duracion_s=argumentos.duracion_reposo_min * 60.0)
    if nombre == "seis_caras":
        return escenarios.crear_seis_caras()
    raise ValueError(f"Escenario desconocido: {nombre}")


def main():
    analizador = argparse.ArgumentParser(description="Genera sesiones simuladas.")
    analizador.add_argument("--escenario", default="todos",
                            choices=["todos"] + list(FECHAS_SIMULADAS))
    analizador.add_argument("--duracion-reposo-min", type=float,
                            default=config.SIM_REPOSO_DURACION_S / 60.0,
                            help="duración del reposo largo, en minutos")
    analizador.add_argument("--semilla", type=int, default=config.SEMILLA_POR_DEFECTO)
    analizador.add_argument("--sin-magnetometro", action="store_true",
                            help="simula un MPU-6500 (sin magnetómetro)")
    analizador.add_argument("--carpeta", default=str(config.CARPETA_DATOS_SIMULADOS),
                            help="carpeta donde se guardan las sesiones")
    argumentos = analizador.parse_args()

    nombres = list(FECHAS_SIMULADAS) if argumentos.escenario == "todos" else [argumentos.escenario]
    for nombre in nombres:
        escenario = _crear_escenario(nombre, argumentos)
        parametros = modelo_sensor.ParametrosSimulacion(
            semilla=argumentos.semilla,
            tiene_magnetometro=not argumentos.sin_magnetometro,
        )
        print(f"Simulando '{nombre}' ({escenario.duracion_s / 60:.1f} min)...", flush=True)
        sesion = simular_sesion(escenario, parametros)
        carpeta = carpeta_de_escenario(nombre, argumentos.carpeta)
        guardar_sesion_simulada(carpeta, sesion)
        print(f"  {len(sesion.imu)} muestras del IMU, {len(sesion.baro)} del barómetro -> {carpeta}")


if __name__ == "__main__":
    main()
