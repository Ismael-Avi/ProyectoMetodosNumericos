"""Predicción del error: cuánto DEBERÍA equivocarse la integración, según el sensor.

Antes de procesar un experimento se puede predecir cómo crece el error con el tiempo, a
partir de la caracterización (sesgo, ruido, deriva, error de escala). Después se compara
con el error observado. Si no coinciden, hay un error que no se tuvo en cuenta.

Todas las fórmulas salen de integrar dos veces el error de la aceleración. Con t = tiempo
integrando (s) y dt = período de muestreo (s):

  causa del error en la aceleración        error de velocidad        error de posición
  --------------------------------------   -----------------------   ------------------------
  sesgo constante b (m/s²)                 b·t                       ½·b·t²
  ruido blanco, desviación σ por muestra   σ·√(dt·t)                 σ·√(dt·t³/3)
  deriva del sesgo (paseo aleatorio), q    q·√(t³/3)                 q·√(t⁵/20)
  error de escala ε (sin unidades)         ε·(velocidad real)        ε·(desplazamiento real)

El sesgo da un error fijo (siempre igual); el ruido y la deriva dan errores aleatorios: la
fórmula es su desviación estándar (el tamaño típico), no su valor.

De dónde sale la del ruido: la velocidad es la suma de N = t/dt muestras, cada una
multiplicada por dt. Cada muestra aporta un error independiente de desviación σ·dt, y las
varianzas de errores independientes se suman: varianza = N·(σ·dt)² = σ²·dt·t. Es un "paseo
aleatorio": crece con √t, no con t.
"""

import numpy as np


def error_velocidad_por_sesgo(sesgo_ms2, t_s):
    """Error de velocidad que produce un sesgo constante: b·t (m/s)."""
    return sesgo_ms2 * np.asarray(t_s, dtype=float)


def error_posicion_por_sesgo(sesgo_ms2, t_s):
    """Error de posición que produce un sesgo constante: ½·b·t² (m)."""
    return 0.5 * sesgo_ms2 * np.asarray(t_s, dtype=float)**2


def std_velocidad_por_ruido(std_ruido_ms2, dt_s, t_s):
    """Desviación del error de velocidad por ruido blanco: σ·√(dt·t) (m/s)."""
    return std_ruido_ms2 * np.sqrt(dt_s * np.asarray(t_s, dtype=float))


def std_posicion_por_ruido(std_ruido_ms2, dt_s, t_s):
    """Desviación del error de posición por ruido blanco: σ·√(dt·t³/3) (m)."""
    return std_ruido_ms2 * np.sqrt(dt_s * np.asarray(t_s, dtype=float)**3 / 3)


def std_posicion_por_ruido_con_zupt(std_ruido_ms2, dt_s, duracion_recorrido_s):
    """Lo mismo, pero en un recorrido corregido con ZUPT: σ·√(dt·T³/12) (m).

    El ZUPT obliga a que la velocidad sea cero al final y reparte el error en línea recta.
    Eso quita una parte del paseo aleatorio: el error de posición al final del recorrido
    baja a la mitad (√(1/12) en lugar de √(1/3)).
    """
    T = np.asarray(duracion_recorrido_s, dtype=float)
    return std_ruido_ms2 * np.sqrt(dt_s * T**3 / 12)


def std_posicion_por_deriva(deriva_std, t_s):
    """Desviación del error de posición por la deriva del sesgo: q·√(t⁵/20) (m).

    deriva_std (q): cuánto se mueve el sesgo, en (m/s²)/√s (paseo aleatorio).
    """
    return deriva_std * np.sqrt(np.asarray(t_s, dtype=float)**5 / 20)


def std_del_sesgo_medido(std_ruido_ms2, dt_s, duracion_reposo_s):
    """Con qué exactitud se conoce el sesgo si se promedia un reposo: σ·√(dt/T_reposo).

    Promediar N muestras reduce el ruido √N veces, y N = T_reposo/dt.
    """
    return std_ruido_ms2 * np.sqrt(dt_s / duracion_reposo_s)


def error_posicion_por_escala(error_escala, desplazamiento_m):
    """Error de posición por un error de escala: ε·(desplazamiento real) (m).

    Vale cuando la gravedad ya se restó midiéndola en reposo con el mismo sensor (así el
    error de escala sobre g se cancela y solo queda el de la aceleración del movimiento).
    """
    return error_escala * np.asarray(desplazamiento_m, dtype=float)


def std_posicion_sin_correcciones(std_ruido_ms2, deriva_std, dt_s, t_s, duracion_reposo_s):
    """Desviación total del error de posición al integrar sin ZUPT, con el sesgo restado.

    Suma (en varianza, porque son errores independientes) tres causas: el ruido blanco, la
    deriva del sesgo y el error con que se midió el sesgo en el reposo inicial.
    """
    por_ruido = std_posicion_por_ruido(std_ruido_ms2, dt_s, t_s)
    por_deriva = std_posicion_por_deriva(deriva_std, t_s)
    sesgo_residual = std_del_sesgo_medido(std_ruido_ms2, dt_s, duracion_reposo_s)
    por_sesgo = error_posicion_por_sesgo(sesgo_residual, t_s)
    return np.sqrt(por_ruido**2 + por_deriva**2 + por_sesgo**2)


def std_altura_barometro(std_presion_Pa, pascales_por_metro):
    """Ruido de la altura barométrica: ruido de presión (Pa) dividido por los Pa/m."""
    return std_presion_Pa / pascales_por_metro
