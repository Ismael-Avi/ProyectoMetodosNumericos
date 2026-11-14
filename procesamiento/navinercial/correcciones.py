"""Correcciones que usan lo que se SABE del problema, no solo lo que mide el sensor.

Lo que se sabe:
- En cada parada (ascensor con las puertas abiertas, tren detenido en una estación) la
  velocidad y la aceleración reales son CERO. El botón marca cuándo empieza y cuándo termina
  cada parada.
- En el metro, la distancia real entre dos estaciones es conocida.

Con eso se corrige:
1. El sesgo del acelerómetro: en una parada, lo que mide el acelerómetro (ya sin gravedad)
   ES el sesgo. Se mide en cada parada y se resta (restar_sesgo_por_paradas).
2. La velocidad: si al llegar a una parada la velocidad calculada no es cero, esa diferencia
   es error acumulado. Se reparte a lo largo del recorrido y se resta (aplicar_zupt).
   ZUPT = "zero velocity update", actualización de velocidad cero.
3. La distancia: se escala el recorrido para que mida la distancia conocida
   (factor_por_distancia_conocida).

Convención del botón: las pulsaciones van alternadas SALIDA, LLEGADA, SALIDA, LLEGADA...
(en el ascensor: cierre de puertas, apertura de puertas). El registro empieza y termina con
el vehículo parado.
"""

import numpy as np

import config
from navinercial.metodos import interpolacion


def paradas_por_eventos(tiempos_eventos_s, t_inicio_s, t_final_s, margen_s=config.ZUPT_MARGEN_S):
    """Tramos en que el vehículo está parado, según las pulsaciones del botón.

    tiempos_eventos_s: instantes de las pulsaciones (salida, llegada, salida, llegada...).
    margen_s: tiempo que se descarta en cada borde, porque la persona no pulsa en el
        instante exacto.

    Devuelve una lista de pares (inicio_s, fin_s): la parada inicial, las paradas
    intermedias (de cada llegada a la salida siguiente) y la parada final.
    """
    eventos = [float(t) for t in tiempos_eventos_s]
    if len(eventos) == 0 or len(eventos) % 2 != 0:
        raise ValueError(
            f"Se esperaba una cantidad par de pulsaciones (salida y llegada de cada "
            f"recorrido) y hay {len(eventos)}. Revisar eventos.csv con la bitácora.")
    salidas = eventos[0::2]
    llegadas = eventos[1::2]

    paradas = [(t_inicio_s, salidas[0] - margen_s)]
    for llegada, salida_siguiente in zip(llegadas[:-1], salidas[1:]):
        paradas.append((llegada + margen_s, salida_siguiente - margen_s))
    paradas.append((llegadas[-1] + margen_s, t_final_s))

    for inicio, fin in paradas:
        if fin <= inicio:
            raise ValueError(f"Parada vacía entre {inicio:.2f} s y {fin:.2f} s: revisar los eventos")
    return paradas


def mascara_de_paradas(t_s, paradas):
    """Arreglo de True/False: True en las muestras que caen dentro de alguna parada."""
    t_s = np.asarray(t_s, dtype=float)
    en_parada = np.zeros(len(t_s), dtype=bool)
    for inicio, fin in paradas:
        en_parada |= (t_s >= inicio) & (t_s <= fin)
    return en_parada


def promedio_en_paradas(t_s, valores, paradas):
    """Promedio de una señal en cada parada. Devuelve (instante medio de la parada, promedio)."""
    t_s = np.asarray(t_s, dtype=float)
    valores = np.asarray(valores, dtype=float)
    t_medio, promedio = [], []
    for inicio, fin in paradas:
        dentro = (t_s >= inicio) & (t_s <= fin)
        t_medio.append((inicio + fin) / 2)
        promedio.append(np.mean(valores[dentro]))
    return np.array(t_medio), np.array(promedio)


def restar_sesgo_por_paradas(t_s, aceleracion, paradas):
    """Resta el sesgo del acelerómetro, medido en cada parada.

    Idea: en una parada la aceleración real es cero, así que el promedio de lo medido es el
    sesgo en ese momento. Entre dos paradas el sesgo se interpola linealmente (el sesgo
    cambia despacio: deriva).

    aceleracion: aceleración del movimiento ya sin gravedad, en m/s².
    Devuelve (aceleración corregida, sesgo restado en cada instante).
    """
    t_medio, sesgo = promedio_en_paradas(t_s, aceleracion, paradas)
    if len(t_medio) == 1:
        sesgo_en_t = np.full(len(t_s), sesgo[0])
    else:
        sesgo_en_t = interpolacion.interpolar_lineal(t_medio, sesgo, t_s)
    return np.asarray(aceleracion, dtype=float) - sesgo_en_t, sesgo_en_t


def aplicar_zupt(t_s, velocidad, paradas):
    """Corrección de velocidad cero: obliga a que la velocidad sea 0 en las paradas.

    Idea: en las paradas la velocidad real es 0, así que la velocidad calculada ahí es
    puro ERROR. Entre dos paradas no se conoce el error, pero se sabe cuánto valía al salir
    y cuánto vale al llegar: se supone que creció en línea recta (es lo que produce un
    sesgo constante) y se resta.

        error(t) = interpolación lineal del error conocido en las paradas
        velocidad corregida = velocidad − error(t)

    Devuelve la velocidad corregida, en las mismas unidades.
    """
    t_s = np.asarray(t_s, dtype=float)
    velocidad = np.asarray(velocidad, dtype=float)
    en_parada = mascara_de_paradas(t_s, paradas)
    error = interpolacion.interpolar_lineal(t_s[en_parada], velocidad[en_parada], t_s)
    return velocidad - error


def factor_por_distancia_conocida(distancia_calculada_m, distancia_conocida_m):
    """Factor por el que hay que multiplicar un recorrido para que mida la distancia conocida.

    Si la integración dio 1030 m y el tramo mide 1000 m, el factor es 1000/1030 = 0,971.
    Multiplicar la velocidad y el avance del tramo por este factor corrige el error de
    escala acumulado (pero no reparte bien un error que no sea proporcional).
    """
    if distancia_calculada_m == 0:
        raise ValueError("La distancia calculada es cero: no se puede ajustar")
    return distancia_conocida_m / distancia_calculada_m
