"""Verifica una sesión: muestras perdidas, frecuencia de muestreo real y jitter.

Uso (desde la carpeta procesamiento/):

    python -m scripts.verificar_sesion                      # sesión simulada de reposo
    python -m scripts.verificar_sesion datos/simulados/sesion_20260101_100000
    python -m scripts.verificar_sesion RUTA_DE_LA_SESION --ventana 30

Guarda en resultados/verificacion/<nombre de la sesión>/:
    reporte.txt       reporte de verificación en texto
    intervalos.png    intervalo entre muestras y jitter
    frecuencia.png    frecuencia de muestreo real a lo largo del registro
    senales.png       las señales en unidades físicas
"""

import argparse
from pathlib import Path

import config
from navinercial import graficas, lectura, verificacion
from simulador import generar


def verificar_y_guardar(carpeta_sesion, carpeta_salida, ventana_s=config.VERIF_VENTANA_FRECUENCIA_S):
    """Carga la sesión, la verifica y guarda el reporte y las gráficas.

    Devuelve el texto del reporte.
    """
    sesion = lectura.cargar_sesion(carpeta_sesion)
    verificaciones = verificacion.verificar_sesion(sesion, ventana_s)
    reporte = verificacion.texto_reporte(sesion, verificaciones)

    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    graficas.guardar_figura(graficas.grafica_intervalos(sesion, verificaciones),
                            carpeta_salida / "intervalos.png")
    graficas.guardar_figura(graficas.grafica_frecuencia(sesion, verificaciones),
                            carpeta_salida / "frecuencia.png")
    graficas.guardar_figura(graficas.grafica_senales(sesion), carpeta_salida / "senales.png")
    return reporte


def main():
    analizador = argparse.ArgumentParser(description="Verifica una sesión.")
    analizador.add_argument("sesion", nargs="?", default=None,
                            help="carpeta de la sesión (por defecto, el reposo simulado)")
    analizador.add_argument("--ventana", type=float, default=config.VERIF_VENTANA_FRECUENCIA_S,
                            help="ventana para medir la frecuencia al inicio y al final, en s")
    argumentos = analizador.parse_args()

    carpeta_sesion = Path(argumentos.sesion or generar.carpeta_de_escenario("reposo"))
    carpeta_salida = config.CARPETA_RESULTADOS / "verificacion" / carpeta_sesion.name

    reporte = verificar_y_guardar(carpeta_sesion, carpeta_salida, argumentos.ventana)
    print(reporte)
    print(f"\nReporte y gráficas guardados en: {carpeta_salida}")


if __name__ == "__main__":
    main()
