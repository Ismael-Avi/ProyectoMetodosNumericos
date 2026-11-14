"""Definición única del formato de archivos de una sesión (PROPUESTA v0).

El firmware todavía no existe, así que este formato es una propuesta. El simulador escribe
con este módulo y el lector lee con este módulo: si el firmware real cambia algo (una
columna, un nombre de archivo), solo hay que modificar este archivo.

Una sesión es una carpeta:

    sesion_YYYYMMDD_HHMMSS/
    ├── meta.json      configuración del sensor y coeficientes del BMP280
    ├── imu.csv        seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz   (crudos, int16)
    ├── baro.csv       seq,t_us,adc_T,adc_P                  (crudos, 20 bits)
    └── eventos.csv    t_us,evento                           (1 = pulsación del botón)

Significado de las columnas:
- seq:  contador de muestra; aumenta de 1 en 1. Un salto indica muestras perdidas.
- t_us: tiempo en microsegundos desde el arranque del ESP32. Es un entero de 64 bits:
        en 90 minutos llega a 5,4e9, que no cabe en 32 bits.
- ax, ay, az, gx, gy, gz: lecturas crudas del acelerómetro y el giroscopio (int16).
- mx, my, mz: lecturas crudas del magnetómetro (int16), o vacío.
- adc_T, adc_P: lecturas crudas de temperatura y presión del BMP280 (enteros de 20 bits).

DECISIÓN sobre el magnetómetro: muestrea más lento que el acelerómetro. En las filas donde
no hay una lectura nueva, mx, my y mz quedan VACÍOS (no se repite la última lectura). Así se
distingue una lectura nueva de una repetida. Si el chip no tiene magnetómetro (MPU-6500),
las tres columnas quedan vacías en todo el archivo.

Este módulo solo trabaja con valores CRUDOS. La conversión a unidades físicas se hace en
lectura.py.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

import config

# ---------------------------------------------------------------------------
# Constantes del formato
# ---------------------------------------------------------------------------

VERSION_FORMATO = 0

ARCHIVO_META = "meta.json"
ARCHIVO_IMU = "imu.csv"
ARCHIVO_BARO = "baro.csv"
ARCHIVO_EVENTOS = "eventos.csv"

PREFIJO_SESION = "sesion_"
FORMATO_FECHA_SESION = "%Y%m%d_%H%M%S"   # YYYYMMDD_HHMMSS

COLUMNAS_MAG = ["mx", "my", "mz"]
COLUMNAS_IMU = ["seq", "t_us", "ax", "ay", "az", "gx", "gy", "gz"] + COLUMNAS_MAG
COLUMNAS_BARO = ["seq", "t_us", "adc_T", "adc_P"]
COLUMNAS_EVENTOS = ["t_us", "evento"]

# Columnas que deben caber en un entero de 16 bits con signo.
COLUMNAS_INT16 = ["ax", "ay", "az", "gx", "gy", "gz"] + COLUMNAS_MAG
INT16_MIN = -32768        # -2^15
INT16_MAX = 32767         # 2^15 - 1

# Columnas del barómetro: enteros sin signo de 20 bits.
COLUMNAS_ADC_20BITS = ["adc_T", "adc_P"]
ADC_20BITS_MAX = 2**20 - 1   # 1 048 575

EVENTO_BOTON = 1          # código de una pulsación del botón en eventos.csv

CAMPOS_META = [
    "formato_version", "firmware_version", "chip_whoami", "tiene_magnetometro",
    "fs_imu_nominal_hz", "fs_baro_nominal_hz", "accel_rango_g", "gyro_rango_dps",
    "bmp280_calib", "notas",
]
CAMPOS_BMP280_CALIB = [
    "dig_T1", "dig_T2", "dig_T3",
    "dig_P1", "dig_P2", "dig_P3", "dig_P4", "dig_P5", "dig_P6", "dig_P7", "dig_P8", "dig_P9",
]


class ErrorDeFormato(ValueError):
    """Error que se lanza cuando una sesión no cumple el formato."""


@dataclass
class SesionCruda:
    """Contenido de una sesión tal como está en los archivos (valores crudos)."""

    carpeta: Path
    meta: dict
    imu: pd.DataFrame       # columnas COLUMNAS_IMU
    baro: pd.DataFrame      # columnas COLUMNAS_BARO
    eventos: pd.DataFrame   # columnas COLUMNAS_EVENTOS


# ---------------------------------------------------------------------------
# Metadatos (meta.json)
# ---------------------------------------------------------------------------

def crear_meta(tiene_magnetometro=True, firmware_version="simulador", notas=""):
    """Devuelve el diccionario de meta.json con la configuración nominal de config.py."""
    whoami = config.WHOAMI_MPU9250 if tiene_magnetometro else config.WHOAMI_MPU6500
    return {
        "formato_version": VERSION_FORMATO,
        "firmware_version": firmware_version,
        "chip_whoami": whoami,
        "tiene_magnetometro": tiene_magnetometro,
        "fs_imu_nominal_hz": config.FS_IMU_NOMINAL_HZ,
        "fs_baro_nominal_hz": config.FS_BARO_NOMINAL_HZ,
        "accel_rango_g": config.ACCEL_RANGO_G,
        "gyro_rango_dps": config.GYRO_RANGO_DPS,
        "bmp280_calib": dict(config.BMP280_CALIB_EJEMPLO),
        "notas": notas,
    }


def validar_meta(meta):
    """Comprueba que meta.json tiene todos los campos y la versión que este programa entiende."""
    faltantes = [campo for campo in CAMPOS_META if campo not in meta]
    if faltantes:
        raise ErrorDeFormato(f"A meta.json le faltan los campos: {faltantes}")

    if meta["formato_version"] != VERSION_FORMATO:
        raise ErrorDeFormato(
            f"Versión de formato {meta['formato_version']} no soportada "
            f"(este programa lee la versión {VERSION_FORMATO})"
        )

    faltantes = [c for c in CAMPOS_BMP280_CALIB if c not in meta["bmp280_calib"]]
    if faltantes:
        raise ErrorDeFormato(f"A bmp280_calib le faltan los coeficientes: {faltantes}")


# ---------------------------------------------------------------------------
# Validación de las tablas
# ---------------------------------------------------------------------------

def _validar_columnas(tabla, columnas, nombre_archivo):
    """Comprueba que la tabla tiene exactamente las columnas del formato, en orden."""
    if list(tabla.columns) != columnas:
        raise ErrorDeFormato(
            f"{nombre_archivo}: se esperaban las columnas {columnas} "
            f"y se encontraron {list(tabla.columns)}"
        )


def _validar_rango(tabla, columnas, minimo, maximo, nombre_archivo):
    """Comprueba que los valores de las columnas están entre minimo y maximo.

    Las celdas vacías (magnetómetro sin lectura nueva) se ignoran.
    """
    for columna in columnas:
        valores = tabla[columna].dropna()
        if len(valores) > 0 and (valores.min() < minimo or valores.max() > maximo):
            raise ErrorDeFormato(
                f"{nombre_archivo}: la columna {columna} tiene valores fuera de "
                f"[{minimo}, {maximo}]"
            )


def validar_tablas(imu, baro, eventos):
    """Comprueba las columnas y los rangos de las tres tablas de una sesión."""
    _validar_columnas(imu, COLUMNAS_IMU, ARCHIVO_IMU)
    _validar_columnas(baro, COLUMNAS_BARO, ARCHIVO_BARO)
    _validar_columnas(eventos, COLUMNAS_EVENTOS, ARCHIVO_EVENTOS)
    _validar_rango(imu, COLUMNAS_INT16, INT16_MIN, INT16_MAX, ARCHIVO_IMU)
    _validar_rango(baro, COLUMNAS_ADC_20BITS, 0, ADC_20BITS_MAX, ARCHIVO_BARO)


# ---------------------------------------------------------------------------
# Tipos de dato en Python
# ---------------------------------------------------------------------------

def _ajustar_tipos(imu, baro, eventos):
    """Devuelve copias de las tablas con los tipos de dato del formato.

    Todo se guarda como entero de 64 bits. Los valores crudos caben en 16 o 20 bits, pero
    con int64 no hay riesgo de desbordamiento al operar con ellos en Python (por ejemplo,
    ax*ax no cabe en int16).

    El magnetómetro usa el tipo "Int64" de pandas (con mayúscula), que es un entero que
    además admite celdas vacías (<NA>). Un entero normal de numpy no puede estar vacío.
    """
    imu = imu.copy()
    for columna in COLUMNAS_IMU:
        tipo = "Int64" if columna in COLUMNAS_MAG else "int64"
        imu[columna] = imu[columna].astype(tipo)
    return imu, baro.astype("int64"), eventos.astype("int64")


# ---------------------------------------------------------------------------
# Escritura y lectura de una sesión
# ---------------------------------------------------------------------------

def nombre_carpeta_sesion(fecha_hora):
    """Nombre de la carpeta de una sesión: sesion_YYYYMMDD_HHMMSS.

    fecha_hora: objeto datetime con el instante de inicio del registro.
    """
    return PREFIJO_SESION + fecha_hora.strftime(FORMATO_FECHA_SESION)


def fecha_de_carpeta_sesion(nombre_carpeta):
    """Operación inversa de nombre_carpeta_sesion: devuelve el datetime de inicio."""
    if not nombre_carpeta.startswith(PREFIJO_SESION):
        raise ErrorDeFormato(f"'{nombre_carpeta}' no empieza con '{PREFIJO_SESION}'")
    texto_fecha = nombre_carpeta[len(PREFIJO_SESION):]
    try:
        return datetime.strptime(texto_fecha, FORMATO_FECHA_SESION)
    except ValueError:
        raise ErrorDeFormato(f"'{nombre_carpeta}' no tiene la forma sesion_YYYYMMDD_HHMMSS")


def escribir_sesion(carpeta, meta, imu, baro, eventos):
    """Escribe los cuatro archivos de una sesión en la carpeta indicada (la crea si no existe).

    meta: diccionario (ver crear_meta). imu, baro, eventos: tablas de pandas con las
    columnas del formato y valores crudos enteros.
    """
    validar_meta(meta)
    validar_tablas(imu, baro, eventos)
    imu, baro, eventos = _ajustar_tipos(imu, baro, eventos)

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)

    with open(carpeta / ARCHIVO_META, "w", encoding="utf-8") as archivo:
        json.dump(meta, archivo, indent=2, ensure_ascii=False)

    # index=False: no se escribe el número de fila. Las celdas vacías del magnetómetro
    # quedan como texto vacío entre dos comas.
    imu.to_csv(carpeta / ARCHIVO_IMU, index=False, lineterminator="\n")
    baro.to_csv(carpeta / ARCHIVO_BARO, index=False, lineterminator="\n")
    eventos.to_csv(carpeta / ARCHIVO_EVENTOS, index=False, lineterminator="\n")


def leer_sesion_cruda(carpeta):
    """Lee los cuatro archivos de una sesión y devuelve un objeto SesionCruda."""
    carpeta = Path(carpeta)
    for nombre in [ARCHIVO_META, ARCHIVO_IMU, ARCHIVO_BARO, ARCHIVO_EVENTOS]:
        if not (carpeta / nombre).is_file():
            raise ErrorDeFormato(f"Falta el archivo {nombre} en {carpeta}")

    with open(carpeta / ARCHIVO_META, encoding="utf-8") as archivo:
        meta = json.load(archivo)
    validar_meta(meta)

    imu = pd.read_csv(carpeta / ARCHIVO_IMU)
    baro = pd.read_csv(carpeta / ARCHIVO_BARO)
    eventos = pd.read_csv(carpeta / ARCHIVO_EVENTOS)
    validar_tablas(imu, baro, eventos)
    imu, baro, eventos = _ajustar_tipos(imu, baro, eventos)

    return SesionCruda(carpeta=carpeta, meta=meta, imu=imu, baro=baro, eventos=eventos)
