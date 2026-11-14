"""Calibra el acelerómetro con una sesión de seis caras y guarda la calibración.

Uso (desde la carpeta procesamiento/):

    python -m scripts.calibrar_seis_caras                  # seis caras simuladas
    python -m scripts.calibrar_seis_caras RUTA_DE_LA_SESION

Guarda:
    resultados/calibracion/calibracion.json        sesgo y escala (la usan los demás análisis)
    resultados/calibracion/<sesión>/reporte.txt    caras detectadas, sesgo y escala
    resultados/calibracion/<sesión>/caras.png      caras detectadas y magnitud de la gravedad

Si la sesión es simulada (tiene verdad_parametros.json), el reporte compara el resultado con
el sesgo y la escala que puso el simulador.
"""

import argparse
import json
from pathlib import Path

import numpy as np

import config
from navinercial import calibracion, graficas, lectura
from simulador import generar


def _magnitud_por_cara(sesion, caras):
    """Magnitud media del acelerómetro en cada cara detectada, en m/s²."""
    t = sesion.imu["t_s"].to_numpy()
    magnitudes = []
    for _, cara in caras.iterrows():
        en_cara = (t >= cara["t_inicio_s"]) & (t <= cara["t_fin_s"])
        magnitudes.append(calibracion.magnitud(sesion.imu[en_cara], lectura.COLUMNAS_ACCEL).mean())
    return np.array(magnitudes)


def _comparacion_con_la_verdad(carpeta_sesion, resultado):
    """Si la sesión es simulada, compara la calibración con lo que puso el simulador."""
    ruta = Path(carpeta_sesion) / generar.ARCHIVO_VERDAD_PARAMETROS
    if not ruta.is_file():
        return ["(Sesión real: no hay valores verdaderos con los que comparar.)"]
    verdad = json.loads(ruta.read_text(encoding="utf-8"))["acelerometro"]
    sesgo_real = np.array(verdad["sesgo"])
    escala_real = 1.0 + np.array(verdad["error_escala"])
    error_sesgo = np.array(resultado.sesgo_accel) - sesgo_real
    error_escala = np.array(resultado.escala_accel) - escala_real
    return [
        "Comparación con los valores que puso el simulador:",
        f"  sesgo real:   {np.round(sesgo_real, 5).tolist()} m/s²",
        f"  error sesgo:  {np.round(error_sesgo, 5).tolist()} m/s²",
        f"  escala real:  {np.round(escala_real, 5).tolist()}",
        f"  error escala: {np.round(error_escala, 6).tolist()}",
    ]


def texto_reporte(carpeta_sesion, sesion, sesion_calibrada, resultado, caras):
    """Reporte de la calibración de seis caras, como texto."""
    antes = _magnitud_por_cara(sesion, caras)
    despues = _magnitud_por_cara(sesion_calibrada, caras)
    columnas = ["cara", "t_inicio_s", "t_fin_s", "n_muestras", "ax", "ay", "az"]
    lineas = [
        "CALIBRACIÓN DE SEIS CARAS",
        f"Carpeta: {carpeta_sesion}",
        f"Gravedad usada: {resultado.g} m/s²",
        "",
        "Caras detectadas (promedio del acelerómetro en m/s²):",
        caras[columnas].to_string(index=False, float_format=lambda v: f"{v:.4f}"),
        "",
        f"Sesgo del acelerómetro:  {np.round(resultado.sesgo_accel, 5).tolist()} m/s²",
        f"Escala del acelerómetro: {np.round(resultado.escala_accel, 5).tolist()}",
        f"Sesgo del giroscopio:    {np.round(resultado.sesgo_gyro, 6).tolist()} rad/s",
        "",
        *_comparacion_con_la_verdad(carpeta_sesion, resultado),
        "",
        "Magnitud de la gravedad en cada cara (no debería cambiar al girar el dispositivo):",
        f"  sin calibrar: de {antes.min():.4f} a {antes.max():.4f} m/s² "
        f"(diferencia {antes.max() - antes.min():.4f})",
        f"  calibrado:    de {despues.min():.4f} a {despues.max():.4f} m/s² "
        f"(diferencia {despues.max() - despues.min():.4f})",
    ]
    return "\n".join(lineas)


def calibrar_y_guardar(carpeta_sesion, carpeta_salida,
                       ruta_calibracion=calibracion.ARCHIVO_CALIBRACION):
    """Calibra con la sesión de seis caras y guarda el JSON, el reporte y la gráfica."""
    sesion = lectura.cargar_sesion(carpeta_sesion)
    resultado, caras = calibracion.calibrar_seis_caras(
        sesion.imu, origen=Path(carpeta_sesion).name)
    sesion_calibrada = calibracion.aplicar_calibracion(sesion, resultado)
    reporte = texto_reporte(carpeta_sesion, sesion, sesion_calibrada, resultado, caras)

    calibracion.guardar_calibracion(resultado, ruta_calibracion)
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    graficas.guardar_figura(
        graficas.grafica_caras(sesion, sesion_calibrada, caras, resultado.g),
        carpeta_salida / "caras.png")
    return reporte


def main():
    analizador = argparse.ArgumentParser(description="Calibración de seis caras.")
    analizador.add_argument("sesion", nargs="?", default=None,
                            help="carpeta de la sesión (por defecto, las seis caras simuladas)")
    argumentos = analizador.parse_args()

    carpeta_sesion = Path(argumentos.sesion or generar.carpeta_de_escenario("seis_caras"))
    carpeta_salida = config.CARPETA_RESULTADOS / "calibracion" / carpeta_sesion.name
    print(calibrar_y_guardar(carpeta_sesion, carpeta_salida))
    print(f"\nCalibración guardada en: {calibracion.ARCHIVO_CALIBRACION}")
    print(f"Reporte y gráfica guardados en: {carpeta_salida}")


if __name__ == "__main__":
    main()
