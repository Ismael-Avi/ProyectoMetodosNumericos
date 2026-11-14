"""Barómetro BMP280: compensación (crudo -> físico) e inversión numérica (físico -> crudo).

El BMP280 no entrega la presión ni la temperatura directamente. Entrega dos enteros de
20 bits (adc_T y adc_P) y trae grabados de fábrica 12 coeficientes de calibración (dig_T1..T3
y dig_P1..P9). Con ellos se calcula la temperatura y la presión usando las fórmulas de
compensación del fabricante.

Fuente de las fórmulas: Bosch Sensortec, hoja de datos del BMP280 (BST-BMP280-DS001),
sección 8.1, "Compensation formulas in double precision floating point".
TODO: confirmar el número de sección con el PDF de la hoja de datos.

Diferencia con la hoja de datos: allí t_fine se trunca a entero de 32 bits. Aquí se deja
como número real, porque así la función es continua y se puede invertir con bisección. La
diferencia en la presión es despreciable (menos de 0,01 Pa).

Las funciones de compensación sirven tanto con un número como con un arreglo de numpy.
"""

from navinercial import formato
from navinercial.metodos.raices import biseccion

# La bisección busca el valor crudo como número real y se detiene cuando lo conoce con esta
# precisión (en unidades del ADC). Después se redondea al entero más cercano.
TOLERANCIA_ADC = 0.01


def compensar_temperatura(adc_T, calib):
    """Convierte la lectura cruda de temperatura a grados Celsius.

    adc_T: lectura cruda de temperatura (entero de 20 bits).
    calib: diccionario con los coeficientes dig_T1, dig_T2 y dig_T3.

    Devuelve (temperatura_C, t_fine). t_fine es una temperatura "fina" en unidades internas
    del sensor (T = t_fine / 5120), que después se necesita para compensar la presión.
    """
    var1 = (adc_T / 16384.0 - calib["dig_T1"] / 1024.0) * calib["dig_T2"]
    diferencia = adc_T / 131072.0 - calib["dig_T1"] / 8192.0
    var2 = diferencia * diferencia * calib["dig_T3"]
    t_fine = var1 + var2
    temperatura_C = t_fine / 5120.0
    return temperatura_C, t_fine


def compensar_presion(adc_P, t_fine, calib):
    """Convierte la lectura cruda de presión a pascales.

    adc_P: lectura cruda de presión (entero de 20 bits).
    t_fine: temperatura fina que devuelve compensar_temperatura (la presión que mide el
        sensor depende de su temperatura, por eso hace falta).
    calib: diccionario con los coeficientes dig_P1 a dig_P9.

    Devuelve la presión en Pa.
    """
    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * calib["dig_P6"] / 32768.0
    var2 = var2 + var1 * calib["dig_P5"] * 2.0
    var2 = var2 / 4.0 + calib["dig_P4"] * 65536.0
    var1 = (calib["dig_P3"] * var1 * var1 / 524288.0 + calib["dig_P2"] * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * calib["dig_P1"]
    # Nota: var1 solo vale cero si dig_P1 es cero, es decir, con un sensor defectuoso.
    presion = 1048576.0 - adc_P
    presion = (presion - var2 / 4096.0) * 6250.0 / var1
    var1 = calib["dig_P9"] * presion * presion / 2147483648.0
    var2 = presion * calib["dig_P8"] / 32768.0
    presion = presion + (var1 + var2 + calib["dig_P7"]) / 16.0
    return presion


def compensar(adc_T, adc_P, calib):
    """Convierte el par de lecturas crudas a (temperatura en °C, presión en Pa)."""
    temperatura_C, t_fine = compensar_temperatura(adc_T, calib)
    presion_Pa = compensar_presion(adc_P, t_fine, calib)
    return temperatura_C, presion_Pa


# ---------------------------------------------------------------------------
# Inversión numérica (la usa el simulador)
# ---------------------------------------------------------------------------
# El simulador conoce la temperatura y la presión "reales" y necesita saber qué valores
# crudos habría entregado el sensor. Despejar adc_T y adc_P de las fórmulas anteriores a
# mano es engorroso, así que se resuelve numéricamente: se busca la raíz de
#     f(adc) = compensar(adc) - valor_deseado
# con bisección en el intervalo [0, 2^20 - 1], que son todos los valores posibles del ADC.

def temperatura_a_adc(temperatura_C, calib):
    """Devuelve el adc_T (entero) cuya temperatura compensada es la más cercana a la pedida."""
    def diferencia(adc_T):
        return compensar_temperatura(adc_T, calib)[0] - temperatura_C

    raiz = biseccion(diferencia, 0.0, float(formato.ADC_20BITS_MAX), TOLERANCIA_ADC)
    return round(raiz)


def presion_a_adc(presion_Pa, adc_T, calib):
    """Devuelve el adc_P (entero) cuya presión compensada es la más cercana a la pedida.

    adc_T: lectura cruda de temperatura de esa misma muestra (la compensación de la presión
        depende de la temperatura).
    """
    t_fine = compensar_temperatura(adc_T, calib)[1]

    def diferencia(adc_P):
        return compensar_presion(adc_P, t_fine, calib) - presion_Pa

    raiz = biseccion(diferencia, 0.0, float(formato.ADC_20BITS_MAX), TOLERANCIA_ADC)
    return round(raiz)
