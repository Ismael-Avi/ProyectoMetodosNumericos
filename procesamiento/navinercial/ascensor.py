"""Análisis del ascensor: altura y velocidad en el tiempo a partir del acelerómetro y el barómetro.

Pasos:
1. Dirección vertical: con el dispositivo quieto al inicio, el acelerómetro solo mide la
   gravedad. El promedio de (ax, ay, az) apunta hacia arriba, aunque el dispositivo esté
   un poco inclinado.
2. Aceleración vertical del movimiento: se proyecta el acelerómetro sobre esa dirección y
   se resta la gravedad.
3. Integración (dos veces) con los métodos de metodos/integracion.py: velocidad y altura.
4. Correcciones con las paradas (correcciones.py): sesgo medido en cada parada y ZUPT.
5. Altura barométrica (barometro.py) y fusión (fusion.py).
6. Instante en que el ascensor cruza la altura de cada piso (metodos/raices.py).

Suposición: el dispositivo NO cambia de orientación durante el registro (va apoyado en el
piso del ascensor). Por eso no hace falta el giroscopio.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from navinercial import barometro, correcciones, fusion
from navinercial.lectura import COLUMNAS_ACCEL
from navinercial.metodos import integracion, interpolacion, raices

# Nombres de las estimaciones de altura que se comparan.
SIN_CORRECCIONES = "inercial: sin correcciones"
SESGO_INICIAL = "inercial: sesgo del reposo inicial"
CON_ZUPT = "inercial: sesgo en paradas + ZUPT"
BAROMETRO = "solo barómetro"
COMPLEMENTARIO = "fusión: complementario (con barómetro)"
KALMAN_ZUPT = "fusión: Kalman sin barómetro (ZUPT)"
KALMAN_BARO = "fusión: Kalman con barómetro"
KALMAN_BARO_ZUPT = "fusión: Kalman con barómetro y ZUPT"

TOLERANCIA_CRUCE_S = 1e-4      # exactitud pedida al instante de cruce: 0,1 ms


@dataclass
class AnalisisAscensor:
    """Resultado del análisis de un registro de ascensor."""

    t_s: np.ndarray                 # instantes del IMU
    paradas: list                   # pares (inicio_s, fin_s)
    aceleracion: np.ndarray         # vertical, sin gravedad, con el sesgo inicial restado (m/s²)
    gravedad_medida: float          # magnitud del acelerómetro en el reposo inicial (m/s²)
    inclinacion_grados: float       # ángulo entre el eje z del dispositivo y la vertical
    altura: dict = field(default_factory=dict)      # nombre de la estimación -> altura (m)
    velocidad: dict = field(default_factory=dict)   # nombre de la estimación -> velocidad (m/s)
    std_kalman: np.ndarray = None   # incertidumbre de la altura según el Kalman con barómetro


# ---------------------------------------------------------------------------
# Aceleración vertical
# ---------------------------------------------------------------------------

def vertical_en_reposo(imu, parada):
    """Dirección "hacia arriba" en ejes del dispositivo, medida con el dispositivo quieto.

    En reposo el acelerómetro mide solo la reacción a la gravedad, que apunta hacia arriba.
    Devuelve (vector unitario hacia arriba, magnitud medida en m/s²).
    """
    inicio, fin = parada
    quieto = (imu["t_s"] >= inicio) & (imu["t_s"] <= fin)
    promedio = imu.loc[quieto, COLUMNAS_ACCEL].mean().to_numpy()
    magnitud = np.linalg.norm(promedio)
    return promedio / magnitud, magnitud


def aceleracion_vertical(imu, vertical, gravedad):
    """Aceleración vertical del movimiento, en m/s² (positiva hacia arriba).

    Se proyecta el acelerómetro sobre la vertical (producto punto) y se resta la gravedad:

        a_vertical = (ax, ay, az) · vertical − gravedad
    """
    return imu[COLUMNAS_ACCEL].to_numpy() @ vertical - gravedad


def integrar(t_s, aceleracion, metodo="trapecio"):
    """Integra dos veces: aceleración -> velocidad -> altura. Empieza en reposo y en altura 0."""
    velocidad = integracion.integral_acumulada(t_s, aceleracion, metodo)
    altura = integracion.integral_acumulada(t_s, velocidad, metodo)
    return velocidad, altura


def integrar_con_zupt(t_s, aceleracion, paradas, metodo="trapecio"):
    """Integra usando lo que se sabe de las paradas (aceleración y velocidad cero).

    1. Resta el sesgo medido en cada parada.   2. Integra: velocidad.
    3. ZUPT: velocidad cero en las paradas.    4. Integra: altura.
    """
    corregida, _ = correcciones.restar_sesgo_por_paradas(t_s, aceleracion, paradas)
    velocidad = integracion.integral_acumulada(t_s, corregida, metodo)
    velocidad = correcciones.aplicar_zupt(t_s, velocidad, paradas)
    altura = integracion.integral_acumulada(t_s, velocidad, metodo)
    return velocidad, altura


# ---------------------------------------------------------------------------
# Barómetro
# ---------------------------------------------------------------------------

def altura_del_barometro(baro, parada_inicial):
    """Altura barométrica sobre el punto de partida, en cada muestra del barómetro (m).

    La presión de referencia es el promedio de la parada inicial.
    """
    inicio, fin = parada_inicial
    quieto = (baro["t_s"] >= inicio) & (baro["t_s"] <= fin)
    presion_referencia = baro.loc[quieto, "presion_Pa"].mean()
    return barometro.altura_barometrica(
        baro["presion_Pa"].to_numpy(), presion_referencia, baro["temperatura_C"].to_numpy())


# ---------------------------------------------------------------------------
# Análisis completo
# ---------------------------------------------------------------------------

def analizar(sesion, metodo="trapecio"):
    """Calcula todas las estimaciones de altura y velocidad de un registro de ascensor."""
    imu, baro = sesion.imu, sesion.baro
    t = imu["t_s"].to_numpy()
    paradas = correcciones.paradas_por_eventos(sesion.eventos["t_s"], t[0], t[-1])
    en_parada = correcciones.mascara_de_paradas(t, paradas)

    vertical, gravedad_medida = vertical_en_reposo(imu, paradas[0])
    a_nominal = aceleracion_vertical(imu, vertical, config.G_QUITO)
    a = aceleracion_vertical(imu, vertical, gravedad_medida)

    analisis = AnalisisAscensor(
        t_s=t, paradas=paradas, aceleracion=a, gravedad_medida=gravedad_medida,
        inclinacion_grados=float(np.degrees(np.arccos(abs(vertical[2])))))

    def guardar(nombre, velocidad, altura):
        analisis.velocidad[nombre] = velocidad
        analisis.altura[nombre] = altura

    guardar(SIN_CORRECCIONES, *integrar(t, a_nominal, metodo))
    guardar(SESGO_INICIAL, *integrar(t, a, metodo))
    guardar(CON_ZUPT, *integrar_con_zupt(t, a, paradas, metodo))

    # Barómetro: en sus propios instantes, y llevado a la base de tiempo del IMU.
    t_baro = baro["t_s"].to_numpy()
    h_baro = altura_del_barometro(baro, paradas[0])
    h_baro_en_t = interpolacion.interpolar_lineal(t_baro, h_baro, t)
    guardar(BAROMETRO, np.gradient(h_baro_en_t, t), h_baro_en_t)

    h, v = fusion.filtro_complementario(t, a, h_baro_en_t)
    guardar(COMPLEMENTARIO, v, h)

    baro_alineado = fusion.alinear_mediciones(t, t_baro, h_baro)
    h, v, _ = fusion.kalman_altura(t, a, en_parada=en_parada)
    guardar(KALMAN_ZUPT, v, h)
    h, v, analisis.std_kalman = fusion.kalman_altura(t, a, altura_baro=baro_alineado)
    guardar(KALMAN_BARO, v, h)
    h, v, _ = fusion.kalman_altura(t, a, altura_baro=baro_alineado, en_parada=en_parada)
    guardar(KALMAN_BARO_ZUPT, v, h)
    return analisis


# ---------------------------------------------------------------------------
# Resultados por parada y por recorrido
# ---------------------------------------------------------------------------

def alturas_en_paradas(t_s, altura, paradas):
    """Altura promedio en cada parada, en m (un valor por parada)."""
    _, promedio = correcciones.promedio_en_paradas(t_s, altura, paradas)
    return promedio


def asignar_pisos(alturas_paradas_m, alturas_pisos_m):
    """Para cada parada, el índice del piso de referencia más cercano a la altura calculada.

    alturas_pisos_m: altura de cada piso sobre el piso donde empezó el registro.
    """
    alturas_pisos_m = np.asarray(alturas_pisos_m, dtype=float)
    return [int(np.argmin(np.abs(alturas_pisos_m - h))) for h in alturas_paradas_m]


def desplazamientos(alturas_paradas_m):
    """Desplazamiento de cada recorrido: diferencia de altura entre paradas seguidas (m)."""
    return np.diff(np.asarray(alturas_paradas_m, dtype=float))


def tabla_de_recorridos(analisis, alturas_referencia_paradas_m):
    """Error del desplazamiento de cada recorrido, para cada estimación.

    alturas_referencia_paradas_m: altura real de cada parada sobre la parada inicial (del
    flexómetro en el experimento real; del simulador ahora).
    Devuelve una tabla: una fila por recorrido, con el desplazamiento real y el error (m)
    de cada estimación.
    """
    real = desplazamientos(alturas_referencia_paradas_m)
    tabla = pd.DataFrame({"recorrido": np.arange(1, len(real) + 1), "desplazamiento_real_m": real})
    for nombre, altura in analisis.altura.items():
        calculado = desplazamientos(alturas_en_paradas(analisis.t_s, altura, analisis.paradas))
        tabla[nombre] = calculado - real
    return tabla


def raiz_cuadratica_media(errores):
    """Raíz del promedio de los cuadrados (RMS): tamaño típico de un conjunto de errores."""
    errores = np.asarray(errores, dtype=float)
    return float(np.sqrt(np.mean(errores**2)))


# ---------------------------------------------------------------------------
# Cruce de pisos (búsqueda de raíces)
# ---------------------------------------------------------------------------

def instante_de_cruce(t_s, altura, altura_piso_m, metodo="biseccion", historial=None):
    """Instante en que la altura cruza altura_piso_m dentro del tramo dado, en s.

    Se busca la raíz de  f(t) = altura(t) − altura_piso,  donde altura(t) es la interpolación
    lineal de las muestras. t_s y altura deben cubrir UN solo recorrido (de una parada a la
    siguiente), para que haya un único cruce.

    metodo: "biseccion" (siempre converge) o "secante" (más rápida; puede fallar con ruido).
    """
    def f(instante):
        return interpolacion.interpolar_lineal(t_s, altura, [instante])[0] - altura_piso_m

    if metodo == "biseccion":
        return raices.biseccion(f, t_s[0], t_s[-1], TOLERANCIA_CRUCE_S, historial=historial)
    return raices.secante(f, t_s[0], t_s[-1], TOLERANCIA_CRUCE_S, historial=historial)


def _cruce_o_nan(t_s, altura, altura_piso_m, metodo):
    """instante_de_cruce que devuelve (NaN, 0) si el método no encuentra la raíz."""
    historial = []
    try:
        instante = instante_de_cruce(t_s, altura, altura_piso_m, metodo, historial)
    except (ValueError, ZeroDivisionError, raices.ErrorDeConvergencia):
        return np.nan, 0
    return instante, len(historial)


def cruces_de_pisos(t_s, altura, paradas, alturas_pisos_m, itinerario):
    """Instante en que el ascensor pasa frente a cada piso intermedio de cada recorrido.

    alturas_pisos_m: altura de cada piso (m). itinerario: índice del piso de cada parada.
    Devuelve una tabla con una fila por cruce: recorrido, piso, instante por bisección y por
    secante, y cuántas iteraciones usó cada método.
    """
    t_s = np.asarray(t_s, dtype=float)
    alturas = np.asarray(alturas_pisos_m, dtype=float) - alturas_pisos_m[itinerario[0]]
    filas = []
    for k in range(len(paradas) - 1):
        origen, destino = itinerario[k], itinerario[k + 1]
        # Tramo del recorrido: desde la mitad de una parada hasta la mitad de la siguiente.
        t_a = (paradas[k][0] + paradas[k][1]) / 2
        t_b = (paradas[k + 1][0] + paradas[k + 1][1]) / 2
        tramo = (t_s >= t_a) & (t_s <= t_b)
        for piso in range(min(origen, destino) + 1, max(origen, destino)):
            t_bis, n_bis = _cruce_o_nan(t_s[tramo], altura[tramo], alturas[piso], "biseccion")
            t_sec, n_sec = _cruce_o_nan(t_s[tramo], altura[tramo], alturas[piso], "secante")
            filas.append({"recorrido": k + 1, "piso": piso, "t_biseccion_s": t_bis,
                          "iteraciones_biseccion": n_bis, "t_secante_s": t_sec,
                          "iteraciones_secante": n_sec})
    return pd.DataFrame(filas)
