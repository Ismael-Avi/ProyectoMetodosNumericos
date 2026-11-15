"""Bitácora de los registros: una fila por sesión, en un archivo CSV.

Cada fila tiene dos partes:
- Columnas MANUALES, que llena el grupo al hacer el experimento: fecha, hora, lugar,
  condiciones, procedimiento, orientación del dispositivo, foto, observaciones.
  (El ESP32 no tiene reloj: la fecha y la hora solo quedan aquí.)
- Columnas AUTOMÁTICAS, que calcula el programa: duración, desplazamiento, velocidad y
  aceleración máximas, duración de cada tramo, frecuencia real y muestras perdidas.

actualizar_bitacora nunca borra lo que se escribió a mano: solo cambia las columnas
automáticas de la fila de esa sesión (o agrega la fila si no existe).
"""

from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial import metro

ARCHIVO_BITACORA = config.CARPETA_BASE / "bitacora" / "bitacora.csv"
# Las sesiones del simulador van a otro archivo, para no mezclar datos inventados con la
# bitácora de los experimentos reales.
ARCHIVO_BITACORA_SIMULADA = config.CARPETA_RESULTADOS / "bitacora_simulada.csv"
FIRMWARE_DEL_SIMULADOR = "simulador"   # valor de firmware_version que escribe el simulador

COLUMNAS_MANUALES = ["sesion", "tipo", "fecha", "hora", "lugar", "condiciones", "procedimiento",
                     "orientacion_dispositivo", "foto", "observaciones"]
COLUMNAS_AUTOMATICAS = ["duracion_s", "fs_real_hz", "muestras_perdidas", "desplazamiento_m",
                        "velocidad_max_ms", "aceleracion_max_ms2", "duracion_tramos_s"]
COLUMNAS = COLUMNAS_MANUALES + COLUMNAS_AUTOMATICAS


def resultados_de_verificacion(verificacion_imu):
    """Columnas automáticas que salen de la verificación (sirven para cualquier registro)."""
    return {"duracion_s": round(verificacion_imu.duracion_s, 1),
            "fs_real_hz": round(verificacion_imu.fs_media_hz, 3),
            "muestras_perdidas": int(verificacion_imu.n_perdidas_seq)}


def resultados_de_movimiento(t_s, velocidad_ms, paradas):
    """Columnas automáticas de un registro con movimiento (ascensor o metro).

    velocidad_ms: velocidad a lo largo del recorrido (vertical en el ascensor, a lo largo
    de la vía en el metro). Devuelve el desplazamiento total recorrido (suma de todos los
    tramos, en m), la velocidad máxima, la aceleración máxima y la duración de cada tramo.
    """
    t_s = np.asarray(t_s, dtype=float)
    velocidad_ms = np.asarray(velocidad_ms, dtype=float)
    # La aceleración se calcula derivando la velocidad suavizada (promedio de 1 s), para
    # que el máximo no sea un pico de ruido.
    suave = metro.promedio_movil(velocidad_ms, config.FS_IMU_NOMINAL_HZ)
    aceleracion = metro.derivada_centrada(t_s, suave)
    recorrido = np.sum(np.abs(velocidad_ms[:-1]) * np.diff(t_s))
    duraciones = [fin - inicio for inicio, fin in metro.tramos_entre_paradas(paradas)]
    return {"desplazamiento_m": round(float(recorrido), 2),
            "velocidad_max_ms": round(float(np.max(np.abs(velocidad_ms))), 3),
            "aceleracion_max_ms2": round(float(np.max(np.abs(aceleracion))), 3),
            "duracion_tramos_s": " ".join(f"{d:.1f}" for d in duraciones)}


def archivo_de_bitacora(meta):
    """Bitácora que le toca a una sesión: la real, o la de simulados si viene del simulador."""
    if meta.get("firmware_version") == FIRMWARE_DEL_SIMULADOR:
        return ARCHIVO_BITACORA_SIMULADA
    return ARCHIVO_BITACORA


def leer_bitacora(ruta=ARCHIVO_BITACORA):
    """Lee la bitácora como tabla de texto (crea una vacía si el archivo no existe)."""
    ruta = Path(ruta)
    if not ruta.exists():
        return pd.DataFrame(columns=COLUMNAS, dtype=str)
    tabla = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    for columna in COLUMNAS:
        if columna not in tabla:
            tabla[columna] = ""
    return tabla


def actualizar_bitacora(nombre_sesion, tipo, resultados, ruta=ARCHIVO_BITACORA):
    """Escribe los resultados automáticos en la fila de la sesión (la agrega si no existe).

    resultados: diccionario con algunas de las COLUMNAS_AUTOMATICAS. Devuelve la ruta.
    """
    ruta = Path(ruta)
    tabla = leer_bitacora(ruta)
    if nombre_sesion not in set(tabla["sesion"]):
        fila_nueva = {columna: "" for columna in tabla.columns}
        fila_nueva.update({"sesion": nombre_sesion, "tipo": tipo})
        tabla = pd.concat([tabla, pd.DataFrame([fila_nueva])], ignore_index=True)
    fila = tabla["sesion"] == nombre_sesion
    for columna, valor in resultados.items():
        if columna not in COLUMNAS_AUTOMATICAS:
            raise ValueError(f"'{columna}' no es una columna automática de la bitácora")
        tabla.loc[fila, columna] = str(valor)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(ruta, index=False)
    return ruta
