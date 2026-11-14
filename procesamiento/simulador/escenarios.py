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

Por ahora: reposo largo y seis caras. El ascensor y el metro se agregan después.
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
