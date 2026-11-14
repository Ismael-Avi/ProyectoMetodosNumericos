"""Caracteriza el sensor con una sesión en reposo: sesgo, ruido y detector de quietud.

Uso (desde la carpeta procesamiento/):

    python -m scripts.caracterizar_reposo                  # reposo simulado
    python -m scripts.caracterizar_reposo RUTA_DE_LA_SESION

Guarda en resultados/caracterizacion/<nombre de la sesión>/:
    reporte.txt   media, desviación y ruido de cada señal; porcentaje de tiempo "quieto"
    ruido.png     histograma del ruido de cada eje
    allan.png     desviación de Allan del acelerómetro y del giroscopio
"""

import argparse
from pathlib import Path

import numpy as np

import config
from navinercial import calibracion, graficas, lectura, verificacion
from simulador import generar

MUESTRAS_PARA_PROMEDIAR_PRESION = 250   # unos 10 s de barómetro al inicio y al final


def texto_reporte(sesion, caracterizacion, fraccion_quieto):
    """Reporte de la caracterización en reposo, como texto."""
    presion = sesion.baro["presion_Pa"]
    n = MUESTRAS_PARA_PROMEDIAR_PRESION
    cambio_presion = presion.iloc[-n:].mean() - presion.iloc[:n].mean()
    lineas = [
        "CARACTERIZACIÓN EN REPOSO",
        f"Carpeta: {sesion.carpeta}",
        f"Duración: {sesion.imu['t_s'].iloc[-1] / 60:.1f} min",
        "",
        caracterizacion.to_string(float_format=lambda v: f"{v:.6g}"),
        "",
        "media: en gx, gy, gz es el sesgo del giroscopio. En ax, ay, az es sesgo + gravedad.",
        "std_total: desviación de todo el registro (ruido + derivas lentas).",
        "ruido: desviación del ruido blanco, estimada con diferencias entre muestras.",
        "",
        f"Magnitud media del acelerómetro: {caracterizacion.loc['|a|', 'media']:.4f} m/s² "
        f"(g de Quito en config.py: {config.G_QUITO} m/s²).",
        "  La diferencia es el error de sesgo y de escala, que corrige la calibración de seis caras.",
        f"Cambio de presión entre el inicio y el final: {cambio_presion:+.1f} Pa (deriva por el clima)",
        f"Detector de quietud: el dispositivo está quieto el {100 * fraccion_quieto:.2f} % del tiempo",
    ]
    return "\n".join(lineas)


def caracterizar_y_guardar(carpeta_sesion, carpeta_salida):
    """Carga la sesión, la caracteriza y guarda el reporte y las gráficas. Devuelve el reporte."""
    sesion = lectura.cargar_sesion(carpeta_sesion)
    caracterizacion = calibracion.caracterizar_reposo(sesion)
    fraccion_quieto = float(np.mean(calibracion.detectar_quietud(sesion.imu)))
    reporte = texto_reporte(sesion, caracterizacion, fraccion_quieto)

    fs = verificacion.frecuencia_real(sesion.imu["seq"], sesion.imu["t_s"])
    curvas_accel = {c: calibracion.desviacion_allan(sesion.imu[c], fs)
                    for c in lectura.COLUMNAS_ACCEL}
    curvas_gyro = {c: calibracion.desviacion_allan(sesion.imu[c], fs)
                   for c in lectura.COLUMNAS_GYRO}

    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    graficas.guardar_figura(graficas.grafica_ruido_reposo(sesion, caracterizacion),
                            carpeta_salida / "ruido.png")
    graficas.guardar_figura(graficas.grafica_allan(curvas_accel, curvas_gyro),
                            carpeta_salida / "allan.png")
    return reporte


def main():
    analizador = argparse.ArgumentParser(description="Caracteriza el sensor en reposo.")
    analizador.add_argument("sesion", nargs="?", default=None,
                            help="carpeta de la sesión (por defecto, el reposo simulado)")
    argumentos = analizador.parse_args()

    carpeta_sesion = Path(argumentos.sesion or generar.carpeta_de_escenario("reposo"))
    carpeta_salida = config.CARPETA_RESULTADOS / "caracterizacion" / carpeta_sesion.name
    print(caracterizar_y_guardar(carpeta_sesion, carpeta_salida))
    print(f"\nReporte y gráficas guardados en: {carpeta_salida}")


if __name__ == "__main__":
    main()
