"""Escenarios del simulador: el movimiento VERDADERO del dispositivo (sin errores de sensor).

Un escenario dice, para cada instante t, qué mediría un sensor perfecto:
- fx, fy, fz: fuerza específica en los ejes del dispositivo, en m/s². Es lo que mide un
  acelerómetro ideal: la aceleración menos la gravedad. En reposo NO es cero: vale +g en
  el eje que apunta hacia arriba (la mesa empuja al dispositivo hacia arriba).
- wx, wy, wz: velocidad angular en los ejes del dispositivo, en rad/s.
- bx, by, bz: campo magnético en los ejes del dispositivo, en µT.
- tramo: texto que describe qué está pasando (p. ej. "reposo", "+z", "giro").

Ejes del mundo: x = este, y = norte, z = arriba.
Orientación: matriz de rotación R que lleva un vector de ejes del dispositivo a ejes del
mundo (v_mundo = R · v_dispositivo). Para pasar del mundo al dispositivo se usa la
traspuesta (v_dispositivo = Rᵀ · v_mundo). Con R = identidad los ejes coinciden.

Escenarios: reposo largo, seis caras, ascensor y metro. Los escenarios con movimiento
agregan columnas extra de "verdad" a la tabla (altura, velocidad, posición...), que solo se
usan para medir el error del procesamiento.
"""

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

import config

COLUMNAS_FUERZA = ["fx", "fy", "fz"]
COLUMNAS_VELOCIDAD_ANGULAR = ["wx", "wy", "wz"]
COLUMNAS_CAMPO = ["bx", "by", "bz"]

VERSORES = {"x": np.array([1.0, 0.0, 0.0]),
            "y": np.array([0.0, 1.0, 0.0]),
            "z": np.array([0.0, 0.0, 1.0])}

# Seis caras: nombre de cada cara (el eje del dispositivo que apunta hacia arriba) y el giro
# que lleva a la cara siguiente (eje del dispositivo alrededor del cual se gira, ángulo en grados).
CARAS = ["+z", "-z", "+x", "-x", "+y", "-y"]
GIROS = [("x", 180.0), ("y", 90.0), ("z", 180.0), ("z", 90.0), ("z", 180.0)]


@dataclass
class Escenario:
    """Movimiento verdadero que se va a simular."""

    nombre: str
    duracion_s: float
    # estado(t_s) recibe un arreglo de tiempos en segundos y devuelve una tabla con las
    # columnas fx..fz, wx..wz, bx..bz y tramo (una fila por cada tiempo).
    estado: Callable
    # Instantes en que se pulsa el botón, en segundos desde el inicio.
    tiempos_eventos_s: list = field(default_factory=list)
    # altura(t_s): altura del dispositivo sobre el punto de partida, en m (None = no cambia).
    # La usa el simulador del barómetro.
    altura: Callable = None
    # Datos de referencia del escenario (alturas de pisos, itinerario...), para verdad_escenario.json.
    info: dict = field(default_factory=dict)


def matriz_rotacion(eje, angulo_rad):
    """Matriz de rotación de 3x3 alrededor de un eje coordenado ("x", "y" o "z").

    Sentido positivo según la regla de la mano derecha.
    """
    c, s = np.cos(angulo_rad), np.sin(angulo_rad)
    if eje == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if eje == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    if eje == "z":
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    raise ValueError(f"Eje desconocido: {eje}")


def orientacion_inclinada(alabeo_grados, cabeceo_grados):
    """Orientación de un dispositivo apoyado en una mesa que no está perfectamente nivelada.

    alabeo: giro alrededor del eje x; cabeceo: giro alrededor del eje y (en grados).
    Con los dos en cero devuelve la identidad (eje z hacia arriba).
    """
    return (matriz_rotacion("x", np.radians(alabeo_grados))
            @ matriz_rotacion("y", np.radians(cabeceo_grados)))


def _vectores_del_mundo():
    """Gravedad "sentida" (hacia arriba) y campo magnético, en ejes del mundo."""
    fuerza_mundo = np.array([0.0, 0.0, config.G_QUITO])        # m/s²
    campo_mundo = np.array(config.SIM_MAG_CAMPO_MUNDO_UT)      # µT
    return fuerza_mundo, campo_mundo


def _armar_estado(fuerza, velocidad_angular, campo, tramo):
    """Junta los arreglos en la tabla que devuelve estado(t)."""
    estado = pd.DataFrame(fuerza, columns=COLUMNAS_FUERZA)
    estado[COLUMNAS_VELOCIDAD_ANGULAR] = velocidad_angular
    estado[COLUMNAS_CAMPO] = campo
    estado["tramo"] = tramo
    return estado


