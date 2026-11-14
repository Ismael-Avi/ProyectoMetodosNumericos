"""Interpolación implementada a mano: lineal y spline cúbico natural.

Problema: se conoce una señal en los instantes t[0] < t[1] < ... < t[n-1] y se necesita su
valor en OTROS instantes. En el proyecto sirve para llevar todas las señales a una base de
tiempo común: el barómetro mide 25 veces por segundo y el acelerómetro 200, y además cada
uno tiene sus propias marcas de tiempo.

    lineal:        une cada par de puntos seguidos con una recta.        error ~ h²
    spline cúbico: une cada par de puntos con un polinomio de grado 3,   error ~ h⁴
                   de modo que la curva completa no tenga quiebres
                   (primera y segunda derivada continuas).

Fuera del intervalo [t[0], t[n-1]] no se extrapola: se devuelve el valor del extremo más
cercano. (Extrapolar con un polinomio da valores que crecen sin control.)

De numpy solo se usan operaciones básicas de arreglos y np.searchsorted, que busca en qué
intervalo cae cada instante (una búsqueda binaria en un arreglo ordenado).
"""

import numpy as np


def _preparar(t, y):
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(t) != len(y):
        raise ValueError(f"t e y deben tener el mismo largo ({len(t)} y {len(y)})")
    if len(t) < 2:
        raise ValueError("Se necesitan al menos 2 puntos para interpolar")
    if np.any(np.diff(t) <= 0):
        raise ValueError("Los instantes t deben ser estrictamente crecientes")
    return t, y


def _buscar_intervalo(t, t_nuevo):
    """Para cada instante nuevo, devuelve el índice i tal que t[i] <= t_nuevo <= t[i+1].

    Los instantes fuera de rango se recortan primero al extremo más cercano, así que el
    índice siempre está entre 0 y n − 2.
    """
    t_recortado = np.clip(np.asarray(t_nuevo, dtype=float), t[0], t[-1])
    indice = np.searchsorted(t, t_recortado, side="right") - 1
    indice = np.clip(indice, 0, len(t) - 2)
    return indice, t_recortado


def interpolar_lineal(t, y, t_nuevo):
    """Interpolación lineal: el valor sobre la recta que une los dos puntos vecinos.

    Si t_nuevo está entre t[i] y t[i+1]:

        fraccion = (t_nuevo − t[i]) / (t[i+1] − t[i])      (0 en t[i], 1 en t[i+1])
        valor    = y[i] + fraccion · (y[i+1] − y[i])

    t, y: puntos conocidos (t creciente). t_nuevo: instantes donde se quiere el valor.
    Devuelve un arreglo del largo de t_nuevo, con las unidades de y.
    """
    t, y = _preparar(t, y)
    i, t_recortado = _buscar_intervalo(t, t_nuevo)
    fraccion = (t_recortado - t[i]) / (t[i + 1] - t[i])
    return y[i] + fraccion * (y[i + 1] - y[i])


def resolver_tridiagonal(inferior, diagonal, superior, lado_derecho):
    """Resuelve un sistema de ecuaciones tridiagonal (algoritmo de Thomas).

    Un sistema es tridiagonal cuando en la ecuación i solo aparecen las incógnitas i−1, i
    e i+1:

        inferior[i]·x[i−1] + diagonal[i]·x[i] + superior[i]·x[i+1] = lado_derecho[i]

    Es la eliminación de Gauss aprovechando que casi todos los coeficientes son cero:
      1. Hacia adelante: se elimina "inferior" fila por fila.
      2. Hacia atrás: se despeja cada incógnita, empezando por la última.
    Cuesta un número de operaciones proporcional a n (Gauss completo cuesta n³).

    inferior[0] y superior[n−1] no se usan. Devuelve el arreglo x.
    """
    n = len(diagonal)
    superior_modificada = np.zeros(n)
    derecho_modificado = np.zeros(n)

    superior_modificada[0] = superior[0] / diagonal[0]
    derecho_modificado[0] = lado_derecho[0] / diagonal[0]
    for i in range(1, n):
        pivote = diagonal[i] - inferior[i] * superior_modificada[i - 1]
        superior_modificada[i] = superior[i] / pivote
        derecho_modificado[i] = (lado_derecho[i] - inferior[i] * derecho_modificado[i - 1]) / pivote

    x = np.zeros(n)
    x[n - 1] = derecho_modificado[n - 1]
    for i in range(n - 2, -1, -1):
        x[i] = derecho_modificado[i] - superior_modificada[i] * x[i + 1]
    return x


