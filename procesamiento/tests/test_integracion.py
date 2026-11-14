"""Pruebas de la integración numérica: contra soluciones analíticas y contra scipy."""

import numpy as np
import pytest
from scipy import integrate

from navinercial.metodos import integracion

METODOS = ["rectangulo", "trapecio", "simpson"]


def _tiempos_irregulares(n, t_final, semilla=1):
    """Instantes crecientes con espaciado irregular (como un muestreo con jitter)."""
    rng = np.random.default_rng(semilla)
    pasos = rng.uniform(0.5, 1.5, n - 1)
    t = np.concatenate([[0.0], np.cumsum(pasos)])
    return t * t_final / t[-1]


def _error_maximo(metodo, n):
    """Error máximo al integrar cos(t) en [0, 2] con n muestras uniformes (exacta: sen(t))."""
    t = np.linspace(0.0, 2.0, n)
    calculada = integracion.integral_acumulada(t, np.cos(t), metodo)
    return np.max(np.abs(calculada - np.sin(t)))


@pytest.mark.parametrize("metodo", METODOS)
def test_constante_es_exacta_y_respeta_el_valor_inicial(metodo):
    t = _tiempos_irregulares(50, 10.0)

    resultado = integracion.integral_acumulada(t, np.full(50, 3.0), metodo, valor_inicial=7.0)

    np.testing.assert_allclose(resultado, 7.0 + 3.0 * t, atol=1e-12)


@pytest.mark.parametrize("metodo", ["trapecio", "simpson"])
def test_recta_es_exacta_con_paso_irregular(metodo):
    t = _tiempos_irregulares(51, 10.0)

    resultado = integracion.integral_acumulada(t, 2.0 * t + 1.0, metodo)

    np.testing.assert_allclose(resultado, t**2 + t, atol=1e-10)


@pytest.mark.parametrize("n", [20, 21])   # cantidad impar y par de intervalos
def test_simpson_es_exacto_para_parabolas_con_paso_irregular(n):
    t = _tiempos_irregulares(n, 5.0)

    resultado = integracion.integral_acumulada_simpson(t, 3.0 * t**2 - t + 2.0)

    np.testing.assert_allclose(resultado, t**3 - t**2 / 2 + 2.0 * t, atol=1e-10)


def test_simpson_es_exacto_para_cubicas_en_los_puntos_pares_con_paso_uniforme():
    t = np.linspace(0.0, 4.0, 41)

    resultado = integracion.integral_acumulada_simpson(t, t**3)

    np.testing.assert_allclose(resultado[::2], t[::2]**4 / 4, atol=1e-10)


def test_simpson_con_tres_puntos_es_la_formula_clasica():
    # h/3 · (y0 + 4·y1 + y2) con h = 0,5
    t = np.array([0.0, 0.5, 1.0])
    y = np.array([1.0, 3.0, 2.0])

    resultado = integracion.integral_acumulada_simpson(t, y)

    assert resultado[-1] == pytest.approx(0.5 / 3 * (1.0 + 4 * 3.0 + 2.0))


@pytest.mark.parametrize("metodo, orden", [("rectangulo", 1), ("trapecio", 2), ("simpson", 4)])
def test_orden_de_convergencia(metodo, orden):
    # Con la mitad del paso el error debe dividirse por 2^orden.
    error_grueso = _error_maximo(metodo, 101)
    error_fino = _error_maximo(metodo, 201)

    orden_medido = np.log2(error_grueso / error_fino)

    assert orden_medido == pytest.approx(orden, abs=0.3)


def test_trapecio_coincide_con_scipy():
    t = _tiempos_irregulares(500, 20.0)
    y = np.sin(t) * np.exp(-0.1 * t)

    propio = integracion.integral_acumulada_trapecio(t, y)

    np.testing.assert_allclose(propio, integrate.cumulative_trapezoid(y, t, initial=0), atol=1e-12)


def test_simpson_coincide_con_scipy_en_la_integral_total():
    # Con cantidad par de intervalos, las dos implementaciones usan las mismas parábolas.
    t = np.linspace(0.0, 20.0, 501)
    y = np.sin(t) * np.exp(-0.1 * t)

    propio = integracion.integral_acumulada_simpson(t, y)

    assert propio[-1] == pytest.approx(integrate.simpson(y, x=t), abs=1e-12)


def test_caida_libre_velocidad_y_posicion():
    # a = -9,77 m/s² constante: v = a·t, x = a·t²/2. El trapecio es exacto para v (a es
    # constante) y para x (v es una recta).
    t = np.linspace(0.0, 3.0, 601)
    a = np.full_like(t, -9.77)

    v = integracion.integral_acumulada_trapecio(t, a)
    x = integracion.integral_acumulada_trapecio(t, v)

    assert v[-1] == pytest.approx(-9.77 * 3.0)
    assert x[-1] == pytest.approx(-9.77 * 3.0**2 / 2)


def test_largos_distintos_y_metodo_desconocido_dan_error():
    with pytest.raises(ValueError, match="mismo largo"):
        integracion.integral_acumulada_trapecio([0, 1, 2], [1, 2])
    with pytest.raises(ValueError, match="desconocido"):
        integracion.integral_acumulada([0, 1], [1, 2], metodo="romberg")
