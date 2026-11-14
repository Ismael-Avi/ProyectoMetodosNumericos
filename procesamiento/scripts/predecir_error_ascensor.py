"""Predicción del error del ascensor comparada con simulaciones Monte Carlo.

Uso (desde la carpeta procesamiento/):

    python -m scripts.predecir_error_ascensor
    python -m scripts.predecir_error_ascensor --cantidad 100

Idea: las fórmulas de navinercial/prediccion_error.py dicen cuánto DEBERÍA crecer el error
con el tiempo, a partir del ruido, la deriva y el error de escala del sensor. Para
comprobarlas se repite la simulación del ascensor muchas veces, cambiando solo la semilla
de los números aleatorios (método de Monte Carlo): cada repetición da un error distinto, y
la dispersión de todos esos errores se compara con la predicción.

Solo se simula el acelerómetro (sin calibrar), que es lo que se integra.

IMPORTANTE: los parámetros del sensor son los del simulador (config.py, SIM_...). Con el
dispositivo real hay que poner aquí el ruido y la deriva medidos en la caracterización.

Guarda en resultados/prediccion_error/:
    reporte.txt
    sin_zupt_dispersion.png   desviación del error de altura: observada y predicha
    sin_zupt_media.png        error medio de altura: observado y predicho (error de escala)
"""

import argparse

import numpy as np
import pandas as pd

import config
from navinercial import ascensor, correcciones, graficas, lectura, prediccion_error
from simulador import escenarios, modelo_sensor


def simular_acelerometro(escenario, parametros, semilla):
    """Una simulación del acelerómetro: tabla con t_s, ax, ay, az (m/s²) y la altura real."""
    rng = np.random.default_rng(semilla)
    tiempo = parametros.tiempo
    t = modelo_sensor.generar_tiempos_s(
        escenario.duracion_s, tiempo.fs_imu_real_hz, tiempo.jitter_std_us, rng)
    estado = escenario.estado(t)
    fuerza = estado[escenarios.COLUMNAS_FUERZA].to_numpy()
    medido = modelo_sensor.medir_triaxial(
        fuerza, parametros.acelerometro, 1.0 / config.FS_IMU_NOMINAL_HZ, rng)
    # Igual que el dispositivo: se guarda como entero de 16 bits y se vuelve a convertir.
    lsb_por_ms2 = config.ACCEL_LSB_POR_G[config.ACCEL_RANGO_G] / config.G_ESTANDAR
    crudo = modelo_sensor.cuantizar_int16(medido, lsb_por_ms2)
    imu = pd.DataFrame(lectura.accel_crudo_a_ms2(crudo.astype(float), config.ACCEL_RANGO_G),
                       columns=lectura.COLUMNAS_ACCEL)
    imu.insert(0, "t_s", t)
    return imu, estado["altura_m"].to_numpy()


def errores_de_una_simulacion(escenario, parametros, semilla, paradas, t_comun):
    """Error de altura sin ZUPT (en la base de tiempo común) y error por recorrido con ZUPT."""
    imu, altura_real = simular_acelerometro(escenario, parametros, semilla)
    t = imu["t_s"].to_numpy()
    vertical, gravedad = ascensor.vertical_en_reposo(imu, paradas[0])
    a = ascensor.aceleracion_vertical(imu, vertical, gravedad)

    _, altura = ascensor.integrar(t, a)
    error_sin_zupt = np.interp(t_comun, t, altura - altura_real)

    _, altura_zupt = ascensor.integrar_con_zupt(t, a, paradas)
    calculado = ascensor.desplazamientos(ascensor.alturas_en_paradas(t, altura_zupt, paradas))
    real = ascensor.desplazamientos(ascensor.alturas_en_paradas(t, altura_real, paradas))
    return error_sin_zupt, calculado - real, vertical


def prediccion_sin_zupt(parametros, t_comun, altura_real, vertical, duracion_reposo_s):
    """Predicción del error de altura sin ZUPT: (media, desviación estándar) en cada instante."""
    p = parametros.acelerometro
    dt = 1.0 / config.FS_IMU_NOMINAL_HZ
    # Error de escala visto en la dirección vertical: cada eje pesa según cuánto apunta
    # hacia arriba (con el dispositivo casi nivelado, es casi el del eje z).
    escala_vertical = float(np.sum(np.array(p.error_escala) * vertical**2))
    media = prediccion_error.error_posicion_por_escala(escala_vertical, altura_real)
    # El error empieza a crecer cuando termina el reposo inicial: durante el reposo, restar
    # el promedio deja la velocidad en cero al final.
    t_desde_el_reposo = np.clip(t_comun - duracion_reposo_s, 0.0, None)
    desviacion = prediccion_error.std_posicion_sin_correcciones(
        p.ruido_std, p.deriva_std, dt, t_desde_el_reposo, duracion_reposo_s)
    return media, desviacion, escala_vertical


