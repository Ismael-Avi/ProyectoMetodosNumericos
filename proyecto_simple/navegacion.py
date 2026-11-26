import sys
import os
import json
import csv
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

G = 9.77   # m/s², enunciado; GRS80 en el ecuador - aire libre a 2850 m da ~9.7715 (calculo en el README)
G_ESTANDAR = 9.80665
LSB_POR_G = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}
LSB_POR_DPS = {250: 131.0, 500: 65.5, 1000: 32.8, 2000: 16.4}
R_GAS = 8.314462618
M_AIRE = 0.0289644
RADIO_TIERRA = 6371000.0

VENTANA_QUIETO_S = 0.5
UMBRAL_ACC = 0.06
UMBRAL_GIRO = np.radians(0.3)
REPOSO_INICIAL_S = 10.0
VENTANA_FRECUENCIA_S = 60.0
CARA_MINIMA_S = 10.0
QUIETO_MINIMO_S = 3.0
MARGEN_CARA_S = 1.0
TAU_FILTRO_S = 3.0
VENTANA_ARRANQUE_S = 5.0
SUAVIZADO_BARO_S = 10.0
VELOCIDAD_MIN_PENDIENTE = 1.0
SENO_MAX = 0.1
REBOTE_BOTON_S = 1.0
BLOQUE_DERIVA_S = 600.0
OPCIONES = {"botones": False, "recorte": 0.0, "hasta": None, "recorridos": None}
TOLERANCIA_PULSO_S = 0.1   # un pulso corregido "es original" si esta a menos de esto de uno de eventos.csv

BMP280_EJEMPLO = {"dig_T1": 27504, "dig_T2": 26435, "dig_T3": -1000,
                  "dig_P1": 36477, "dig_P2": -10685, "dig_P3": 3024, "dig_P4": 2855,
                  "dig_P5": 140, "dig_P6": -7, "dig_P7": 15500, "dig_P8": -14600, "dig_P9": 6000}

PRUEBA_SESGO = 0.05
PRUEBA_RUIDO = 0.02

CARPETA = os.path.dirname(os.path.abspath(__file__))
RESULTADOS = os.path.join(CARPETA, "resultados")
BITACORA = os.path.join(CARPETA, "bitacora.csv")
CALIBRACION = os.path.join(RESULTADOS, "calibracion.json")   # solo calibracion REAL; es la unica que se usa
CALIBRACION_SIMULADA = os.path.join(RESULTADOS, "simulados", "calibracion_simulada.json")   # nunca se carga
PISOS = os.path.join(CARPETA, "datos", "pisos.csv")
ESTACIONES = os.path.join(CARPETA, "datos", "estaciones.csv")
VIAJES = os.path.join(CARPETA, "datos", "viajes.csv")
COLUMNAS_BITACORA = ["fecha_proceso", "comando", "sesion", "firmware", "duracion_s", "recorte_s", "desplazamiento_m",
                     "vel_max_ms", "acel_max_ms2", "duracion_tramos_s", "resultado", "condiciones"]

USO = """Uso:
  python navegacion.py verificar datos/sesion_NNN
  python navegacion.py reposo    datos/sesion_NNN
  python navegacion.py caras     datos/sesion_NNN
  python navegacion.py metodos
  python navegacion.py ascensor  datos/sesion_NNN
  python navegacion.py metro     datos/sesion_NNN [datos/sesion_MMM ...]
Opciones (para cualquier comando con sesion):
  --botones      usar solo desde la primera hasta la ultima pulsacion del boton
  --recorte N    quitar N segundos al inicio y al final (despues de --botones si se usan los dos)
  --hasta T      usar la sesion solo hasta T segundos (tiempo desde la primera muestra del IMU)
  --recorridos 1,2,5   (ascensor) solo esos recorridos entran en las tablas de error; los demas se
                 siguen integrando (el ascensor si se movio)
Archivos opcionales en la carpeta de la sesion:
  eventos_corregidos.csv  se usa en vez de eventos.csv (pulsos corregidos a mano)
  paradas.csv             piso de cada parada (ascensor), en vez del piso mas cercano"""


def bmp280(adc_T, adc_P, c):
    adc_T = np.asarray(adc_T, dtype=float)
    adc_P = np.asarray(adc_P, dtype=float)
    v1 = (adc_T / 16384.0 - c["dig_T1"] / 1024.0) * c["dig_T2"]
    v2 = (adc_T / 131072.0 - c["dig_T1"] / 8192.0) ** 2 * c["dig_T3"]
    t_fine = v1 + v2
    temperatura = t_fine / 5120.0
    v1 = t_fine / 2.0 - 64000.0
    v2 = v1 * v1 * c["dig_P6"] / 32768.0
    v2 = v2 + v1 * c["dig_P5"] * 2.0
    v2 = v2 / 4.0 + c["dig_P4"] * 65536.0
    v1 = (c["dig_P3"] * v1 * v1 / 524288.0 + c["dig_P2"] * v1) / 524288.0
    v1 = (1.0 + v1 / 32768.0) * c["dig_P1"]
    p = 1048576.0 - adc_P
    p = (p - v2 / 4096.0) * 6250.0 / v1
    v1 = c["dig_P9"] * p * p / 2147483648.0
    v2 = p * c["dig_P8"] / 32768.0
    presion = p + (v1 + v2 + c["dig_P7"]) / 16.0
    return temperatura, presion


