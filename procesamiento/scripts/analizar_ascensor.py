"""Analiza un registro de ascensor: altura, velocidad, correcciones, fusión y errores.

Uso (desde la carpeta procesamiento/):

    python -m scripts.analizar_ascensor                        # ascensor simulado
    python -m scripts.analizar_ascensor RUTA_DE_LA_SESION
    python -m scripts.analizar_ascensor RUTA --pisos datos_referencia/pisos_ascensor.csv
    python -m scripts.analizar_ascensor RUTA --itinerario 0,3,5,2,0

Referencia (alturas reales de los pisos):
- Sesión simulada: se lee de verdad_escenario.json (datos SINTÉTICOS del simulador).
- Sesión real: archivo CSV con las columnas piso,altura_m (medidas con flexómetro). Si no
  se da el itinerario (piso de cada parada, según la bitácora), se asigna a cada parada el
  piso más cercano a la altura calculada.
- Sin referencia: se calculan alturas y velocidades, pero no errores.

Si existe resultados/calibracion/calibracion.json (seis caras), se aplica; el reporte
compara también el resultado sin calibrar.

Guarda en resultados/ascensor/<nombre de la sesión>/:
    reporte.txt       todas las tablas
    altura.png        altura y velocidad en el tiempo, con los pisos y las pulsaciones
    errores.png       error de altura en el tiempo (solo con sesión simulada)
    comparacion.png   error de cada estimación, por recorrido
    recorridos.csv    error del desplazamiento de cada recorrido, por estimación
    cruces.csv        instante de cruce de cada piso
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial import ascensor, calibracion, graficas, lectura
from navinercial.metodos import integracion
from simulador import escenarios, generar

ESTIMACIONES_EN_LA_GRAFICA = [ascensor.BAROMETRO, ascensor.CON_ZUPT, ascensor.KALMAN_BARO_ZUPT]


# ---------------------------------------------------------------------------
# Referencia
# ---------------------------------------------------------------------------

def cargar_referencia(carpeta_sesion, archivo_pisos, texto_itinerario):
    """Devuelve (alturas de los pisos en m, itinerario, descripción) o (None, None, texto)."""
    archivo_verdad = Path(carpeta_sesion) / generar.ARCHIVO_VERDAD_ESCENARIO
    if archivo_verdad.exists():
        with open(archivo_verdad, encoding="utf-8") as archivo:
            info = json.load(archivo)
        return (np.array(info["alturas_pisos_m"]), info["itinerario"],
                "SINTÉTICA (verdad_escenario.json del simulador)")
    if archivo_pisos is None:
        return None, None, "no hay (no se calculan errores)"
    pisos = pd.read_csv(archivo_pisos, comment="#").dropna(subset=["altura_m"])
    if len(pisos) == 0:
        return None, None, f"{archivo_pisos} todavía no tiene alturas (no se calculan errores)"
    itinerario = [int(p) for p in texto_itinerario.split(",")] if texto_itinerario else None
    return pisos["altura_m"].to_numpy(), itinerario, str(archivo_pisos)


def alturas_de_referencia_en_paradas(alturas_pisos, itinerario):
    """Altura real de cada parada sobre la parada inicial, en m."""
    alturas_pisos = np.asarray(alturas_pisos, dtype=float)
    return alturas_pisos[itinerario] - alturas_pisos[itinerario[0]]


# ---------------------------------------------------------------------------
# Tablas del reporte
# ---------------------------------------------------------------------------

def resumen_de_errores(analisis, alturas_ref_paradas, verdad_altura):
    """Tabla con una fila por estimación: errores por recorrido y, si hay verdad, de altura."""
    recorridos = ascensor.tabla_de_recorridos(analisis, alturas_ref_paradas)
    filas = []
    for nombre, altura in analisis.altura.items():
        fila = {"estimación": nombre,
                "RMS por recorrido (m)": ascensor.raiz_cuadratica_media(recorridos[nombre]),
                "máx por recorrido (m)": float(np.max(np.abs(recorridos[nombre])))}
        if verdad_altura is not None:
            error = altura - verdad_altura
            fila["RMS de altura (m)"] = ascensor.raiz_cuadratica_media(error)
            fila["máx de altura (m)"] = float(np.max(np.abs(error)))
        filas.append(fila)
    return pd.DataFrame(filas).set_index("estimación"), recorridos


def comparar_metodos_de_integracion(analisis, alturas_ref_paradas):
    """Error RMS por recorrido con cada método de integración, con y sin ZUPT."""
    real = ascensor.desplazamientos(alturas_ref_paradas)
    t, a, paradas = analisis.t_s, analisis.aceleracion, analisis.paradas
    filas = []
    for metodo in integracion.METODOS:
        _, h_simple = ascensor.integrar(t, a, metodo)
        _, h_zupt = ascensor.integrar_con_zupt(t, a, paradas, metodo)
        fila = {"método": metodo}
        for nombre, h in [("sesgo inicial", h_simple), ("sesgo en paradas + ZUPT", h_zupt)]:
            calculado = ascensor.desplazamientos(ascensor.alturas_en_paradas(t, h, paradas))
            fila[f"{nombre}: RMS por recorrido (m)"] = ascensor.raiz_cuadratica_media(calculado - real)
            fila[f"{nombre}: altura final (m)"] = h[-1]
        filas.append(fila)
    return pd.DataFrame(filas).set_index("método")


def error_solo_del_metodo(carpeta_sesion, sesion):
    """Error de cada método de integración con una aceleración SIN errores de sensor.

    Se usa la aceleración exacta del escenario (una fórmula) en los mismos instantes de
    muestreo, y se compara la altura integrada con la altura exacta (otra fórmula). Como la
    señal no tiene ruido ni sesgo, todo el error es del método numérico.
    """
    with open(Path(carpeta_sesion) / generar.ARCHIVO_VERDAD_ESCENARIO, encoding="utf-8") as archivo:
        info = json.load(archivo)
    with open(Path(carpeta_sesion) / generar.ARCHIVO_VERDAD_PARAMETROS, encoding="utf-8") as archivo:
        t_inicial_us = json.load(archivo)["tiempo"]["t_inicial_us"]
    escenario = escenarios.crear_ascensor(info["alturas_pisos_m"], info["itinerario"])
    t_escenario = (sesion.imu["t_us"].to_numpy() - t_inicial_us) * 1e-6
    exacto = escenario.estado(t_escenario)

    filas = []
    for metodo in integracion.METODOS:
        _, altura = ascensor.integrar(t_escenario, exacto["aceleracion_z_ms2"].to_numpy(), metodo)
        error = altura - (exacto["altura_m"].to_numpy() - exacto["altura_m"].iloc[0])
        filas.append({"método": metodo, "error máximo de altura (m)": float(np.max(np.abs(error))),
                      "error al final (m)": float(error[-1])})
    return pd.DataFrame(filas).set_index("método")


def tabla_de_cruces(analisis, alturas_pisos, itinerario, verdad_altura):
    """Cruces de pisos con la mejor estimación; con sesión simulada agrega el instante real."""
    altura = analisis.altura[ascensor.KALMAN_BARO_ZUPT]
    cruces = ascensor.cruces_de_pisos(analisis.t_s, altura, analisis.paradas, alturas_pisos, itinerario)
    if verdad_altura is not None and len(cruces) > 0:
        reales = ascensor.cruces_de_pisos(analisis.t_s, verdad_altura, analisis.paradas,
                                          alturas_pisos, itinerario)
        cruces["t_real_s"] = reales["t_biseccion_s"]
        cruces["error_s"] = cruces["t_biseccion_s"] - cruces["t_real_s"]
    return cruces


def _formato(tabla):
    return tabla.to_string(float_format=lambda v: f"{v:.4g}")


def texto_reporte(sesion, analisis, descripcion_referencia, secciones):
    """Arma el reporte: encabezado y una sección por cada (título, texto) de la lista."""
    paradas = analisis.paradas
    lineas = [
        "ANÁLISIS DEL ASCENSOR",
        f"Carpeta: {sesion.carpeta}",
        f"Duración: {analisis.t_s[-1]:.1f} s   Paradas: {len(paradas)}   "
        f"Recorridos: {len(paradas) - 1}",
        f"Referencia de alturas: {descripcion_referencia}",
        f"Gravedad medida en el reposo inicial: {analisis.gravedad_medida:.4f} m/s² "
        f"(g de Quito en config.py: {config.G_QUITO})",
        f"Inclinación del dispositivo respecto a la vertical: {analisis.inclinacion_grados:.2f}°",
    ]
    for titulo, texto in secciones:
        lineas += ["", titulo, "-" * len(titulo), texto]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def _cargar_verdad(carpeta_sesion):
    """Altura y velocidad verdaderas (solo existen en sesiones simuladas), o (None, None)."""
    archivo = Path(carpeta_sesion) / generar.ARCHIVO_VERDAD
    if not archivo.exists():
        return None, None
    verdad = pd.read_csv(archivo)
    altura = verdad["altura_m"].to_numpy() - verdad["altura_m"].iloc[0]
    return altura, verdad["velocidad_z_ms"].to_numpy()


def _guardar_graficas(carpeta_salida, sesion, analisis, alturas_pisos, itinerario,
                      verdad_altura, verdad_velocidad, resumen):
    alturas_rel = None
    if alturas_pisos is not None:
        alturas_rel = np.asarray(alturas_pisos) - alturas_pisos[itinerario[0]]
    graficas.guardar_figura(
        graficas.grafica_ascensor(
            analisis.t_s, {n: analisis.altura[n] for n in ESTIMACIONES_EN_LA_GRAFICA},
            {n: analisis.velocidad[n] for n in ESTIMACIONES_EN_LA_GRAFICA[1:]},
            sesion.eventos["t_s"], alturas_rel, verdad_altura, verdad_velocidad),
        carpeta_salida / "altura.png")
    if resumen is not None:
        graficas.guardar_figura(
            graficas.grafica_comparacion(
                resumen["RMS por recorrido (m)"].to_dict(),
                "Error del desplazamiento por recorrido (RMS)", "error (m), escala logarítmica"),
            carpeta_salida / "comparacion.png")
    if verdad_altura is not None:
        error = {n: analisis.altura[n] - verdad_altura for n in analisis.altura}
        graficas.guardar_figura(
            graficas.grafica_errores_en_el_tiempo(
                analisis.t_s,
                {n: error[n] for n in [ascensor.SESGO_INICIAL]},
                {n: error[n] for n in [ascensor.BAROMETRO, ascensor.CON_ZUPT,
                                       ascensor.KALMAN_ZUPT, ascensor.KALMAN_BARO_ZUPT]},
                "Error de altura sin usar las paradas", "Error de altura con correcciones y fusión"),
            carpeta_salida / "errores.png")


def analizar_y_guardar(carpeta_sesion, carpeta_salida, archivo_pisos=None, texto_itinerario=None,
                       archivo_calibracion=calibracion.ARCHIVO_CALIBRACION):
    """Analiza la sesión y guarda el reporte, las tablas y las gráficas.

    Devuelve un diccionario con el reporte (texto) y el análisis.
    """
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    cruda = lectura.cargar_sesion(carpeta_sesion)
    alturas_pisos, itinerario, descripcion = cargar_referencia(
        carpeta_sesion, archivo_pisos, texto_itinerario)
    verdad_altura, verdad_velocidad = _cargar_verdad(carpeta_sesion)

    hay_calibracion = Path(archivo_calibracion).exists()
    sesion = cruda
    if hay_calibracion:
        sesion = calibracion.aplicar_calibracion(cruda, calibracion.cargar_calibracion(archivo_calibracion))
    analisis = ascensor.analizar(sesion)

    secciones, resumen = [], None
    if alturas_pisos is None:
        alturas = {n: ascensor.alturas_en_paradas(analisis.t_s, h, analisis.paradas)
                   for n, h in analisis.altura.items()}
        secciones.append(("ALTURA CALCULADA EN CADA PARADA (m)", _formato(pd.DataFrame(alturas))))
    else:
        if itinerario is None:
            h_paradas = ascensor.alturas_en_paradas(
                analisis.t_s, analisis.altura[ascensor.KALMAN_BARO_ZUPT], analisis.paradas)
            itinerario = ascensor.asignar_pisos(h_paradas + alturas_pisos[0], alturas_pisos)
            descripcion += "; itinerario deducido: " + ",".join(str(p) for p in itinerario)
        referencia = alturas_de_referencia_en_paradas(alturas_pisos, itinerario)
        resumen, recorridos = resumen_de_errores(analisis, referencia, verdad_altura)
        estado = "CON calibración de seis caras" if hay_calibracion else "SIN calibración"
        secciones.append((f"ERROR DE CADA ESTIMACIÓN ({estado})", _formato(resumen)))
        if hay_calibracion:
            resumen_crudo, _ = resumen_de_errores(ascensor.analizar(cruda), referencia, verdad_altura)
            secciones.append(("LO MISMO, SIN CALIBRACIÓN DE SEIS CARAS", _formato(resumen_crudo)))
        secciones.append(("MÉTODOS DE INTEGRACIÓN COMPARADOS (datos del sensor)",
                          _formato(comparar_metodos_de_integracion(analisis, referencia))))
        if verdad_altura is not None:
            secciones.append(("ERROR SOLO DEL MÉTODO (aceleración exacta, sin errores de sensor)",
                              _formato(error_solo_del_metodo(carpeta_sesion, sesion))
                              + "\nComparar con la tabla anterior: la diferencia es el error del sensor."))
        cruces = tabla_de_cruces(analisis, alturas_pisos, itinerario, verdad_altura)
        sin_secante = int(cruces["t_secante_s"].isna().sum()) if len(cruces) else 0
        secciones.append((
            "CRUCE DE PISOS (raíz de altura(t) − altura del piso)",
            _formato(cruces) + f"\nLa secante no encontró la raíz en {sin_secante} de {len(cruces)} "
            "cruces (parte de un tramo plano); la bisección siempre la encuentra."))
        recorridos.to_csv(carpeta_salida / "recorridos.csv", index=False, float_format="%.5f")
        cruces.to_csv(carpeta_salida / "cruces.csv", index=False, float_format="%.5f")

    reporte = texto_reporte(sesion, analisis, descripcion, secciones)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    _guardar_graficas(carpeta_salida, sesion, analisis, alturas_pisos, itinerario,
                      verdad_altura, verdad_velocidad, resumen)
    return {"reporte": reporte, "analisis": analisis}


def main():
    analizador = argparse.ArgumentParser(description="Analiza un registro de ascensor.")
    analizador.add_argument("sesion", nargs="?", default=None,
                            help="carpeta de la sesión (por defecto, el ascensor simulado)")
    analizador.add_argument("--pisos", default=None,
                            help="CSV con las columnas piso,altura_m (referencia real)")
    analizador.add_argument("--itinerario", default=None,
                            help="piso de cada parada, separados por comas (de la bitácora)")
    argumentos = analizador.parse_args()

    carpeta_sesion = Path(argumentos.sesion or generar.carpeta_de_escenario("ascensor"))
    carpeta_salida = config.CARPETA_RESULTADOS / "ascensor" / carpeta_sesion.name
    resultado = analizar_y_guardar(carpeta_sesion, carpeta_salida, argumentos.pisos,
                                   argumentos.itinerario)
    print(resultado["reporte"])
    print(f"\nReporte, tablas y gráficas guardados en: {carpeta_salida}")


if __name__ == "__main__":
    main()
