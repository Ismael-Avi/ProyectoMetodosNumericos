"""Analiza uno o varios viajes en metro: velocidad, distancia por tramo, rumbo y mapa.

Uso (desde la carpeta procesamiento/):

    python -m scripts.analizar_metro                          # los tres viajes simulados
    python -m scripts.analizar_metro SESION_1 SESION_2 ...
    python -m scripts.analizar_metro datos/sesion_004 --estaciones "Quitumbe,Morán Valverde,Solanda"

Referencia (posición de las estaciones y longitud de los tramos):
- Sesión simulada: verdad_escenario.json (ruta SINTÉTICA del simulador, no es el metro real).
- Sesión real: --estaciones con los nombres de las estaciones del viaje, en orden. Las
  coordenadas se leen de datos_referencia/estaciones_metro.csv y las longitudes de
  datos_referencia/tramos_metro.csv. Mientras esos archivos no tengan datos, el viaje se
  analiza sin referencia: se obtienen distancias, velocidades y la forma del recorrido, pero
  no errores ni la posición sobre el mapa real.

Si existe resultados/calibracion/calibracion.json (seis caras), se aplica.

Guarda en resultados/metro/<nombre de la sesión>/:
    reporte.txt, tramos.csv, mapa.png, viaje.png, rumbo.png
y, si hay más de un viaje, en resultados/metro/combinado/:
    reporte.txt, mapa.png      los viajes juntos y la dispersión de cada tramo
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial import calibracion, graficas, lectura, metro
from simulador import generar

ARCHIVO_ESTACIONES = config.CARPETA_REFERENCIA / "estaciones_metro.csv"
ARCHIVO_TRAMOS = config.CARPETA_REFERENCIA / "tramos_metro.csv"


# ---------------------------------------------------------------------------
# Referencia
# ---------------------------------------------------------------------------

def _longitudes_de_tramos(nombres):
    """Longitud de cada tramo del viaje según tramos_metro.csv, o None si falta alguna."""
    if not ARCHIVO_TRAMOS.exists():
        return None
    tramos = pd.read_csv(ARCHIVO_TRAMOS, comment="#").dropna(subset=["longitud_m"])
    longitudes = []
    for desde, hasta in zip(nombres[:-1], nombres[1:]):
        fila = tramos[((tramos["desde"] == desde) & (tramos["hasta"] == hasta))
                      | ((tramos["desde"] == hasta) & (tramos["hasta"] == desde))]
        if len(fila) == 0:
            return None
        longitudes.append(float(fila["longitud_m"].iloc[0]))
    return longitudes


def referencia_desde_csv(nombres):
    """Referencia de un viaje real a partir de los CSV de datos_referencia/.

    Devuelve (referencia o None, descripción). La referencia tiene el mismo contenido que
    verdad_escenario.json: estaciones (con x_m, y_m), longitudes_tramos_m, rumbo_inicial_rad
    y trazado.
    """
    estaciones = pd.read_csv(ARCHIVO_ESTACIONES, comment="#").set_index("estacion")
    desconocidas = [n for n in nombres if n not in estaciones.index]
    if desconocidas:
        raise ValueError(f"Estaciones que no están en {ARCHIVO_ESTACIONES.name}: {desconocidas}")
    del_viaje = estaciones.loc[nombres]
    if del_viaje[["lat", "lon"]].isna().any().any():
        return None, (f"{ARCHIVO_ESTACIONES.name} todavía no tiene coordenadas: "
                      "se analiza sin referencia")
    x, y = metro.geograficas_a_locales(del_viaje["lat"].to_numpy(), del_viaje["lon"].to_numpy(),
                                       del_viaje["lat"].iloc[0], del_viaje["lon"].iloc[0])
    referencia = {
        "estaciones": [{"nombre": n, "x_m": float(x[k]), "y_m": float(y[k])}
                       for k, n in enumerate(nombres)],
        "longitudes_tramos_m": _longitudes_de_tramos(nombres),
        # Aproximación: dirección en línea recta hacia la segunda estación.
        # TODO: usar la dirección real del túnel al salir de la primera estación.
        "rumbo_inicial_rad": float(np.arctan2(y[1] - y[0], x[1] - x[0])),
        "trazado": {"x_m": [float(v) for v in x], "y_m": [float(v) for v in y]},
    }
    return referencia, f"{ARCHIVO_ESTACIONES.name} (trazado aproximado: líneas rectas entre estaciones)"


def cargar_referencia(carpeta_sesion, texto_estaciones):
    """Devuelve (referencia o None, descripción) para una sesión."""
    archivo_verdad = Path(carpeta_sesion) / generar.ARCHIVO_VERDAD_ESCENARIO
    if archivo_verdad.exists():
        with open(archivo_verdad, encoding="utf-8") as archivo:
            return json.load(archivo), "SINTÉTICA (verdad_escenario.json del simulador)"
    if texto_estaciones is None:
        return None, "no hay (usar --estaciones con los nombres de las estaciones del viaje)"
    return referencia_desde_csv([n.strip() for n in texto_estaciones.split(",")])


# ---------------------------------------------------------------------------
# Análisis de un viaje
# ---------------------------------------------------------------------------

def _cargar_verdad(carpeta_sesion):
    archivo = Path(carpeta_sesion) / generar.ARCHIVO_VERDAD
    return pd.read_csv(archivo) if archivo.exists() else None


def _errores_contra_la_verdad(analisis, verdad):
    """Errores de cada estimación contra la verdad del simulador (tabla)."""
    filas = []
    for nombre in analisis.velocidad:
        error_v = analisis.velocidad[nombre] - verdad["velocidad_ms"].to_numpy()
        error_p = np.hypot(analisis.x_m[nombre] - verdad["x_m"], analisis.y_m[nombre] - verdad["y_m"])
        filas.append({"estimación": nombre,
                      "RMS de velocidad (m/s)": float(np.sqrt(np.mean(error_v**2))),
                      "máx de velocidad (m/s)": float(np.max(np.abs(error_v))),
                      "error de posición máx (m)": float(error_p.max()),
                      "error de posición final (m)": float(error_p.iloc[-1])})
    return pd.DataFrame(filas).set_index("estimación")


def _formato(tabla):
    return tabla.to_string(float_format=lambda v: f"{v:.4g}")


def _texto_magnetometro(magnetometro):
    if magnetometro is None:
        return "Magnetómetro: no hay (MPU-6500) o no tiene lecturas."
    estado = "CONFIABLE" if magnetometro["confiable"] else "NO CONFIABLE"
    return (f"Magnetómetro: {estado}. La magnitud del campo varía un "
            f"{100 * magnetometro['variacion']:.0f} % durante el viaje (límite: "
            f"{100 * config.MAG_VARIACION_MAXIMA_CONFIABLE:.0f} %). Diferencia con el rumbo del "
            f"giroscopio: {magnetometro['diferencia_rms_grados']:.1f}° RMS.")


def texto_reporte(sesion, analisis, descripcion, tramos, estaciones, errores_verdad, error_rumbo):
    lineas = [
        "ANÁLISIS DE UN VIAJE EN METRO",
        f"Carpeta: {sesion.carpeta}",
        f"Duración: {analisis.t_s[-1]:.1f} s   Paradas: {len(analisis.paradas)}   "
        f"Tramos: {len(analisis.paradas) - 1}",
        f"Referencia: {descripcion}",
        f"Orientación del dispositivo: \"adelante\" está a {analisis.montaje_grados:.1f}° del eje x "
        "(medido en el primer arranque).",
        f"Giro total del rumbo: {np.degrees(analisis.rumbo_rad[-1] - analisis.rumbo_rad[0]):.1f}°",
        _texto_magnetometro(analisis.magnetometro),
        "", "TRAMOS (distancias en m)", "------------------------", _formato(tramos),
    ]
    if estaciones is not None:
        lineas += ["", "DISTANCIA ENTRE LA POSICIÓN CALCULADA Y CADA ESTACIÓN DE REFERENCIA (m)",
                   "-----------------------------------------------------------------------",
                   _formato(estaciones)]
    if errores_verdad is not None:
        lineas += ["", "ERRORES CONTRA LA VERDAD DEL SIMULADOR", "--------------------------------------",
                   _formato(errores_verdad),
                   f"Error máximo del rumbo por giroscopio: {error_rumbo:.2f}°"]
    return "\n".join(lineas)


def analizar_y_guardar(carpeta_sesion, carpeta_salida, texto_estaciones=None,
                       archivo_calibracion=calibracion.ARCHIVO_CALIBRACION):
    """Analiza un viaje y guarda reporte, tabla y gráficas. Devuelve un diccionario con el
    reporte, el análisis, la referencia y la tabla de tramos."""
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    sesion = lectura.cargar_sesion(carpeta_sesion)
    if Path(archivo_calibracion).exists():
        sesion = calibracion.aplicar_calibracion(sesion, calibracion.cargar_calibracion(archivo_calibracion))
    referencia, descripcion = cargar_referencia(carpeta_sesion, texto_estaciones)
    verdad = _cargar_verdad(carpeta_sesion)

    nombres, longitudes, tabla_estaciones, trazado, estaciones = None, None, None, None, None
    if referencia is None:
        analisis = metro.analizar(sesion)
    else:
        estaciones = referencia["estaciones"]
        nombres = [e["nombre"] for e in estaciones]
        longitudes = referencia["longitudes_tramos_m"]
        analisis = metro.analizar(sesion, referencia["rumbo_inicial_rad"], estaciones[0]["x_m"],
                                  estaciones[0]["y_m"], longitudes)
        tabla_estaciones = metro.errores_en_estaciones(analisis, estaciones)
        trazado = (referencia["trazado"]["x_m"], referencia["trazado"]["y_m"])
    if nombres is None and texto_estaciones is not None:
        nombres = [n.strip() for n in texto_estaciones.split(",")]
    tramos = metro.tabla_de_tramos(analisis, nombres, longitudes)

    errores_verdad, error_rumbo = None, None
    if verdad is not None:
        errores_verdad = _errores_contra_la_verdad(analisis, verdad)
        error_rumbo = float(np.degrees(np.max(np.abs(
            metro.diferencia_de_angulos(analisis.rumbo_rad, verdad["rumbo_rad"].to_numpy())))))

    reporte = texto_reporte(sesion, analisis, descripcion, tramos, tabla_estaciones,
                            errores_verdad, error_rumbo)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    tramos.to_csv(carpeta_salida / "tramos.csv", index=False, float_format="%.4f")
    _guardar_graficas(carpeta_salida, sesion, analisis, trazado, estaciones, verdad)
    return {"reporte": reporte, "analisis": analisis, "referencia": referencia, "tramos": tramos}


def _guardar_graficas(carpeta_salida, sesion, analisis, trazado, estaciones, verdad):
    nombres = [n for n in analisis.x_m if n != metro.SIN_ZUPT]
    graficas.guardar_figura(
        graficas.grafica_mapa({n: (analisis.x_m[n], analisis.y_m[n]) for n in nombres},
                              trazado, estaciones),
        carpeta_salida / "mapa.png")
    hay_verdad = verdad is not None
    graficas.guardar_figura(
        graficas.grafica_viaje(
            analisis.t_s, {n: analisis.velocidad[n] for n in [metro.ZUPT, metro.ZUPT_BARO]},
            {"barómetro (suavizado)": analisis.altura_baro_m}, sesion.eventos["t_s"],
            verdad["velocidad_ms"].to_numpy() if hay_verdad else None,
            verdad["altura_m"].to_numpy() if hay_verdad else None),
        carpeta_salida / "viaje.png")
    graficas.guardar_figura(
        graficas.grafica_rumbo(analisis.t_s, analisis.rumbo_rad, analisis.magnetometro,
                               verdad["rumbo_rad"].to_numpy() if hay_verdad else None),
        carpeta_salida / "rumbo.png")


# ---------------------------------------------------------------------------
# Varios viajes
# ---------------------------------------------------------------------------

def combinar_y_guardar(resultados, carpeta_salida):
    """Junta varios viajes: dispersión de cada tramo y mapa con todos. Devuelve el reporte."""
    carpeta_salida = Path(carpeta_salida)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    con_nombres = {viaje: r["tramos"] for viaje, r in resultados.items() if "desde" in r["tramos"]}
    lineas = ["VIAJES EN METRO COMBINADOS", f"Viajes: {', '.join(resultados)}", ""]
    if len(con_nombres) >= 2:
        dispersion = metro.combinar_viajes(con_nombres)
        lineas += [f"Distancia de cada tramo según \"{metro.ZUPT_BARO}\":", _formato(dispersion),
                   "dispersion_m: desviación estándar entre viajes (qué tanto se repite la medida)."]
        dispersion.to_csv(carpeta_salida / "dispersion.csv", float_format="%.3f")
    else:
        lineas.append("Para comparar tramos entre viajes hacen falta los nombres de las estaciones "
                      "(--estaciones) en al menos dos viajes.")

    # Mapa con todos los viajes (cada uno con su mejor estimación disponible).
    trayectorias, referencia = {}, None
    for viaje, r in resultados.items():
        analisis = r["analisis"]
        nombre = metro.AJUSTADO if metro.AJUSTADO in analisis.x_m else metro.ZUPT_BARO
        trayectorias[viaje] = (analisis.x_m[nombre], analisis.y_m[nombre])
        referencia = referencia or r["referencia"]
    trazado = estaciones = None
    if referencia is not None:
        trazado = (referencia["trazado"]["x_m"], referencia["trazado"]["y_m"])
        estaciones = referencia["estaciones"]
    graficas.guardar_figura(
        graficas.grafica_mapa(trayectorias, trazado, estaciones, "Todos los viajes sobre el mapa"),
        carpeta_salida / "mapa.png")
    reporte = "\n".join(lineas)
    (carpeta_salida / "reporte.txt").write_text(reporte, encoding="utf-8")
    return reporte


def main():
    analizador = argparse.ArgumentParser(description="Analiza viajes en metro.")
    analizador.add_argument("sesiones", nargs="*",
                            help="carpetas de las sesiones (por defecto, los viajes simulados)")
    analizador.add_argument("--estaciones", default=None,
                            help="nombres de las estaciones del viaje, en orden, separados por comas")
    argumentos = analizador.parse_args()

    carpetas = [Path(s) for s in argumentos.sesiones] or [
        generar.carpeta_de_escenario(nombre) for nombre in generar.ESCENARIOS_DE_METRO]
    carpeta_base = config.CARPETA_RESULTADOS / "metro"
    resultados = {}
    for carpeta in carpetas:
        resultado = analizar_y_guardar(carpeta, carpeta_base / carpeta.name, argumentos.estaciones)
        resultados[carpeta.name] = resultado
        print(resultado["reporte"], "\n")
    if len(resultados) > 1:
        print(combinar_y_guardar(resultados, carpeta_base / "combinado"))
    print(f"\nReportes y gráficas guardados en: {carpeta_base}")


if __name__ == "__main__":
    main()
