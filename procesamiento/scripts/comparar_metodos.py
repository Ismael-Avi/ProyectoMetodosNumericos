"""Compara los métodos numéricos hechos a mano con problemas de solución conocida.

Uso (desde la carpeta procesamiento/):

    python -m scripts.comparar_metodos

No usa datos del sensor: todas las señales son funciones matemáticas, así que el error que se
ve es SOLO el del método numérico. Guarda en resultados/metodos/:

    reporte.txt          tablas de error y orden de convergencia medido
    integracion.png      error de rectángulo, trapecio y Simpson según el paso
    interpolacion.png    error de la interpolación lineal y del spline según el paso
    raices.png           error de bisección, Newton y secante en cada iteración
"""

import numpy as np

import config
from navinercial import graficas
from navinercial.metodos import integracion, interpolacion, raices

# Problema de integración: una "aceleración" a(t) = cos(t) m/s² durante 10 s.
# Su integral exacta (la velocidad) es sen(t).
DURACION_S = 10.0
CANTIDADES_DE_MUESTRAS = [21, 41, 81, 161, 321, 641, 1281, 2001]   # 2001 = 200 Hz en 10 s

# Problema de raíces: f(x) = x³ − 2x − 5 (ejemplo clásico de Newton).
RAIZ_EXACTA = 2.0945514815423265
ERROR_MINIMO_DIBUJABLE = 1e-16      # un error exactamente 0 no se puede dibujar en escala log


def _f(x):
    return x**3 - 2 * x - 5


def _derivada_f(x):
    return 3 * x**2 - 2


def errores_de_integracion():
    """Error máximo de cada método de integración para cada cantidad de muestras."""
    pasos = np.array([DURACION_S / (n - 1) for n in CANTIDADES_DE_MUESTRAS])
    errores = {metodo: [] for metodo in integracion.METODOS}
    for n in CANTIDADES_DE_MUESTRAS:
        t = np.linspace(0.0, DURACION_S, n)
        for metodo in integracion.METODOS:
            calculada = integracion.integral_acumulada(t, np.cos(t), metodo)
            errores[metodo].append(np.max(np.abs(calculada - np.sin(t))))
    return pasos, {metodo: np.array(e) for metodo, e in errores.items()}


def errores_de_interpolacion():
    """Error máximo de cada método de interpolación al reconstruir sen(t) entre muestras."""
    pasos = np.array([DURACION_S / (n - 1) for n in CANTIDADES_DE_MUESTRAS])
    # Se evalúa lejos de los extremos: ahí el spline natural pierde exactitud porque se le
    # impone curvatura cero, y sen(t) no la tiene.
    t_nuevo = np.linspace(0.25 * DURACION_S, 0.75 * DURACION_S, 5000)
    errores = {metodo: [] for metodo in interpolacion.METODOS}
    for n in CANTIDADES_DE_MUESTRAS:
        t = np.linspace(0.0, DURACION_S, n)
        for metodo in interpolacion.METODOS:
            calculada = interpolacion.interpolar(t, np.sin(t), t_nuevo, metodo)
            errores[metodo].append(np.max(np.abs(calculada - np.sin(t_nuevo))))
    return pasos, {metodo: np.array(e) for metodo, e in errores.items()}


def errores_de_raices():
    """Error de cada método de raíces en cada iteración."""
    historiales = {"bisección": [], "Newton": [], "secante": []}
    raices.biseccion(_f, 2.0, 3.0, tolerancia=1e-13, historial=historiales["bisección"])
    raices.newton(_f, _derivada_f, 3.0, tolerancia=1e-13, historial=historiales["Newton"])
    raices.secante(_f, 2.0, 3.0, tolerancia=1e-13, historial=historiales["secante"])
    return {nombre: np.maximum(np.abs(np.array(h) - RAIZ_EXACTA), ERROR_MINIMO_DIBUJABLE)
            for nombre, h in historiales.items()}


def orden_medido(pasos, errores):
    """Orden de convergencia p, medido con los dos pasos más pequeños: error ~ h^p.

    Si error = C·h^p, entonces p = log(error1/error2) / log(h1/h2).
    """
    return np.log(errores[-2] / errores[-1]) / np.log(pasos[-2] / pasos[-1])


def _tabla(pasos, errores_por_metodo):
    lineas = ["  paso h (s)  " + "".join(f"{m:>14s}" for m in errores_por_metodo)]
    for i, h in enumerate(pasos):
        lineas.append(f"  {h:10.5f}  " + "".join(f"{e[i]:14.3e}" for e in errores_por_metodo.values()))
    lineas.append("  orden medido" + "".join(f"{orden_medido(pasos, e):14.2f}"
                                             for e in errores_por_metodo.values()))
    return lineas


def texto_reporte(pasos, e_integracion, e_interpolacion, e_raices):
    lineas = ["COMPARACIÓN DE LOS MÉTODOS NUMÉRICOS (señales matemáticas, sin sensor)", "",
              "INTEGRACIÓN: error máximo al integrar a(t) = cos(t) durante 10 s (exacta: sen(t))"]
    lineas += _tabla(pasos, e_integracion)
    lineas += ["  Esperado: rectángulo 1, trapecio 2, Simpson 4.", "",
               "INTERPOLACIÓN: error máximo al reconstruir sen(t) entre las muestras"]
    lineas += _tabla(pasos, e_interpolacion)
    lineas += ["  Esperado: lineal 2, spline 4.", "",
               "RAÍCES: f(x) = x³ − 2x − 5, iteraciones hasta un paso menor que 1e-13"]
    for nombre, errores in e_raices.items():
        lineas.append(f"  {nombre:10s} {len(errores):3d} iteraciones")
    lineas += ["",
               f"Con el paso del sensor (h = {1 / config.FS_IMU_NOMINAL_HZ} s, 200 Hz), el error del "
               "método es el de la última fila",
               "de cada tabla. Compararlo con el error que produce el sensor (etapa del ascensor)."]
    return "\n".join(lineas)


def main():
    pasos, e_integracion = errores_de_integracion()
    _, e_interpolacion = errores_de_interpolacion()
    e_raices = errores_de_raices()
    reporte = texto_reporte(pasos, e_integracion, e_interpolacion, e_raices)

    carpeta = config.CARPETA_RESULTADOS / "metodos"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "reporte.txt").write_text(reporte, encoding="utf-8")
    graficas.guardar_figura(
        graficas.grafica_convergencia(
            pasos, e_integracion, "Integración de cos(t)",
            "paso h (s)", "error máximo de la integral (m/s)"),
        carpeta / "integracion.png")
    graficas.guardar_figura(
        graficas.grafica_convergencia(
            pasos, e_interpolacion, "Interpolación de sen(t)",
            "paso h (s)", "error máximo"),
        carpeta / "interpolacion.png")
    graficas.guardar_figura(
        graficas.grafica_iteraciones_raices(e_raices, "Raíz de x³ − 2x − 5"),
        carpeta / "raices.png")
    print(reporte)
    print(f"\nReporte y gráficas guardados en: {carpeta}")


if __name__ == "__main__":
    main()
