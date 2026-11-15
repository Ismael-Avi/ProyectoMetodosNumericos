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


def _movimiento_por_recorridos(t_s, posiciones_m, recorridos, velocidad_max_ms, duracion_rampa_s):
    """Posición, velocidad y aceleración (en una dimensión) de un vehículo que va de parada
    en parada. posiciones_m: posición de cada parada. recorridos: horario (ver
    _recorridos_del_ascensor)."""
    t_s = np.asarray(t_s, dtype=float)
    posicion = np.full(len(t_s), float(posiciones_m[recorridos[0]["piso_origen"]]))
    velocidad = np.zeros(len(t_s))
    aceleracion = np.zeros(len(t_s))
    for recorrido in recorridos:
        p_origen = posiciones_m[recorrido["piso_origen"]]
        p_destino = posiciones_m[recorrido["piso_destino"]]
        sentido = np.sign(p_destino - p_origen)                 # +1 sube o avanza, −1 al revés
        desde_salida = t_s >= recorrido["t_salida_s"]
        avance, v, a = perfil_de_movimiento(
            t_s[desde_salida] - recorrido["t_salida_s"], abs(p_destino - p_origen),
            velocidad_max_ms, duracion_rampa_s)
        posicion[desde_salida] = p_origen + sentido * avance
        velocidad[desde_salida] = sentido * v
        aceleracion[desde_salida] = sentido * a
    return posicion, velocidad, aceleracion


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
        return _movimiento_por_recorridos(
            t_s, alturas_m, recorridos, config.SIM_ASCENSOR_VELOCIDAD_MAX_MS,
            config.SIM_ASCENSOR_DURACION_RAMPA_S)

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


# ---------------------------------------------------------------------------
# Escenario 4: metro (ruta SINTÉTICA en 2D)
# ---------------------------------------------------------------------------

class Ruta:
    """Trazado en planta hecho de rectas y arcos de círculo, con un perfil de alturas.

    La posición a lo largo de la ruta se mide con s, la distancia recorrida en m desde la
    primera estación (como los kilómetros de una carretera).
    """

    def __init__(self, tramos, desniveles_m, rumbo_inicial_rad):
        # Tabla de piezas: s donde empieza, punto y rumbo de inicio, curvatura (1/radio).
        self.piezas = []
        self.s_estaciones = [0.0]
        self.h_estaciones = [0.0]
        s, x, y, rumbo = 0.0, 0.0, 0.0, rumbo_inicial_rad
        for piezas_del_tramo, desnivel in zip(tramos, desniveles_m):
            for pieza in piezas_del_tramo:
                if pieza[0] == "recta":
                    largo, curvatura = pieza[1], 0.0
                else:
                    radio, angulo = pieza[1], np.radians(pieza[2])
                    largo, curvatura = radio * abs(angulo), np.sign(angulo) / radio
                self.piezas.append((s, x, y, rumbo, curvatura))
                x, y, rumbo = self._avanzar(x, y, rumbo, curvatura, largo)
                s += largo
            self.s_estaciones.append(s)
            self.h_estaciones.append(self.h_estaciones[-1] + desnivel)
        self.largo_total = s

    @staticmethod
    def _avanzar(x, y, rumbo, curvatura, distancia):
        """Punto y rumbo después de avanzar una distancia por una recta o un arco."""
        if curvatura == 0.0:
            return x + distancia * np.cos(rumbo), y + distancia * np.sin(rumbo), rumbo + 0 * distancia
        rumbo_nuevo = rumbo + curvatura * distancia
        return (x + (np.sin(rumbo_nuevo) - np.sin(rumbo)) / curvatura,
                y - (np.cos(rumbo_nuevo) - np.cos(rumbo)) / curvatura, rumbo_nuevo)

    def planta(self, s):
        """x, y (m), rumbo (rad) y curvatura (1/m) en la posición s (arreglo)."""
        s = np.clip(np.asarray(s, dtype=float), 0.0, self.largo_total)
        x, y, rumbo, curvatura = (np.zeros_like(s) for _ in range(4))
        inicios = np.array([pieza[0] for pieza in self.piezas])
        indice = np.clip(np.searchsorted(inicios, s, side="right") - 1, 0, len(self.piezas) - 1)
        for k, (s0, x0, y0, rumbo0, curvatura0) in enumerate(self.piezas):
            aqui = indice == k
            x[aqui], y[aqui], rumbo[aqui] = self._avanzar(x0, y0, rumbo0, curvatura0, s[aqui] - s0)
            curvatura[aqui] = curvatura0
        return x, y, rumbo, curvatura

    def perfil(self, s):
        """Altura h (m), pendiente dh/ds y su derivada d²h/ds² en la posición s.

        En cada tramo la altura cambia con la rampa suave: las estaciones son horizontales
        y la pendiente máxima está en la mitad del tramo.
        """
        s = np.clip(np.asarray(s, dtype=float), 0.0, self.largo_total)
        h, pendiente, curvatura_vertical = (np.zeros_like(s) for _ in range(3))
        for k in range(len(self.s_estaciones) - 1):
            s0, s1 = self.s_estaciones[k], self.s_estaciones[k + 1]
            desnivel = self.h_estaciones[k + 1] - self.h_estaciones[k]
            largo = s1 - s0
            aqui = (s >= s0) & (s <= s1)
            u = (s[aqui] - s0) / largo
            valor, derivada, _ = _rampa(u)
            h[aqui] = self.h_estaciones[k] + desnivel * valor
            pendiente[aqui] = desnivel / largo * derivada
            curvatura_vertical[aqui] = desnivel / largo**2 * 2 * np.pi * np.sin(2 * np.pi * u)
        return h, pendiente, curvatura_vertical


