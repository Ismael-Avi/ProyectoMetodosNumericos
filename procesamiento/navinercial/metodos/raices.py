"""Búsqueda de raíces: resolver f(x) = 0 con métodos implementados a mano.

Por ahora solo está la bisección, que el simulador necesita para invertir la fórmula del
BMP280. En la etapa de métodos numéricos se agrega Newton o secante y la validación completa.
"""


def biseccion(f, a, b, tolerancia=1e-10, max_iteraciones=200):
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
