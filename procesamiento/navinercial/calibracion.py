"""Caracterización del sensor en reposo, detector de quietud y calibración de seis caras.

Modelo de cada eje del acelerómetro (el mismo del simulador):

    medido = escala · real + sesgo          =>      real = (medido − sesgo) / escala

Calibración de seis caras: con el eje hacia arriba el valor real es +g y con el eje hacia
abajo es −g. Si a₊ y a₋ son los promedios medidos en esas dos posiciones:

    a₊ = escala · g + sesgo
    a₋ = −escala · g + sesgo
    =>  sesgo = (a₊ + a₋) / 2        escala = (a₊ − a₋) / (2g)

Se usa la gravedad de Quito (config.G_QUITO), no 9,81.
"""

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import config
from navinercial.lectura import COLUMNAS_ACCEL, COLUMNAS_GYRO

ARCHIVO_CALIBRACION = config.CARPETA_RESULTADOS / "calibracion" / "calibracion.json"


# ---------------------------------------------------------------------------
# Caracterización en reposo
# ---------------------------------------------------------------------------

def ruido_por_diferencias(valores):
    """Desviación estándar del ruido blanco, estimada con las diferencias entre muestras.

    Si x_k = (valor lento) + ruido_k, al restar dos muestras seguidas el valor lento se
    cancela y queda la diferencia de dos ruidos independientes, cuya desviación estándar es
    √2 · σ. Entonces σ ≈ desviación(x_{k+1} − x_k) / √2.

    Ventaja frente a la desviación estándar directa: no se infla con las derivas lentas
    (por ejemplo, la presión que cambia con el clima durante una hora).
    """
    valores = np.asarray(valores, dtype=float)
    return float(np.std(np.diff(valores)) / np.sqrt(2))


def caracterizar_reposo(sesion):
    """Media, desviación estándar y ruido de cada señal de una sesión en reposo.

    Devuelve una tabla con una fila por señal y las columnas:
    - media:     en el giroscopio es el sesgo. En el acelerómetro es sesgo + gravedad (para
                 separarlos hacen falta las seis caras).
    - std_total: desviación estándar de todo el registro (ruido + derivas lentas).
    - ruido:     desviación estándar del ruido blanco (ver ruido_por_diferencias).
    """
    senales = {columna: sesion.imu[columna] for columna in COLUMNAS_ACCEL + COLUMNAS_GYRO}
    senales["|a|"] = magnitud(sesion.imu, COLUMNAS_ACCEL)
    senales["presion_Pa"] = sesion.baro["presion_Pa"]
    senales["temperatura_C"] = sesion.baro["temperatura_C"]
    unidades = {**{c: "m/s²" for c in COLUMNAS_ACCEL}, **{c: "rad/s" for c in COLUMNAS_GYRO},
                "|a|": "m/s²", "presion_Pa": "Pa", "temperatura_C": "°C"}

    filas = []
    for nombre, valores in senales.items():
        valores = np.asarray(valores, dtype=float)
        filas.append({"señal": nombre, "unidad": unidades[nombre], "media": valores.mean(),
                      "std_total": valores.std(), "ruido": ruido_por_diferencias(valores)})
    return pd.DataFrame(filas).set_index("señal")


def magnitud(tabla, columnas):
    """Magnitud del vector formado por tres columnas: √(x² + y² + z²)."""
    return np.linalg.norm(tabla[columnas].to_numpy(dtype=float), axis=1)


