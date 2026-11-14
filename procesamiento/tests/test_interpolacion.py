"""Pruebas de la interpolación: contra soluciones analíticas, numpy y scipy."""

import numpy as np
import pytest
from scipy import interpolate

from navinercial.metodos import interpolacion


def _puntos_irregulares(n=40, semilla=2):
    rng = np.random.default_rng(semilla)
    t = np.cumsum(rng.uniform(0.5, 1.5, n))
    return t, np.sin(0.3 * t) + 0.1 * t


def test_lineal_pasa_por_los_puntos_y_por_el_punto_medio():
    t = np.array([0.0, 1.0, 3.0])
    y = np.array([10.0, 20.0, 0.0])

    resultado = interpolacion.interpolar_lineal(t, y, [0.0, 0.5, 1.0, 2.0, 3.0])

    np.testing.assert_allclose(resultado, [10.0, 15.0, 20.0, 10.0, 0.0])


def test_lineal_coincide_con_numpy():
    t, y = _puntos_irregulares()
    t_nuevo = np.linspace(t[0], t[-1], 333)

    propio = interpolacion.interpolar_lineal(t, y, t_nuevo)

    np.testing.assert_allclose(propio, np.interp(t_nuevo, t, y), atol=1e-12)


@pytest.mark.parametrize("metodo", ["lineal", "spline"])
def test_fuera_de_rango_devuelve_el_valor_del_extremo(metodo):
    t, y = _puntos_irregulares()

    resultado = interpolacion.interpolar(t, y, [t[0] - 5.0, t[-1] + 5.0], metodo)

    np.testing.assert_allclose(resultado, [y[0], y[-1]])


def test_tridiagonal_coincide_con_numpy():
    rng = np.random.default_rng(3)
    n = 8
    inferior, superior = rng.uniform(-1, 1, n), rng.uniform(-1, 1, n)
    diagonal = rng.uniform(3, 4, n)          # diagonal dominante: sistema bien condicionado
    lado_derecho = rng.uniform(-1, 1, n)
    matriz = np.diag(diagonal) + np.diag(inferior[1:], -1) + np.diag(superior[:-1], 1)

    x = interpolacion.resolver_tridiagonal(inferior, diagonal, superior, lado_derecho)

    np.testing.assert_allclose(x, np.linalg.solve(matriz, lado_derecho), atol=1e-12)


def test_spline_pasa_por_los_puntos():
    t, y = _puntos_irregulares()

    np.testing.assert_allclose(interpolacion.interpolar_spline(t, y, t), y, atol=1e-12)


def test_spline_coincide_con_scipy():
    t, y = _puntos_irregulares()
    t_nuevo = np.linspace(t[0], t[-1], 500)
    referencia = interpolate.CubicSpline(t, y, bc_type="natural")

    propio = interpolacion.interpolar_spline(t, y, t_nuevo)

    np.testing.assert_allclose(propio, referencia(t_nuevo), atol=1e-10)


def test_spline_de_una_recta_es_la_recta():
    t, _ = _puntos_irregulares()
    t_nuevo = np.linspace(t[0], t[-1], 100)

    resultado = interpolacion.interpolar_spline(t, 2.0 * t - 3.0, t_nuevo)

    np.testing.assert_allclose(resultado, 2.0 * t_nuevo - 3.0, atol=1e-10)


def test_spline_es_mas_exacto_que_lineal_en_una_senal_suave():
    t = np.linspace(0.0, 10.0, 26)            # como el barómetro: pocas muestras
    t_nuevo = np.linspace(2.0, 8.0, 400)      # lejos de los extremos
    exacto = np.sin(t_nuevo)

    error_lineal = np.max(np.abs(interpolacion.interpolar_lineal(t, np.sin(t), t_nuevo) - exacto))
    error_spline = np.max(np.abs(interpolacion.interpolar_spline(t, np.sin(t), t_nuevo) - exacto))

    assert error_spline < error_lineal / 10


def test_error_lineal_baja_a_la_cuarta_parte_con_la_mitad_del_paso():
    t_nuevo = np.linspace(0.0, 10.0, 1000)

    def error(n):
        t = np.linspace(0.0, 10.0, n)
        return np.max(np.abs(interpolacion.interpolar_lineal(t, np.sin(t), t_nuevo) - np.sin(t_nuevo)))

    assert np.log2(error(51) / error(101)) == pytest.approx(2.0, abs=0.2)


def test_tiempos_no_crecientes_dan_error():
    with pytest.raises(ValueError, match="crecientes"):
        interpolacion.interpolar_lineal([0.0, 2.0, 1.0], [1.0, 2.0, 3.0], [0.5])


def test_base_de_tiempo_uniforme():
    t = interpolacion.base_de_tiempo_uniforme(1.0, 2.0, 100.0)

    assert len(t) == 101
    assert t[0] == 1.0 and t[-1] == pytest.approx(2.0)
