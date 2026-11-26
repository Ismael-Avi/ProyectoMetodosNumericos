"""CALCULO TEORICO del error de distancia en un viaje hipotetico del Metro de Quito.

Sirve para la GUIA_ESTUDIO.md, seccion e). No usa datos del metro ni simulaciones: solo el sesgo
y el ruido medidos con nuestro sensor (reposo y ascensor), el error de escala de las seis caras y
un perfil de viaje supuesto. Correr desde proyecto_simple/:

    python guia/estimar_error_metro.py

Guarda guia/error_metro_estimado.png e imprime la tabla de la guia.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Numeros medidos (fuente entre parentesis) ---
DT = 0.005               # s, 200 Hz (meta.json; verificar: 200,000 Hz)
SIGMA_MESA = 0.013       # m/s², ruido en reposo sobre la mesa (resultados/reposo_90min_..._reposo.txt)
SIGMA_VIBRA = 0.095      # m/s², ruido con el piso del ascensor vibrando (resultados/ascensor_2026-11-26_ascensor.txt)
B_RESIDUAL = 2 * 154.26 / 305.0 ** 2   # m/s², sesgo que queda tras restar el del reposo inicial:
                                       # 154 m de error en 305 s en el ascensor (mismo reporte) -> 0,0033
B_DERIVA = 0.0142        # m/s², cambio de ax en 95 min de reposo (reposo_90min_..._reposo.txt)
ERROR_ESCALA = 0.0092 / 9.77   # 0,094 %: desv. est. de |g| calibrado en 8 posiciones (caras_2026-11-24_caras.txt)

# --- Viaje supuesto (no medido): Quitumbe - El Labrador ---
DISTANCIA_M = 22000.0
N_ESTACIONES = 15
DURACION_S = 35 * 60
PARADA_S = 60.0          # con paradas de 1 min; con 3 min no alcanzan los 35 min (ver la guia)
ACEL = 1.0               # m/s², aceleracion y frenado tipicos de un tren (supuesto)

# --- Prueba de la formula del ZUPT con el ascensor real ---
# Con ZUPT, el ruido deja en cada tramo de duracion tau un error de posicion
#   sigma_x = sigma * raiz(dt) * tau^1.5 / raiz(12)   (puente browniano integrado)
TAU_ASCENSOR = np.array([11.7, 16.1, 15.5, 12.1, 12.7])   # s, recorridos 2, 5, 6, 9, 11 (eventos_corregidos.csv)


def error_zupt(sigma, tau):
    return sigma * np.sqrt(DT) * tau ** 1.5 / np.sqrt(12)


def main():
    pred = SIGMA_VIBRA * np.sqrt(DT) * np.sqrt(np.mean(TAU_ASCENSOR ** 3)) / np.sqrt(12)
    print(f"Ascensor, recorridos sin PB: error RMS del desnivel predicho {pred:.3f} m; medido 0,106 m (trapecio + ZUPT)")

    n_tramos = N_ESTACIONES - 1
    tau = (DURACION_S - (n_tramos - 1) * PARADA_S) / n_tramos          # s en movimiento por tramo
    largo = DISTANCIA_M / n_tramos
    vmax = (ACEL * tau - np.sqrt((ACEL * tau) ** 2 - 4 * ACEL * largo)) / 2   # perfil trapezoidal
    print(f"Viaje supuesto: {n_tramos} tramos de {largo:.0f} m, {tau:.1f} s en movimiento cada uno, "
          f"paradas de {PARADA_S:.0f} s, velocidad maxima {vmax:.1f} m/s ({vmax * 3.6:.0f} km/h)")

    # Linea de tiempo cada 0,5 s: distancia recorrida y en que tramo va
    t, d, tramo_de = [0.0], [0.0], [0]
    paso = 0.5
    for k in range(n_tramos):
        t_ac = vmax / ACEL
        for u in np.arange(paso, tau + paso / 2, paso):
            if u < t_ac:
                dd = 0.5 * ACEL * u ** 2
            elif u < tau - t_ac:
                dd = 0.5 * ACEL * t_ac ** 2 + vmax * (u - t_ac)
            else:
                dd = largo - 0.5 * ACEL * (tau - u) ** 2
            t.append(t[-1] + paso)
            d.append(k * largo + dd)
            tramo_de.append(k)
        if k < n_tramos - 1:
            for _ in np.arange(paso, PARADA_S + paso / 2, paso):
                t.append(t[-1] + paso)
                d.append((k + 1) * largo)
                tramo_de.append(k + 1)
    t, d, tramo_de = np.array(t), np.array(d), np.array(tramo_de)

    # Caso A: sin ZUPT (solo se resta el sesgo del reposo inicial). El error crece aunque el tren este parado.
    a_sesgo = 0.5 * B_RESIDUAL * t ** 2
    a_deriva = 0.5 * B_DERIVA * t ** 2
    a_ruido = SIGMA_VIBRA * np.sqrt(DT) * t ** 1.5 / np.sqrt(3)
    # Caso B: ZUPT en cada estacion. Un sesgo constante dentro del tramo se elimina entero; queda el ruido de
    # cada tramo (se suma como paseo aleatorio entre tramos) y el error de escala (proporcional a la distancia).
    tramos_terminados = np.floor((d + 0.5) / largo)   # +0,5 m: al llegar a la estacion el tramo cuenta como terminado
    b_ruido = error_zupt(SIGMA_VIBRA, tau) * np.sqrt(tramos_terminados)
    b_ruido_mesa = error_zupt(SIGMA_MESA, tau) * np.sqrt(tramos_terminados)
    b_escala = ERROR_ESCALA * d
    b_total = np.sqrt(b_ruido ** 2 + b_escala ** 2)

    print("distancia (km) | t (min) | A: sesgo 0,0033 | A: deriva 0,014 | A: ruido 0,095 | "
          "B: ruido 0,095 | B: ruido 0,013 | B: escala 0,094 % | B: total")
    for km in [1.571, 5, 11, 22]:
        i = min(np.searchsorted(d, km * 1000 - 1e-6), len(d) - 1)
        if km == 22:
            i = len(d) - 1
        print(f"  {d[i] / 1000:5.1f} | {t[i] / 60:5.1f} | {a_sesgo[i]:9.0f} m | {a_deriva[i]:9.0f} m | {a_ruido[i]:7.1f} m | "
              f"{b_ruido[i]:5.1f} m | {b_ruido_mesa[i]:5.2f} m | {b_escala[i]:5.1f} m | {b_total[i]:5.1f} m")

    fig, ax = plt.subplots(figsize=(8, 5))
    km = d / 1000
    ax.semilogy(km[1:], a_deriva[1:], color="tab:red", ls="--", label="A sin ZUPT: sesgo 0,014 m/s² (deriva 95 min)")
    ax.semilogy(km[1:], a_sesgo[1:], color="tab:red", label="A sin ZUPT: sesgo residual 0,0033 m/s²")
    ax.semilogy(km[1:], a_ruido[1:], color="tab:orange", label="A sin ZUPT: ruido 0,095 m/s²")
    ax.semilogy(km[1:], b_total[1:], color="tab:green", lw=2, label="B con ZUPT: total")
    ax.semilogy(km[1:], b_escala[1:], color="tab:green", ls="--", label="B con ZUPT: escala 0,094 %")
    ax.semilogy(km[1:], np.maximum(b_ruido[1:], 1e-3), color="tab:olive", ls=":", label="B con ZUPT: ruido 0,095 m/s²")
    for k in range(1, n_tramos):
        ax.axvline(k * largo / 1000, color="0.85", lw=0.6, zorder=0)
    ax.set(xlabel="distancia recorrida (km)", ylabel="error de distancia (m)", ylim=(0.1, 5e4),
           title="Calculo teorico: error en un viaje hipotetico de 22 km (gris: estaciones)")
    ax.grid(True, which="major", alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_metro_estimado.png")
    fig.savefig(salida, dpi=120)
    print(f"Figura: {salida}")


if __name__ == "__main__":
    main()