def desviacion_allan(valores, fs_hz, n_puntos=30):
    """Desviación de Allan: cómo cambia la estabilidad de la señal al promediar más tiempo.

    Para un tiempo de promediado τ se divide la señal en grupos seguidos de duración τ, se
    promedia cada grupo y se calcula
        σ²(τ) = ½ · promedio[(ȳ_{k+1} − ȳ_k)²]
    Con ruido blanco, σ(τ) baja como 1/√τ. Cuando la curva deja de bajar, promediar más ya
    no ayuda: ahí domina la deriva del sesgo.

    Devuelve (taus en s, desviación de Allan en las unidades de la señal).
    """
    valores = np.asarray(valores, dtype=float)
    n = len(valores)
    # Tamaños de grupo repartidos en escala logarítmica, con al menos 9 grupos por tamaño.
    tamanos = np.unique(np.logspace(0, np.log10(n // 9), n_puntos).astype(int))
    taus, desviaciones = [], []
    for m in tamanos:
        n_grupos = n // m
        promedios = valores[:n_grupos * m].reshape(n_grupos, m).mean(axis=1)
        varianza = 0.5 * np.mean(np.diff(promedios) ** 2)
        taus.append(m / fs_hz)
        desviaciones.append(np.sqrt(varianza))
    return np.array(taus), np.array(desviaciones)


# ---------------------------------------------------------------------------
# Detector de quietud
# ---------------------------------------------------------------------------

def detectar_quietud(imu,
                     ventana_s=config.QUIETUD_VENTANA_S,
                     umbral_accel_std=config.QUIETUD_UMBRAL_ACCEL_STD_MS2,
                     umbral_gyro_std=config.QUIETUD_UMBRAL_GYRO_STD_RADS,
                     umbral_gyro_media=config.QUIETUD_UMBRAL_GYRO_MEDIA_RADS):
    """Indica, para cada muestra, si el dispositivo está quieto.

    El registro se divide en bloques de "ventana_s" segundos. Un bloque está quieto si:
    1. la desviación estándar de cada eje del acelerómetro es menor que umbral_accel_std,
    2. la desviación estándar de cada eje del giroscopio es menor que umbral_gyro_std, y
    3. la velocidad angular media de cada eje es menor (en valor absoluto) que umbral_gyro_media.

    LÍMITE FÍSICO: un acelerómetro no distingue el reposo de un movimiento con velocidad
    constante (en los dos casos solo mide la gravedad). Un ascensor o un tren que avanza
    sin acelerar y sin vibrar parecería "quieto". Por eso, en esos análisis, la quietud se
    combina con las marcas del botón.

    Devuelve un arreglo de True/False del mismo largo que la tabla imu.
    """
    t_s = imu["t_s"].to_numpy()
    accel = imu[COLUMNAS_ACCEL].to_numpy()
    gyro = imu[COLUMNAS_GYRO].to_numpy()
    periodo = np.median(np.diff(t_s))
    muestras_por_bloque = max(2, int(round(ventana_s / periodo)))

    quieto = np.zeros(len(imu), dtype=bool)
    for inicio in range(0, len(imu), muestras_por_bloque):
        bloque = slice(inicio, inicio + muestras_por_bloque)
        if len(accel[bloque]) < 2:
            continue
        quieto[bloque] = (
            np.all(accel[bloque].std(axis=0) < umbral_accel_std)
            and np.all(gyro[bloque].std(axis=0) < umbral_gyro_std)
            and np.all(np.abs(gyro[bloque].mean(axis=0)) < umbral_gyro_media)
        )
    return quieto


def tramos_de_quietud(quieto, t_s, duracion_minima_s=0.0):
    """Convierte el arreglo de True/False en una lista de tramos quietos seguidos.

    Devuelve una lista de pares (inicio, fin) con índices de muestra; "fin" no se incluye,
    igual que en los cortes de Python (tabla[inicio:fin]). Solo se devuelven los tramos que
    duran al menos duracion_minima_s.
    """
    quieto = np.asarray(quieto, dtype=bool)
    t_s = np.asarray(t_s)
    # Un cambio de False a True marca un inicio; de True a False, un fin.
    con_bordes = np.concatenate([[False], quieto, [False]]).astype(int)
    cambios = np.diff(con_bordes)
    inicios = np.flatnonzero(cambios == 1)
    fines = np.flatnonzero(cambios == -1)
    return [(int(i), int(f)) for i, f in zip(inicios, fines)
            if t_s[f - 1] - t_s[i] >= duracion_minima_s]


# ---------------------------------------------------------------------------
# Calibración de seis caras
# ---------------------------------------------------------------------------

@dataclass
class Calibracion:
    """Resultado de la calibración. Los arreglos tienen un valor por eje (x, y, z)."""

    sesgo_accel: list      # m/s²
    escala_accel: list     # sin unidades (1.0 = sin error de escala)
    sesgo_gyro: list       # rad/s
    g: float               # gravedad usada para calcular la escala, en m/s²
    origen: str = ""       # de qué sesión salió


def nombre_de_cara(media_accel, g=config.G_QUITO):
    """Nombre de la cara según qué eje mide la gravedad: "+x", "-x", "+y", "-y", "+z" o "-z".

    Devuelve None si ningún eje mide al menos CARAS_FRACCION_MINIMA_DE_G de la gravedad
    (el dispositivo estaba inclinado, no apoyado sobre una cara).
    """
    eje = int(np.argmax(np.abs(media_accel)))
    if abs(media_accel[eje]) < config.CARAS_FRACCION_MINIMA_DE_G * g:
        return None
    signo = "+" if media_accel[eje] > 0 else "-"
    return signo + "xyz"[eje]


def detectar_caras(imu, g=config.G_QUITO):
    """Encuentra automáticamente los tramos quietos y dice a qué cara corresponde cada uno.

    Devuelve una tabla con una fila por tramo: cara, t_inicio_s, t_fin_s, n_muestras y la
    media de cada eje del acelerómetro y del giroscopio en el tramo. Al inicio y al final de
    cada tramo se descarta CARAS_MARGEN_S, por si el dispositivo todavía se estaba asentando.
    """
    t_s = imu["t_s"].to_numpy()
    quieto = detectar_quietud(imu)
    filas = []
    for inicio, fin in tramos_de_quietud(quieto, t_s, config.CARAS_DURACION_MINIMA_S):
        dentro = ((t_s >= t_s[inicio] + config.CARAS_MARGEN_S)
                  & (t_s <= t_s[fin - 1] - config.CARAS_MARGEN_S))
        tramo = imu[dentro]
        medias = tramo[COLUMNAS_ACCEL + COLUMNAS_GYRO].mean()
        cara = nombre_de_cara(medias[COLUMNAS_ACCEL].to_numpy(), g)
        if cara is None:
            continue
        filas.append({"cara": cara, "t_inicio_s": tramo["t_s"].iloc[0],
                      "t_fin_s": tramo["t_s"].iloc[-1], "n_muestras": len(tramo),
                      **medias.to_dict()})
    return pd.DataFrame(filas)


def calibrar_seis_caras(imu, g=config.G_QUITO, origen=""):
    """Calcula el sesgo y la escala de cada eje del acelerómetro con las seis caras.

    sesgo = (a₊ + a₋) / 2,   escala = (a₊ − a₋) / (2g)
    El sesgo del giroscopio es su promedio en todos los tramos quietos (en reposo la
    velocidad angular real es cero).

    Devuelve (calibracion, tabla de caras detectadas).
    """
    caras = detectar_caras(imu, g)
    encontradas = set(caras["cara"]) if len(caras) > 0 else set()
    faltantes = [c for c in ["+x", "-x", "+y", "-y", "+z", "-z"] if c not in encontradas]
    if faltantes:
        raise ValueError(f"No se encontraron todas las caras. Faltan: {faltantes}")

    # Si una cara aparece más de una vez, se promedian sus tramos.
    media_por_cara = caras.groupby("cara")[COLUMNAS_ACCEL].mean()
    sesgo, escala = [], []
    for letra, columna in zip("xyz", COLUMNAS_ACCEL):
        a_mas = media_por_cara.loc["+" + letra, columna]
        a_menos = media_por_cara.loc["-" + letra, columna]
        sesgo.append(float((a_mas + a_menos) / 2))
        escala.append(float((a_mas - a_menos) / (2 * g)))

    sesgo_gyro = [float(v) for v in caras[COLUMNAS_GYRO].mean()]
    return Calibracion(sesgo, escala, sesgo_gyro, g, origen), caras


def aplicar_calibracion(sesion, calibracion):
    """Devuelve una copia de la sesión con el acelerómetro y el giroscopio corregidos.

    acelerómetro: real = (medido − sesgo) / escala
    giroscopio:   real = medido − sesgo
    """
    imu = sesion.imu.copy()
    imu[COLUMNAS_ACCEL] = ((imu[COLUMNAS_ACCEL] - np.array(calibracion.sesgo_accel))
                           / np.array(calibracion.escala_accel))
    imu[COLUMNAS_GYRO] = imu[COLUMNAS_GYRO] - np.array(calibracion.sesgo_gyro)
    return dataclasses.replace(sesion, imu=imu)


def guardar_calibracion(calibracion, ruta=ARCHIVO_CALIBRACION):
    """Guarda la calibración en un archivo JSON para usarla en otros análisis."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(dataclasses.asdict(calibracion), archivo, indent=2)
    return ruta


def cargar_calibracion(ruta=ARCHIVO_CALIBRACION):
    """Lee una calibración guardada con guardar_calibracion."""
    with open(ruta, encoding="utf-8") as archivo:
        return Calibracion(**json.load(archivo))
