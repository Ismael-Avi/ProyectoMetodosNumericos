"""Análisis de un viaje en metro: velocidad, distancia, rumbo y trayectoria en 2D.

IDEA GENERAL
Un tren no se mueve en cualquier dirección: avanza hacia donde apunta el vagón. Por eso no
hace falta integrar la aceleración en dos ejes. Basta con dos números en cada instante:

    v(t)  velocidad a lo largo de la vía   <- integral de la aceleración "hacia adelante"
    ψ(t)  rumbo del vagón                  <- integral del giroscopio (giro alrededor de la vertical)

y la posición en el mapa sale de integrar la velocidad en la dirección del rumbo:

    x(t) = x0 + ∫ v·cos(ψ) dt          y(t) = y0 + ∫ v·sen(ψ) dt

El rumbo se mide desde el este hacia el norte (ψ = 0 es el este, ψ = 90° es el norte).

PASOS
1. Ejes del vagón en el dispositivo: "arriba" se mide en el reposo inicial (gravedad) y
   "adelante" en el primer arranque (el tren solo puede acelerar hacia adelante). Así no
   importa cómo quedó orientado el dispositivo, mientras no se mueva dentro del vagón.
2. Velocidad: integral de la aceleración hacia adelante, con ZUPT en las estaciones.
3. Pendiente: en una subida, el acelerómetro "hacia adelante" mide también una parte de la
   gravedad, g·sen(θ), que parece una aceleración. El barómetro dice cuánto sube el tren:
   sen(θ) = (dh/dt) / v. Con eso se corrige (esta es la versión "con barómetro").
4. Rumbo: integral del giroscopio. El magnetómetro se compara, pero dentro del vagón puede
   no ser confiable (hierro, motores): se revisa si la magnitud del campo se mantiene.
5. Ajuste con la distancia conocida entre estaciones (si hay referencia).
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from navinercial import ascensor, correcciones
from navinercial.lectura import COLUMNAS_ACCEL, COLUMNAS_GYRO, COLUMNAS_MAG
from navinercial.metodos import integracion, interpolacion

SIN_ZUPT = "sin ZUPT (solo sesgo inicial)"
ZUPT = "ZUPT, sin barómetro"
ZUPT_BARO = "ZUPT + pendiente con barómetro"
AJUSTADO = "ZUPT + barómetro + distancia conocida"

SENO_PENDIENTE_MAXIMA = 0.1      # una vía de metro no supera el 10 % de pendiente


@dataclass
class AnalisisMetro:
    """Resultado del análisis de un viaje."""

    t_s: np.ndarray
    paradas: list
    adelante: np.ndarray            # dirección "adelante" en ejes del dispositivo (unitario)
    vertical: np.ndarray            # dirección "arriba" en ejes del dispositivo (unitario)
    montaje_grados: float           # ángulo entre el eje x del dispositivo y "adelante"
    rumbo_rad: np.ndarray           # rumbo por giroscopio, en cada muestra
    altura_baro_m: np.ndarray       # altura barométrica suavizada, en cada muestra
    magnetometro: dict              # resultado de analizar_magnetometro (o None)
    velocidad: dict = field(default_factory=dict)   # nombre -> velocidad (m/s)
    distancia: dict = field(default_factory=dict)   # nombre -> distancia recorrida (m)
    x_m: dict = field(default_factory=dict)         # nombre -> posición este (m)
    y_m: dict = field(default_factory=dict)         # nombre -> posición norte (m)


# ---------------------------------------------------------------------------
# Ejes del vagón
# ---------------------------------------------------------------------------

def ejes_del_vagon(imu, paradas, ventana_s=config.METRO_VENTANA_ARRANQUE_S):
    """Direcciones "arriba" y "adelante" del vagón, en ejes del dispositivo.

    arriba: promedio del acelerómetro en el reposo inicial (solo mide la gravedad).
    adelante: en el primer arranque la única aceleración nueva es la del tren, que va hacia
    adelante. Se promedia (acelerómetro − su valor en reposo) durante ventana_s y se le
    quita la parte vertical.
    Devuelve (arriba, adelante), dos vectores unitarios.
    """
    reposo_inicio, reposo_fin = paradas[0]
    t = imu["t_s"]
    en_reposo = (t >= reposo_inicio) & (t <= reposo_fin)
    en_arranque = (t > reposo_fin) & (t <= reposo_fin + ventana_s)
    reposo = imu.loc[en_reposo, COLUMNAS_ACCEL].mean().to_numpy()
    arriba = reposo / np.linalg.norm(reposo)

    cambio = imu.loc[en_arranque, COLUMNAS_ACCEL].mean().to_numpy() - reposo
    horizontal = cambio - (cambio @ arriba) * arriba      # se quita la componente vertical
    return arriba, horizontal / np.linalg.norm(horizontal)


def proyectar(tabla, columnas, direccion):
    """Componente de una señal de tres ejes en una dirección (producto punto fila por fila)."""
    return tabla[columnas].to_numpy() @ direccion


# ---------------------------------------------------------------------------
# Rumbo: giroscopio y magnetómetro
# ---------------------------------------------------------------------------

def rumbo_por_giroscopio(imu, arriba, paradas, rumbo_inicial_rad=0.0):
    """Rumbo del vagón, en rad: rumbo inicial + integral del giro alrededor de la vertical.

    El sesgo del giroscopio se mide en cada parada (ahí el giro real es cero) y se resta.
    """
    t = imu["t_s"].to_numpy()
    giro = proyectar(imu, COLUMNAS_GYRO, arriba)                  # rad/s
    giro, _ = correcciones.restar_sesgo_por_paradas(t, giro, paradas)
    return integracion.integral_acumulada_trapecio(t, giro, rumbo_inicial_rad)


def diferencia_de_angulos(a_rad, b_rad):
    """a − b llevado al intervalo (−π, π]: 359° − 1° da −2°, no 358°."""
    return np.angle(np.exp(1j * (np.asarray(a_rad) - np.asarray(b_rad))))


def analizar_magnetometro(imu, arriba, adelante, rumbo_gyro_rad):
    """Rumbo según el magnetómetro y comprobación de si es confiable.

    El campo de la Tierra, visto en el plano horizontal, apunta al norte. Con el rumbo ψ
    medido desde el este: campo hacia adelante = B·sen(ψ), campo hacia la izquierda =
    B·cos(ψ), así que ψ = atan2(campo adelante, campo izquierda).
    (No se corrige la declinación magnética. TODO: buscar su valor en Quito y citar la fuente.)

    Confiabilidad: el campo de la Tierra tiene magnitud constante. Si la magnitud medida
    cambia durante el viaje, hay otras fuentes (hierro del vagón, motores) y el rumbo
    magnético no sirve.

    Devuelve None si no hay magnetómetro; si hay, un diccionario con t_s, rumbo_rad,
    variacion (desviación de |B| dividida por su media), confiable y diferencia_rms_grados
    (respecto al giroscopio, quitando la diferencia inicial).
    """
    con_lectura = imu[COLUMNAS_MAG[0]].notna().to_numpy()
    if not con_lectura.any():
        return None
    mag = imu.loc[con_lectura]
    izquierda = np.cross(arriba, adelante)
    rumbo = np.arctan2(proyectar(mag, COLUMNAS_MAG, adelante), proyectar(mag, COLUMNAS_MAG, izquierda))
    magnitud = np.linalg.norm(mag[COLUMNAS_MAG].to_numpy(), axis=1)
    variacion = float(np.std(magnitud) / np.mean(magnitud))

    diferencia = diferencia_de_angulos(rumbo, rumbo_gyro_rad[con_lectura])
    diferencia = diferencia_de_angulos(diferencia, diferencia[0])
    return {"t_s": mag["t_s"].to_numpy(), "rumbo_rad": rumbo, "variacion": variacion,
            "confiable": variacion < config.MAG_VARIACION_MAXIMA_CONFIABLE,
            "diferencia_rms_grados": float(np.degrees(np.sqrt(np.mean(diferencia**2))))}


# ---------------------------------------------------------------------------
# Pendiente con el barómetro
# ---------------------------------------------------------------------------

def promedio_movil(valores, cantidad):
    """Promedio de cada muestra con sus vecinas (ventana centrada de "cantidad" muestras).

    Suaviza el ruido. Cerca de los bordes la ventana se acorta.
    """
    valores = np.asarray(valores, dtype=float)
    mitad = max(1, cantidad // 2)
    suma = np.concatenate([[0.0], np.cumsum(valores)])
    indices = np.arange(len(valores))
    inicio = np.clip(indices - mitad, 0, len(valores))
    fin = np.clip(indices + mitad + 1, 0, len(valores))
    return (suma[fin] - suma[inicio]) / (fin - inicio)


def derivada_centrada(t_s, valores):
    """Derivada numérica por diferencias centradas: (y[i+1] − y[i−1]) / (t[i+1] − t[i−1]).

    En los dos extremos se usa la diferencia con el único vecino. Error ~ h².
    """
    t_s = np.asarray(t_s, dtype=float)
    valores = np.asarray(valores, dtype=float)
    derivada = np.empty(len(valores))
    derivada[1:-1] = (valores[2:] - valores[:-2]) / (t_s[2:] - t_s[:-2])
    derivada[0] = (valores[1] - valores[0]) / (t_s[1] - t_s[0])
    derivada[-1] = (valores[-1] - valores[-2]) / (t_s[-1] - t_s[-2])
    return derivada


def altura_barometrica_suavizada(sesion, paradas, t_s):
    """Altura barométrica (m) suavizada y llevada a los instantes del IMU."""
    baro = sesion.baro
    altura = ascensor.altura_del_barometro(baro, paradas[0])
    fs_baro = (len(baro) - 1) / (baro["t_s"].iloc[-1] - baro["t_s"].iloc[0])
    suave = promedio_movil(altura, int(config.METRO_VENTANA_BARO_S * fs_baro))
    return interpolacion.interpolar_lineal(baro["t_s"].to_numpy(), suave, t_s)


def gravedad_por_pendiente(t_s, altura_m, velocidad_ms, g=config.G_QUITO):
    """Parte de la gravedad que el acelerómetro "hacia adelante" mide en una pendiente (m/s²).

    Si la vía sube con un ángulo θ, el acelerómetro mide g·sen(θ) de más. El tren sube a
    razón de dh/dt = v·sen(θ), así que sen(θ) = (dh/dt) / v, con h del barómetro.
    Con el tren casi parado la división no es confiable: ahí se supone vía horizontal.
    """
    subida = derivada_centrada(t_s, altura_m)                     # dh/dt, en m/s
    seno = np.zeros(len(t_s))
    rapido = np.abs(velocidad_ms) > config.METRO_VELOCIDAD_MINIMA_PENDIENTE_MS
    seno[rapido] = subida[rapido] / velocidad_ms[rapido]
    return g * np.clip(seno, -SENO_PENDIENTE_MAXIMA, SENO_PENDIENTE_MAXIMA)


# ---------------------------------------------------------------------------
# Posición y ajuste con la distancia conocida
# ---------------------------------------------------------------------------

def posicion_en_el_mapa(t_s, velocidad_ms, rumbo_rad, x0_m=0.0, y0_m=0.0):
    """Integra la velocidad en la dirección del rumbo: devuelve (x, y) en m."""
    x = integracion.integral_acumulada_trapecio(t_s, velocidad_ms * np.cos(rumbo_rad), x0_m)
    y = integracion.integral_acumulada_trapecio(t_s, velocidad_ms * np.sin(rumbo_rad), y0_m)
    return x, y


def tramos_entre_paradas(paradas):
    """Intervalos (inicio, fin) de cada tramo en movimiento: del fin de una parada al inicio
    de la siguiente."""
    return [(paradas[k][1], paradas[k + 1][0]) for k in range(len(paradas) - 1)]


def ajustar_a_distancias(t_s, velocidad_ms, paradas, longitudes_m):
    """Escala la velocidad de cada tramo para que su distancia sea la conocida.

    En cada tramo: factor = longitud conocida / distancia calculada, y la velocidad del
    tramo se multiplica por ese factor. Devuelve (velocidad ajustada, lista de factores).
    """
    distancia = integracion.integral_acumulada_trapecio(t_s, velocidad_ms)
    ajustada = np.array(velocidad_ms, dtype=float)
    factores = []
    for (inicio, fin), longitud in zip(tramos_entre_paradas(paradas), longitudes_m):
        en_tramo = (t_s >= inicio) & (t_s <= fin)
        calculada = distancia[en_tramo][-1] - distancia[en_tramo][0]
        factor = correcciones.factor_por_distancia_conocida(calculada, longitud)
        ajustada[en_tramo] *= factor
        factores.append(factor)
    return ajustada, factores


# ---------------------------------------------------------------------------
# Análisis completo
# ---------------------------------------------------------------------------

def analizar(sesion, rumbo_inicial_rad=0.0, x0_m=0.0, y0_m=0.0, longitudes_m=None):
    """Analiza un viaje. rumbo_inicial, x0, y0: de la referencia (mapa) si existe.

    longitudes_m: distancia conocida de cada tramo; si se da, se agrega la estimación
    ajustada a esas distancias.
    """
    imu = sesion.imu
    t = imu["t_s"].to_numpy()
    paradas = correcciones.paradas_por_eventos(sesion.eventos["t_s"], t[0], t[-1])
    arriba, adelante = ejes_del_vagon(imu, paradas)
    en_reposo = (t >= paradas[0][0]) & (t <= paradas[0][1])

    aceleracion = proyectar(imu, COLUMNAS_ACCEL, adelante)
    aceleracion = aceleracion - np.mean(aceleracion[en_reposo])     # sesgo del reposo inicial
    rumbo = rumbo_por_giroscopio(imu, arriba, paradas, rumbo_inicial_rad)
    altura_baro = altura_barometrica_suavizada(sesion, paradas, t)

    analisis = AnalisisMetro(
        t_s=t, paradas=paradas, adelante=adelante, vertical=arriba,
        montaje_grados=float(np.degrees(np.arctan2(adelante[1], adelante[0]))),
        rumbo_rad=rumbo, altura_baro_m=altura_baro,
        magnetometro=analizar_magnetometro(imu, arriba, adelante, rumbo))

    def guardar(nombre, velocidad):
        analisis.velocidad[nombre] = velocidad
        analisis.distancia[nombre] = integracion.integral_acumulada_trapecio(t, velocidad)
        analisis.x_m[nombre], analisis.y_m[nombre] = posicion_en_el_mapa(t, velocidad, rumbo, x0_m, y0_m)

    guardar(SIN_ZUPT, integracion.integral_acumulada_trapecio(t, aceleracion))
    velocidad_zupt, _ = ascensor.integrar_con_zupt(t, aceleracion, paradas)
    guardar(ZUPT, velocidad_zupt)

    # Con barómetro: se quita la gravedad que se cuela por la pendiente y se repite.
    corregida = aceleracion - gravedad_por_pendiente(t, altura_baro, velocidad_zupt)
    velocidad_baro, _ = ascensor.integrar_con_zupt(t, corregida, paradas)
    guardar(ZUPT_BARO, velocidad_baro)

    if longitudes_m is not None:
        ajustada, _ = ajustar_a_distancias(t, velocidad_baro, paradas, longitudes_m)
        guardar(AJUSTADO, ajustada)
    return analisis


# ---------------------------------------------------------------------------
# Resultados por tramo
# ---------------------------------------------------------------------------

def tabla_de_tramos(analisis, nombres_estaciones=None, longitudes_m=None):
    """Una fila por tramo: duración, distancia de cada estimación, velocidad y aceleración máximas.

    Si se dan las longitudes de referencia, agrega el error de cada estimación (m).
    """
    t = analisis.t_s
    filas = []
    for k, (inicio, fin) in enumerate(tramos_entre_paradas(analisis.paradas)):
        en_tramo = (t >= inicio) & (t <= fin)
        fila = {"tramo": k + 1}
        if nombres_estaciones is not None:
            fila["desde"], fila["hasta"] = nombres_estaciones[k], nombres_estaciones[k + 1]
        fila["duracion_s"] = fin - inicio
        velocidad = analisis.velocidad[ZUPT_BARO][en_tramo]
        fila["velocidad_max_ms"] = float(np.max(np.abs(velocidad)))
        fila["aceleracion_max_ms2"] = float(np.max(np.abs(
            derivada_centrada(t[en_tramo], promedio_movil(velocidad, config.FS_IMU_NOMINAL_HZ)))))
        for nombre, distancia in analisis.distancia.items():
            fila[f"distancia: {nombre}"] = distancia[en_tramo][-1] - distancia[en_tramo][0]
            if longitudes_m is not None:
                fila[f"error: {nombre}"] = fila[f"distancia: {nombre}"] - longitudes_m[k]
        if longitudes_m is not None:
            fila["longitud_referencia_m"] = longitudes_m[k]
        filas.append(fila)
    return pd.DataFrame(filas)


def posiciones_en_paradas(analisis, nombre):
    """Posición (x, y) promedio en cada parada, según una estimación."""
    _, x = correcciones.promedio_en_paradas(analisis.t_s, analisis.x_m[nombre], analisis.paradas)
    _, y = correcciones.promedio_en_paradas(analisis.t_s, analisis.y_m[nombre], analisis.paradas)
    return x, y


def errores_en_estaciones(analisis, estaciones):
    """Distancia (m) entre la posición calculada en cada parada y la estación de referencia.

    estaciones: lista de diccionarios con nombre, x_m, y_m (en el orden del viaje).
    Devuelve una tabla: una fila por estación y una columna por estimación.
    """
    tabla = pd.DataFrame({"estacion": [e["nombre"] for e in estaciones]})
    x_ref = np.array([e["x_m"] for e in estaciones])
    y_ref = np.array([e["y_m"] for e in estaciones])
    for nombre in analisis.x_m:
        x, y = posiciones_en_paradas(analisis, nombre)
        tabla[nombre] = np.hypot(x - x_ref, y - y_ref)
    return tabla


# ---------------------------------------------------------------------------
# Referencia geográfica
# ---------------------------------------------------------------------------

def geograficas_a_locales(lat_grados, lon_grados, lat0_grados, lon0_grados):
    """Pasa latitud y longitud a metros en un mapa local plano (x = este, y = norte).

    Aproximación válida para distancias de decenas de km: la Tierra se trata como una
    esfera de radio R y, cerca del punto de origen (lat0, lon0),

        y = R · (lat − lat0)                    (en radianes)
        x = R · (lon − lon0) · cos(lat0)        los meridianos se juntan hacia los polos

    En Quito (latitud ≈ 0) el coseno vale casi 1.
    """
    lat, lon = np.radians(lat_grados), np.radians(lon_grados)
    lat0, lon0 = np.radians(lat0_grados), np.radians(lon0_grados)
    x = config.RADIO_TIERRA_M * (lon - lon0) * np.cos(lat0)
    y = config.RADIO_TIERRA_M * (lat - lat0)
    return x, y


def combinar_viajes(tablas_de_tramos, estimacion=ZUPT_BARO):
    """Junta los tramos de varios viajes y calcula el promedio y la dispersión de cada tramo.

    tablas_de_tramos: diccionario {nombre del viaje: tabla de tabla_de_tramos (con las
    columnas desde y hasta)}. Un tramo recorrido en sentido contrario cuenta como el mismo.
    Devuelve una tabla por tramo: cantidad de viajes, distancia media, desviación estándar
    (dispersión entre viajes), duración media y velocidad máxima media.
    """
    filas = []
    for viaje, tabla in tablas_de_tramos.items():
        for _, fila in tabla.iterrows():
            extremos = sorted([fila["desde"], fila["hasta"]])
            filas.append({"tramo": f"{extremos[0]} – {extremos[1]}", "viaje": viaje,
                          "distancia_m": fila[f"distancia: {estimacion}"],
                          "duracion_s": fila["duracion_s"],
                          "velocidad_max_ms": fila["velocidad_max_ms"]})
    todos = pd.DataFrame(filas)
    grupos = todos.groupby("tramo")
    return pd.DataFrame({
        "viajes": grupos["distancia_m"].count(),
        "distancia_media_m": grupos["distancia_m"].mean(),
        "dispersion_m": grupos["distancia_m"].std(ddof=1),
        "duracion_media_s": grupos["duracion_s"].mean(),
        "velocidad_max_media_ms": grupos["velocidad_max_ms"].mean(),
    })
