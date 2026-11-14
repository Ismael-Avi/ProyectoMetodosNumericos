"""Gráficas del proyecto (matplotlib). Cada función devuelve la figura; guardar_figura la escribe.

Estilo común: un solo eje vertical por panel, una magnitud por panel, rejilla tenue y los
mismos tres colores para los ejes x, y, z en todas las gráficas.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # dibuja a archivos, sin abrir ventanas
import matplotlib.pyplot as plt
import numpy as np

from navinercial import verificacion

# Colores de los ejes x, y, z (se distinguen también con daltonismo) y tonos neutros.
COLOR_EJE = {"x": "#2a78d6", "y": "#eb6834", "z": "#1baf7a"}
COLOR_SERIE = "#2a78d6"
COLOR_REFERENCIA = "#52514e"
COLOR_REJILLA = "#e1e0d9"
COLOR_TEXTO = "#0b0b0b"
COLOR_TEXTO_SECUNDARIO = "#52514e"

# Para dibujar no hace falta cada muestra: con más puntos que estos la gráfica se ve igual
# y tarda mucho más. Solo afecta al dibujo, nunca a los cálculos.
MAX_PUNTOS_POR_CURVA = 20000


def _aplicar_estilo(eje, titulo=None, etiqueta_x=None, etiqueta_y=None):
    """Estilo común de un panel: rejilla tenue, sin bordes superior ni derecho."""
    eje.grid(True, color=COLOR_REJILLA, linewidth=0.8)
    eje.set_axisbelow(True)
    for lado in ["top", "right"]:
        eje.spines[lado].set_visible(False)
    for lado in ["left", "bottom"]:
        eje.spines[lado].set_color("#c3c2b7")
    eje.tick_params(colors=COLOR_TEXTO_SECUNDARIO, labelsize=9)
    if titulo:
        eje.set_title(titulo, fontsize=11, color=COLOR_TEXTO, loc="left")
    if etiqueta_x:
        eje.set_xlabel(etiqueta_x, fontsize=9, color=COLOR_TEXTO_SECUNDARIO)
    if etiqueta_y:
        eje.set_ylabel(etiqueta_y, fontsize=9, color=COLOR_TEXTO_SECUNDARIO)


def _leyenda_arriba(eje, columnas=3):
    """Leyenda sobre el panel, a la derecha del título, para que no tape los datos."""
    eje.legend(fontsize=8, ncols=columnas, loc="lower right", bbox_to_anchor=(1.0, 1.0),
               frameon=False, borderaxespad=0.2)


def _diezmar(*arreglos):
    """Toma una muestra de cada "paso" para que no queden más de MAX_PUNTOS_POR_CURVA puntos."""
    paso = max(1, len(arreglos[0]) // MAX_PUNTOS_POR_CURVA)
    return [np.asarray(arreglo)[::paso] for arreglo in arreglos]


def _escala_de_tiempo(duracion_s):
    """Elige minutos para registros largos y segundos para registros cortos."""
    if duracion_s > 600:
        return 1 / 60.0, "tiempo (min)"
    return 1.0, "tiempo (s)"


def guardar_figura(figura, ruta):
    """Guarda la figura como PNG (crea la carpeta si no existe) y la cierra."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(figura)
    return ruta


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------

def grafica_intervalos(sesion, verificaciones):
    """Intervalo entre muestras: en el tiempo (izquierda) y su histograma (derecha).

    En el tiempo se dibujan TODOS los intervalos (los huecos se ven como puntos altos, marcados
    con un círculo). El histograma solo usa muestras consecutivas y muestra el jitter.
    """
    figura, ejes = plt.subplots(2, 2, figsize=(12, 6.5), width_ratios=[2, 1])
    tablas = {"imu": sesion.imu, "baro": sesion.baro}
    for fila, (nombre, tabla) in enumerate(tablas.items()):
        v = verificaciones[nombre]
        seq, t_s = tabla["seq"].to_numpy(), tabla["t_s"].to_numpy()
        factor, etiqueta_tiempo = _escala_de_tiempo(v.duracion_s)
        periodo_nominal_ms = 1000.0 / v.fs_nominal_hz

        eje = ejes[fila, 0]
        eje.plot(t_s[1:] * factor, np.diff(t_s) * 1000, ".", markersize=1.5,
                 color=COLOR_SERIE, rasterized=True)
        eje.plot(v.huecos["t_s"] * factor, v.huecos["intervalo_s"] * 1000, "o", markersize=6,
                 markerfacecolor="none", color="#d03b3b", label=f"huecos ({len(v.huecos)})")
        eje.axhline(periodo_nominal_ms, color=COLOR_REFERENCIA, linewidth=1, linestyle="--",
                    label=f"período nominal ({periodo_nominal_ms:.1f} ms)")
        _leyenda_arriba(eje, columnas=2)
        _aplicar_estilo(eje, f"{nombre}: intervalo entre muestras", etiqueta_tiempo,
                        "intervalo (ms)")

        eje = ejes[fila, 1]
        intervalos_us = verificacion.intervalos_consecutivos_us(seq, t_s)
        eje.hist(intervalos_us, bins=60, color=COLOR_SERIE)
        eje.axvline(periodo_nominal_ms * 1000, color=COLOR_REFERENCIA, linewidth=1, linestyle="--")
        _aplicar_estilo(
            eje, f"{nombre}: jitter (desviación {v.intervalo['std_us']:.0f} µs)",
            "intervalo entre muestras consecutivas (µs)", "cantidad de muestras")
    figura.tight_layout()
    return figura