# ---------------------------------------------------------------------------
# Escenario 1: reposo largo
# ---------------------------------------------------------------------------

def crear_reposo(duracion_s=config.SIM_REPOSO_DURACION_S, alabeo_grados=0.0, cabeceo_grados=0.0):
    """Dispositivo quieto sobre una mesa, con el eje z hacia arriba.

    alabeo y cabeceo permiten simular una mesa ligeramente inclinada: la gravedad se reparte
    entre los ejes, pero su magnitud sigue siendo g.
    """
    R = orientacion_inclinada(alabeo_grados, cabeceo_grados)
    fuerza_mundo, campo_mundo = _vectores_del_mundo()
    fuerza_dispositivo = R.T @ fuerza_mundo
    campo_dispositivo = R.T @ campo_mundo

    def estado(t_s):
        n = len(t_s)
        return _armar_estado(
            fuerza=np.tile(fuerza_dispositivo, (n, 1)),
            velocidad_angular=np.zeros((n, 3)),
            campo=np.tile(campo_dispositivo, (n, 1)),
            tramo="reposo",
        )

    return Escenario(nombre="reposo", duracion_s=duracion_s, estado=estado)


# ---------------------------------------------------------------------------
# Escenario 2: seis caras
# ---------------------------------------------------------------------------

def perfil_de_giro(fraccion, angulo_total_rad, duracion_s):
    """Ángulo girado y velocidad angular durante un giro suave.

    El giro empieza y termina con velocidad angular cero:
        ángulo(s)    = ángulo_total · (s − sen(2πs) / (2π))
        velocidad(s) = (ángulo_total / duración) · (1 − cos(2πs))
    donde s es la fracción del giro ya recorrida (0 al inicio, 1 al final). La velocidad es
    la derivada del ángulo respecto al tiempo.

    Devuelve (ángulo en rad, velocidad angular en rad/s).
    """
    angulo = angulo_total_rad * (fraccion - np.sin(2 * np.pi * fraccion) / (2 * np.pi))
    velocidad = angulo_total_rad / duracion_s * (1 - np.cos(2 * np.pi * fraccion))
    return angulo, velocidad


def crear_seis_caras(duracion_cara_s=config.SIM_CARA_DURACION_S,
                     duracion_giro_s=config.SIM_GIRO_DURACION_S,
                     alabeo_grados=0.0, cabeceo_grados=0.0):
    """Dispositivo en reposo sobre cada una de sus seis caras, con un giro entre cara y cara.

    Orden de las caras: +z, -z, +x, -x, +y, -y (el eje que apunta hacia arriba). En la cara
    "+x" el acelerómetro ideal mide fx = +g; en la cara "-x" mide fx = -g.
    """
    R_inicial = orientacion_inclinada(alabeo_grados, cabeceo_grados)
    fuerza_mundo, campo_mundo = _vectores_del_mundo()
    duracion_total = len(CARAS) * duracion_cara_s + len(GIROS) * duracion_giro_s

    def estado(t_s):
        # El jitter puede dejar una muestra apenas fuera de [0, duración]: se recorta.
        t_s = np.clip(t_s, 0.0, duracion_total)
        n = len(t_s)
        fuerza = np.zeros((n, 3))
        velocidad_angular = np.zeros((n, 3))
        campo = np.zeros((n, 3))
        tramo = np.empty(n, dtype=object)

        R = R_inicial
        t_inicio = 0.0
        for numero, cara in enumerate(CARAS):
            # Tramo quieto sobre esta cara.
            t_fin = t_inicio + duracion_cara_s
            en_cara = (t_s >= t_inicio) & (t_s <= t_fin)
            fuerza[en_cara] = R.T @ fuerza_mundo
            campo[en_cara] = R.T @ campo_mundo
            tramo[en_cara] = cara
            t_inicio = t_fin
            if numero == len(GIROS):
                break   # después de la última cara no hay giro

            # Giro hacia la cara siguiente.
            eje, angulo_grados = GIROS[numero]
            angulo_total = np.radians(angulo_grados)
            t_fin = t_inicio + duracion_giro_s
            for k in np.flatnonzero((t_s > t_inicio) & (t_s < t_fin)):
                fraccion = (t_s[k] - t_inicio) / duracion_giro_s
                angulo, velocidad = perfil_de_giro(fraccion, angulo_total, duracion_giro_s)
                R_k = R @ matriz_rotacion(eje, angulo)
                fuerza[k] = R_k.T @ fuerza_mundo
                campo[k] = R_k.T @ campo_mundo
                velocidad_angular[k] = VERSORES[eje] * velocidad
                tramo[k] = "giro"
            R = R @ matriz_rotacion(eje, angulo_total)
            t_inicio = t_fin

        return _armar_estado(fuerza, velocidad_angular, campo, tramo)

    return Escenario(nombre="seis_caras", duracion_s=duracion_total, estado=estado)


