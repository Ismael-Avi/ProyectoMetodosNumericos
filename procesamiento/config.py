"""Constantes y parámetros del proyecto.

Regla: ninguna constante "mágica" en el resto del código. Todo número con significado físico
vive aquí, con su fuente o con un "TODO: citar fuente".

Unidades: Sistema Internacional (m, s, kg, Pa, rad), salvo donde se indique lo contrario.
"""

import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Gravedad
# ---------------------------------------------------------------------------

# Gravedad local en Quito (altitud aproximada 2850 m), en m/s².
# Se usa para restar la gravedad y para la calibración de seis caras.
# TODO: citar fuente (valor aproximado tomado del enunciado del proyecto).
G_QUITO = 9.77

# Gravedad estándar, en m/s². Es la definición de la unidad "g" que usan las hojas de datos
# de los sensores: 1 g = 9,80665 m/s² exactos. Se usa SOLO para pasar de "g" a m/s².
# No es la gravedad de Quito.
# Fuente: valor convencional adoptado por la 3.ª CGPM (1901).
G_ESTANDAR = 9.80665

# ---------------------------------------------------------------------------
# Factores de conversión del sensor inercial (MPU-9250 / MPU-6500)
# ---------------------------------------------------------------------------
# TODO: confirmar cada valor con el PDF de la hoja de datos en la mano (ver
# docs/PENDIENTES_HARDWARE.md cuando exista).

# Sensibilidad del acelerómetro en LSB por g, según el rango configurado (±g).
# Fuente: InvenSense, "MPU-9250 Product Specification" rev. 1.1, tabla 6.2
# (Accelerometer Specifications, Sensitivity Scale Factor).
ACCEL_LSB_POR_G = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}

# Sensibilidad del giroscopio en LSB por (°/s), según el rango configurado (±°/s).
# Fuente: InvenSense, "MPU-9250 Product Specification" rev. 1.1, tabla 6.1
# (Gyroscope Specifications, Sensitivity Scale Factor).
GYRO_LSB_POR_DPS = {250: 131.0, 500: 65.5, 1000: 32.8, 2000: 16.4}

# Resolución del magnetómetro AK8963 en modo de 16 bits, en µT por LSB.
# Fuente: AKM, hoja de datos del AK8963 (rango ±4912 µT en 16 bits; aprox. 0,15 µT/LSB).
MAG_UT_POR_LSB = 0.15

# Valor del registro WHO_AM_I de cada chip (sirve para saber si hay magnetómetro).
# Fuente: mapas de registros de InvenSense del MPU-9250, del MPU-9255 y del MPU-6500.
WHOAMI_MPU9250 = "0x71"  # con magnetómetro AK8963
WHOAMI_MPU9255 = "0x73"  # con magnetómetro AK8963
WHOAMI_MPU6500 = "0x70"  # sin magnetómetro

# Chips aceptados en meta.json: valor de WHO_AM_I -> ¿tiene magnetómetro?
WHOAMI_TIENE_MAGNETOMETRO = {
    WHOAMI_MPU9250: True,
    WHOAMI_MPU9255: True,
    WHOAMI_MPU6500: False,
}

# Frecuencia del magnetómetro AK8963 en modo de medición continua 2, en Hz.
# Fuente: AKM, hoja de datos del AK8963 (Continuous measurement mode 2: 100 Hz).
FS_MAG_NOMINAL_HZ = 100

# ---------------------------------------------------------------------------
# Configuración nominal del dispositivo (propuesta, hasta que exista el firmware)
# ---------------------------------------------------------------------------

FS_IMU_NOMINAL_HZ = 200   # frecuencia de muestreo del acelerómetro y el giroscopio, en Hz
FS_BARO_NOMINAL_HZ = 25   # frecuencia de muestreo del barómetro, en Hz
ACCEL_RANGO_G = 4         # rango del acelerómetro: ±4 g
GYRO_RANGO_DPS = 500      # rango del giroscopio: ±500 °/s

# ---------------------------------------------------------------------------
# Barómetro BMP280
# ---------------------------------------------------------------------------