def grafica_frecuencia(sesion, verificaciones):
    """Frecuencia de muestreo real en ventanas consecutivas, comparada con la nominal."""
    figura, ejes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    tablas = {"imu": sesion.imu, "baro": sesion.baro}
    for eje, (nombre, tabla) in zip(ejes, tablas.items()):
        v = verificaciones[nombre]
        factor, etiqueta_tiempo = _escala_de_tiempo(v.duracion_s)
        centros, frecuencias = verificacion.frecuencia_por_ventanas(
            tabla["seq"], tabla["t_s"], v.ventana_s)

        eje.plot(centros * factor, frecuencias, "-o", markersize=3, linewidth=1.5,
                 color=COLOR_SERIE, label=f"real, en ventanas de {v.ventana_s:.0f} s")
        eje.axhline(v.fs_nominal_hz, color=COLOR_REFERENCIA, linewidth=1, linestyle="--",
                    label=f"nominal ({v.fs_nominal_hz:g} Hz)")
        eje.ticklabel_format(useOffset=False, axis="y")
        _leyenda_arriba(eje, columnas=2)
        _aplicar_estilo(
            eje, f"{nombre}: inicio {v.fs_inicio_hz:.4f} Hz, final {v.fs_final_hz:.4f} Hz",
            etiqueta_y="frecuencia real (Hz)")
    ejes[-1].set_xlabel(etiqueta_tiempo, fontsize=9, color=COLOR_TEXTO_SECUNDARIO)
    figura.tight_layout()
    return figura


# ---------------------------------------------------------------------------
# Señales
# ---------------------------------------------------------------------------

def _dibujar_tres_ejes(eje, t, tabla, columnas):
    """Dibuja las tres componentes (x, y, z) de un sensor en un mismo panel."""
    for columna in columnas:
        letra = columna[-1]
        validas = tabla[columna].notna().to_numpy()   # el magnetómetro tiene celdas vacías
        t_dibujo, valores = _diezmar(t[validas], tabla[columna].to_numpy()[validas])
        eje.plot(t_dibujo, valores, linewidth=0.7, color=COLOR_EJE[letra], label=f"eje {letra}")
    _leyenda_arriba(eje, columnas=3)


def grafica_senales(sesion):
    """Señales de la sesión en unidades físicas: un panel por magnitud."""
    hay_magnetometro = sesion.meta["tiene_magnetometro"]
    n_paneles = 5 if hay_magnetometro else 4
    figura, ejes = plt.subplots(n_paneles, 1, figsize=(11, 2.4 * n_paneles), sharex=True)
    factor, etiqueta_tiempo = _escala_de_tiempo(sesion.imu["t_s"].iloc[-1])
    t_imu = sesion.imu["t_s"].to_numpy() * factor
    t_baro = sesion.baro["t_s"].to_numpy() * factor

    _dibujar_tres_ejes(ejes[0], t_imu, sesion.imu, ["ax", "ay", "az"])
    _aplicar_estilo(ejes[0], "Acelerómetro (sin calibrar)", etiqueta_y="aceleración (m/s²)")

    _dibujar_tres_ejes(ejes[1], t_imu, sesion.imu, ["gx", "gy", "gz"])
    _aplicar_estilo(ejes[1], "Giroscopio (sin calibrar)", etiqueta_y="velocidad angular (rad/s)")

    ejes[2].plot(*_diezmar(t_baro, sesion.baro["presion_Pa"]), linewidth=0.7, color=COLOR_SERIE)
    ejes[2].ticklabel_format(useOffset=False, axis="y")
    _aplicar_estilo(ejes[2], "Barómetro: presión", etiqueta_y="presión (Pa)")

    ejes[3].plot(*_diezmar(t_baro, sesion.baro["temperatura_C"]), linewidth=0.7, color=COLOR_SERIE)
    _aplicar_estilo(ejes[3], "Barómetro: temperatura", etiqueta_y="temperatura (°C)")

    if hay_magnetometro:
        _dibujar_tres_ejes(ejes[4], t_imu, sesion.imu, ["mx", "my", "mz"])
        _aplicar_estilo(ejes[4], "Magnetómetro (sin calibrar)", etiqueta_y="campo (µT)")

    # Marcas del botón: una línea vertical en cada panel.
    for eje in ejes:
        for t_evento in sesion.eventos["t_s"]:
            eje.axvline(t_evento * factor, color=COLOR_REFERENCIA, linewidth=0.8, linestyle=":")
    ejes[-1].set_xlabel(etiqueta_tiempo, fontsize=9, color=COLOR_TEXTO_SECUNDARIO)
    figura.tight_layout()
    return figura