# ---------------------------------------------------------------------------
# Perfil de movimiento suave (lo usan el ascensor y el metro)
# ---------------------------------------------------------------------------

def _rampa(s):
    """Rampa suave de 0 a 1: valor, derivada e integral, para s entre 0 y 1.

        rampa(s)    = s − sen(2πs)/(2π)          sube de 0 a 1 sin quiebres
        derivada(s) = 1 − cos(2πs)               vale 0 al inicio y al final
        integral(s) = s²/2 + (cos(2πs) − 1)/(4π²)
    """
    valor = s - np.sin(2 * np.pi * s) / (2 * np.pi)
    derivada = 1 - np.cos(2 * np.pi * s)
    integral = s**2 / 2 + (np.cos(2 * np.pi * s) - 1) / (4 * np.pi**2)
    return valor, derivada, integral


def duracion_del_perfil(distancia_m, velocidad_max_ms, duracion_rampa_s):
    """Velocidad de crucero y duración total de un recorrido (ver perfil_de_movimiento)."""
    # En un recorrido corto no se alcanza la velocidad máxima: se baja la de crucero.
    velocidad_crucero = min(velocidad_max_ms, distancia_m / duracion_rampa_s)
    duracion_crucero = distancia_m / velocidad_crucero - duracion_rampa_s
    return velocidad_crucero, 2 * duracion_rampa_s + duracion_crucero


def perfil_de_movimiento(t_s, distancia_m, velocidad_max_ms, duracion_rampa_s):
    """Posición, velocidad y aceleración de un recorrido en línea recta de A a B.

    Tres fases: arranque (la velocidad sube con una rampa suave), crucero (velocidad
    constante) y frenado (el arranque al revés). Empieza y termina con velocidad y
    aceleración cero. Las tres magnitudes son fórmulas exactas (no se integra nada), así que
    sirven como "verdad" para medir el error de la integración numérica.

    t_s: tiempo desde el inicio del recorrido (arreglo). Devuelve (posición en m, velocidad
    en m/s, aceleración en m/s²); antes del inicio vale (0, 0, 0) y después (distancia, 0, 0).
    """
    v, duracion_total = duracion_del_perfil(distancia_m, velocidad_max_ms, duracion_rampa_s)
    T = duracion_rampa_s
    t_s = np.clip(np.asarray(t_s, dtype=float), 0.0, duracion_total)

    posicion = np.zeros_like(t_s)
    velocidad = np.zeros_like(t_s)
    aceleracion = np.zeros_like(t_s)

    arranque = t_s < T
    valor, derivada, integral = _rampa(t_s[arranque] / T)
    posicion[arranque] = v * T * integral
    velocidad[arranque] = v * valor
    aceleracion[arranque] = v / T * derivada

    crucero = (t_s >= T) & (t_s <= duracion_total - T)
    posicion[crucero] = v * T / 2 + v * (t_s[crucero] - T)
    velocidad[crucero] = v

    frenado = t_s > duracion_total - T
    # El frenado es el arranque visto al revés: "falta" es la fracción que queda por frenar.
    falta = (duracion_total - t_s[frenado]) / T
    valor, derivada, integral = _rampa(falta)
    posicion[frenado] = distancia_m - v * T * integral
    velocidad[frenado] = v * valor
    aceleracion[frenado] = -v / T * derivada
    return posicion, velocidad, aceleracion


# ---------------------------------------------------------------------------
# Escenario 3: ascensor
# ---------------------------------------------------------------------------

