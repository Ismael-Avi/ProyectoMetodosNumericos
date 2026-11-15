"""Reporte automático de una sesión: verificación + análisis según el tipo + bitácora.

Uso (desde la carpeta procesamiento/):

    python -m scripts.reporte_sesion RUTA_DE_LA_SESION --tipo reposo
    python -m scripts.reporte_sesion RUTA_DE_LA_SESION --tipo seis_caras
    python -m scripts.reporte_sesion RUTA_DE_LA_SESION --tipo ascensor --pisos datos_referencia/pisos_ascensor.csv --itinerario 0,3,5,0
    python -m scripts.reporte_sesion RUTA_DE_LA_SESION --tipo metro --estaciones "Quitumbe,Morán Valverde"
    python -m scripts.reporte_sesion --simulados          # todas las sesiones simuladas

Hace tres cosas:
1. Corre la verificación (muestras perdidas, frecuencia real) y el análisis del tipo
   indicado, con los mismos scripts que se pueden correr por separado.
2. Escribe resultados/reportes/<sesión>.md: un resumen con todos los reportes y la lista
   de gráficas generadas.
3. Actualiza la fila de la sesión en bitacora/bitacora.csv con los resultados automáticos
   (las columnas manuales no se tocan). Las sesiones del simulador van aparte, a
   resultados/bitacora_simulada.csv, para no mezclarlas con los experimentos reales.

OJO: con --tipo seis_caras se vuelve a calcular y a guardar la calibración
(resultados/calibracion/calibracion.json), que después usan el ascensor y el metro.
"""

import argparse
from pathlib import Path

import config
from navinercial import ascensor, bitacora, lectura, metro, verificacion
from scripts import (analizar_ascensor, analizar_metro, calibrar_seis_caras, caracterizar_reposo,
                     verificar_sesion)
from simulador import generar

TIPOS = ["reposo", "seis_caras", "ascensor", "metro"]

# Tipo de cada escenario del simulador (para la opción --simulados).
TIPO_DE_ESCENARIO = {"reposo": "reposo", "seis_caras": "seis_caras", "ascensor": "ascensor",
                     "metro_1": "metro", "metro_2": "metro", "metro_3": "metro"}


def _analizar_segun_tipo(carpeta_sesion, tipo, argumentos):
    """Corre el análisis del tipo. Devuelve (carpeta de resultados, reporte, columnas de bitácora)."""
    nombre = Path(carpeta_sesion).name
    resultados = config.CARPETA_RESULTADOS
    if tipo == "reposo":
        carpeta = resultados / "caracterizacion" / nombre
        return carpeta, caracterizar_reposo.caracterizar_y_guardar(carpeta_sesion, carpeta), {}
    if tipo == "seis_caras":
        carpeta = resultados / "calibracion" / nombre
        return carpeta, calibrar_seis_caras.calibrar_y_guardar(carpeta_sesion, carpeta), {}
    if tipo == "ascensor":
        carpeta = resultados / "ascensor" / nombre
        resultado = analizar_ascensor.analizar_y_guardar(
            carpeta_sesion, carpeta, argumentos.pisos, argumentos.itinerario)
        analisis = resultado["analisis"]
        columnas = bitacora.resultados_de_movimiento(
            analisis.t_s, analisis.velocidad[ascensor.CON_ZUPT], analisis.paradas)
        return carpeta, resultado["reporte"], columnas
    carpeta = resultados / "metro" / nombre
    resultado = analizar_metro.analizar_y_guardar(carpeta_sesion, carpeta, argumentos.estaciones)
    analisis = resultado["analisis"]
    columnas = bitacora.resultados_de_movimiento(
        analisis.t_s, analisis.velocidad[metro.ZUPT_BARO], analisis.paradas)
    return carpeta, resultado["reporte"], columnas


def _lista_de_graficas(carpetas):
    """Líneas de Markdown con las gráficas (PNG) que hay en las carpetas de resultados."""
    lineas = []
    for carpeta in carpetas:
        for imagen in sorted(Path(carpeta).glob("*.png")):
            relativa = imagen.relative_to(config.CARPETA_RESULTADOS).as_posix()
            lineas.append(f"- [{relativa}](../{relativa})")
    return lineas


def generar_reporte(carpeta_sesion, tipo, argumentos):
    """Genera el reporte completo de una sesión. Devuelve la ruta del archivo .md."""
    carpeta_sesion = Path(carpeta_sesion)
    nombre = carpeta_sesion.name
    carpeta_verificacion = config.CARPETA_RESULTADOS / "verificacion" / nombre
    reporte_verificacion = verificar_sesion.verificar_y_guardar(carpeta_sesion, carpeta_verificacion)
    carpeta_analisis, reporte_analisis, columnas = _analizar_segun_tipo(carpeta_sesion, tipo, argumentos)

    sesion = lectura.cargar_sesion(carpeta_sesion)
    columnas.update(bitacora.resultados_de_verificacion(verificacion.verificar_sesion(sesion)["imu"]))
    archivo_bitacora = bitacora.archivo_de_bitacora(sesion.meta)
    bitacora.actualizar_bitacora(nombre, tipo, columnas, archivo_bitacora)

    lineas = [f"# Reporte de {nombre} ({tipo})", "",
              f"Notas de meta.json: {sesion.meta.get('notas', '') or '(ninguna)'}", "",
              f"## Resultados automáticos (también en {archivo_bitacora.name})", ""]
    lineas += [f"- {columna}: {valor}" for columna, valor in columnas.items()]
    lineas += ["", "## Verificación", "", "```", reporte_verificacion, "```", "",
               "## Análisis", "", "```", reporte_analisis, "```", "", "## Gráficas", ""]
    lineas += _lista_de_graficas([carpeta_verificacion, carpeta_analisis])
    ruta = config.CARPETA_RESULTADOS / "reportes" / f"{nombre}.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def main():
    analizador = argparse.ArgumentParser(description="Reporte automático de una sesión.")
    analizador.add_argument("sesion", nargs="?", default=None, help="carpeta de la sesión")
    analizador.add_argument("--tipo", choices=TIPOS, help="qué experimento es")
    analizador.add_argument("--simulados", action="store_true",
                            help="genera el reporte de todas las sesiones simuladas")
    analizador.add_argument("--pisos", default=None, help="ascensor: CSV con piso,altura_m")
    analizador.add_argument("--itinerario", default=None, help="ascensor: piso de cada parada")
    analizador.add_argument("--estaciones", default=None, help="metro: estaciones del viaje")
    argumentos = analizador.parse_args()

    if argumentos.simulados:
        trabajos = [(generar.carpeta_de_escenario(escenario), tipo)
                    for escenario, tipo in TIPO_DE_ESCENARIO.items()]
    elif argumentos.sesion and argumentos.tipo:
        trabajos = [(Path(argumentos.sesion), argumentos.tipo)]
    else:
        analizador.error("indicar la carpeta de la sesión y --tipo, o usar --simulados")

    for carpeta, tipo in trabajos:
        print(f"Reporte de {carpeta.name} ({tipo})...", flush=True)
        print(f"  -> {generar_reporte(carpeta, tipo, argumentos)}")
    print(f"Bitácora de sesiones reales:    {bitacora.ARCHIVO_BITACORA}")
    print(f"Bitácora de sesiones simuladas: {bitacora.ARCHIVO_BITACORA_SIMULADA}")


if __name__ == "__main__":
    main()
