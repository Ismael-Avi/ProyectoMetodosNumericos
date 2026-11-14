"""Verificación de una sesión: muestras perdidas, frecuencia de muestreo real y jitter.

Se usan dos datos de cada muestra:
- seq: el contador de muestra. Si entre dos filas seguidas aumenta más de 1, se perdieron
  muestras.
- t_s: la marca de tiempo. Si el intervalo entre dos filas es mucho mayor que el período
  normal, también faltan muestras (aunque seq no lo diga).

Frecuencia real: se calcula como (muestras transcurridas) / (tiempo transcurrido), usando
seq para contar las muestras. Así las muestras perdidas no alteran el resultado.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config


@dataclass
class VerificacionTabla:
    """Resultado de verificar una tabla (imu o baro)."""

    nombre: str
    n_muestras: int
    duracion_s: float
    fs_nominal_hz: float
    fs_media_hz: float            # en todo el registro
    fs_inicio_hz: float           # en la primera ventana
    fs_final_hz: float            # en la última ventana
    ventana_s: float              # duración de esas ventanas
    huecos: pd.DataFrame          # un renglón por cada salto (ver buscar_huecos)
    n_perdidas_seq: int           # muestras perdidas según el contador seq
    n_perdidas_tiempo: int        # muestras perdidas según las marcas de tiempo
    n_seq_no_creciente: int       # veces que seq no aumentó (repetido o reiniciado)
    n_tiempo_no_creciente: int    # veces que el tiempo no aumentó
    intervalo: dict               # estadísticas del intervalo entre muestras, en µs

    @property
    def diferencia_inicio_final_ppm(self):
        """Cambio relativo de la frecuencia entre el inicio y el final, en partes por millón."""
        return (self.fs_final_hz - self.fs_inicio_hz) / self.fs_inicio_hz * 1e6


# ---------------------------------------------------------------------------
# Frecuencia de muestreo real
# ---------------------------------------------------------------------------

def frecuencia_real(seq, t_s):
    """Frecuencia de muestreo real de un tramo, en Hz.

    fs = (muestras transcurridas) / (tiempo transcurrido)
       = (seq_final − seq_inicial) / (t_final − t_inicial)
    """
    seq = np.asarray(seq)
    t_s = np.asarray(t_s)
    return (seq[-1] - seq[0]) / (t_s[-1] - t_s[0])


def frecuencia_inicio_y_final(seq, t_s, ventana_s=config.VERIF_VENTANA_FRECUENCIA_S):
    """Frecuencia real en la primera y en la última ventana del registro.

    Si el registro dura menos de dos ventanas, cada ventana se acorta a la mitad del registro.
    Devuelve (fs_inicio en Hz, fs_final en Hz, ventana usada en s).
    """
    seq = np.asarray(seq)
    t_s = np.asarray(t_s)
    duracion = t_s[-1] - t_s[0]
    ventana_s = min(ventana_s, duracion / 2)

    al_inicio = t_s <= t_s[0] + ventana_s
    al_final = t_s >= t_s[-1] - ventana_s
    return (frecuencia_real(seq[al_inicio], t_s[al_inicio]),
            frecuencia_real(seq[al_final], t_s[al_final]),
            ventana_s)


def frecuencia_por_ventanas(seq, t_s, ventana_s=config.VERIF_VENTANA_FRECUENCIA_S):
    """Frecuencia real en ventanas consecutivas, para ver cómo cambia durante el registro.

    Devuelve (centro de cada ventana en s, frecuencia de cada ventana en Hz).
    """
    seq = np.asarray(seq)
    t_s = np.asarray(t_s)
    bordes = np.arange(t_s[0], t_s[-1], ventana_s)
    centros, frecuencias = [], []
    for inicio in bordes:
        en_ventana = (t_s >= inicio) & (t_s < inicio + ventana_s)
        if en_ventana.sum() < 2:
            continue
        centros.append(inicio + ventana_s / 2)
        frecuencias.append(frecuencia_real(seq[en_ventana], t_s[en_ventana]))
    return np.array(centros), np.array(frecuencias)


# ---------------------------------------------------------------------------
# Muestras perdidas e intervalo entre muestras
# ---------------------------------------------------------------------------

def buscar_huecos(seq, t_s):
    """Busca saltos en el contador seq y en las marcas de tiempo.

    Para cada par de filas seguidas se calcula:
    - perdidas_seq    = (aumento de seq) − 1
    - perdidas_tiempo = redondear(intervalo / período normal) − 1
      donde el período normal es la mediana de todos los intervalos (la mediana no se
      altera por unos pocos intervalos largos).

    Devuelve una tabla con un renglón por cada par donde alguna de las dos es mayor que
    cero: fila, t_s, seq_anterior, seq_siguiente, intervalo_s, perdidas_seq, perdidas_tiempo.
    Si las dos cuentas no coinciden en un renglón, el contador y el reloj se contradicen.
    """
    seq = np.asarray(seq)
    t_s = np.asarray(t_s)
    aumento_seq = np.diff(seq)
    intervalo = np.diff(t_s)
    periodo = np.median(intervalo)

    perdidas_seq = aumento_seq - 1
    perdidas_tiempo = np.rint(intervalo / periodo).astype(int) - 1
    filas = np.flatnonzero((perdidas_seq > 0) | (perdidas_tiempo > 0))

    return pd.DataFrame({
        "fila": filas,
        "t_s": t_s[filas],
        "seq_anterior": seq[filas],
        "seq_siguiente": seq[filas + 1],
        "intervalo_s": intervalo[filas],
        "perdidas_seq": perdidas_seq[filas],
        "perdidas_tiempo": perdidas_tiempo[filas],
    })


def intervalos_consecutivos_us(seq, t_s):
    """Intervalo entre muestras seguidas, en µs, sin contar los huecos.

    Solo se toman los pares de filas donde seq aumenta exactamente 1.
    """
    seq = np.asarray(seq)
    t_s = np.asarray(t_s)
    son_consecutivas = np.diff(seq) == 1
    return np.diff(t_s)[son_consecutivas] * 1e6


def estadisticas_intervalo(seq, t_s):
    """Estadísticas del intervalo entre muestras consecutivas, en µs.

    La desviación estándar mide el jitter: cuánto varía el intervalo alrededor de su media.
    """
    intervalos = intervalos_consecutivos_us(seq, t_s)
    return {
        "media_us": float(np.mean(intervalos)),
        "std_us": float(np.std(intervalos)),
        "min_us": float(np.min(intervalos)),
        "max_us": float(np.max(intervalos)),
        "p01_us": float(np.percentile(intervalos, 1)),
        "p99_us": float(np.percentile(intervalos, 99)),
    }


# ---------------------------------------------------------------------------
# Verificación completa
# ---------------------------------------------------------------------------

def verificar_tabla(nombre, tabla, fs_nominal_hz, ventana_s=config.VERIF_VENTANA_FRECUENCIA_S):
    """Verifica una tabla con columnas seq y t_s. Devuelve un objeto VerificacionTabla."""
    seq = tabla["seq"].to_numpy()
    t_s = tabla["t_s"].to_numpy()
    huecos = buscar_huecos(seq, t_s)
    fs_inicio, fs_final, ventana_usada = frecuencia_inicio_y_final(seq, t_s, ventana_s)

    return VerificacionTabla(
        nombre=nombre,
        n_muestras=len(tabla),
        duracion_s=float(t_s[-1] - t_s[0]),
        fs_nominal_hz=fs_nominal_hz,
        fs_media_hz=float(frecuencia_real(seq, t_s)),
        fs_inicio_hz=float(fs_inicio),
        fs_final_hz=float(fs_final),
        ventana_s=float(ventana_usada),
        huecos=huecos,
        n_perdidas_seq=int(huecos["perdidas_seq"].clip(lower=0).sum()),
        n_perdidas_tiempo=int(huecos["perdidas_tiempo"].clip(lower=0).sum()),
        n_seq_no_creciente=int((np.diff(seq) <= 0).sum()),
        n_tiempo_no_creciente=int((np.diff(t_s) <= 0).sum()),
        intervalo=estadisticas_intervalo(seq, t_s),
    )


def verificar_sesion(sesion, ventana_s=config.VERIF_VENTANA_FRECUENCIA_S):
    """Verifica el IMU y el barómetro de una sesión. Devuelve {"imu": ..., "baro": ...}."""
    return {
        "imu": verificar_tabla("imu", sesion.imu, sesion.meta["fs_imu_nominal_hz"], ventana_s),
        "baro": verificar_tabla("baro", sesion.baro, sesion.meta["fs_baro_nominal_hz"], ventana_s),
    }


# ---------------------------------------------------------------------------
# Reporte en texto
# ---------------------------------------------------------------------------

MAX_HUECOS_EN_REPORTE = 15   # si hay más huecos, en el reporte solo se listan los primeros


def _texto_tabla(v):
    """Líneas del reporte para una tabla verificada."""
    i = v.intervalo
    lineas = [
        f"--- {v.nombre} ---",
        f"Muestras: {v.n_muestras}    Duración: {v.duracion_s:.1f} s ({v.duracion_s / 60:.2f} min)",
        f"Frecuencia nominal:             {v.fs_nominal_hz:.4f} Hz",
        f"Frecuencia real (todo):         {v.fs_media_hz:.4f} Hz",
        f"Frecuencia real al inicio:      {v.fs_inicio_hz:.4f} Hz  (primeros {v.ventana_s:.0f} s)",
        f"Frecuencia real al final:       {v.fs_final_hz:.4f} Hz  (últimos {v.ventana_s:.0f} s)",
        f"Cambio del inicio al final:     {v.diferencia_inicio_final_ppm:+.1f} ppm",
        f"Intervalo entre muestras (µs):  media {i['media_us']:.1f}, desviación (jitter) "
        f"{i['std_us']:.1f}, mínimo {i['min_us']:.0f}, máximo {i['max_us']:.0f}",
        f"Muestras perdidas según seq:    {v.n_perdidas_seq}",
        f"Muestras perdidas según tiempo: {v.n_perdidas_tiempo}",
        f"seq que no aumenta: {v.n_seq_no_creciente}    tiempo que no aumenta: "
        f"{v.n_tiempo_no_creciente}",
    ]
    if len(v.huecos) > 0:
        lineas.append(f"Huecos encontrados: {len(v.huecos)}")
        lineas.append(v.huecos.head(MAX_HUECOS_EN_REPORTE).to_string(index=False))
        if len(v.huecos) > MAX_HUECOS_EN_REPORTE:
            lineas.append(f"... y {len(v.huecos) - MAX_HUECOS_EN_REPORTE} más")
    return lineas


def _texto_requisitos(imu):
    """Compara el IMU con los requisitos del enunciado."""
    cumple_fs = imu.fs_media_hz >= config.REQUISITO_FS_MINIMA_HZ
    sin_perdidas = imu.n_perdidas_seq == 0 and imu.n_perdidas_tiempo == 0
    duracion_min = imu.duracion_s / 60
    return [
        "--- Requisitos del enunciado (IMU) ---",
        f"Muestreo de {config.REQUISITO_FS_MINIMA_HZ:.0f} Hz o más: "
        f"{'CUMPLE' if cumple_fs else 'NO CUMPLE'} ({imu.fs_media_hz:.2f} Hz)",
        f"Sin muestras perdidas: {'CUMPLE' if sin_perdidas else 'NO CUMPLE'}",
        f"Duración del registro: {duracion_min:.1f} min "
        f"(el requisito de {config.REQUISITO_DURACION_MIN:.0f} min continuos "
        f"{'se puede' if duracion_min >= config.REQUISITO_DURACION_MIN else 'NO se puede'} "
        f"comprobar con esta sesión)",
    ]


def texto_reporte(sesion, verificaciones):
    """Reporte de verificación de la sesión, como texto de varias líneas."""
    meta = sesion.meta
    lineas = [
        "REPORTE DE VERIFICACIÓN DE LA SESIÓN",
        f"Carpeta: {sesion.carpeta}",
        f"Firmware: {meta['firmware_version']}    Chip: {meta['chip_whoami']}    "
        f"Magnetómetro: {'sí' if meta['tiene_magnetometro'] else 'no'}",
        f"Notas: {meta['notas']}",
        f"Eventos del botón: {len(sesion.eventos)}",
        "",
    ]
    for verificacion in verificaciones.values():
        lineas += _texto_tabla(verificacion) + [""]
    lineas += _texto_requisitos(verificaciones["imu"])
    return "\n".join(lineas)
