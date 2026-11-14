"""Pruebas del BMP280: ejemplo de la hoja de datos e inversión numérica."""

import numpy as np
import pytest

import config
from navinercial import bmp280

CALIB = config.BMP280_CALIB_EJEMPLO

# Ejemplo de cálculo de la hoja de datos de Bosch (mismos coeficientes que CALIB).
ADC_T_EJEMPLO = 519888
ADC_P_EJEMPLO = 415148
TEMPERATURA_EJEMPLO_C = 25.08
PRESION_EJEMPLO_PA = 100653.27


def test_compensacion_reproduce_el_ejemplo_de_la_hoja_de_datos():
    temperatura, presion = bmp280.compensar(ADC_T_EJEMPLO, ADC_P_EJEMPLO, CALIB)

    assert temperatura == pytest.approx(TEMPERATURA_EJEMPLO_C, abs=0.005)
    assert presion == pytest.approx(PRESION_EJEMPLO_PA, abs=0.02)


def test_compensacion_funciona_con_arreglos():
    adc_T = np.array([ADC_T_EJEMPLO, ADC_T_EJEMPLO])
    adc_P = np.array([ADC_P_EJEMPLO, ADC_P_EJEMPLO])

    temperatura, presion = bmp280.compensar(adc_T, adc_P, CALIB)

    assert temperatura == pytest.approx([TEMPERATURA_EJEMPLO_C] * 2, abs=0.005)
    assert presion == pytest.approx([PRESION_EJEMPLO_PA] * 2, abs=0.02)


def test_inversion_recupera_los_crudos_del_ejemplo():
    temperatura, presion = bmp280.compensar(ADC_T_EJEMPLO, ADC_P_EJEMPLO, CALIB)

    adc_T = bmp280.temperatura_a_adc(temperatura, CALIB)
    adc_P = bmp280.presion_a_adc(presion, adc_T, CALIB)

    assert adc_T == ADC_T_EJEMPLO
    assert adc_P == ADC_P_EJEMPLO


@pytest.mark.parametrize("temperatura_C, presion_Pa", [
    (20.0, 72000.0),     # condiciones parecidas a las de Quito (valores sintéticos)
    (5.0, 71500.0),
    (35.0, 101325.0),
])
def test_ida_y_vuelta_dentro_de_un_lsb(temperatura_C, presion_Pa):
    """Físico -> crudo -> físico debe devolver casi lo mismo.

    La diferencia es solo el redondeo a entero: menos de 0,001 °C y de 0,5 Pa.
    """
    adc_T = bmp280.temperatura_a_adc(temperatura_C, CALIB)
    adc_P = bmp280.presion_a_adc(presion_Pa, adc_T, CALIB)

    temperatura, presion = bmp280.compensar(adc_T, adc_P, CALIB)

    assert temperatura == pytest.approx(temperatura_C, abs=0.001)
    assert presion == pytest.approx(presion_Pa, abs=0.5)