def _a_ejes_del_vagon(vector_mundo, rumbo, inclinacion):
    """Componentes (adelante, izquierda, arriba) de vectores dados en ejes del mundo.

    El vagón apunta según el rumbo (giro alrededor de la vertical) y sube o baja según la
    inclinación de la vía. vector_mundo: arreglo de n x 3.
    """
    c_r, s_r, c_i, s_i = np.cos(rumbo), np.sin(rumbo), np.cos(inclinacion), np.sin(inclinacion)
    adelante = np.column_stack([c_r * c_i, s_r * c_i, s_i])
    izquierda = np.column_stack([-s_r, c_r, np.zeros_like(rumbo)])
    arriba = np.column_stack([-c_r * s_i, -s_r * s_i, c_i])
    return np.column_stack([np.sum(vector_mundo * eje, axis=1)
                            for eje in (adelante, izquierda, arriba)])


def crear_metro(sentido=1, nombre="metro"):
    """Viaje en metro por una ruta SINTÉTICA con rectas, curvas, pendientes y paradas.

    sentido: +1 recorre las estaciones en el orden de config.py; −1 en el orden contrario.
    El dispositivo va fijo al vagón, con el eje x casi hacia adelante (girado
    SIM_METRO_MONTAJE_GRADOS) y un poco inclinado.

    Columnas extra de verdad: x_m, y_m (posición en el mapa), altura_m, rumbo_rad,
    velocidad_ms (a lo largo de la vía), aceleracion_ms2 (a lo largo de la vía),
    distancia_m (recorrida desde la primera estación del viaje).
    """
    ruta = Ruta(config.SIM_METRO_TRAMOS, config.SIM_METRO_DESNIVELES_M,
                np.radians(config.SIM_METRO_RUMBO_INICIAL_GRADOS))
    s_estaciones = np.array(ruta.s_estaciones)
    nombres = list(config.SIM_METRO_ESTACIONES)
    if sentido == -1:
        nombres = nombres[::-1]
    # d = distancia recorrida en ESTE viaje. De ida, s = d; de vuelta, s = largo total − d.
    d_estaciones = s_estaciones if sentido == 1 else (ruta.largo_total - s_estaciones)[::-1]

    recorridos, eventos = _recorridos_del_ascensor(
        d_estaciones, list(range(len(d_estaciones))), config.SIM_METRO_VELOCIDAD_MAX_MS,
        config.SIM_METRO_DURACION_RAMPA_S, config.SIM_METRO_ESPERA_BOTON_S,
        config.SIM_METRO_PARADA_S - 2 * config.SIM_METRO_ESPERA_BOTON_S,
        config.SIM_METRO_REPOSO_INICIAL_S)
    duracion_total = eventos[-1] + config.SIM_METRO_REPOSO_FINAL_S
    R_montaje = (matriz_rotacion("z", np.radians(config.SIM_METRO_MONTAJE_GRADOS))
                 @ orientacion_inclinada(config.SIM_METRO_ALABEO_GRADOS,
                                         config.SIM_METRO_CABECEO_GRADOS))
    _, campo_mundo = _vectores_del_mundo()

    def geometria(d):
        """Planta y perfil en la distancia recorrida d, teniendo en cuenta el sentido."""
        s = d if sentido == 1 else ruta.largo_total - d
        x, y, rumbo, curvatura = ruta.planta(s)
        h, pendiente, curvatura_vertical = ruta.perfil(s)
        if sentido == -1:
            # Al revés: se mira hacia el otro lado; las curvas y las pendientes cambian de signo.
            rumbo, curvatura, pendiente = rumbo + np.pi, -curvatura, -pendiente
        return x, y, rumbo, curvatura, h - ruta.perfil(geometria_inicio)[0], pendiente, curvatura_vertical

    geometria_inicio = np.array([0.0 if sentido == 1 else ruta.largo_total])

    def estado(t_s):
        d, v, a = _movimiento_por_recorridos(
            t_s, d_estaciones, recorridos, config.SIM_METRO_VELOCIDAD_MAX_MS,
            config.SIM_METRO_DURACION_RAMPA_S)
        x, y, rumbo, curvatura, h, pendiente, curvatura_vertical = geometria(d)
        n = len(d)
        inclinacion = np.arctan(pendiente)
        # Aceleración en ejes del mundo: a lo largo de la vía, centrípeta (v²/radio, hacia
        # el centro de la curva) y vertical (segunda derivada de la altura).
        tangente = np.column_stack([np.cos(rumbo), np.sin(rumbo), np.zeros(n)])
        normal = np.column_stack([-np.sin(rumbo), np.cos(rumbo), np.zeros(n)])
        aceleracion_mundo = a[:, None] * tangente + (v**2 * curvatura)[:, None] * normal
        aceleracion_mundo[:, 2] = curvatura_vertical * v**2 + pendiente * a
        fuerza_mundo = aceleracion_mundo.copy()
        fuerza_mundo[:, 2] += config.G_QUITO

        # Velocidad angular en ejes del vagón: giro del rumbo (vertical) y de la inclinación.
        giro_rumbo = v * curvatura
        giro_inclinacion = curvatura_vertical * v / (1 + pendiente**2)
        w_vagon = np.column_stack([giro_rumbo * np.sin(inclinacion), -giro_inclinacion,
                                   giro_rumbo * np.cos(inclinacion)])

        campo_vagon = _a_ejes_del_vagon(np.tile(campo_mundo, (n, 1)), rumbo, inclinacion)
        campo = (campo_vagon @ R_montaje + np.array(config.SIM_METRO_MAG_HIERRO_UT)
                 + a[:, None] * np.array(config.SIM_METRO_MAG_MOTOR_UT_POR_MS2))
        tabla = _armar_estado(
            fuerza=_a_ejes_del_vagon(fuerza_mundo, rumbo, inclinacion) @ R_montaje,
            velocidad_angular=w_vagon @ R_montaje,
            campo=campo,
            tramo=np.where(v == 0, "parada", "movimiento"),
        )
        for columna, valores in [("x_m", x), ("y_m", y), ("altura_m", h), ("rumbo_rad", rumbo),
                                 ("velocidad_ms", v), ("aceleracion_ms2", a), ("distancia_m", d)]:
            tabla[columna] = valores
        return tabla

    x_est, y_est, rumbo_est, _, h_est, _, _ = geometria(np.asarray(d_estaciones, dtype=float))
    x_trazado, y_trazado, _, _ = ruta.planta(np.arange(0.0, ruta.largo_total + 1.0, 10.0))
    info = {
        "SINTETICO": True, "sentido": int(sentido),
        "estaciones": [{"nombre": nombre_estacion, "x_m": float(x_est[k]), "y_m": float(y_est[k]),
                        "altura_m": float(h_est[k])} for k, nombre_estacion in enumerate(nombres)],
        "longitudes_tramos_m": [float(v) for v in np.diff(d_estaciones)],
        "rumbo_inicial_rad": float(rumbo_est[0]),
        "trazado": {"x_m": [float(v) for v in x_trazado], "y_m": [float(v) for v in y_trazado]},
        "recorridos": recorridos,
    }
    return Escenario(nombre=nombre, duracion_s=duracion_total, estado=estado,
                     tiempos_eventos_s=eventos, altura=lambda t_s: estado(t_s)["altura_m"].to_numpy(),
                     info=info)
