"""Constantes y parámetros del proyecto.

Regla: ninguna constante "mágica" en el resto del código. Todo número con significado físico
vive aquí, con su fuente o con un "TODO: citar fuente".

Unidades: Sistema Internacional (m, s, kg, Pa, rad), salvo donde se indique lo contrario.
"""

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
# Fuente: mapas de registros de InvenSense del MPU-9250 y del MPU-6500.
WHOAMI_MPU9250 = "0x71"  # con magnetómetro AK8963
WHOAMI_MPU6500 = "0x70"  # sin magnetómetro

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
# Reproducibilidad y carpetas
# ---------------------------------------------------------------------------

# Semilla de los números aleatorios: con la misma semilla, el simulador genera siempre
# los mismos datos.
SEMILLA_POR_DEFECTO = 12345

CARPETA_BASE = Path(__file__).resolve().parent           # carpeta procesamiento/
CARPETA_DATOS = CARPETA_BASE / "datos"                   # sesiones (simuladas o reales)
CARPETA_RESULTADOS = CARPETA_BASE / "resultados"         # figuras y reportes
CARPETA_REFERENCIA = CARPETA_BASE / "datos_referencia"   # datos externos (estaciones, pisos)
