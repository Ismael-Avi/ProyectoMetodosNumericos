"""Búsqueda de raíces: resolver f(x) = 0 con métodos implementados a mano.

Tres métodos:

    bisección: necesita un intervalo [a, b] con cambio de signo. Siempre converge, pero
               despacio: cada iteración gana un bit (el error se divide por 2).
    Newton:    necesita la derivada y un punto de partida cercano. Muy rápido: cerca de la
               raíz, la cantidad de cifras correctas se duplica en cada iteración.
    secante:   como Newton, pero estima la derivada con los dos últimos puntos. Casi tan
               rápido y no necesita la derivada.

En el proyecto se usan para invertir la fórmula del BMP280 (simulador) y para encontrar el
instante en que el ascensor cruza la altura de cada piso.

Las tres funciones aceptan una lista opcional "historial": si se pasa, se le agrega la
aproximación de cada iteración. Sirve para contar iteraciones y comparar la convergencia.
"""


class ErrorDeConvergencia(RuntimeError):
    """El método no llegó a la tolerancia pedida en el máximo de iteraciones."""


def biseccion(f, a, b, tolerancia=1e-10, max_iteraciones=200, historial=None):
    """Encuentra una raíz de f en el intervalo [a, b] por el método de bisección.

    Idea matemática: si f es continua y f(a) y f(b) tienen signos opuestos, entonces hay al
    menos una raíz entre a y b (teorema de Bolzano). Se evalúa f en el punto medio m y se
    conserva la mitad del intervalo donde sigue habiendo cambio de signo. Cada iteración
    reduce el intervalo a la mitad, así que después de n iteraciones el error es como máximo
    (b - a) / 2^n.

    f: función de una variable.
    a, b: extremos del intervalo; f(a) y f(b) deben tener signos opuestos.
    tolerancia: se termina cuando la mitad del intervalo es menor que este valor, es decir,
        cuando el punto medio está a menos de "tolerancia" de la raíz (unidades de x).

    Devuelve la raíz aproximada (el punto medio del último intervalo).
    """
    fa = f(a)
    fb = f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        raise ValueError(
            f"f(a) y f(b) deben tener signos opuestos: f({a}) = {fa}, f({b}) = {fb}"
        )

    for _ in range(max_iteraciones):
        medio = (a + b) / 2
        if historial is not None:
            historial.append(medio)
        if (b - a) / 2 < tolerancia:
            return medio

        f_medio = f(medio)
        if f_medio == 0:
            return medio

        if fa * f_medio < 0:
            # El cambio de signo está en la mitad izquierda [a, medio].
            b = medio
        else:
            # El cambio de signo está en la mitad derecha [medio, b].
            a = medio
            fa = f_medio

    return (a + b) / 2


def newton(f, derivada, x0, tolerancia=1e-10, max_iteraciones=50, historial=None):
    """Encuentra una raíz de f por el método de Newton-Raphson, partiendo de x0.

    Idea matemática: cerca de x, la función se parece a su recta tangente. Se busca dónde
    esa recta cruza el cero y se usa ese punto como nueva aproximación:

        x_nuevo = x − f(x) / f'(x)

    f: función. derivada: función que devuelve f'(x). x0: aproximación inicial.
    tolerancia: se termina cuando el paso |x_nuevo − x| es menor que este valor.

    Devuelve la raíz aproximada. Lanza ErrorDeConvergencia si no converge (puede pasar si
    x0 está lejos de la raíz) y ZeroDivisionError si la derivada se anula.
    """
    x = x0
    for _ in range(max_iteraciones):
        pendiente = derivada(x)
        if pendiente == 0:
            raise ZeroDivisionError(f"La derivada vale cero en x = {x}: Newton no puede seguir")
        x_nuevo = x - f(x) / pendiente
        if historial is not None:
            historial.append(x_nuevo)
        if abs(x_nuevo - x) < tolerancia:
            return x_nuevo
        x = x_nuevo
    raise ErrorDeConvergencia(f"Newton no convergió en {max_iteraciones} iteraciones")


def secante(f, x0, x1, tolerancia=1e-10, max_iteraciones=100, historial=None):
    """Encuentra una raíz de f por el método de la secante, partiendo de x0 y x1.

    Idea matemática: es el método de Newton, pero en lugar de la derivada se usa la
    pendiente de la recta (secante) que pasa por los dos últimos puntos:

        pendiente ≈ (f(x1) − f(x0)) / (x1 − x0)
        x_nuevo = x1 − f(x1) / pendiente

    No hace falta conocer la derivada, y no hace falta que x0 y x1 encierren la raíz.
    tolerancia: se termina cuando el paso |x_nuevo − x1| es menor que este valor.
    """
    f0 = f(x0)
    f1 = f(x1)
    for _ in range(max_iteraciones):
        if f1 == 0:
            return x1
        if f1 == f0:
            raise ZeroDivisionError("La secante es horizontal (f(x0) = f(x1)): no puede seguir")
        x_nuevo = x1 - f1 * (x1 - x0) / (f1 - f0)
        if historial is not None:
            historial.append(x_nuevo)
        if abs(x_nuevo - x1) < tolerancia:
            return x_nuevo
        x0, f0 = x1, f1
        x1, f1 = x_nuevo, f(x_nuevo)
    raise ErrorDeConvergencia(f"La secante no convergió en {max_iteraciones} iteraciones")