# ---------------------------------------------------------------------------
# Caracterización y calibración
# ---------------------------------------------------------------------------

def grafica_ruido_reposo(sesion, caracterizacion):
    """Histograma del ruido de cada eje del acelerómetro y del giroscopio en reposo.

    A cada señal se le resta su media, para ver solo cómo se reparte alrededor de ella.
    """
    figura, ejes = plt.subplots(2, 3, figsize=(12, 6))
    columnas = [["ax", "ay", "az"], ["gx", "gy", "gz"]]
    for fila in range(2):
        for columna_panel, columna in enumerate(columnas[fila]):
            eje = ejes[fila, columna_panel]
            valores = sesion.imu[columna].to_numpy()
            datos = caracterizacion.loc[columna]
            eje.hist(valores - datos["media"], bins=60, color=COLOR_EJE[columna[-1]])
            _aplicar_estilo(
                eje, f"{columna}: media {datos['media']:.4f}, ruido {datos['ruido']:.4f}",
                f"{columna} − media ({datos['unidad']})", "cantidad de muestras")
    figura.tight_layout()
    return figura


def grafica_allan(curvas_accel, curvas_gyro):
    """Desviación de Allan del acelerómetro y del giroscopio (escalas logarítmicas).

    curvas_accel, curvas_gyro: diccionarios {columna: (taus, desviaciones)}.
    """
    figura, ejes = plt.subplots(1, 2, figsize=(12, 4.5))
    paneles = [(ejes[0], curvas_accel, "Acelerómetro", "desviación de Allan (m/s²)"),
               (ejes[1], curvas_gyro, "Giroscopio", "desviación de Allan (rad/s)")]
    for eje, curvas, titulo, etiqueta_y in paneles:
        for columna, (taus, desviaciones) in curvas.items():
            eje.loglog(taus, desviaciones, "-o", markersize=3, linewidth=1.5,
                       color=COLOR_EJE[columna[-1]], label=f"eje {columna[-1]}")
        _leyenda_arriba(eje)
        _aplicar_estilo(eje, titulo, "tiempo de promediado τ (s)", etiqueta_y)
    figura.tight_layout()
    return figura


