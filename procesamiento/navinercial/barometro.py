"""Altura a partir de la presión: fórmula barométrica.

IDEA FÍSICA
La presión del aire es el peso de la columna de aire que hay encima. Al subir una altura
pequeña dh queda menos aire encima, y la presión baja (ecuación hidrostática):

    dP = −ρ · g · dh                    ρ = densidad del aire, en kg/m³

El aire se comporta como un gas ideal, así que su densidad depende de la presión y de la
temperatura:

    ρ = P · M / (R · T)                 M = masa molar del aire, R = constante de los gases,
                                        T = temperatura absoluta, en K

Sustituyendo:  dP / P = −(M · g / (R · T)) · dh.  Si la temperatura T es la misma en todo
el tramo (válido para un edificio o un túnel, donde la altura cambia decenas de metros), se
integra entre la referencia y el punto actual:

    ln(P / P_ref) = −(M · g / (R · T)) · Δh

    Δh = (R · T / (M · g)) · ln(P_ref / P)          <- altura sobre la referencia, en m

CONSTANTES (todas en config.py)
- g: gravedad LOCAL de Quito (9,77 m/s²), no la estándar.
- R = 8,314462618 J/(mol·K) y M = 0,0289644 kg/mol.
- T: la temperatura que mide el propio BMP280. OJO: el sensor está dentro de la caja y
  puede estar más caliente que el aire. Un error de 3 K en T cambia la altura un 1 %.
  TODO: comparar con un termómetro al hacer los experimentos.

En Quito (72 000 Pa, 20 °C) la presión baja unos 8,4 Pa por cada metro que se sube.

LIMITACIÓN: la presión también cambia con el clima (decenas de Pa por hora). Por eso la
altura barométrica solo sirve como altura RELATIVA durante un rato corto, y P_ref hay que
medirla al inicio de cada registro.
"""

import numpy as np

import config


def _altura_de_escala_m(temperatura_C, g=config.G_QUITO):
    """R·T/(M·g), en m: altura en la que la presión se divide por e ≈ 2,718 (unos 8,6 km)."""
    temperatura_K = np.asarray(temperatura_C, dtype=float) + config.CERO_CELSIUS_EN_KELVIN
    return config.R_GAS * temperatura_K / (config.MASA_MOLAR_AIRE * g)


def altura_barometrica(presion_Pa, presion_referencia_Pa, temperatura_C, g=config.G_QUITO):
    """Altura sobre el punto de referencia, en m: Δh = (R·T/(M·g)) · ln(P_ref / P).

    presion_Pa: presión medida (número o arreglo). presion_referencia_Pa: presión en el
    punto que se toma como altura cero. temperatura_C: temperatura del aire, en °C.
    """
    presion_Pa = np.asarray(presion_Pa, dtype=float)
    return _altura_de_escala_m(temperatura_C, g) * np.log(presion_referencia_Pa / presion_Pa)


def presion_a_altura(altura_m, presion_referencia_Pa, temperatura_C, g=config.G_QUITO):
    """Operación inversa: presión a una altura dada, P = P_ref · exp(−Δh·M·g/(R·T)).

    La usa el simulador para generar la presión que mediría el barómetro al subir.
    """
    altura_m = np.asarray(altura_m, dtype=float)
    return presion_referencia_Pa * np.exp(-altura_m / _altura_de_escala_m(temperatura_C, g))


def pascales_por_metro(presion_Pa, temperatura_C, g=config.G_QUITO):
    """Cuánto baja la presión al subir 1 m, en Pa/m: P·M·g/(R·T).

    Sirve para pasar el ruido del barómetro (Pa) a ruido de altura (m).
    """
    return presion_Pa / _altura_de_escala_m(temperatura_C, g)
