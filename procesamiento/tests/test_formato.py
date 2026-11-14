"""Pruebas del módulo de formato: lo que se escribe debe ser lo mismo que se lee."""

import json
from datetime import datetime

import pandas as pd
import pytest

from navinercial import formato


def _tablas_de_ejemplo(con_magnetometro=True):
    """Tres tablas pequeñas con valores crudos inventados (incluye los extremos de int16)."""
    imu = pd.DataFrame({
        "seq": [0, 1, 2, 3],
        "t_us": [1000, 6000, 11000, 5_400_000_000],   # el último no cabe en 32 bits
        "ax": [0, 10, -10, 32767],
        "ay": [5, 6, 7, -32768],
        "az": [8192, 8190, 8195, 8192],
        "gx": [1, -1, 0, 2],
        "gy": [0, 0, 0, 0],
        "gz": [-3, 3, -3, 3],
        # El magnetómetro solo tiene lectura nueva en las filas 0 y 2.
        "mx": [100, None, 101, None] if con_magnetometro else [None] * 4,
        "my": [-50, None, -51, None] if con_magnetometro else [None] * 4,
        "mz": [300, None, 299, None] if con_magnetometro else [None] * 4,
    })
    baro = pd.DataFrame({
        "seq": [0, 1],
        "t_us": [1000, 41000],
        "adc_T": [519888, 519890],
        "adc_P": [415148, 415150],
    })
    eventos = pd.DataFrame({"t_us": [6000], "evento": [formato.EVENTO_BOTON]})
    return imu, baro, eventos


def _como_lista(columna):
    """Pasa una columna a lista de enteros, con None en las celdas vacías (NaN o <NA>)."""
    return [None if pd.isna(valor) else int(valor) for valor in columna]


@pytest.mark.parametrize("con_magnetometro", [True, False])
def test_escribir_y_leer_devuelve_lo_mismo(tmp_path, con_magnetometro):
    meta = formato.crear_meta(tiene_magnetometro=con_magnetometro)
    imu, baro, eventos = _tablas_de_ejemplo(con_magnetometro)

    formato.escribir_sesion(tmp_path, meta, imu, baro, eventos)
    sesion = formato.leer_sesion_cruda(tmp_path)

    assert sesion.meta == meta
    for columna in formato.COLUMNAS_IMU:
        assert _como_lista(sesion.imu[columna]) == _como_lista(imu[columna]), columna
    assert sesion.baro.equals(baro)
    assert sesion.eventos.equals(eventos)


def test_magnetometro_sin_lectura_queda_vacio_en_el_csv(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)

    lineas = (tmp_path / formato.ARCHIVO_IMU).read_text().splitlines()

    assert lineas[0] == "seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz"
    assert lineas[1] == "0,1000,0,5,8192,1,0,-3,100,-50,300"
    assert lineas[2] == "1,6000,10,6,8190,-1,0,3,,,"   # sin lectura nueva: tres campos vacíos


def test_sesion_sin_eventos(tmp_path):
    imu, baro, _ = _tablas_de_ejemplo()
    sin_eventos = pd.DataFrame({"t_us": [], "evento": []})

    formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, sin_eventos)
    sesion = formato.leer_sesion_cruda(tmp_path)

    assert len(sesion.eventos) == 0
    assert list(sesion.eventos.columns) == formato.COLUMNAS_EVENTOS


def test_meta_incompleto_da_error_claro(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    meta = formato.crear_meta()
    del meta["accel_rango_g"]

    with pytest.raises(formato.ErrorDeFormato, match="accel_rango_g"):
        formato.escribir_sesion(tmp_path, meta, imu, baro, eventos)


def test_version_de_formato_desconocida_da_error(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)

    # Se modifica meta.json a mano, como si viniera de un firmware más nuevo.
    ruta_meta = tmp_path / formato.ARCHIVO_META
    meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
    meta["formato_version"] = 99
    ruta_meta.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(formato.ErrorDeFormato, match="99"):
        formato.leer_sesion_cruda(tmp_path)


def test_valor_fuera_de_int16_da_error(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    imu.loc[0, "ax"] = 40000

    with pytest.raises(formato.ErrorDeFormato, match="ax"):
        formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)


def test_columnas_incorrectas_dan_error(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    baro = baro.rename(columns={"adc_P": "presion"})

    with pytest.raises(formato.ErrorDeFormato, match="baro.csv"):
        formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)


def test_falta_un_archivo_da_error(tmp_path):
    imu, baro, eventos = _tablas_de_ejemplo()
    formato.escribir_sesion(tmp_path, formato.crear_meta(), imu, baro, eventos)
    (tmp_path / formato.ARCHIVO_BARO).unlink()

    with pytest.raises(formato.ErrorDeFormato, match="baro.csv"):
        formato.leer_sesion_cruda(tmp_path)


def test_nombre_de_carpeta_ida_y_vuelta():
    inicio = datetime(2026, 11, 14, 9, 30, 5)

    nombre = formato.nombre_carpeta_sesion(inicio)

    assert nombre == "sesion_20261114_093005"
    assert formato.fecha_de_carpeta_sesion(nombre) == inicio


def test_nombre_de_carpeta_invalido_da_error():
    with pytest.raises(formato.ErrorDeFormato):
        formato.fecha_de_carpeta_sesion("viaje_metro_1")
