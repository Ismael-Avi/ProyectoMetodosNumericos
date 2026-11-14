"""Fusión de sensores en una dimensión: acelerómetro + barómetro (+ paradas).

Por qué fusionar: cada sensor falla de una manera distinta.

- Acelerómetro integrado dos veces: muy bueno para cambios RÁPIDOS (sigue cada arranque y
  cada frenada), pero su error crece con el tiempo (un sesgo b da un error ½·b·t²).
- Barómetro: su error NO crece con el tiempo de la misma manera (no se integra nada), pero
  tiene ruido (≈0,2 m) y cambia lentamente con el clima.

Dos formas de combinarlos, las dos escritas a mano (sin librerías de filtros):

1. Filtro complementario: una regla fija. "Créele al acelerómetro en lo rápido y al
   barómetro en lo lento." Un solo parámetro: la constante de tiempo τ.
2. Filtro de Kalman: lleva la cuenta de cuánta INCERTIDUMBRE tiene su estimación y, cada vez
   que llega una medición, decide cuánto creerle según esa incertidumbre. Además de la
   altura barométrica acepta la medición "velocidad = 0" en las paradas (ZUPT).

En las dos, el estado es la altura h (m) y la velocidad vertical v (m/s).
"""

import numpy as np

import config


def alinear_mediciones(t_s, t_medicion_s, valores):
    """Coloca mediciones lentas (barómetro) sobre la base de tiempo rápida (IMU).

    Devuelve un arreglo del largo de t_s lleno de NaN, con cada medición puesta en la
    primera muestra del IMU posterior a ella. NaN significa "aquí no hay medición nueva".
    No se interpola: cada medición del barómetro se usa una sola vez.
    """
    alineado = np.full(len(t_s), np.nan)
    indice = np.searchsorted(t_s, t_medicion_s)
    dentro = indice < len(t_s)
    alineado[indice[dentro]] = np.asarray(valores, dtype=float)[dentro]
    return alineado


def filtro_complementario(t_s, aceleracion, altura_baro, tau_s=config.COMPLEMENTARIO_TAU_S):
    """Filtro complementario de altura: acelerómetro + barómetro.

    En cada paso se integra la aceleración (como siempre) y además se "tira" de la
    estimación hacia la altura del barómetro:

        error = altura_baro − h
        v ← v + (a + k_v · error) · dt
        h ← h + (v + k_h · error) · dt

    con k_h = 2/τ y k_v = 1/τ². Si la estimación se aleja del barómetro, el error la trae
    de vuelta en un tiempo del orden de τ. Con esas dos ganancias el regreso es lo más
    rápido posible sin oscilar (amortiguamiento crítico).

    - τ grande: se le cree más al acelerómetro (curva suave, pero más deriva).
    - τ pequeño: se le cree más al barómetro (sin deriva, pero con su ruido).

    t_s: instantes del IMU. aceleracion: aceleración vertical sin gravedad, en m/s².
    altura_baro: altura barométrica en los mismos instantes (interpolada), en m.
    Devuelve (altura en m, velocidad en m/s).
    """
    n = len(t_s)
    k_h = 2.0 / tau_s
    k_v = 1.0 / tau_s**2
    altura = np.zeros(n)
    velocidad = np.zeros(n)
    altura[0] = altura_baro[0]
    for i in range(1, n):
        dt = t_s[i] - t_s[i - 1]
        error = altura_baro[i - 1] - altura[i - 1]
        velocidad[i] = velocidad[i - 1] + (aceleracion[i - 1] + k_v * error) * dt
        altura[i] = altura[i - 1] + (velocidad[i - 1] + k_h * error) * dt
    return altura, velocidad


def _predecir(x, P, aceleracion, dt, std_accel):
    """Paso de predicción del Kalman: avanzar dt con la aceleración medida.

    Estado x = [h, v]. Modelo de movimiento (cinemática con aceleración constante en dt):

        h ← h + v·dt + a·dt²/2
        v ← v + a·dt

    En forma de matriz: x ← F·x + B·a, con F = [[1, dt], [0, 1]] y B = [dt²/2, dt].
    La incertidumbre P (matriz de covarianza 2x2) crece, porque la aceleración medida tiene
    un error de desviación std_accel:

        P ← F·P·Fᵀ + Q,      Q = std_accel² · B·Bᵀ
    """
    F = np.array([[1.0, dt], [0.0, 1.0]])
    B = np.array([dt**2 / 2, dt])
    x = F @ x + B * aceleracion
    P = F @ P @ F.T + std_accel**2 * np.outer(B, B)
    return x, P


def _actualizar(x, P, H, medicion, std_medicion):
    """Paso de actualización del Kalman con UNA medición escalar.

    H dice qué parte del estado se midió: [1, 0] = la altura, [0, 1] = la velocidad.

        innovación  y = medición − H·x          lo que la medición "sorprende" al filtro
        S = H·P·Hᵀ + std_medicion²              incertidumbre de esa sorpresa
        ganancia    K = P·Hᵀ / S                cuánto creerle a la medición (entre 0 y 1
                                                para la magnitud medida)
        x ← x + K·y
        P ← P − K·(H·P)                         la incertidumbre baja

    Si el filtro está muy seguro (P pequeña) casi ignora la medición; si está inseguro
    (P grande) la sigue.
    """
    y = medicion - H @ x
    S = H @ P @ H + std_medicion**2
    K = P @ H / S
    x = x + K * y
    P = P - np.outer(K, H @ P)
    return x, P


def kalman_altura(t_s, aceleracion, altura_baro=None, en_parada=None,
                  std_accel=config.KALMAN_ACCEL_STD_MS2, std_baro=config.KALMAN_BARO_STD_M,
                  std_zupt=config.KALMAN_ZUPT_STD_MS):
    """Filtro de Kalman 1D para la altura. Estado: [altura h, velocidad v].

    t_s, aceleracion: instantes del IMU y aceleración vertical sin gravedad (m/s²).
    altura_baro: None (sin barómetro) o un arreglo alineado con t_s, con NaN donde no hay
        medición nueva (ver alinear_mediciones).
    en_parada: None (sin ZUPT) o un arreglo de True/False; en las muestras True se agrega
        la medición "velocidad = 0".

    Devuelve (altura, velocidad, desviación estándar de la altura según el propio filtro).
    La tercera salida es la incertidumbre que el filtro CREE tener: se puede comparar con el
    error real.
    """
    n = len(t_s)
    H_ALTURA = np.array([1.0, 0.0])
    H_VELOCIDAD = np.array([0.0, 1.0])

    x = np.array([0.0, 0.0])                     # empieza quieto, en la altura de referencia
    P = np.diag([std_baro**2, std_zupt**2])      # incertidumbre inicial
    altura, velocidad, std_altura = np.zeros(n), np.zeros(n), np.zeros(n)
    std_altura[0] = np.sqrt(P[0, 0])

    for i in range(1, n):
        x, P = _predecir(x, P, aceleracion[i - 1], t_s[i] - t_s[i - 1], std_accel)
        if altura_baro is not None and not np.isnan(altura_baro[i]):
            x, P = _actualizar(x, P, H_ALTURA, altura_baro[i], std_baro)
        if en_parada is not None and en_parada[i]:
            x, P = _actualizar(x, P, H_VELOCIDAD, 0.0, std_zupt)
        altura[i], velocidad[i] = x
        std_altura[i] = np.sqrt(P[0, 0])
    return altura, velocidad, std_altura