def segundas_derivadas_spline_natural(t, y):
    """Calcula la segunda derivada M[i] del spline cúbico natural en cada punto.

    Idea: en cada intervalo el spline es un polinomio de grado 3, así que su segunda
    derivada es una recta que va de M[i] a M[i+1]. Al exigir que la PRIMERA derivada sea
    continua en cada punto interior sale una ecuación por punto (con h[i] = t[i+1] − t[i]):

        h[i−1]·M[i−1] + 2·(h[i−1] + h[i])·M[i] + h[i]·M[i+1]
            = 6·[ (y[i+1] − y[i])/h[i] − (y[i] − y[i−1])/h[i−1] ]

    Spline "natural": en los dos extremos se impone M = 0 (la curva termina sin curvatura).
    Queda un sistema tridiagonal, que se resuelve con resolver_tridiagonal.
    """
    t, y = _preparar(t, y)
    n = len(t)
    h = np.diff(t)
    pendiente = np.diff(y) / h          # pendiente de la recta en cada intervalo

    inferior = np.zeros(n)
    diagonal = np.ones(n)               # primera y última ecuación: 1·M = 0
    superior = np.zeros(n)
    lado_derecho = np.zeros(n)

    inferior[1:-1] = h[:-1]
    diagonal[1:-1] = 2 * (h[:-1] + h[1:])
    superior[1:-1] = h[1:]
    lado_derecho[1:-1] = 6 * (pendiente[1:] - pendiente[:-1])
    return resolver_tridiagonal(inferior, diagonal, superior, lado_derecho)


def interpolar_spline(t, y, t_nuevo):
    """Interpolación con spline cúbico natural.

    Con las segundas derivadas M (ver segundas_derivadas_spline_natural), el valor en un
    instante entre t[i] y t[i+1] es, con h = t[i+1] − t[i], A = t[i+1] − t_nuevo y
    B = t_nuevo − t[i]:

        valor = M[i]·A³/(6h) + M[i+1]·B³/(6h)
              + (y[i]/h − M[i]·h/6)·A + (y[i+1]/h − M[i+1]·h/6)·B

    (Se comprueba fácil: en A = h, B = 0 da y[i]; en A = 0, B = h da y[i+1].)

    Con solo 2 puntos el spline natural es la recta que los une.
    """
    t, y = _preparar(t, y)
    M = segundas_derivadas_spline_natural(t, y)
    i, t_recortado = _buscar_intervalo(t, t_nuevo)
    h = t[i + 1] - t[i]
    A = t[i + 1] - t_recortado
    B = t_recortado - t[i]
    return (M[i] * A**3 / (6 * h) + M[i + 1] * B**3 / (6 * h)
            + (y[i] / h - M[i] * h / 6) * A + (y[i + 1] / h - M[i + 1] * h / 6) * B)


METODOS = {"lineal": interpolar_lineal, "spline": interpolar_spline}


def interpolar(t, y, t_nuevo, metodo="lineal"):
    """Interpola con el método indicado: "lineal" o "spline"."""
    if metodo not in METODOS:
        raise ValueError(f"Método desconocido: '{metodo}'. Opciones: {list(METODOS)}")
    return METODOS[metodo](t, y, t_nuevo)


def base_de_tiempo_uniforme(t_inicio_s, t_final_s, fs_hz):
    """Instantes igualmente espaciados entre t_inicio y t_final, a fs muestras por segundo."""
    cantidad = int(np.floor((t_final_s - t_inicio_s) * fs_hz)) + 1
    return t_inicio_s + np.arange(cantidad) / fs_hz