# Coeficientes de calibración de ejemplo. Cada BMP280 trae los suyos grabados de fábrica;
# estos son los del ejemplo de cálculo de la hoja de datos y se usan en el simulador y en
# las pruebas (adc_T = 519888, adc_P = 415148 -> T = 25,08 °C y P = 100653,27 Pa).
# Fuente: Bosch Sensortec, hoja de datos del BMP280 (BST-BMP280-DS001), sección 3.12,
# "Calculation example".
BMP280_CALIB_EJEMPLO = {
    "dig_T1": 27504, "dig_T2": 26435, "dig_T3": -1000,
    "dig_P1": 36477, "dig_P2": -10685, "dig_P3": 3024,
    "dig_P4": 2855, "dig_P5": 140, "dig_P6": -7,
    "dig_P7": 15500, "dig_P8": -14600, "dig_P9": 6000,
}

# ---------------------------------------------------------------------------
# Parámetros por defecto del SIMULADOR (valores SINTÉTICOS)
# ---------------------------------------------------------------------------
# Estos números NO son mediciones de nuestro dispositivo. Son valores razonables, del orden
# de los "típicos" de las hojas de datos, para que el simulador se parezca a un sensor real.
# Cuando exista el dispositivo se reemplazan por los valores medidos en la caracterización.
# TODO: comparar con los valores típicos de las hojas de datos y con los medidos.

# Acelerómetro (un valor por eje x, y, z).
SIM_ACCEL_SESGO_MS2 = (0.15, -0.10, 0.25)        # sesgo constante, en m/s²
SIM_ACCEL_ERROR_ESCALA = (0.010, -0.008, 0.015)  # error de escala (0.010 = mide 1 % de más)
# Desviación estándar del ruido blanco, en m/s². Relación con la hoja de datos:
#     σ ≈ densidad de ruido · √(ancho de banda)
# Densidad de ruido del acelerómetro del MPU-9250: 300 µg/√Hz (valor típico).
# Con un ancho de banda de 100 Hz: σ ≈ 300e-6 g · √100 = 0,003 g ≈ 0,029 m/s².
# TODO: confirmar la densidad de ruido en la hoja de datos (tabla 6.2).
# TODO: el ancho de banda depende del filtro pasabajos (DLPF) que configure el firmware;
#       100 Hz es una suposición (la mitad de la frecuencia de muestreo de 200 Hz).
SIM_ACCEL_RUIDO_STD_MS2 = 0.03
SIM_ACCEL_DERIVA_STD = 2e-5                      # deriva del sesgo (paseo aleatorio), en (m/s²)/√s

# Giroscopio (un valor por eje x, y, z). Se escriben en °/s y se pasan a rad/s.
SIM_GYRO_SESGO_RADS = tuple(math.radians(v) for v in (0.5, -0.3, 0.2))   # rad/s
SIM_GYRO_ERROR_ESCALA = (0.005, -0.004, 0.003)
# Desviación estándar del ruido blanco, en rad/s (se escribe en °/s). Misma relación:
#     σ ≈ densidad de ruido · √(ancho de banda)
# Densidad de ruido del giroscopio del MPU-9250: 0,01 (°/s)/√Hz (valor típico).
# Con un ancho de banda de 100 Hz: σ ≈ 0,01 · √100 = 0,1 °/s.
# TODO: confirmar la densidad de ruido en la hoja de datos (tabla 6.1) y el ancho de banda
#       del filtro pasabajos (DLPF) que configure el firmware.
SIM_GYRO_RUIDO_STD_RADS = math.radians(0.1)
SIM_GYRO_DERIVA_STD = math.radians(1e-4)         # (rad/s)/√s

# Magnetómetro.
# Campo magnético terrestre en ejes del mundo (x = este, y = norte, z = arriba), en µT.
# SINTÉTICO. TODO: reemplazar por el campo real en Quito con su fuente (p. ej. modelo IGRF).
SIM_MAG_CAMPO_MUNDO_UT = (0.0, 25.0, -10.0)
SIM_MAG_SESGO_UT = (5.0, -3.0, 8.0)              # sesgo constante ("hierro duro"), en µT
# Ruido del magnetómetro, en µT. Aquí no se usa σ ≈ densidad · √(ancho de banda) porque no
# tenemos un valor de densidad de ruido del AK8963: es un valor supuesto, de unos 3 LSB.
# TODO: buscar el ruido de salida en la hoja de datos del AK8963 o medirlo en reposo.
SIM_MAG_RUIDO_STD_UT = 0.5

