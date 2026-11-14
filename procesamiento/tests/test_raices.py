"""Pruebas básicas de la bisección (la validación completa llega con la etapa de métodos)."""

import math

import pytest

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