def _magnitud_promediada(tabla, t, en_cara, muestras_por_punto=100):
    """Magnitud del acelerómetro promediada en grupos, para que el ruido no tape el valor."""
    magnitud = np.linalg.norm(tabla.loc[en_cara, ["ax", "ay", "az"]].to_numpy(), axis=1)
    n_grupos = max(1, len(magnitud) // muestras_por_punto)
    usadas = n_grupos * min(muestras_por_punto, len(magnitud))
    tiempos = t[en_cara][:usadas].reshape(n_grupos, -1).mean(axis=1)
    return tiempos, magnitud[:usadas].reshape(n_grupos, -1).mean(axis=1)


def grafica_caras(sesion, sesion_calibrada, caras, g):
    """Seis caras: las caras detectadas y la magnitud de la gravedad antes y después de calibrar.

    Si la calibración es buena, la magnitud calibrada vale g en todas las caras.
    """
    figura, ejes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    t = sesion.imu["t_s"].to_numpy()

    _dibujar_tres_ejes(ejes[0], t, sesion.imu, ["ax", "ay", "az"])
    for _, cara in caras.iterrows():
        ejes[0].axvspan(cara["t_inicio_s"], cara["t_fin_s"], color=COLOR_REJILLA, alpha=0.6, lw=0)
        ejes[0].text((cara["t_inicio_s"] + cara["t_fin_s"]) / 2, 0.75, cara["cara"],
                     transform=ejes[0].get_xaxis_transform(), ha="center", va="center",
                     fontsize=12, color=COLOR_TEXTO)
    _aplicar_estilo(ejes[0], "Acelerómetro sin calibrar y caras detectadas (zonas grises)",
                    etiqueta_y="aceleración (m/s²)")

    # Magnitud solo en los tramos quietos (en los giros no tiene por qué valer g).
    series = [(sesion.imu, "#898781", "sin calibrar"),
              (sesion_calibrada.imu, COLOR_SERIE, "calibrado")]
    for numero, (_, cara) in enumerate(caras.iterrows()):
        en_cara = (t >= cara["t_inicio_s"]) & (t <= cara["t_fin_s"])
        for tabla, color, etiqueta in series:
            tiempos, promedios = _magnitud_promediada(tabla, t, en_cara)
            ejes[1].plot(tiempos, promedios, linewidth=1.5, color=color,
                         label=etiqueta if numero == 0 else None)
    ejes[1].axhline(g, color=COLOR_REFERENCIA, linewidth=1, linestyle="--",
                    label=f"g de Quito ({g} m/s²)")
    _leyenda_arriba(ejes[1])
    _aplicar_estilo(ejes[1], "Magnitud de la gravedad en cada cara", "tiempo (s)", "|a| (m/s²)")
    figura.tight_layout()
    return figura


# ---------------------------------------------------------------------------
# Métodos numéricos
# ---------------------------------------------------------------------------

COLORES_DE_METODOS = ["#2a78d6", "#eb6834", "#1baf7a"]


def grafica_convergencia(pasos, errores_por_metodo, titulo, etiqueta_x, etiqueta_y):
    """Error de cada método según el paso h, en escala logarítmica en los dos ejes.

    En esta escala un error proporcional a h^p se ve como una recta de pendiente p: cuanto
    más inclinada la recta, más rápido mejora el método al reducir el paso.

    errores_por_metodo: diccionario {nombre del método: arreglo de errores, uno por paso}.
    """
    figura, eje = plt.subplots(figsize=(7.5, 4.8))
    for (nombre, errores), color in zip(errores_por_metodo.items(), COLORES_DE_METODOS):
        eje.loglog(pasos, errores, "o-", color=color, linewidth=2, markersize=5, label=nombre)
    _leyenda_arriba(eje)
    _aplicar_estilo(eje, titulo, etiqueta_x, etiqueta_y)
    return figura


def grafica_iteraciones_raices(errores_por_metodo, titulo):
    """Error de cada método de raíces en cada iteración (eje vertical logarítmico)."""
    figura, eje = plt.subplots(figsize=(7.5, 4.8))
    for (nombre, errores), color in zip(errores_por_metodo.items(), COLORES_DE_METODOS):
        iteraciones = np.arange(1, len(errores) + 1)
        eje.semilogy(iteraciones, errores, "o-", color=color, linewidth=2, markersize=5,
                     label=nombre)
    _leyenda_arriba(eje)
    _aplicar_estilo(eje, titulo, "iteración", "error |x − raíz|")
    return figura


# ---------------------------------------------------------------------------
# Ascensor
# ---------------------------------------------------------------------------

COLORES_DE_SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#8a5cd6"]
COLOR_VERDAD = "#52514e"
COLOR_EVENTO = "#898781"


def _marcar_eventos(eje, tiempos_eventos_s):
    """Marca cada pulsación del botón con una raya corta en la parte baja del panel."""
    for t_evento in tiempos_eventos_s:
        eje.axvline(t_evento, ymin=0.0, ymax=0.04, color=COLOR_EVENTO, linewidth=1)


def _dibujar_series(eje, t_s, series, verdad=None):
    """Dibuja varias curvas (diccionario nombre -> valores) y, si hay, la verdad en gris."""
    if verdad is not None:
        t_d, v_d = _diezmar(t_s, verdad)
        eje.plot(t_d, v_d, color=COLOR_VERDAD, linewidth=3, alpha=0.35, label="verdad (simulador)")
    for (nombre, valores), color in zip(series.items(), COLORES_DE_SERIES):
        t_d, v_d = _diezmar(t_s, valores)
        eje.plot(t_d, v_d, color=color, linewidth=1.3, label=nombre)


def grafica_ascensor(t_s, alturas, velocidades, tiempos_eventos_s, alturas_pisos_m=None,
                     verdad_altura=None, verdad_velocidad=None):
    """Altura (arriba) y velocidad (abajo) del ascensor en el tiempo.

    alturas, velocidades: diccionarios {nombre de la estimación: arreglo}.
    alturas_pisos_m: alturas de referencia de los pisos (líneas horizontales), o None.
    """
    figura, (eje_h, eje_v) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                          height_ratios=[3, 2])
    if alturas_pisos_m is not None:
        for numero, altura_piso in enumerate(alturas_pisos_m):
            eje_h.axhline(altura_piso, color=COLOR_REJILLA, linewidth=1.2, zorder=0)
            eje_h.annotate(f"piso {numero}", (t_s[-1], altura_piso), xytext=(4, 0),
                           textcoords="offset points", fontsize=8, va="center",
                           color=COLOR_TEXTO_SECUNDARIO, annotation_clip=False)
    _dibujar_series(eje_h, t_s, alturas, verdad_altura)
    _marcar_eventos(eje_h, tiempos_eventos_s)
    _leyenda_arriba(eje_h, columnas=4)
    _aplicar_estilo(eje_h, "Altura", None, "altura sobre el punto de partida (m)")
    eje_h.grid(False)

    _dibujar_series(eje_v, t_s, velocidades, verdad_velocidad)
    _marcar_eventos(eje_v, tiempos_eventos_s)
    _aplicar_estilo(eje_v, "Velocidad vertical (rayas grises abajo: pulsaciones del botón)",
                    "tiempo (s)", "velocidad (m/s)")
    figura.tight_layout()
    return figura