def leer_sesion(carpeta):
    with open(os.path.join(carpeta, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    imu = pd.read_csv(os.path.join(carpeta, "imu.csv"))
    baro = pd.read_csv(os.path.join(carpeta, "baro.csv"))
    # Si alguien corrigio los pulsos a mano (faltantes, dobles), se usa ese archivo; eventos.csv no se toca.
    archivo_eventos = "eventos_corregidos.csv"
    if not os.path.exists(os.path.join(carpeta, archivo_eventos)):
        archivo_eventos = "eventos.csv"
    eventos = pd.read_csv(os.path.join(carpeta, archivo_eventos))
    t0 = imu["t_us"].iloc[0]
    s = {"nombre": os.path.basename(os.path.normpath(carpeta)), "meta": meta, "archivo_eventos": archivo_eventos}
    s["seq"] = imu["seq"].to_numpy()
    s["t_us"] = imu["t_us"].to_numpy()
    s["t"] = (s["t_us"] - t0) / 1e6
    s["acc"] = imu[["ax", "ay", "az"]].to_numpy(float) / LSB_POR_G[meta["accel_rango_g"]] * G_ESTANDAR
    s["giro"] = np.radians(imu[["gx", "gy", "gz"]].to_numpy(float) / LSB_POR_DPS[meta["gyro_rango_dps"]])
    s["seq_baro"] = baro["seq"].to_numpy()
    s["t_us_baro"] = baro["t_us"].to_numpy()
    s["t_baro"] = (s["t_us_baro"] - t0) / 1e6
    s["temp"], s["presion"] = bmp280(baro["adc_T"], baro["adc_P"], meta["bmp280_calib"])
    ev = (eventos["t_us"].to_numpy() - t0) / 1e6
    if len(ev) > 1:
        ev = ev[np.concatenate([[True], np.diff(ev) > REBOTE_BOTON_S])]
    s["eventos"] = ev
    s["rebotes"] = len(eventos) - len(ev)
    # pulsos tal como salieron del firmware, para saber cuales de los corregidos son originales
    s["eventos_csv"] = (pd.read_csv(os.path.join(carpeta, "eventos.csv"))["t_us"].to_numpy() - t0) / 1e6
    if meta.get("firmware_version") == "simulador":
        print("AVISO: sesion SIMULADA (solo sirve para probar el codigo)")
    return recortar(s)


def recortar(s):
    ini, fin = s["t"][0], s["t"][-1]
    if OPCIONES["botones"] and len(s["eventos"]) >= 2:
        ini, fin = s["eventos"][0], s["eventos"][-1]
    ini, fin = ini + OPCIONES["recorte"], fin - OPCIONES["recorte"]
    if OPCIONES["hasta"] is not None:
        fin = min(fin, OPCIONES["hasta"])
    s["recorte"] = ""
    if ini > s["t"][0] or fin < s["t"][-1]:
        s["recorte"] = f"{ini:.1f}-{fin:.1f}"
        m = (s["t"] >= ini) & (s["t"] <= fin)
        mb = (s["t_baro"] >= ini) & (s["t_baro"] <= fin)
        for k in ["seq", "t_us", "t", "acc", "giro"]:
            s[k] = s[k][m]
        for k in ["seq_baro", "t_us_baro", "t_baro", "temp", "presion"]:
            s[k] = s[k][mb]
        s["eventos"] = s["eventos"][(s["eventos"] >= ini) & (s["eventos"] <= fin)]
    s["duracion"] = s["t"][-1] - s["t"][0]
    return s


def texto_recorte(s):
    if s["recorte"] == "":
        return "registro completo"
    return f"recortado: se usa de {s['recorte'].replace('-', ' a ')} s"


def texto_eventos(s):
    if s["archivo_eventos"] == "eventos.csv":
        return "pulsos del boton: eventos.csv"
    return f"pulsos del boton: {s['archivo_eventos']} (corregidos a mano; se usa EN VEZ de eventos.csv)"


def decir(r, texto):
    print(texto)
    r.append(texto)


def guardar_reporte(nombre, r):
    os.makedirs(RESULTADOS, exist_ok=True)
    with open(os.path.join(RESULTADOS, nombre), "w", encoding="utf-8") as f:
        f.write("\n".join(r) + "\n")


def guardar_figura(fig, nombre):
    os.makedirs(RESULTADOS, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTADOS, nombre), dpi=120)
    plt.close(fig)


def marcar_eventos(ax, eventos):
    for e in eventos:
        ax.axvline(e, color="gray", lw=0.6, alpha=0.5)


def agregar_bitacora(fila):
    nuevo = not os.path.exists(BITACORA)
    fila["fecha_proceso"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(BITACORA, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(COLUMNAS_BITACORA)
        w.writerow([fila.get(c, "") for c in COLUMNAS_BITACORA])


def fila_sesion(s, comando):
    simulado = s["meta"].get("firmware_version") == "simulador"
    return {"comando": comando, "sesion": s["nombre"], "firmware": s["meta"].get("firmware_version", ""),
            "duracion_s": f"{s['duracion']:.1f}", "recorte_s": s["recorte"], "condiciones": "SIMULADO" if simulado else ""}


def rectangulo(t, y):
    return np.concatenate([[0.0], np.cumsum(y[:-1] * np.diff(t))])


def trapecio(t, y):
    return np.concatenate([[0.0], np.cumsum((y[1:] + y[:-1]) / 2 * np.diff(t))])


def interpolar(x, y, xn):
    xn = np.clip(xn, x[0], x[-1])
    j = np.clip(np.searchsorted(x, xn) - 1, 0, len(x) - 2)
    return y[j] + (y[j + 1] - y[j]) * (xn - x[j]) / (x[j + 1] - x[j])


def biseccion(f, a, b, tol=1e-6):
    fa = f(a)
    while b - a > tol:
        m = (a + b) / 2
        fm = f(m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
    return (a + b) / 2


def detectar_quieto(t, acc, giro):
    n = max(1, int(round(VENTANA_QUIETO_S / np.median(np.diff(t)))))
    a = np.linalg.norm(acc, axis=1)
    w = np.linalg.norm(giro, axis=1)
    quieto = np.zeros(len(t), dtype=bool)
    for i in range(0, len(t), n):
        quieto[i:i + n] = a[i:i + n].std() < UMBRAL_ACC and w[i:i + n].std() < UMBRAL_GIRO
    return quieto


def tramos(mascara):
    d = np.diff(np.concatenate([[0], mascara.astype(int), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def mascara_movimiento(s):
    ev = s["eventos"]
    if len(ev) >= 2 and len(ev) % 2 == 0:
        mov = np.zeros(len(s["t"]), dtype=bool)
        for k in range(0, len(ev), 2):
            mov = mov | ((s["t"] >= ev[k]) & (s["t"] <= ev[k + 1]))
        return mov, f"{s['archivo_eventos']} (pares salida/llegada)"
    return ~detectar_quieto(s["t"], s["acc"], s["giro"]), f"detector de quietud ({s['archivo_eventos']} vacio o impar)"


def reposo_inicial(s):
    fin = s["t"][0] + REPOSO_INICIAL_S
    if len(s["eventos"]) > 0:
        fin = min(fin, s["eventos"][0] - 1.0)
    return s["t"] < fin


def cargar_calibracion(r):
    # Solo se usa la calibracion de una sesion real de caras. La de la sesion simulada se guarda
    # aparte (CALIBRACION_SIMULADA) y no se carga nunca, para que no pase por un resultado real.
    if not os.path.exists(CALIBRACION):
        decir(r, "AVISO: no existe resultados/calibracion.json (correr 'caras' con una sesion real); "
                 "se sigue SIN CALIBRAR: sesgo 0 y escala 1")
        return np.zeros(3), np.ones(3)
    with open(CALIBRACION, encoding="utf-8") as f:
        c = json.load(f)
    decir(r, f"Calibracion de caras usada: sesion {c['sesion']}")
    return np.array(c["sesgo"]), np.array(c["escala"])


def altura_barometrica(presion, temperatura_C, p0):
    T = np.mean(temperatura_C) + 273.15
    return R_GAS * T / (M_AIRE * G) * np.log(p0 / presion)


def altura_baro_en_imu(s, rep):
    p0 = s["presion"][s["t_baro"] <= s["t"][rep][-1]].mean()
    hb = altura_barometrica(s["presion"], s["temp"], p0)
    return hb, interpolar(s["t_baro"], hb, s["t"])


def velocidad_zupt(t, a, mov, metodo):
    v = np.zeros(len(t))
    for i0, i1 in tramos(mov):
        if i1 - i0 < 2:
            continue
        vs = metodo(t[i0:i1], a[i0:i1])
        if i1 < len(t):
            vs = vs - vs[-1] * (t[i0:i1] - t[i0]) / (t[i1 - 1] - t[i0])
        v[i0:i1] = vs
    return v


def filtro_complementario(t, a, h_baro, mov):
    k1 = 2.0 / TAU_FILTRO_S
    k2 = 1.0 / TAU_FILTRO_S ** 2
    h = np.zeros(len(t))
    v = np.zeros(len(t))
    h[0] = h_baro[0]
    for k in range(1, len(t)):
        dt = t[k] - t[k - 1]
        e = h_baro[k - 1] - h[k - 1]
        h[k] = h[k - 1] + (v[k - 1] + k1 * e) * dt
        if mov[k]:
            v[k] = v[k - 1] + (a[k - 1] + k2 * e) * dt
    return h, v


def frecuencia_en(t, seq, mascara):
    return (seq[mascara][-1] - seq[mascara][0]) / (t[mascara][-1] - t[mascara][0])


def revisar_tiempos(r, nombre, t_us, seq, nominal):
    t = (t_us - t_us[0]) / 1e6
    ventana = min(VENTANA_FRECUENCIA_S, t[-1] / 2)
    d = np.diff(seq)
    perdidas = int(np.sum(d[d > 1] - 1))
    dt = np.diff(t_us)[d == 1]
    decir(r, f"{nombre}: {len(seq)} muestras, perdidas {perdidas} ({100 * perdidas / (len(seq) + perdidas):.4f} %), "
             f"seq repetidos o hacia atras: {int(np.sum(d < 1))}, t_us siempre creciente: {bool(np.all(np.diff(t_us) > 0))}")
    decir(r, f"  frecuencia real: inicio {frecuencia_en(t, seq, t <= ventana):.3f} Hz, "
             f"final {frecuencia_en(t, seq, t >= t[-1] - ventana):.3f} Hz (nominal {nominal} Hz, ventanas de {ventana:.0f} s)")
    decir(r, f"  periodo: medio {dt.mean():.1f} us, jitter (desv. est.) {dt.std():.1f} us, minimo {dt.min()} us, maximo {dt.max()} us")
    return perdidas


def comando_verificar(carpeta):
    s = leer_sesion(carpeta)
    r = []
    m = s["meta"]
    decir(r, f"=== Verificacion de {s['nombre']} ===")
    decir(r, f"chip WHO_AM_I {m.get('chip_whoami')}, firmware {m.get('firmware_version')}, "
             f"±{m['accel_rango_g']} g, ±{m['gyro_rango_dps']} °/s, duracion {s['duracion']:.1f} s ({s['duracion'] / 60:.1f} min), {texto_recorte(s)}")
    p1 = revisar_tiempos(r, "IMU", s["t_us"], s["seq"], m.get("fs_imu_nominal_hz"))
    p2 = revisar_tiempos(r, "Barometro", s["t_us_baro"], s["seq_baro"], m.get("fs_baro_nominal_hz"))
    fs = 1 / np.median(np.diff(s["t"]))
    decir(r, f"Requisito >= 100 Hz: {'cumple' if fs >= 100 else 'NO cumple'}; "
             f"requisito 90 min sin perdidas: {'cumple' if s['duracion'] >= 5400 and p1 == 0 else 'no (registro mas corto o con perdidas)'}")
    decir(r, f"Eventos del boton ({texto_eventos(s)}): {len(s['eventos'])} en [{', '.join(f'{e:.1f}' for e in s['eventos'])}] s "
             f"(se ignoraron {s['rebotes']} pulsaciones a menos de {REBOTE_BOTON_S} s de la anterior: rebote)")
    decir(r, f"|a| medio {np.linalg.norm(s['acc'], axis=1).mean():.3f} m/s² (g Quito {G}), "
             f"giroscopio medio {np.round(np.degrees(s['giro'].mean(axis=0)), 3)} °/s, "
             f"presion media {s['presion'].mean():.1f} Pa, temperatura media {s['temp'].mean():.2f} °C")
    paso = max(1, len(s["t"]) // 20000)
    pb = max(1, len(s["t_baro"]) // 20000)
    fig, ax = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    for i, eje in enumerate("xyz"):
        ax[0].plot(s["t"][::paso], s["acc"][::paso, i], lw=0.6, label=eje)
        ax[1].plot(s["t"][::paso], np.degrees(s["giro"][::paso, i]), lw=0.6, label=eje)
    ax[2].plot(s["t_baro"][::pb], s["presion"][::pb], lw=0.6, color="k")
    ax[3].plot(s["t_baro"][::pb], s["temp"][::pb], lw=0.6, color="k")
    ax[0].set(ylabel="aceleracion (m/s²)", title=f"Senales de {s['nombre']}")
    ax[1].set(ylabel="giroscopio (°/s)")
    ax[2].set(ylabel="presion (Pa)")
    ax[3].set(ylabel="temperatura (°C)", xlabel="tiempo (s)")
    ax[0].legend(loc="upper right")
    ax[1].legend(loc="upper right")
    for a in ax:
        marcar_eventos(a, s["eventos"])
    guardar_figura(fig, f"{s['nombre']}_senales.png")
    guardar_reporte(f"{s['nombre']}_verificar.txt", r)
    fila = fila_sesion(s, "verificar")
    fila["resultado"] = f"perdidas imu={p1} baro={p2}; fs={fs:.2f} Hz"
    agregar_bitacora(fila)


def comando_reposo(carpeta):
    s = leer_sesion(carpeta)
    r = []
    decir(r, f"=== Reposo: {s['nombre']} ({s['duracion']:.1f} s = {s['duracion'] / 60:.1f} min, {texto_recorte(s)}) ===")
    q = detectar_quieto(s["t"], s["acc"], s["giro"])
    decir(r, f"Detector: quieto el {100 * q.mean():.1f} % del tiempo (ventanas de {VENTANA_QUIETO_S} s)")
    movimientos = tramos(~q)
    for i0, i1 in movimientos[:10]:
        decir(r, f"  EN MOVIMIENTO de {s['t'][i0]:.1f} s a {s['t'][i1 - 1]:.1f} s")
    if len(movimientos) > 10:
        decir(r, f"  ... y {len(movimientos) - 10} tramos mas")
    if len(movimientos) == 0:
        decir(r, "  El dispositivo no se movio en todo el registro.")
    if q.sum() < 10:
        decir(r, "No hay suficientes muestras quietas para calcular sesgo y ruido.")
        guardar_reporte(f"{s['nombre']}_reposo.txt", r)
        return
    acc = s["acc"][q]
    giro = np.degrees(s["giro"][q])
    dt = np.median(np.diff(s["t"]))
    decir(r, "eje | media acel (m/s²) | ruido acel (m/s²) | sesgo giro (°/s) | ruido giro (°/s)")
    for i, eje in enumerate("xyz"):
        decir(r, f"  {eje} | {acc[:, i].mean():9.4f} | {acc[:, i].std():8.4f} | {giro[:, i].mean():8.3f} | {giro[:, i].std():7.4f}")
    modulo = np.linalg.norm(acc, axis=1).mean()
    decir(r, f"|a| medio {modulo:.4f} m/s², g Quito {G} -> diferencia {modulo - G:+.4f} m/s² (error de escala/sesgo; se corrige con 'caras')")
    media = acc.mean(axis=0)
    decir(r, f"Inclinacion respecto al eje mas cercano (sin calibrar): {np.degrees(np.arccos(np.abs(media).max() / np.linalg.norm(media))):.1f}°")
    sa = acc.std(axis=0).mean()
    decir(r, f"Prediccion: con ruido {sa:.4f} m/s² la velocidad hace un paseo aleatorio de "
             f"{sa * np.sqrt(dt * 60):.4f} m/s en 60 s y {sa * np.sqrt(dt * 600):.4f} m/s en 10 min")
    bg = np.abs(giro.mean(axis=0)).max()
    decir(r, f"Prediccion: un sesgo de giroscopio de {bg:.3f} °/s sin restar gira el rumbo {bg * 60:.1f}° en 1 min")
    horas = (s["t_baro"] - s["t_baro"][0]) / 3600
    pendiente = np.polyfit(horas, s["presion"], 1)[0] if horas[-1] > 0 else 0.0
    decir(r, f"Presion media {s['presion'].mean():.1f} Pa (desv. {s['presion'].std():.2f} Pa), "
             f"tendencia {pendiente:+.1f} Pa/h; temperatura {s['temp'].min():.2f} a {s['temp'].max():.2f} °C")
    paso = max(1, len(s["t"]) // 20000)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(s["t"][::paso], np.linalg.norm(s["acc"], axis=1)[::paso], lw=0.6, color="k")
    ax[0].axhline(G, color="tab:blue", ls="--", label=f"g Quito = {G}")
    ax[1].plot(s["t"][::paso], np.degrees(np.linalg.norm(s["giro"], axis=1))[::paso], lw=0.6, color="k")
    for i0, i1 in movimientos:
        for a in ax:
            a.axvspan(s["t"][i0], s["t"][i1 - 1], color="tab:orange", alpha=0.3)
    ax[0].set(ylabel="|a| (m/s²)", title=f"Reposo y detector de quietud: {s['nombre']}")
    ax[1].set(ylabel="|w| (°/s)", xlabel="tiempo (s)  (naranja = en movimiento)")
    ax[0].legend()
    guardar_figura(fig, f"{s['nombre']}_reposo.png")
    deriva = deriva_por_bloques(s, q, r)
    guardar_reporte(f"{s['nombre']}_reposo.txt", r)
    fila = fila_sesion(s, "reposo")
    fila["resultado"] = f"quieto {100 * q.mean():.1f} %; ruido acel {sa:.4f} m/s²; sesgo giro {np.round(giro.mean(axis=0), 3)} °/s" + deriva
    agregar_bitacora(fila)


def deriva_por_bloques(s, q, r):
    dt = np.median(np.diff(s["t"]))
    filas = []
    for t0 in np.arange(s["t"][0], s["t"][-1], BLOQUE_DERIVA_S):
        m = q & (s["t"] >= t0) & (s["t"] < t0 + BLOQUE_DERIVA_S)
        mb = (s["t_baro"] >= t0) & (s["t_baro"] < t0 + BLOQUE_DERIVA_S)
        if m.sum() * dt < 60 or mb.sum() == 0:
            continue
        g = np.degrees(s["giro"][m].mean(axis=0))
        a = s["acc"][m].mean(axis=0)
        filas.append({"min_ini": (t0 - s["t"][0]) / 60, "min_quieto": m.sum() * dt / 60, "gx": g[0], "gy": g[1], "gz": g[2],
                      "ax": a[0], "ay": a[1], "az": a[2], "|a|": np.linalg.norm(s["acc"][m], axis=1).mean(),
                      "P_hPa": s["presion"][mb].mean() / 100, "T_C": s["temp"][mb].mean()})
    decir(r, f"--- Deriva por bloques de {BLOQUE_DERIVA_S / 60:.0f} min (solo muestras quietas; giro en °/s, acel en m/s²) ---")
    if len(filas) < 2:
        decir(r, "  Registro demasiado corto para ver deriva (hacen falta al menos 2 bloques).")
        return ""
    b = pd.DataFrame(filas)
    decir(r, b.to_string(index=False, float_format="{:.4f}".format))
    d = b.iloc[-1] - b.iloc[0]
    horas = (b["min_ini"] + b["min_quieto"] / 2).to_numpy() / 60
    dh = altura_barometrica(b["P_hPa"].iloc[-1] * 100, b["T_C"].to_numpy(), b["P_hPa"].iloc[0] * 100)
    decir(r, f"Del primer al ultimo bloque: giro {d['gx']:+.3f} {d['gy']:+.3f} {d['gz']:+.3f} °/s; acel {d['ax']:+.4f} {d['ay']:+.4f} "
             f"{d['az']:+.4f} m/s² (|a| {d['|a|']:+.4f}); presion {d['P_hPa']:+.2f} hPa (si fuera altura serian {dh:+.2f} m falsos); temperatura {d['T_C']:+.2f} °C")
    pendientes = [np.polyfit(horas, b[e], 1)[0] for e in ["gx", "gy", "gz"]]
    peor = int(np.argmax(np.abs(pendientes)))
    k = pendientes[peor] / 3600
    decir(r, f"Pendiente del sesgo del giroscopio: {np.round(pendientes, 4)} (°/s)/h. Prediccion: si solo se resta el sesgo del inicio, "
             f"el eje {'xyz'[peor]} acumula un error de rumbo ½·k·t² = {0.5 * abs(k) * 600 ** 2:.1f}° en 10 min y {0.5 * abs(k) * 5400 ** 2:.0f}° en 90 min")
    t_min = (b["min_ini"] + b["min_quieto"] / 2).to_numpy()
    paso = max(1, len(s["t_baro"]) // 5000)
    tb_min = (s["t_baro"][::paso] - s["t"][0]) / 60
    fig, ax = plt.subplots(4, 1, figsize=(9, 10), sharex=True)
    for e in "xyz":
        ax[0].plot(t_min, b["g" + e] - b["g" + e].iloc[0], "o-", label=f"g{e} (primer bloque {b['g' + e].iloc[0]:.3f} °/s)")
        ax[1].plot(t_min, b["a" + e] - b["a" + e].iloc[0], "o-", label=f"a{e} (primer bloque {b['a' + e].iloc[0]:.3f} m/s²)")
    ax[2].plot(tb_min, s["presion"][::paso] / 100, color="0.75", lw=0.5, label="medida")
    ax[2].plot(t_min, b["P_hPa"], "ko-", label="promedio del bloque")
    ax[3].plot(tb_min, s["temp"][::paso], color="0.75", lw=0.5, label="medida")
    ax[3].plot(t_min, b["T_C"], "ko-", label="promedio del bloque")
    ax[0].set(ylabel="cambio del sesgo\ndel giroscopio (°/s)", title=f"Deriva por bloques de {BLOQUE_DERIVA_S / 60:.0f} min: {s['nombre']}")
    ax[1].set(ylabel="cambio de la\naceleracion (m/s²)")
    ax[2].set(ylabel="presion (hPa)")
    ax[3].set(ylabel="temperatura (°C)", xlabel="minutos desde el inicio usado")
    for a in ax:
        a.legend(fontsize=8)
        a.grid(alpha=0.3)
    guardar_figura(fig, f"{s['nombre']}_deriva.png")
    return f"; deriva {b['min_quieto'].sum():.0f} min: gx {b['gx'].iloc[0]:.3f}->{b['gx'].iloc[-1]:.3f} °/s, P {d['P_hPa']:+.2f} hPa, T {d['T_C']:+.2f} °C"


def comando_caras(carpeta):
    s = leer_sesion(carpeta)
    r = []
    decir(r, f"=== Calibracion de seis caras: {s['nombre']} ===")
    q = detectar_quieto(s["t"], s["acc"], s["giro"])
    margen = int(MARGEN_CARA_S / np.median(np.diff(s["t"])))
    quietos = []
    for i0, i1 in tramos(q):
        if s["t"][i1 - 1] - s["t"][i0] >= QUIETO_MINIMO_S + 2 * MARGEN_CARA_S:
            quietos.append((s["t"][i0], s["t"][i1 - 1], s["acc"][i0 + margen:i1 - margen].mean(axis=0),
                            s["giro"][i0 + margen:i1 - margen].mean(axis=0)))
    caras = {}
    for k, (t0, t1, m, w) in enumerate(quietos):
        eje = int(np.argmax(np.abs(m)))
        clave = "xyz"[eje] + ("+" if m[eje] > 0 else "-")
        if t1 - t0 >= CARA_MINIMA_S + 2 * MARGEN_CARA_S and abs(m[eje]) >= 0.8 * G:
            if clave not in caras or t1 - t0 > quietos[caras[clave]][1] - quietos[caras[clave]][0]:
                caras[clave] = k
    extras = [k for k in range(len(quietos)) if k not in caras.values()]
    decir(r, f"Tramos quietos: {len(quietos)}; caras distintas {len(caras)} {sorted(caras)}; tramos extra {len(extras)}")
    faltan = [c for c in ["x+", "x-", "y+", "y-", "z+", "z-"] if c not in caras]
    fila = fila_sesion(s, "caras")
    if faltan:
        decir(r, f"FALTAN caras: {faltan}. Repetir el experimento (al menos {CARA_MINIMA_S:.0f} s quieto en cada cara).")
        if not os.path.exists(CALIBRACION):
            guardar_reporte(f"{s['nombre']}_caras.txt", r)
            return
        decir(r, "No se calibra; los tramos quietos se revisan con la calibracion guardada.")
        sesgo, escala = cargar_calibracion(r)
        extras = list(range(len(quietos)))
        fila["resultado"] = f"faltan caras {faltan}; solo revision de tramos"
    else:
        sesgo = np.zeros(3)
        escala = np.zeros(3)
        for i, e in enumerate("xyz"):
            mas = quietos[caras[e + "+"]][2][i]
            menos = quietos[caras[e + "-"]][2][i]
            sesgo[i] = (mas + menos) / 2
            escala[i] = (mas - menos) / (2 * G)
            decir(r, f"eje {e}: a+ = {mas:.4f}, a- = {menos:.4f} -> sesgo {sesgo[i]:+.4f} m/s², escala {escala[i]:.5f}")
        decir(r, "cara | inclinacion vs eje (°) | |g| antes (m/s²) | error antes | |g| despues | error despues   (despues ~9.77: se calibro con estas caras)")
        for clave in ["x+", "x-", "y+", "y-", "z+", "z-"]:
            antes = np.linalg.norm(quietos[caras[clave]][2])
            m = (quietos[caras[clave]][2] - sesgo) / escala
            despues = np.linalg.norm(m)
            inclinacion = np.degrees(np.arccos(np.abs(m).max() / despues))
            decir(r, f"  {clave} | {inclinacion:5.1f} | {antes:.4f} | {antes - G:+.4f} | {despues:.4f} | {despues - G:+.4f}")
        giro = np.degrees(np.array([quietos[k][3] for k in caras.values()]))
        decir(r, f"Sesgo del giroscopio (promedio de las caras, solo informativo): {np.round(giro.mean(axis=0), 3)} °/s; "
                 f"variacion entre caras {np.round(giro.std(axis=0), 3)} °/s")
        # Una sesion simulada no debe dejar una calibracion que parezca real: va a otra carpeta.
        simulada = s["meta"].get("firmware_version") == "simulador"
        destino = CALIBRACION_SIMULADA if simulada else CALIBRACION
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump({"sesion": s["nombre"], "g": G, "sesgo": list(sesgo), "escala": list(escala),
                       "sesgo_giro_dps_informativo": list(giro.mean(axis=0))}, f, indent=2)
        decir(r, f"Guardado en {os.path.relpath(destino, CARPETA).replace(os.sep, '/')}"
                 + (" (sesion SIMULADA: no se usa en ascensor ni metro)" if simulada else ""))
        fila["resultado"] = f"sesgo {np.round(sesgo, 4)} m/s²; escala {np.round(escala, 5)}"
    decir(r, f"--- Prueba independiente: tramos quietos que no se usaron para calibrar (minimo {QUIETO_MINIMO_S:.0f} s) ---")
    if len(extras) == 0:
        decir(r, "  No hay tramos extra. Para la prueba, dejar el dispositivo quieto en algunas posiciones inclinadas.")
    else:
        decir(r, "tramo | t (s) | inclinacion vs eje mas cercano (°) | |g| antes (m/s²) | error antes | |g| calibrado | error calibrado")
        antes = np.array([np.linalg.norm(quietos[k][2]) for k in extras])
        despues = np.array([np.linalg.norm((quietos[k][2] - sesgo) / escala) for k in extras])
        for j, k in enumerate(extras):
            m = (quietos[k][2] - sesgo) / escala
            inclinacion = np.degrees(np.arccos(np.abs(m).max() / np.linalg.norm(m)))
            decir(r, f"  {j:2d} | {quietos[k][0]:7.1f}-{quietos[k][1]:7.1f} | {inclinacion:5.1f} | "
                     f"{antes[j]:.4f} | {antes[j] - G:+.4f} | {despues[j]:.4f} | {despues[j] - G:+.4f}")
        decir(r, f"Variacion de |g| entre tramos (desv. est.): antes {antes.std():.4f} m/s², calibrado {despues.std():.4f} m/s²; "
                 f"error maximo calibrado {np.abs(despues - G).max():.4f} m/s²")
        fila["resultado"] += f"; {len(extras)} tramos extra, error max |g| calibrado {np.abs(despues - G).max():.4f} m/s²"
    # Figura: |g| antes y despues de calibrar en cada tramo quieto (caras y extras), en orden de tiempo.
    nombres = {k: f"extra {j}" for j, k in enumerate(extras)}
    if not faltan:
        nombres.update({k: f"cara {c}" for c, k in caras.items()})
    x = np.arange(len(quietos))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x, [np.linalg.norm(q_[2]) for q_ in quietos], "o", color="tab:red", label="antes de calibrar")
    ax.plot(x, [np.linalg.norm((q_[2] - sesgo) / escala) for q_ in quietos], "s", color="tab:green", label="calibrado")
    ax.axhline(G, color="k", ls="--", lw=1, label=f"g Quito = {G}")
    ax.set_xticks(x, [nombres[k] for k in x], rotation=45)
    ax.set(ylabel="|g| (m/s²)", title=f"|g| en cada tramo quieto: {s['nombre']}")
    ax.grid(alpha=0.3)
    ax.legend()
    guardar_figura(fig, f"{s['nombre']}_caras.png")
    guardar_reporte(f"{s['nombre']}_caras.txt", r)
    agregar_bitacora(fila)


def polinomio_prueba(x):
    return x ** 3 - 2 * x - 5


def comando_metodos():
    r = []
    decir(r, "=== Pruebas de los metodos numericos ===")
    T, P = bmp280([519888], [415148], BMP280_EJEMPLO)
    ok = abs(T[0] - 25.08) < 0.005 and abs(P[0] - 100653.27) < 0.01
    decir(r, f"BMP280, ejemplo de la hoja de datos: T = {T[0]:.4f} °C (esperado ~25.08), "
             f"P = {P[0]:.4f} Pa (esperado ~100653.27) -> {'OK' if ok else 'FALLA'}")
    A, w, dur = 0.5, 2 * np.pi * 0.15, 30.0
    decir(r, f"Senal de prueba: a(t) = {A} sin(w t), w = 2pi*0.15 rad/s, {dur:.0f} s. "
             "Exactas: v = A/w (1 - cos wt), x = A/w (t - sin(wt)/w)")
    x_exacta = A / w * (dur - np.sin(w * dur) / w)
    decir(r, "fs (Hz) | dt (s) | error x rectangulo (m) | error x trapecio (m)")
    pasos, e_rect, e_trap = [], [], []
    for fs in [25, 50, 100, 200, 400, 800]:
        t = np.arange(0, dur + 1e-9, 1 / fs)
        a = A * np.sin(w * t)
        e_rect.append(abs(rectangulo(t, rectangulo(t, a))[-1] - x_exacta))
        e_trap.append(abs(trapecio(t, trapecio(t, a))[-1] - x_exacta))
        pasos.append(1 / fs)
        decir(r, f"  {fs:4d} | {1 / fs:.5f} | {e_rect[-1]:.3e} | {e_trap[-1]:.3e}")
    orden_r = np.log(e_rect[-2] / e_rect[-1]) / np.log(2)
    orden_t = np.log(e_trap[-2] / e_trap[-1]) / np.log(2)
    decir(r, f"Orden observado (al dividir dt a la mitad): rectangulo {orden_r:.2f} (teoria 1), trapecio {orden_t:.2f} (teoria 2)")
    t = np.arange(0, dur + 1e-9, 1 / 200)
    a = A * np.sin(w * t)
    decir(r, f"Trapecio propio vs np.trapezoid: diferencia {abs(trapecio(t, a)[-1] - np.trapezoid(a, t)):.2e} m/s")
    tb = np.arange(0, 10 + 1e-9, 1 / 25)
    ti = np.arange(0, 10, 1 / 200)
    yi = interpolar(tb, np.sin(np.pi * tb), ti)
    decir(r, f"Interpolacion lineal de sin(pi t) muestreado a 25 Hz llevado a 200 Hz: error maximo "
             f"{np.abs(yi - np.sin(np.pi * ti)).max():.2e} (cota h²/8·max|f''| = {(1 / 25) ** 2 / 8 * np.pi ** 2:.2e}), "
             f"diferencia con np.interp {np.abs(yi - np.interp(ti, tb, np.sin(np.pi * tb))).max():.1e}")
    raiz = biseccion(polinomio_prueba, 2, 3, 1e-10)
    raiz_np = np.roots([1, 0, -2, -5])
    raiz_np = raiz_np[np.abs(raiz_np.imag) < 1e-12].real[0]
    decir(r, f"Biseccion de x³ - 2x - 5 en [2, 3]: {raiz:.10f}; np.roots: {raiz_np:.10f}; "
             f"diferencia {abs(raiz - raiz_np):.1e}; iteraciones para tol 1e-10: {int(np.ceil(np.log2(1 / 1e-10)))}")
    decir(r, f"--- Error del metodo vs error del sensor (fs 200 Hz, {dur:.0f} s, sesgo {PRUEBA_SESGO} m/s², ruido {PRUEBA_RUIDO} m/s²) ---")
    gen = np.random.default_rng(1)
    dt = 1 / 200
    e_met = trapecio(t, trapecio(t, a))[-1] - x_exacta
    e_sesgo = trapecio(t, trapecio(t, a + PRUEBA_SESGO))[-1] - x_exacta
    finales = []
    for k in range(200):
        ruido = gen.normal(0, PRUEBA_RUIDO, len(t))
        finales.append(trapecio(t, trapecio(t, a + ruido))[-1] - x_exacta)
    e_ruido = np.std(finales)
    decir(r, f"  solo metodo (senal exacta): {e_met:.2e} m")
    decir(r, f"  con sesgo: {e_sesgo:.3f} m; prediccion ½·b·t² = {0.5 * PRUEBA_SESGO * dur ** 2:.3f} m -> el sensor aporta {e_sesgo - e_met:.3f} m")
    decir(r, f"  con ruido (200 repeticiones): desv. est. {e_ruido:.4f} m; prediccion ruido·raiz(dt)·t^1.5/raiz(3) = "
             f"{PRUEBA_RUIDO * np.sqrt(dt) * dur ** 1.5 / np.sqrt(3):.4f} m")
    decir(r, f"  Conclusion: el error del metodo es ~{abs(e_sesgo / e_met):.0e} veces menor que el del sesgo del sensor.")
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.loglog(pasos, e_rect, "o-", label="rectangulo")
    ax.loglog(pasos, e_trap, "s-", label="trapecio")
    ax.set(xlabel="paso dt (s)", ylabel="error en x al final (m)", title="Convergencia de la integracion doble")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    guardar_figura(fig, "metodos_convergencia.png")
    guardar_reporte("metodos.txt", r)
    agregar_bitacora({"comando": "metodos", "sesion": "-", "resultado": f"bmp280 {'OK' if ok else 'FALLA'}; "
                      f"orden rect {orden_r:.2f}, trap {orden_t:.2f}"})


def leer_pisos():
    # {numero de piso: altura en m}
    pisos = pd.read_csv(PISOS).dropna(subset=["altura_m"])
    return dict(zip(pisos["piso"].astype(int), pisos["altura_m"].astype(float)))


def leer_paradas(carpeta, n_paradas, r):
    # paradas.csv: una fila por parada (la primera es el reposo inicial) con el piso donde estaba.
    archivo = os.path.join(carpeta, "paradas.csv")
    if not os.path.exists(archivo):
        return None
    pisos = pd.read_csv(archivo)["piso"].astype(int).tolist()
    if len(pisos) != n_paradas:
        decir(r, f"AVISO: paradas.csv tiene {len(pisos)} paradas pero se detectaron {n_paradas}; no se usa")
        return None
    return pisos


def pulsos_originales(s, k):
    # True si los dos pulsos del recorrido k (1, 2, ...) estan en eventos.csv (no se inventaron ni movieron)
    par = s["eventos"][2 * (k - 1):2 * k]
    return all(np.min(np.abs(s["eventos_csv"] - e)) < TOLERANCIA_PULSO_S for e in par)


def resumen_desnivel(r, titulo, ks, desnivel, real):
    # error del desnivel (llegada - salida) de cada metodo, solo en los recorridos ks
    decir(r, f"{titulo}: recorridos {', '.join(map(str, ks)) if ks else 'ninguno'}")
    if not ks:
        return {}
    idx = np.array(ks) - 1
    decir(r, "  metodo                       | error medio (m) | error RMS (m) | error max (m)")
    rms = {}
    for m in desnivel:
        e = desnivel[m][idx] - real[idx]
        rms[m] = np.sqrt(np.mean(e ** 2))
        decir(r, f"  {m:28s} | {e.mean():+9.3f} | {rms[m]:9.3f} | {np.abs(e).max():9.3f}")
    return rms


def comando_ascensor(carpeta):
    s = leer_sesion(carpeta)
    r = []
    decir(r, f"=== Ascensor: {s['nombre']} ({s['duracion']:.1f} s, {texto_recorte(s)}) ===")
    sesgo, escala = cargar_calibracion(r)
    t = s["t"]
    acc = (s["acc"] - sesgo) / escala
    rep = reposo_inicial(s)
    g_vec = acc[rep].mean(axis=0)
    arriba = g_vec / np.linalg.norm(g_vec)
    a_bruta = acc @ arriba - G
    b = a_bruta[rep].mean()
    a_corr = a_bruta - b
    ruido = a_corr[rep].std()
    decir(r, f"Reposo inicial: de {t[rep][0]:.1f} a {t[rep][-1]:.1f} s; |g| medido {np.linalg.norm(g_vec):.4f} m/s²; inclinacion "
             f"{np.degrees(np.arccos(arriba[2])):.2f}°; sesgo vertical b = {b:+.4f} m/s²; ruido {ruido:.4f} m/s²")
    mov, fuente = mascara_movimiento(s)
    decir(r, texto_eventos(s))
    decir(r, f"Paradas (ZUPT) segun {fuente}")
    hb, hb_imu = altura_baro_en_imu(s, rep)
    v_zupt = velocidad_zupt(t, a_corr, mov, trapecio)
    h_f, v_f = filtro_complementario(t, a_corr, hb_imu, mov)
    est = {"rectangulo sin correccion": rectangulo(t, rectangulo(t, a_bruta)),
           "trapecio sin correccion": trapecio(t, trapecio(t, a_bruta)),
           "trapecio - sesgo": trapecio(t, trapecio(t, a_corr)),
           "rectangulo - sesgo + ZUPT": rectangulo(t, velocidad_zupt(t, a_corr, mov, rectangulo)),
           "trapecio - sesgo + ZUPT": trapecio(t, v_zupt),
           "solo barometro": hb_imu,
           "fusion acel+baro + ZUPT": h_f}
    paradas = tramos(~mov)
    h_paradas = {k: np.array([h[i0:i1].mean() for i0, i1 in paradas]) for k, h in est.items()}
    alturas = leer_pisos()
    pisos = np.sort(list(alturas.values()))
    piso_de_parada = leer_paradas(carpeta, len(paradas), r) if len(pisos) > 0 else None
    if piso_de_parada is not None:
        ref = np.array([alturas[p] for p in piso_de_parada])
        niveles = pisos
        nombre_ref = "piso de cada parada (paradas.csv), altura de pisos.csv"
    elif len(pisos) > 0:
        ref = np.array([pisos[np.argmin(np.abs(pisos - h))] for h in h_paradas["fusion acel+baro + ZUPT"]])
        niveles = pisos
        nombre_ref = "piso real mas cercano (pisos.csv)"
    else:
        ref = h_paradas["solo barometro"]
        niveles, grupo = [], []
        for h in np.sort(h_paradas["fusion acel+baro + ZUPT"]):
            if grupo and h - grupo[-1] > 1.0:
                niveles.append(np.mean(grupo))
                grupo = []
            grupo.append(h)
        niveles.append(np.mean(grupo))
        nombre_ref = "barometro (pisos.csv vacio: NO es error real, es acuerdo acelerometro-barometro)"
    decir(r, f"Referencia en cada parada: {nombre_ref}")
    n_rec = len(paradas) - 1
    evaluar = list(range(1, n_rec + 1)) if OPCIONES["recorridos"] is None else [k for k in OPCIONES["recorridos"] if 1 <= k <= n_rec]
    if piso_de_parada is None:
        decir(r, "metodo | error RMS en paradas (m) | error max (m) | altura final (m)")
        errores = {}
        for k in est:
            e = h_paradas[k] - ref
            errores[k] = e
            decir(r, f"  {k:28s} | {np.sqrt(np.mean(e ** 2)):10.3f} | {np.abs(e).max():10.3f} | {est[k][-1]:9.3f}")
        resultado = f"RMS fusion {np.sqrt(np.mean(errores['fusion acel+baro + ZUPT'] ** 2)):.3f} m vs {nombre_ref.split(' (')[0]}"
    decir(r, "Altura absoluta en cada parada" + (" (solo informativa: la evaluacion es por desnivel, abajo)" if piso_de_parada else ""))
    decir(r, "parada | piso | t (s) | baro (m) | trapecio+ZUPT (m) | fusion (m) | referencia (m) | fusion - ref (m)")
    for j, (i0, i1) in enumerate(paradas):
        piso = "-" if piso_de_parada is None else piso_de_parada[j]
        decir(r, f"  {j:2d} | {piso} | {t[i0]:7.1f} | {h_paradas['solo barometro'][j]:7.2f} | {h_paradas['trapecio - sesgo + ZUPT'][j]:7.2f} | "
                 f"{h_paradas['fusion acel+baro + ZUPT'][j]:7.2f} | {ref[j]:7.2f} | {h_paradas['fusion acel+baro + ZUPT'][j] - ref[j]:+.3f}")
    if piso_de_parada is not None:
        # Evaluacion por DESNIVEL de cada recorrido (llegada - salida): no depende de la altura
        # absoluta de cada piso, solo de la distancia entre los dos pisos del recorrido.
        desnivel = {m: np.diff(h_paradas[m]) for m in est}
        real = np.diff(ref)
        toca_pb = {k: 0 in piso_de_parada[k - 1:k + 1] for k in range(1, n_rec + 1)}
        original = {k: pulsos_originales(s, k) for k in range(1, n_rec + 1)}
        decir(r, f"Recorridos evaluados: {', '.join(map(str, evaluar))}"
                 + ("" if OPCIONES["recorridos"] is None else " (--recorridos; los demas se integran pero no entran en los errores)"))
        decir(r, "Desnivel de cada recorrido (m). Evaluado: entra en los errores. PB: toca la planta baja. "
                 f"Orig.: sus dos pulsos estan en eventos.csv (a menos de {TOLERANCIA_PULSO_S} s)")
        decir(r, "rec | pisos | evaluado | PB | orig. | real | baro | trapecio+ZUPT | rectangulo+ZUPT | fusion | baro - trap")
        for k in range(1, n_rec + 1):
            d = {m: desnivel[m][k - 1] for m in est}
            decir(r, f"  {k:2d} | {piso_de_parada[k - 1]}->{piso_de_parada[k]} | {'si' if k in evaluar else 'NO'} | "
                     f"{'si' if toca_pb[k] else 'no'} | {'si' if original[k] else 'no'} | {real[k - 1]:6.2f} | {d['solo barometro']:6.2f} | "
                     f"{d['trapecio - sesgo + ZUPT']:6.2f} | {d['rectangulo - sesgo + ZUPT']:6.2f} | {d['fusion acel+baro + ZUPT']:6.2f} | "
                     f"{d['solo barometro'] - d['trapecio - sesgo + ZUPT']:+.2f}")
        sin_pb = [k for k in evaluar if not toca_pb[k]]
        con_pb = [k for k in evaluar if toca_pb[k]]
        decir(r, "Error del desnivel (metodo - cinta):")
        rms_principal = resumen_desnivel(r, "VALIDACION PRINCIPAL, sin pasar por PB", sin_pb, desnivel, real)
        resumen_desnivel(r, "Recorridos que tocan PB (incluyen la altura PB->1 de la cinta)", con_pb, desnivel, real)
        resumen_desnivel(r, "Todos los evaluados", evaluar, desnivel, real)
        if s["archivo_eventos"] != "eventos.csv":
            orig = [k for k in evaluar if original[k]]
            decir(r, "Validacion extra: lo mismo solo con los recorridos de pulsos 100 % originales "
                     "(si sale parecido, las correcciones de pulsos no sesgaron el resultado)")
            resumen_desnivel(r, "  originales sin pasar por PB", [k for k in orig if not toca_pb[k]], desnivel, real)
            resumen_desnivel(r, "  originales que tocan PB", [k for k in orig if toca_pb[k]], desnivel, real)
            resumen_desnivel(r, "  todos los originales", orig, desnivel, real)
        if 1 in alturas and con_pb:
            # Cada recorrido con PB da una estimacion de la altura PB->1: |desnivel medido| menos la
            # distancia (de la cinta) entre el piso 1 y el otro piso del recorrido.
            decir(r, f"Altura PB->1 que implica cada recorrido con PB (cinta: {alturas[1] - alturas[0]:.2f} m):")
            decir(r, "rec | pisos | baro | trapecio+ZUPT | rectangulo+ZUPT | fusion")
            est_pb1 = {m: [] for m in ["solo barometro", "trapecio - sesgo + ZUPT", "rectangulo - sesgo + ZUPT", "fusion acel+baro + ZUPT"]}
            for k in con_pb:
                otro = max(piso_de_parada[k - 1:k + 1])
                for m in est_pb1:
                    est_pb1[m].append(abs(desnivel[m][k - 1]) - (alturas[otro] - alturas[1]))
                decir(r, f"  {k:2d} | {piso_de_parada[k - 1]}->{piso_de_parada[k]} | " + " | ".join(f"{est_pb1[m][-1]:5.2f}" for m in est_pb1))
            decir(r, "  media    | " + " | ".join(f"{np.mean(v):5.2f}" for v in est_pb1.values())
                     + " ; desv. est. | " + " | ".join(f"{np.std(v, ddof=1) if len(v) > 1 else 0:5.2f}" for v in est_pb1.values()))
        resultado = (f"desnivel sin PB (rec {','.join(map(str, sin_pb))}): RMS trapecio+ZUPT "
                     f"{rms_principal.get('trapecio - sesgo + ZUPT', np.nan):.3f} m, fusion {rms_principal.get('fusion acel+baro + ZUPT', np.nan):.3f} m")
    cruces = []
    for k, (i0, i1) in enumerate(tramos(mov)):
        if piso_de_parada is not None:
            # se sabe de que piso a que piso fue: solo se buscan los pisos que quedan en medio
            bajo, alto = sorted(piso_de_parada[k:k + 2])
            buscar = [(p, alturas[p]) for p in sorted(alturas) if bajo < p < alto]
        else:
            buscar = [(None, n) for n in niveles if min(abs(h_f[i0] - n), abs(h_f[i1 - 1] - n)) > 0.5]
        for piso, nivel in buscar:
            if (h_f[i0] - nivel) * (h_f[i1 - 1] - nivel) < 0:
                def altura_menos_nivel(tt):
                    return interpolar(t, h_f, np.array([tt]))[0] - nivel
                cruces.append((biseccion(altura_menos_nivel, t[i0], t[i1 - 1]), nivel, piso, k + 1))
    decir(r, f"Cruces de pisos intermedios por biseccion (fusion; la llegada la marca {s['archivo_eventos']}): {len(cruces)}")
    for tc, nivel, piso, k in sorted(cruces):
        decir(r, f"  recorrido {k:2d}: t = {tc:8.3f} s cruza {nivel:6.2f} m" + ("" if piso is None else f" (piso {piso})"))
    t_fin = s["duracion"]
    obs_sin = abs(est["trapecio sin correccion"][-1] - h_f[-1])
    obs_con = abs(est["trapecio - sesgo"][-1] - h_f[-1])
    dt = np.median(np.diff(t))
    decir(r, "Prediccion del error al final (contra la fusion como mejor estimacion):")
    decir(r, f"  sin restar sesgo: predicho ½·b·t² = {0.5 * abs(b) * t_fin ** 2:.2f} m (más el ruido, ver abajo), observado {obs_sin:.2f} m")
    decir(r, f"  restando sesgo (queda el ruido): predicho ruido·raiz(dt)·t^1.5/raiz(3) = "
             f"{ruido * np.sqrt(dt) * t_fin ** 1.5 / np.sqrt(3):.2f} m, observado {obs_con:.2f} m "
             "(si es mucho mayor, el sesgo cambio durante el registro)")
    fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    ax[0].plot(t, hb_imu, color="0.6", lw=0.6, label="barometro")
    ax[0].plot(t, est["trapecio - sesgo + ZUPT"], lw=1.2, label="trapecio - sesgo + ZUPT (sin baro)")
    ax[0].plot(t, h_f, lw=1.2, label="fusion acel+baro")
    for nivel in niveles:
        ax[0].axhline(nivel, color="k", ls=":", lw=0.6)
    if cruces:
        ax[0].plot([c[0] for c in cruces], [c[1] for c in cruces], "k.", ms=8, label="cruces (biseccion)")
    ax[0].set(ylabel="altura (m)", title=f"Ascensor {s['nombre']} (punteado: {'pisos reales' if len(pisos) else 'niveles de las paradas'})")
    ax[1].plot(t, trapecio(t, a_corr), lw=0.8, label="trapecio - sesgo, sin ZUPT")
    ax[1].plot(t, v_zupt, lw=1.0, label="trapecio - sesgo + ZUPT")
    ax[1].plot(t, v_f, lw=1.0, label="fusion acel+baro")
    ax[1].set(xlabel="tiempo (s)", ylabel="velocidad vertical (m/s)")
    for k, (i0, i1) in enumerate(tramos(mov)):
        # numero de cada recorrido arriba; los que no se evaluan, en rojo y sombreados
        fuera = k + 1 not in evaluar
        ax[0].text((t[i0] + t[i1 - 1]) / 2, 0.99, str(k + 1), transform=ax[0].get_xaxis_transform(),
                   ha="center", va="top", fontsize=9, color="red" if fuera else "k")
        if fuera:
            for a in ax:
                a.axvspan(t[i0], t[i1 - 1], color="red", alpha=0.08, lw=0)
    for a, lugar in zip(ax, ["lower right", "upper right"]):
        marcar_eventos(a, s["eventos"])
        a.legend(loc=lugar, fontsize=8)
    guardar_figura(fig, f"{s['nombre']}_ascensor.png")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogy(t[1:], np.abs(est["trapecio sin correccion"] - h_f)[1:], lw=0.8, label="observado sin restar sesgo")
    te = t[1:] - t[0]
    ax.semilogy(t[1:], 0.5 * abs(b) * te ** 2, "--", label="predicho ½·b·t²")
    ax.semilogy(t[1:], np.abs(est["trapecio - sesgo"] - h_f)[1:], lw=0.8, label="observado restando sesgo")
    ax.semilogy(t[1:], ruido * np.sqrt(dt) * te ** 1.5 / np.sqrt(3), "--", label="predicho por ruido")
    ax.set(xlabel="tiempo (s)", ylabel="error de altura (m)", title="Error predicho vs observado")
    ax.legend(fontsize=8)
    guardar_figura(fig, f"{s['nombre']}_ascensor_error.png")
    guardar_reporte(f"{s['nombre']}_ascensor.txt", r)
    fila = fila_sesion(s, "ascensor")
    duraciones = [t[i1 - 1] - t[i0] for i0, i1 in tramos(mov)]
    fila.update({"desplazamiento_m": f"{h_f.max() - h_f.min():.2f}", "vel_max_ms": f"{np.abs(v_f).max():.2f}",
                 "acel_max_ms2": f"{np.abs(a_corr[mov]).max():.2f}",
                 "duracion_tramos_s": ";".join(f"{d:.1f}" for d in duraciones), "resultado": resultado})
    agregar_bitacora(fila)


def referencia_viaje(nombre):
    estaciones = pd.read_csv(ESTACIONES)
    if len(estaciones) == 0 or not os.path.exists(VIAJES):
        return None
    viajes = pd.read_csv(VIAJES)
    fila = viajes[viajes["sesion"] == nombre]
    if len(fila) == 0:
        return None
    estaciones = estaciones.sort_values("orden").reset_index(drop=True)
    sentido = int(fila["sentido"].iloc[0])
    i = int(np.where(estaciones["estacion"] == fila["estacion_inicial"].iloc[0])[0][0])
    orden = list(range(i, len(estaciones))) if sentido > 0 else list(range(i, -1, -1))
    ref = estaciones.iloc[orden].reset_index(drop=True)
    largos = []
    for k in range(len(ref) - 1):
        largos.append(ref["distancia_al_siguiente_m"].iloc[k] if sentido > 0 else ref["distancia_al_siguiente_m"].iloc[k + 1])
    ref["largo_tramo"] = largos + [np.nan]
    return ref


def analizar_viaje(carpeta, sesgo, escala, r):
    s = leer_sesion(carpeta)
    t = s["t"]
    decir(r, f"--- Viaje {s['nombre']} ({s['duracion']:.1f} s, {texto_recorte(s)}) ---")
    acc = (s["acc"] - sesgo) / escala
    rep = reposo_inicial(s)
    g_vec = acc[rep].mean(axis=0)
    arriba = g_vec / np.linalg.norm(g_vec)
    sesgo_giro = s["giro"][rep].mean(axis=0)
    decir(r, f"Sesgo del giroscopio medido en el reposo inicial ({t[rep][0]:.1f} a {t[rep][-1]:.1f} s): {np.round(np.degrees(sesgo_giro), 3)} °/s (se resta)")
    rumbo = trapecio(t, (s["giro"] - sesgo_giro) @ arriba)
    mov, fuente = mascara_movimiento(s)
    decir(r, f"Paradas (ZUPT) segun {fuente}")
    viajes = tramos(mov)
    i0 = viajes[0][0]
    d = acc[(t >= t[i0]) & (t <= t[i0] + VENTANA_ARRANQUE_S)].mean(axis=0) - g_vec
    d = d - (d @ arriba) * arriba
    adelante = d / np.linalg.norm(d)
    decir(r, f"Direccion 'adelante' (primer arranque) en ejes del dispositivo: {np.round(adelante, 3)}")
    a_adelante = (acc - g_vec) @ adelante
    v_sin_zupt = trapecio(t, a_adelante)
    v = velocidad_zupt(t, a_adelante, mov, trapecio)
    hb, hb_imu = altura_baro_en_imu(s, rep)
    n = max(1, int(SUAVIZADO_BARO_S / np.median(np.diff(t))))
    h_suave = np.convolve(hb_imu, np.ones(n) / n, mode="same")
    dhdt = np.gradient(h_suave, t)
    seno = np.clip(np.where(v > VELOCIDAD_MIN_PENDIENTE, dhdt / np.maximum(v, VELOCIDAD_MIN_PENDIENTE), 0), -SENO_MAX, SENO_MAX)
    v_baro = velocidad_zupt(t, a_adelante - G * seno, mov, trapecio)
    dist = trapecio(t, v)
    dist_baro = trapecio(t, v_baro)
    filas = []
    for k, (j0, j1) in enumerate(viajes):
        dur = t[j1 - 1] - t[j0]
        filas.append({"tramo": k, "duracion": dur, "dist": dist[j1 - 1] - dist[j0], "dist_baro": dist_baro[j1 - 1] - dist_baro[j0],
                      "v_max": v_baro[j0:j1].max(), "a_max": np.abs(a_adelante[j0:j1]).max(), "subida": hb_imu[j1 - 1] - hb_imu[j0]})
    tabla = pd.DataFrame(filas)
    tabla["v_media"] = tabla["dist_baro"] / tabla["duracion"]
    ref = referencia_viaje(s["nombre"])
    factor = 1.0
    if ref is not None and len(ref) > len(tabla) and ref["largo_tramo"].iloc[:len(tabla)].notna().all():
        tabla["estacion"] = [f"{ref['estacion'].iloc[k]} -> {ref['estacion'].iloc[k + 1]}" for k in range(len(tabla))]
        tabla["par"] = [" / ".join(sorted([ref["estacion"].iloc[k], ref["estacion"].iloc[k + 1]])) for k in range(len(tabla))]
        tabla["real"] = ref["largo_tramo"].iloc[:len(tabla)].to_numpy(float)
        tabla["error_sin_baro"] = tabla["dist"] - tabla["real"]
        tabla["error_con_baro"] = tabla["dist_baro"] - tabla["real"]
        factor = np.sum(tabla["dist_baro"] * tabla["real"]) / np.sum(tabla["dist_baro"] ** 2)
        tabla["error_ajustado"] = tabla["dist_baro"] * factor - tabla["real"]
        decir(r, f"Ajuste por distancia conocida: factor de escala {factor:.4f} (minimos cuadrados con todos los tramos)")
    else:
        decir(r, "Sin referencia (estaciones.csv / viajes.csv vacios para esta sesion): no se calcula error de distancia")
    decir(r, tabla.drop(columns="par", errors="ignore").round(2).to_string(index=False))
    decir(r, f"Distancia total: {dist[-1]:.1f} m sin baro, {dist_baro[-1]:.1f} m con baro; sin ZUPT la velocidad final queda en {v_sin_zupt[-1]:.2f} m/s")
    v_mapa = v_baro * factor
    x = trapecio(t, v_mapa * np.cos(rumbo))
    y = trapecio(t, v_mapa * np.sin(rumbo))
    xy_real = None
    if ref is not None and ref["lat"].notna().sum() > len(tabla):
        lat0, lon0 = np.radians(ref["lat"].iloc[0]), np.radians(ref["lon"].iloc[0])
        xr = RADIO_TIERRA * (np.radians(ref["lon"].to_numpy(float)) - lon0) * np.cos(lat0)
        yr = RADIO_TIERRA * (np.radians(ref["lat"].to_numpy(float)) - lat0)
        fin1 = viajes[0][1] - 1
        giro = np.arctan2(yr[1], xr[1]) - np.arctan2(y[fin1], x[fin1])
        x, y = x * np.cos(giro) - y * np.sin(giro), x * np.sin(giro) + y * np.cos(giro)
        xy_real = (xr, yr)
        errores = [np.hypot(x[j1 - 1] - xr[k + 1], y[j1 - 1] - yr[k + 1]) for k, (j0, j1) in enumerate(viajes)]
        decir(r, "Error de posicion en cada estacion de llegada (m), alineando el primer tramo: " + ", ".join(f"{e:.1f}" for e in errores))
    fila = fila_sesion(s, "metro")
    fila.update({"desplazamiento_m": f"{dist_baro[-1]:.1f}", "vel_max_ms": f"{v_baro.max():.2f}",
                 "acel_max_ms2": f"{np.abs(a_adelante[mov]).max():.2f}",
                 "duracion_tramos_s": ";".join(f"{d:.1f}" for d in tabla["duracion"]),
                 "resultado": f"{len(tabla)} tramos; giro total {np.degrees(rumbo[-1]):.1f}°"})
    agregar_bitacora(fila)
    return {"s": s, "t": t, "v": v, "v_baro": v_baro, "rumbo": rumbo, "x": x, "y": y, "tabla": tabla, "real": xy_real}


def comando_metro(carpetas):
    r = []
    decir(r, "=== Metro ===")
    sesgo, escala = cargar_calibracion(r)
    viajes = [analizar_viaje(c, sesgo, escala, r) for c in carpetas]
    if len(viajes) > 1:
        decir(r, "--- Dispersion de la distancia de cada tramo entre viajes (con barometro) ---")
        todas = pd.concat([v["tabla"] for v in viajes])
        if all("par" in v["tabla"] for v in viajes):
            clave = todas["par"]
        else:
            clave = "tramo " + todas["tramo"].astype(str)
            decir(r, "AVISO: sin viajes.csv los tramos se emparejan por numero; vale solo si todos los viajes van en el mismo sentido y desde la misma estacion")
        resumen = todas.groupby(clave)[["dist", "dist_baro"]].agg(["count", "mean", "std"])
        decir(r, resumen.round(2).to_string())
    fig, ax = plt.subplots(len(viajes), 2, figsize=(12, 3.2 * len(viajes)), squeeze=False)
    for k, v in enumerate(viajes):
        ax[k, 0].plot(v["t"], v["v"], lw=0.8, label="ZUPT sin baro")
        ax[k, 0].plot(v["t"], v["v_baro"], lw=0.8, label="ZUPT + pendiente con baro")
        marcar_eventos(ax[k, 0], v["s"]["eventos"])
        ax[k, 0].set(xlabel="tiempo (s)", ylabel="velocidad (m/s)", title=v["s"]["nombre"])
        ax[k, 0].legend(fontsize=8)
        ax[k, 1].plot(v["t"], np.degrees(v["rumbo"]), lw=0.8, color="k")
        marcar_eventos(ax[k, 1], v["s"]["eventos"])
        ax[k, 1].set(xlabel="tiempo (s)", ylabel="rumbo girado (°)")
    guardar_figura(fig, "metro_velocidad_rumbo.png")
    fig, ax = plt.subplots(figsize=(8, 7))
    for v in viajes:
        ax.plot(v["x"], v["y"], lw=1.2, label=v["s"]["nombre"])
    reales = [v["real"] for v in viajes if v["real"] is not None]
    if reales:
        ax.plot(reales[0][0], reales[0][1], "ks--", lw=0.8, label="estaciones reales")
    ax.set(xlabel="x (m)" if reales else "x (m), eje = direccion inicial", ylabel="y (m)",
           title="Trayectoria 2D estimada" + ("" if reales else " (sin coordenadas reales)"))
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(fontsize=8)
    guardar_figura(fig, "metro_trayectoria.png")
    guardar_reporte("metro.txt", r)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if "--botones" in args:
        OPCIONES["botones"] = True
        args.remove("--botones")
    if "--recorte" in args:
        i = args.index("--recorte")
        OPCIONES["recorte"] = float(args[i + 1])
        del args[i:i + 2]
    if "--hasta" in args:
        i = args.index("--hasta")
        OPCIONES["hasta"] = float(args[i + 1])
        del args[i:i + 2]
    if "--recorridos" in args:
        i = args.index("--recorridos")
        OPCIONES["recorridos"] = [int(k) for k in args[i + 1].split(",")]
        del args[i:i + 2]
    comandos = {"verificar": comando_verificar, "reposo": comando_reposo, "caras": comando_caras, "ascensor": comando_ascensor}
    if len(args) == 1 and args[0] == "metodos":
        comando_metodos()
    elif len(args) == 2 and args[0] in comandos:
        comandos[args[0]](args[1])
    elif len(args) >= 2 and args[0] == "metro":
        comando_metro(args[1:])
    else:
        print(USO)


if __name__ == "__main__":
    main()