def _recorridos_del_ascensor(alturas_m, itinerario, velocidad_max_ms, duracion_rampa_s,
                             espera_puerta_s, puerta_abierta_s, reposo_inicial_s):
    """Calcula el horario del ascensor: cuándo sale y cuándo llega en cada recorrido.

    Devuelve (lista de recorridos, lista de instantes del botón). Cada recorrido es un
    diccionario con piso_origen, piso_destino, t_salida_s y t_llegada_s.
    Botón: una pulsación al cerrar las puertas (antes de salir) y otra al abrirlas (después
    de llegar).
    """
    recorridos, eventos = [], []
    t = reposo_inicial_s
    for origen, destino in zip(itinerario[:-1], itinerario[1:]):
        distancia = abs(alturas_m[destino] - alturas_m[origen])
        _, duracion = duracion_del_perfil(distancia, velocidad_max_ms, duracion_rampa_s)
        eventos.append(t - espera_puerta_s)                  # cierre de puertas
        recorridos.append({"piso_origen": int(origen), "piso_destino": int(destino),
                           "t_salida_s": float(t), "t_llegada_s": float(t + duracion)})
        t = t + duracion
        eventos.append(t + espera_puerta_s)                  # apertura de puertas
        t = t + espera_puerta_s + puerta_abierta_s + espera_puerta_s
    return recorridos, eventos


def crear_ascensor(alturas_m=config.SIM_ASCENSOR_ALTURAS_PISOS_M,
                   itinerario=config.SIM_ASCENSOR_ITINERARIO):
    """Ascensor SINTÉTICO: sube y baja entre pisos de alturas distintas, con paradas.

    El dispositivo va apoyado en el piso del ascensor, con el eje z casi hacia arriba (un
    poco inclinado, como pasará en la realidad). Solo hay movimiento vertical.

    Columnas extra de verdad: altura_m, velocidad_z_ms, aceleracion_z_ms2.
    """
    recorridos, eventos = _recorridos_del_ascensor(
        alturas_m, itinerario, config.SIM_ASCENSOR_VELOCIDAD_MAX_MS,
        config.SIM_ASCENSOR_DURACION_RAMPA_S, config.SIM_ASCENSOR_ESPERA_PUERTA_S,
        config.SIM_ASCENSOR_PUERTA_ABIERTA_S, config.SIM_ASCENSOR_REPOSO_INICIAL_S)
    # Después de la última apertura de puertas queda un rato quieto.
    duracion_total = eventos[-1] + config.SIM_ASCENSOR_REPOSO_FINAL_S
    R = orientacion_inclinada(config.SIM_ASCENSOR_ALABEO_GRADOS, config.SIM_ASCENSOR_CABECEO_GRADOS)
    _, campo_mundo = _vectores_del_mundo()

    def movimiento_vertical(t_s):
        """Altura, velocidad y aceleración verticales verdaderas en cada instante."""
        t_s = np.asarray(t_s, dtype=float)
        altura = np.full(len(t_s), float(alturas_m[itinerario[0]]))
        velocidad = np.zeros(len(t_s))
        aceleracion = np.zeros(len(t_s))
        for recorrido in recorridos:
            h_origen = alturas_m[recorrido["piso_origen"]]
            h_destino = alturas_m[recorrido["piso_destino"]]
            sentido = np.sign(h_destino - h_origen)             # +1 sube, −1 baja
            desde_salida = t_s >= recorrido["t_salida_s"]
            posicion, v, a = perfil_de_movimiento(
                t_s[desde_salida] - recorrido["t_salida_s"], abs(h_destino - h_origen),
                config.SIM_ASCENSOR_VELOCIDAD_MAX_MS, config.SIM_ASCENSOR_DURACION_RAMPA_S)
            altura[desde_salida] = h_origen + sentido * posicion
            velocidad[desde_salida] = sentido * v
            aceleracion[desde_salida] = sentido * a
        return altura, velocidad, aceleracion

    def estado(t_s):
        altura, velocidad, aceleracion = movimiento_vertical(t_s)
        n = len(t_s)
        # Acelerómetro ideal: gravedad "sentida" (hacia arriba) más la aceleración real.
        fuerza_mundo = np.zeros((n, 3))
        fuerza_mundo[:, 2] = config.G_QUITO + aceleracion
        tabla = _armar_estado(
            fuerza=fuerza_mundo @ R,          # cada fila: Rᵀ · f_mundo
            velocidad_angular=np.zeros((n, 3)),
            campo=np.tile(R.T @ campo_mundo, (n, 1)),
            tramo=np.where(velocidad == 0, "parada", "movimiento"),
        )
        tabla["altura_m"] = altura
        tabla["velocidad_z_ms"] = velocidad
        tabla["aceleracion_z_ms2"] = aceleracion
        return tabla

    info = {"SINTETICO": True, "alturas_pisos_m": [float(h) for h in alturas_m],
            "itinerario": [int(p) for p in itinerario], "recorridos": recorridos}
    return Escenario(nombre="ascensor", duracion_s=duracion_total, estado=estado,
                     tiempos_eventos_s=eventos, altura=lambda t_s: movimiento_vertical(t_s)[0],
                     info=info)