def grafica_errores_en_el_tiempo(t_s, errores_arriba, errores_abajo, titulo_arriba, titulo_abajo,
                                 etiqueta_y="error de altura (m)"):
    """Error de varias estimaciones en el tiempo, en dos paneles con escalas distintas.

    Arriba van las estimaciones con error grande y abajo las de error pequeño; en un solo
    panel las segundas se verían como una línea plana.
    """
    figura, (eje_a, eje_b) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True)
    for eje, errores, titulo in [(eje_a, errores_arriba, titulo_arriba),
                                 (eje_b, errores_abajo, titulo_abajo)]:
        _dibujar_series(eje, t_s, errores)
        eje.axhline(0.0, color=COLOR_REFERENCIA, linewidth=1)
        _leyenda_arriba(eje, columnas=2)
        _aplicar_estilo(eje, titulo, None, etiqueta_y)
    eje_b.set_xlabel("tiempo (s)", fontsize=9, color=COLOR_TEXTO_SECUNDARIO)
    figura.tight_layout()
    return figura


def grafica_comparacion(valores_por_nombre, titulo, etiqueta_x):
    """Compara un número por estimación (por ejemplo el error RMS) con puntos en escala log.

    Se usa escala logarítmica porque los errores van de centímetros a kilómetros. Cada punto
    lleva su valor escrito al lado.
    """
    nombres = list(valores_por_nombre)[::-1]          # el primero queda arriba
    valores = [valores_por_nombre[n] for n in nombres]
    figura, eje = plt.subplots(figsize=(9, 0.5 * len(nombres) + 1.6))
    eje.scatter(valores, range(len(nombres)), s=60, color=COLOR_SERIE, zorder=3)
    for posicion, valor in enumerate(valores):
        eje.annotate(f"{valor:.3g}", (valor, posicion), xytext=(8, 0),
                     textcoords="offset points", fontsize=9, va="center", color=COLOR_TEXTO)
    eje.set_xscale("log")
    eje.set_yticks(range(len(nombres)), nombres)
    eje.margins(x=0.15, y=0.12)
    _aplicar_estilo(eje, titulo, etiqueta_x, None)
    eje.tick_params(axis="y", labelsize=9, colors=COLOR_TEXTO)
    return figura


def grafica_prediccion(t_s, observado, predicho, titulo, etiqueta_y, nombre_observado,
                       nombre_predicho):
    """Compara una curva observada (línea) con la predicha por las fórmulas (línea de trazos)."""
    figura, eje = plt.subplots(figsize=(8.5, 4.8))
    t_d, o_d, p_d = _diezmar(t_s, observado, predicho)
    eje.plot(t_d, o_d, color=COLOR_SERIE, linewidth=2, label=nombre_observado)
    eje.plot(t_d, p_d, color=COLOR_EJE["y"], linewidth=2, linestyle="--", label=nombre_predicho)
    _leyenda_arriba(eje, columnas=2)
    _aplicar_estilo(eje, titulo, "tiempo (s)", etiqueta_y)
    return figura
