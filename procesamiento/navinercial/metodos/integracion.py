"""Integración numérica ACUMULATIVA, implementada a mano.

Problema: se conoce una señal y(t) solo en instantes t[0], t[1], ..., t[n-1] (por ejemplo la
aceleración) y se quiere su integral desde el inicio hasta cada instante:

    I[i] = valor_inicial + ∫ y(t) dt   entre t[0] y t[i]

Con y = aceleración (m/s²) el resultado es la velocidad (m/s); con y = velocidad (m/s) el
resultado es la posición (m). Las unidades del resultado son (unidades de y) · segundos.

Los tres métodos hacen lo mismo: calculan cuánto aporta cada intervalo [t[i], t[i+1]] y van
sumando los aportes. Lo que cambia es cómo se aproxima y(t) dentro del intervalo:

    rectángulo (Euler): y constante, igual al valor del inicio      error global ~ h
    trapecio:           una recta entre los dos extremos             error global ~ h²
    Simpson:            una parábola por tres puntos seguidos        error global ~ h⁴ (*)

h es el paso de tiempo. "error ~ h²" significa que con la mitad del paso el error baja a la
cuarta parte. (*) h⁴ con paso uniforme; con paso irregular Simpson baja a h³.

Los instantes NO tienen que estar igualmente espaciados: se usa el intervalo real entre
muestras, así que el jitter y las muestras perdidas no dañan la integral.

De numpy solo se usan operaciones básicas de arreglos (restas, productos y la suma acumulada).
"""

import numpy as np


def _preparar(t, y):
    """Convierte a arreglos de números reales y revisa que tengan el mismo largo."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(t) != len(y):
        raise ValueError(f"t e y deben tener el mismo largo ({len(t)} y {len(y)})")
    if len(t) < 2:
        raise ValueError("Se necesitan al menos 2 muestras para integrar")
    return t, y


def _acumular(aportes, valor_inicial):
    """Suma acumulada de los aportes de cada intervalo, empezando en valor_inicial.

    resultado[0] = valor_inicial
    resultado[i] = valor_inicial + aportes[0] + ... + aportes[i-1]
    """
    resultado = np.empty(len(aportes) + 1)
    resultado[0] = valor_inicial
    resultado[1:] = valor_inicial + np.cumsum(aportes)
    return resultado


def integral_acumulada_rectangulo(t, y, valor_inicial=0.0):
    """Integral acumulada por la regla del rectángulo (método de Euler hacia adelante).

    Idea: en cada intervalo se supone que y vale lo mismo que al inicio del intervalo:

        aporte[i] = y[i] · (t[i+1] − t[i])

    Es el método más simple y el menos exacto: su error es proporcional al paso h.

    t: instantes, en s. y: valores de la señal. Devuelve un arreglo del mismo largo que t.
    """
    t, y = _preparar(t, y)
    pasos = np.diff(t)                 # t[i+1] − t[i]
    aportes = y[:-1] * pasos
    return _acumular(aportes, valor_inicial)


def integral_acumulada_trapecio(t, y, valor_inicial=0.0):
    """Integral acumulada por la regla del trapecio.

    Idea: en cada intervalo se une y[i] con y[i+1] con una recta. El área bajo la recta es
    la de un trapecio: el promedio de las dos alturas por el ancho.

        aporte[i] = (y[i] + y[i+1]) / 2 · (t[i+1] − t[i])

    Su error es proporcional a h². Es exacto si y(t) es una recta.
    """
    t, y = _preparar(t, y)
    pasos = np.diff(t)
    aportes = (y[:-1] + y[1:]) / 2 * pasos
    return _acumular(aportes, valor_inicial)


def _aportes_de_parabola(t0, t1, t2, y0, y1, y2):
    """Áreas bajo la parábola que pasa por (t0, y0), (t1, y1), (t2, y2).

    La parábola se escribe en la forma de Newton (diferencias divididas):

        p(t) = y0 + d1·(t − t0) + d2·(t − t0)·(t − t1)

        d1 = (y1 − y0) / (t1 − t0)                     pendiente del primer tramo
        d2 = [(y2 − y1)/(t2 − t1) − d1] / (t2 − t0)    cuánto cambia la pendiente (curvatura)

    Integrando p(t) a mano, con h0 = t1 − t0 y H = t2 − t0:

        área en [t0, t1] = y0·h0 + d1·h0²/2 − d2·h0³/6
        área en [t0, t2] = y0·H  + d1·H²/2  + d2·(H³/3 − h0·H²/2)

    Devuelve (área del primer intervalo, área del segundo intervalo). Con paso uniforme h,
    la suma de las dos es la fórmula conocida de Simpson: h/3 · (y0 + 4·y1 + y2).
    """
    h0 = t1 - t0
    h1 = t2 - t1
    H = h0 + h1
    d1 = (y1 - y0) / h0
    d2 = ((y2 - y1) / h1 - d1) / H
    area_primero = y0 * h0 + d1 * h0**2 / 2 - d2 * h0**3 / 6
    area_total = y0 * H + d1 * H**2 / 2 + d2 * (H**3 / 3 - h0 * H**2 / 2)
    return area_primero, area_total - area_primero


def integral_acumulada_simpson(t, y, valor_inicial=0.0):
    """Integral acumulada por la regla de Simpson (parábola por tres puntos).

    Idea: se toman las muestras de tres en tres (0-1-2, 2-3-4, 4-5-6, ...). Por cada trío
    pasa una única parábola, y su área en cada uno de los dos intervalos del trío es el
    aporte de ese intervalo (ver _aportes_de_parabola).

    Si la cantidad de intervalos es impar, el último intervalo queda sin pareja: para él se
    usa la parábola de los tres últimos puntos.

    Su error es proporcional a h⁴ con paso uniforme. Es exacto si y(t) es una parábola (y,
    con paso uniforme, también si es un polinomio de grado 3).

    Con solo 2 muestras no se puede trazar una parábola: se usa el trapecio.
    """
    t, y = _preparar(t, y)
    n = len(t)
    if n == 2:
        return integral_acumulada_trapecio(t, y, valor_inicial)

    aportes = np.empty(n - 1)
    # Índices donde empieza cada trío: 0, 2, 4, ... (el trío usa i, i+1, i+2).
    inicio = np.arange(0, n - 2, 2)
    primero, segundo = _aportes_de_parabola(
        t[inicio], t[inicio + 1], t[inicio + 2], y[inicio], y[inicio + 1], y[inicio + 2])
    aportes[inicio] = primero
    aportes[inicio + 1] = segundo

    cantidad_de_intervalos = n - 1
    if cantidad_de_intervalos % 2 == 1:
        # Último intervalo sin pareja: parábola por los tres últimos puntos.
        _, ultimo = _aportes_de_parabola(t[-3], t[-2], t[-1], y[-3], y[-2], y[-1])
        aportes[-1] = ultimo
    return _acumular(aportes, valor_inicial)


METODOS = {
    "rectangulo": integral_acumulada_rectangulo,
    "trapecio": integral_acumulada_trapecio,
    "simpson": integral_acumulada_simpson,
}


def integral_acumulada(t, y, metodo="trapecio", valor_inicial=0.0):
    """Integral acumulada con el método indicado: "rectangulo", "trapecio" o "simpson"."""
    if metodo not in METODOS:
        raise ValueError(f"Método desconocido: '{metodo}'. Opciones: {list(METODOS)}")
    return METODOS[metodo](t, y, valor_inicial)