# Barómetro.
# Presión y temperatura del ambiente. SINTÉTICOS (orden de magnitud para ~2850 m de altitud).
# TODO: reemplazar por valores medidos en Quito.
SIM_BARO_PRESION_BASE_PA = 72000.0
SIM_BARO_TEMPERATURA_BASE_C = 20.0
# Ruido de la lectura de presión, en Pa. La hoja de datos del BMP280 no da una densidad de
# ruido sino el ruido RMS total para cada configuración de sobremuestreo y filtro: 1,3 Pa
# corresponde a la resolución "ultra alta" (sobremuestreo x16) sin filtro IIR. Es el
# equivalente a σ ≈ densidad · √(ancho de banda), ya calculado por el fabricante.
# TODO: confirmar el valor en la hoja de datos (tabla de ruido de presión) y ajustarlo al
#       sobremuestreo y al filtro IIR que configure el firmware.
SIM_BARO_RUIDO_PRESION_STD_PA = 1.3
# Ruido de la lectura de temperatura, en °C. Valor supuesto.
# TODO: confirmar con la hoja de datos del BMP280 (ruido de temperatura) o medirlo en reposo.
SIM_BARO_RUIDO_TEMPERATURA_STD_C = 0.01
SIM_BARO_DERIVA_CLIMA_PA_POR_HORA = 30.0         # tendencia lenta de la presión por el clima
# Marea barométrica semidiurna: la presión atmosférica sube y baja dos veces al día (período
# de 12 h), y cerca del ecuador esa variación es grande. Se modela con una sinusoide.
# SINTÉTICO: la amplitud es un orden de magnitud. TODO: citar fuente y medirla en Quito.
SIM_BARO_MAREA_AMPLITUD_PA = 100.0               # amplitud de la sinusoide, en Pa (0 = sin marea)
SIM_BARO_MAREA_PERIODO_H = 12.0                  # período, en horas
SIM_BARO_MAREA_FASE_H = 0.0                      # horas transcurridas desde el último máximo
                                                 # de presión al empezar el registro
SIM_BARO_PASEO_CLIMA_STD = 0.05                  # parte aleatoria de esa deriva, en Pa/√s
SIM_BARO_DERIVA_TEMPERATURA_C_POR_HORA = 0.5     # el dispositivo se calienta poco a poco

# Tiempo.
SIM_T_INICIAL_US = 2_000_000       # el registro empieza 2 s después de encender el ESP32
SIM_JITTER_STD_US = 50.0           # desviación estándar del jitter del muestreo, en µs
SIM_PROB_MUESTRA_PERDIDA = 2e-5    # probabilidad de perder cada muestra (≈ 14 por hora a 200 Hz)
SIM_FS_IMU_REAL_HZ = 199.96        # frecuencia REAL del simulador: a propósito no es la nominal,
SIM_FS_BARO_REAL_HZ = 24.995       # para comprobar que la verificación mide la frecuencia real

# Escenarios.
SIM_REPOSO_DURACION_S = 3600.0     # reposo largo: 1 hora
SIM_CARA_DURACION_S = 60.0         # seis caras: tiempo quieto en cada cara
SIM_GIRO_DURACION_S = 5.0          # seis caras: tiempo que toma girar de una cara a la siguiente

# ---------------------------------------------------------------------------
# Reproducibilidad y carpetas
# ---------------------------------------------------------------------------

# Semilla de los números aleatorios: con la misma semilla, el simulador genera siempre
# los mismos datos.
SEMILLA_POR_DEFECTO = 12345

CARPETA_BASE = Path(__file__).resolve().parent           # carpeta procesamiento/
CARPETA_DATOS = CARPETA_BASE / "datos"                   # sesiones (simuladas o reales)
CARPETA_DATOS_SIMULADOS = CARPETA_DATOS / "simulados"    # sesiones que genera el simulador
CARPETA_RESULTADOS = CARPETA_BASE / "resultados"         # figuras y reportes
CARPETA_REFERENCIA = CARPETA_BASE / "datos_referencia"   # datos externos (estaciones, pisos)
