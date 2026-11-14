"""Pruebas de los métodos de raíces: contra soluciones analíticas y contra scipy."""

import math

import pytest
from scipy import optimize

from navinercial.metodos import raices
from navinercial.metodos.raices import biseccion


def test_biseccion_encuentra_raiz_de_dos():
    raiz = biseccion(lambda x: x**2 - 2, 0.0, 2.0, tolerancia=1e-12)

    assert raiz == pytest.approx(math.sqrt(2), abs=1e-12)


def test_biseccion_funciona_con_funcion_decreciente():
    raiz = biseccion(lambda x: math.cos(x), 0.0, 3.0, tolerancia=1e-10)

    assert raiz == pytest.approx(math.pi / 2, abs=1e-10)


def test_biseccion_devuelve_el_extremo_si_ya_es_raiz():
    assert biseccion(lambda x: x - 1, 1.0, 5.0) == 1.0


def test_biseccion_sin_cambio_de_signo_da_error():
    with pytest.raises(ValueError, match="signos opuestos"):
        biseccion(lambda x: x**2 + 1, -1.0, 1.0)


# ---------------------------------------------------------------------------
# Newton y secante; comparación con scipy
# ---------------------------------------------------------------------------

def _f(x):
    return x**3 - 2 * x - 5          # raíz real cerca de 2,0946 (ejemplo clásico de Newton)


def _derivada_f(x):
    return 3 * x**2 - 2


RAIZ_DE_REFERENCIA = optimize.brentq(_f, 2.0, 3.0, xtol=1e-14)


def test_los_tres_metodos_coinciden_con_scipy():
    assert raices.biseccion(_f, 2.0, 3.0, tolerancia=1e-12) == pytest.approx(
        RAIZ_DE_REFERENCIA, abs=1e-11)
    assert raices.newton(_f, _derivada_f, 2.0) == pytest.approx(RAIZ_DE_REFERENCIA, abs=1e-12)
    assert raices.secante(_f, 2.0, 3.0) == pytest.approx(RAIZ_DE_REFERENCIA, abs=1e-12)


def test_newton_calcula_la_raiz_cuadrada_de_dos():
    raiz = raices.newton(lambda x: x**2 - 2, lambda x: 2 * x, 1.0, tolerancia=1e-14)

    assert raiz == pytest.approx(math.sqrt(2), abs=1e-14)


def test_newton_y_secante_usan_muchas_menos_iteraciones_que_la_biseccion():
    pasos_biseccion, pasos_newton, pasos_secante = [], [], []

    raices.biseccion(_f, 2.0, 3.0, tolerancia=1e-10, historial=pasos_biseccion)
    raices.newton(_f, _derivada_f, 2.0, tolerancia=1e-10, historial=pasos_newton)
    raices.secante(_f, 2.0, 3.0, tolerancia=1e-10, historial=pasos_secante)

    # Bisección: (b − a)/2^n < 1e-10 con b − a = 1 necesita n = 33 mitades.
    assert 33 <= len(pasos_biseccion) <= 35
    assert len(pasos_newton) <= 6
    assert len(pasos_secante) <= 9


def test_error_de_biseccion_se_divide_por_dos_en_cada_iteracion():
    historial = []
    raices.biseccion(_f, 2.0, 3.0, tolerancia=1e-9, historial=historial)

    # El error de la iteración n está acotado por (b − a) / 2^(n+1).
    for n, x in enumerate(historial):
        assert abs(x - RAIZ_DE_REFERENCIA) <= 1.0 / 2 ** (n + 1) + 1e-15


def test_newton_converge_cuadraticamente():
    historial = []
    raices.newton(lambda x: x**2 - 2, lambda x: 2 * x, 1.5, tolerancia=1e-15, historial=historial)
    errores = [abs(x - math.sqrt(2)) for x in historial]

    # Convergencia cuadrática: error_nuevo ≈ C · error², con C = 1/(2·√2) ≈ 0,354.
    assert errores[1] == pytest.approx(0.354 * errores[0]**2, rel=0.05)


def test_newton_con_derivada_cero_da_error():
    with pytest.raises(ZeroDivisionError):
        raices.newton(lambda x: x**2 + 1, lambda x: 2 * x, 0.0)


def test_newton_que_no_converge_da_error():
    # x² + 1 no tiene raíces reales: Newton salta sin parar.
    with pytest.raises(raices.ErrorDeConvergencia):
        raices.newton(lambda x: x**2 + 1, lambda x: 2 * x, 0.7, max_iteraciones=30)