def tabla_con_zupt(parametros, paradas, errores_por_recorrido, alturas_paradas, escala_vertical):
    """Por recorrido: error medio y dispersión observados, junto a los predichos."""
    p = parametros.acelerometro
    dt = 1.0 / config.FS_IMU_NOMINAL_HZ
    # Tiempo que se integra "a ciegas" en cada recorrido: de una parada a la siguiente.
    duracion = np.array([paradas[k + 1][0] - paradas[k][1] for k in range(len(paradas) - 1)])
    desplazamiento = np.diff(alturas_paradas)
    return pd.DataFrame({
        "recorrido": np.arange(1, len(duracion) + 1),
        "duración (s)": duracion,
        "desplazamiento (m)": desplazamiento,
        "error medio observado (m)": errores_por_recorrido.mean(axis=0),
        "error medio predicho (m)": prediccion_error.error_posicion_por_escala(
            escala_vertical, desplazamiento),
        "desviación observada (m)": errores_por_recorrido.std(axis=0, ddof=1),
        "desviación predicha (m)": prediccion_error.std_posicion_por_ruido_con_zupt(
            p.ruido_std, dt, duracion),
    }).set_index("recorrido")


def texto_reporte(cantidad, parametros, t_comun, media_obs, media_pred, std_obs, std_pred,
                  tabla, escala_vertical):
    p = parametros.acelerometro
    lineas = [
        "PREDICCIÓN DEL ERROR DEL ASCENSOR Y COMPROBACIÓN POR MONTE CARLO",
        f"Simulaciones: {cantidad} (semillas 0 a {cantidad - 1}). Acelerómetro SIN calibrar.",
        f"Parámetros del simulador: ruido {p.ruido_std} m/s² por muestra, deriva del sesgo "
        f"{p.deriva_std} (m/s²)/√s,",
        f"  error de escala en la vertical {100 * escala_vertical:.2f} %.",
        "",
        "SIN ZUPT (sesgo del reposo inicial restado): error de altura según el tiempo",
        "  tiempo (s)   media obs.   media pred.   desviación obs.   desviación pred.",
    ]
    for instante in [60, 120, 240, 360, t_comun[-1]]:
        i = int(np.searchsorted(t_comun, instante, side="right")) - 1
        lineas.append(f"  {t_comun[i]:9.0f}   {media_obs[i]:10.3f}   {media_pred[i]:11.3f}   "
                      f"{std_obs[i]:15.3f}   {std_pred[i]:16.3f}")
    lineas += [
        "  media predicha = error de escala · altura real;",
        "  desviación predicha = ruido σ·√(dt·t³/3), deriva q·√(t⁵/20) y sesgo mal medido ½·σ_b·t²,",
        "  con t contado desde el final del reposo inicial.",
        f"  Con {cantidad} simulaciones, la desviación observada tiene una incertidumbre de "
        f"±{100 / np.sqrt(2 * (cantidad - 1)):.0f} %.",
        "",
        "CON ZUPT: error del desplazamiento de cada recorrido",
        tabla.to_string(float_format=lambda v: f"{v:.4f}"),
        "  error medio predicho = error de escala · desplazamiento;",
        "  desviación predicha = σ·√(dt·T³/12), con T = tiempo entre dos paradas.",
    ]
    return "\n".join(lineas)


def main():
    analizador = argparse.ArgumentParser(description="Predicción del error y Monte Carlo.")
    analizador.add_argument("--cantidad", type=int, default=config.MONTE_CARLO_CANTIDAD)
    cantidad = analizador.parse_args().cantidad

    escenario = escenarios.crear_ascensor()
    parametros = modelo_sensor.ParametrosSimulacion()
    paradas = correcciones.paradas_por_eventos(escenario.tiempos_eventos_s, 0.0, escenario.duracion_s)
    t_comun = np.arange(0.0, escenario.duracion_s, 0.5)
    altura_real = escenario.altura(t_comun)

    errores_sin_zupt, errores_por_recorrido = [], []
    for semilla in range(cantidad):
        e_sin, e_recorrido, vertical = errores_de_una_simulacion(
            escenario, parametros, semilla, paradas, t_comun)
        errores_sin_zupt.append(e_sin)
        errores_por_recorrido.append(e_recorrido)
    errores_sin_zupt = np.array(errores_sin_zupt)
    errores_por_recorrido = np.array(errores_por_recorrido)

    media_obs = errores_sin_zupt.mean(axis=0)
    std_obs = errores_sin_zupt.std(axis=0, ddof=1)
    duracion_reposo = paradas[0][1] - paradas[0][0]
    media_pred, std_pred, escala_vertical = prediccion_sin_zupt(
        parametros, t_comun, altura_real, vertical, duracion_reposo)
    alturas_paradas = ascensor.alturas_en_paradas(t_comun, altura_real, paradas)
    tabla = tabla_con_zupt(parametros, paradas, errores_por_recorrido, alturas_paradas,
                           escala_vertical)

    reporte = texto_reporte(cantidad, parametros, t_comun, media_obs, media_pred, std_obs,
                            std_pred, tabla, escala_vertical)
    carpeta = config.CARPETA_RESULTADOS / "prediccion_error"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "reporte.txt").write_text(reporte, encoding="utf-8")
    graficas.guardar_figura(
        graficas.grafica_prediccion(
            t_comun, std_obs, std_pred, "Dispersión del error de altura, sin ZUPT",
            "desviación estándar del error (m)", f"observada ({cantidad} simulaciones)",
            "predicha con las fórmulas"),
        carpeta / "sin_zupt_dispersion.png")
    graficas.guardar_figura(
        graficas.grafica_prediccion(
            t_comun, media_obs, media_pred, "Error medio de altura, sin ZUPT",
            "error medio (m)", f"observado ({cantidad} simulaciones)",
            "predicho: error de escala · altura"),
        carpeta / "sin_zupt_media.png")
    print(reporte)
    print(f"\nReporte y gráficas guardados en: {carpeta}")


if __name__ == "__main__":
    main()
