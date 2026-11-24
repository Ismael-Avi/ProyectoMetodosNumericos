# Cómo funciona `navegacion.py` (para nosotros)

La idea general: el sensor mide **aceleración** (y velocidad angular). Integrando una vez sale la
**velocidad**, integrando otra vez sale la **posición**. El problema es que cualquier error pequeño
en la aceleración crece con el tiempo al integrar, así que la mayor parte del código sirve para
quitar errores: calibrar, restar sesgos, usar las paradas (ZUPT) y combinar con el barómetro.

---

## 1. Lectura y unidades

**`leer_sesion(carpeta)`** lee los 4 archivos de la sesión y devuelve un diccionario `s` con todo
en unidades SI:

- tiempo: `t = (t_us - t_us[0]) / 1e6` en segundos (el barómetro usa el mismo `t_us[0]`, así las dos
  señales comparten el mismo cero).
- aceleración: `crudo / 8192 * 9.80665` → m/s². 8192 es cuántas cuentas da el sensor por cada "g" en
  el rango ±4 g. El "g" de la hoja de datos es el estándar (9,80665), no el de Quito.
- giroscopio: `crudo / 65.5` → °/s, y luego a rad/s.
- barómetro: `bmp280()`.
- eventos (botón): en segundos, con el mismo cero.

Ignora cualquier campo extra de meta.json y las columnas mx, my, mz (vacías: el MPU-6500 no tiene
magnetómetro). Si `firmware_version` es "simulador", avisa.

**`bmp280(adc_T, adc_P, c)`** es la fórmula de la hoja de datos de Bosch copiada tal cual. Cada chip
trae de fábrica 12 coeficientes (`dig_T1`…`dig_P9`), que el firmware guarda en meta.json. Primero se
calcula la temperatura (y `t_fine`), porque la presión depende de la temperatura. Se prueba con el
ejemplo de la hoja de datos: da 25,08 °C y 100653,27 Pa.

## 2. Herramientas que se usan en todos lados

**`detectar_quieto(t, acc, giro)`**: parte el registro en ventanas de 0,5 s. En cada ventana calcula
la desviación estándar del módulo de la aceleración |a| y del módulo de la velocidad angular |ω|.
Si las dos son pequeñas (menos que los umbrales), la ventana está "quieta". Se usa la desviación
estándar y no el promedio porque el promedio incluye la gravedad y el sesgo; lo que delata el
movimiento es que la señal *cambie*. Limitación: a velocidad constante (ascensor en crucero) |a| no
cambia y el detector cree que está quieto.

**`tramos(mascara)`**: convierte un arreglo de True/False en una lista de intervalos (inicio, fin)
donde vale True. Truco: `diff` de la máscara vale +1 donde empieza un tramo y -1 donde termina.

**`mascara_movimiento(s)`**: True mientras el dispositivo se mueve. Si hay un número par de pulsos
del botón, los toma en pares (salida, llegada). Si no, usa el detector de quietud.

**`reposo_inicial(s)`**: los primeros 10 s (o hasta 1 s antes del primer pulso).

**`decir`, `guardar_reporte`, `guardar_figura`, `agregar_bitacora`**: imprimir y guardar. Cada
comando escribe un `.txt` en resultados/ y agrega una fila a bitacora.csv.

## 3. Métodos numéricos (hechos a mano)

**`rectangulo(t, y)`**: integral acumulada sumando rectángulos con la altura del punto izquierdo:
`I[k] = I[k-1] + y[k-1]·(t[k] - t[k-1])`. Error proporcional a dt (orden 1).

**`trapecio(t, y)`**: igual pero con trapecios: `I[k] = I[k-1] + (y[k-1] + y[k])/2·(t[k] - t[k-1])`.
Error proporcional a dt² (orden 2). Las dos funciones usan `np.cumsum` para hacer la suma acumulada
de golpe en vez de un `for` (es la misma cuenta, pero mucho más rápida).

**`interpolar(x, y, xn)`**: interpolación lineal. Para cada punto nuevo `xn` busca entre qué dos
muestras cae (`searchsorted`) y une esas dos con una recta:
`y = y0 + (y1 - y0)·(xn - x0)/(x1 - x0)`. Se usa para llevar el barómetro (25 Hz) a los tiempos del
IMU (200 Hz). Error máximo ≤ h²/8 · max|f''|.

**`biseccion(f, a, b)`**: si f(a) y f(b) tienen distinto signo, hay una raíz en medio. Se parte el
intervalo a la mitad y se queda la mitad donde sigue habiendo cambio de signo, hasta que el
intervalo mide menos que `tol`. Cada paso divide el error entre 2: para tol = 10⁻¹⁰ en [2, 3] hacen
falta 34 pasos.

**`comando_metodos()`** prueba todo:
- BMP280 contra el ejemplo de Bosch.
- Integra dos veces a(t) = 0,5·sin(ωt), que tiene solución exacta x(t) = A/ω·(t − sin(ωt)/ω), con
  varios dt. Al dividir dt a la mitad, el error del rectángulo se divide entre 2 (orden 1) y el del
  trapecio entre 4 (orden 2). (Ojo: si la prueba dura un número entero de periodos, el rectángulo
  parece de orden 2 por casualidad; por eso usamos 0,15 Hz y 30 s = 4,5 periodos.)
- Compara con `np.trapezoid`, `np.interp` y `np.roots` (diferencias ~10⁻¹⁵).
- **Error del método vs error del sensor:** integra la misma señal exacta (solo error del método:
  ~4·10⁻⁵ m), luego con un sesgo de 0,05 m/s² (error 22,5 m, igual a ½·b·t²) y con ruido de 0,02 m/s²
  (200 repeticiones; desviación ≈ ruido·√dt·t^1,5/√3). Conclusión: el método aporta ~10⁶ veces menos
  error que el sensor. Mejorar el método no sirve de nada; hay que corregir el sensor.

## 4. Caracterización

**`comando_verificar`**: cuenta muestras perdidas (`seq` debería subir de 1 en 1; cada salto de n
son n−1 perdidas). Frecuencia real = (muestras entre la primera y la última de una ventana) / (tiempo
entre ellas), en el primer y el último minuto. Jitter = desviación estándar del periodo entre
muestras seguidas. Gráfica de todas las señales.

**`comando_reposo`**: con las muestras quietas, media y desviación estándar de cada eje.
- La desviación estándar es el **ruido**.
- La media del giroscopio es su **sesgo** (quieto debería marcar 0).
- La media del acelerómetro es la gravedad más el sesgo; por eso se compara |a| con 9,77.
- Predicciones: el ruido hace un paseo aleatorio en la velocidad, σ_v = ruido·√(dt·t); un sesgo de
  giroscopio b gira el rumbo b·t.
- Tendencia de la presión (Pa/h, recta por mínimos cuadrados con `np.polyfit`): sirve para ver la
  deriva por clima.
- Inclinación: ángulo entre la aceleración media y el eje más cercano, arccos(max|a_i| / |a|).

**`deriva_por_bloques`** (la llama `reposo`): parte el registro en bloques de 10 min y en cada uno
promedia, con las muestras quietas, el giroscopio (= sesgo), el acelerómetro, la presión y la
temperatura. Si el sensor fuera estable, todos los bloques darían lo mismo. Muestra:
- el cambio del primer al último bloque. El cambio de presión también se pasa a "altura falsa"
  con la fórmula barométrica: es lo que vería el ascensor si no se midiera P0 en cada sesión;
- la pendiente del sesgo del giroscopio k en (°/s)/h, con una recta por mínimos cuadrados sobre los
  bloques. Si solo se resta el sesgo medido al inicio, el sesgo que queda crece como k·t, y el rumbo
  (su integral) se desvía ½·k·t².

En el reposo real de 95 min (21/11/2026): la presión subió 0,80 hPa (tendencia +59,5 Pa/h, equivale
a 9,65 m de altura falsa) y el sesgo de gx pasó de -4,452 a -4,540 °/s. Al encender, la temperatura
del BMP280 sube de 25,2 a 26,3 °C en ~2 min y luego baja hasta ~25,1 °C hacia el minuto 18–20; en
ese tramo es donde más cambia el sesgo (-0,043 °/s entre el primer y el segundo bloque). Después la
temperatura queda plana y gx sigue derivando lento (~-0,005 °/s cada 10 min), así que la deriva no
se explica solo con la temperatura.

**`recortar(s)`** (dentro de `leer_sesion`): con `--botones` y/o `--recorte N` se quedan solo las
muestras dentro de la ventana elegida (IMU, barómetro y eventos), sin cambiar el eje de tiempo.
Antes, `leer_sesion` ignora las pulsaciones a menos de 1 s de la anterior (rebote del pulsador).

**`comando_caras`**: busca tramos quietos de más de 10 s. En cada uno promedia la aceleración y
mira qué eje tiene casi toda la gravedad y con qué signo (eso dice qué cara está arriba). Con las 6
caras, para cada eje:
- con el eje hacia arriba mide `a+ = escala·g + sesgo`
- con el eje hacia abajo mide `a- = -escala·g + sesgo`
- sumando y restando: **sesgo = (a+ + a-)/2**, **escala = (a+ − a-)/(2g)**

Corregir: `a_cal = (a − sesgo)/escala`. La tabla muestra |g| antes y después en cada cara. Ojo:
después da casi 9,77 en esas mismas caras porque se calibró con ellas, así que esa tabla no prueba
nada. (Con la sesión real `caras_2026-11-24` da 9,782 a 9,790 y no 9,77 exacto, porque las caras no
quedan perfectamente verticales: la calibración usa solo el eje que tiene la gravedad, y |g| suma
además lo poco que cae en los otros dos ejes.)

**Prueba independiente:** el comando guarda *todos* los tramos quietos de más de 3 s. Los que no se
usaron como cara (posiciones inclinadas, o una cara repetida) se revisan aparte. En cada uno se
muestra la inclinación respecto al eje más cercano, arccos(max|a_i| / |a|), y |g| antes y después de
calibrar. Si la calibración es buena, |g| calibrado da 9,77 en cualquier posición, aunque esos
tramos no se usaron para calcular el sesgo y la escala. Al final se compara la variación de |g|
entre tramos antes y después.

Con la sesión real `caras_2026-11-24` (6 caras + 8 posiciones inclinadas de 5° a 22°): |g| sin
calibrar va de 9,661 a 10,127 m/s² según la posición; calibrado, de 9,770 a 9,799 m/s². La
desviación estándar entre las 8 posiciones bajó de 0,1693 a 0,0092 m/s² (18 veces menor) y el error
máximo quedó en 0,029 m/s². La calibración oficial es `resultados/calibracion.json`, que sale de esa
sesión. (Antes, con una sesión sintética, la variación había bajado de 0,078 a 0,0006 m/s²; con
datos reales queda más: las caras reales no quedan perfectamente verticales y el sensor puede tener
errores que el modelo de sesgo + escala no incluye, por ejemplo ejes no perfectamente
perpendiculares.)

Si la sesión no tiene las 6 caras, no se calibra, pero se revisan todos sus tramos quietos con la
`calibracion.json` que ya existe (la real). Así se puede grabar otro día una sesión solo con inclinaciones y
comprobar la calibración vieja.

Si la sesión de caras es simulada (`firmware_version` = `simulador`), el resultado se guarda en
`resultados/simulados/calibracion_simulada.json`. `cargar_calibracion` solo lee
`resultados/calibracion.json`, así que una calibración simulada nunca se aplica a datos reales.

## 5. Ascensor (`comando_ascensor`)

> **Todavía solo con datos simulados.** No hemos grabado el ascensor; los números de esta sección
> salen de `datos/simulados/ascensor` y sus resultados están en `resultados/simulados/`.

1. Calibra con caras. En el reposo inicial, la aceleración promedio apunta hacia arriba (el
   acelerómetro quieto mide +g hacia arriba). Su dirección `arriba` también corrige si la caja está
   un poco inclinada.
2. Aceleración vertical sin gravedad: `a_bruta = a·arriba − 9,77`.
3. **Restar sesgo:** en el reposo `a_bruta` debería ser 0; su promedio `b` es el sesgo que queda
   después de calibrar. `a_corr = a_bruta − b`.
4. Velocidad y altura con rectángulo y con trapecio.
5. **ZUPT (`velocidad_zupt`)**: en las paradas la velocidad es 0 sí o sí. En cada tramo de movimiento
   se integra desde 0; al final del tramo la velocidad *debería* volver a 0, y lo que sobra es error
   acumulado. Ese error se reparte como una recta (crece de 0 al inicio hasta el valor sobrante al
   final) y se resta. En las paradas, v = 0.
6. **Barómetro (`altura_barometrica`)**: ecuación hipsométrica h = (R·T/(M·g))·ln(P0/P), con P0 = presión
   en el reposo inicial y T = temperatura media en kelvin. R·T/(M·g) ≈ 8600 m en Quito: 1 Pa ≈ 12 cm.
   Usa g = 9,77 y la temperatura medida, no los valores estándar a nivel del mar. (La temperatura es
   la del chip, que puede no ser la del aire.)
7. **Filtro complementario (`filtro_complementario`)**: el acelerómetro es bueno en tiempos cortos
   (poco ruido) pero deriva; el barómetro es ruidoso pero no deriva. En cada paso:
   `e = h_baro − h`, `h += (v + k1·e)·dt`, `v += (a + k2·e)·dt`, con k1 = 2/τ y k2 = 1/τ² (τ = 3 s).
   Es como un resorte que jala la altura integrada hacia la del barómetro con una constante de tiempo
   τ. En las paradas también se pone v = 0. Se eligió el complementario y no Kalman porque tiene un
   solo parámetro (τ), se entiende y alcanza para un movimiento en una dimensión.
8. **Errores:** altura promedio en cada parada, comparada con el piso real más cercano de
   `pisos.csv`. Si está vacío, se compara con el barómetro: eso **no es error real**, es cuánto
   coinciden acelerómetro y barómetro.
9. **Cruces de piso:** en cada tramo el ascensor va en una sola dirección, así que
   f(t) = h(t) − h_piso cambia de signo una sola vez entre el inicio y el fin del tramo. La bisección
   encuentra ese instante (h(t) entre muestras se obtiene con `interpolar`). Solo se buscan pisos
   intermedios; la llegada la marca el botón.
10. **Predicción del error:** sin restar el sesgo, la altura se desvía ½·b·t²; restándolo queda el
    ruido, que da σ_h ≈ ruido·√dt·t^1,5/√3. Se compara con lo observado (contra la fusión) en la
    figura `*_ascensor_error.png`.

Lo que salió con el ascensor simulado (pisos sintéticos, solo para probar): sin correcciones, ~12 m
de error; restando el sesgo, ~5 m; con ZUPT, 0,05 m. La fusión dio 0,20 m porque el barómetro
simulado deriva 0,35 m con el clima durante la sesión. El ZUPT corrige la velocidad, y el barómetro
la altura a largo plazo, pero también mete su deriva.

## 6. Metro (`analizar_viaje`, `comando_metro`)

> **Todavía solo con datos simulados** (ruta sintética, `datos/simulados/metro_*`). Los resultados
> están en `resultados/simulados/`.

1. Calibra, mide `arriba` y el **sesgo del giroscopio** en el reposo inicial y lo resta.
2. **Rumbo:** velocidad angular alrededor de la vertical = (ω − sesgo)·arriba; integrada con
   trapecio da cuánto ha girado el tren desde el inicio.
3. **Dirección "adelante":** en el primer arranque, lo único que acelera es el tren, y hacia
   adelante. Se promedia (a − gravedad) en los primeros 5 s, se le quita la parte vertical y se
   normaliza. Así no importa cómo esté puesta la caja.
4. Velocidad = integral de la aceleración hacia adelante con ZUPT en cada estación. Distancia =
   integral de la velocidad.
5. **Pendiente con barómetro:** en una subida, el eje "adelante" se inclina y mide también g·sen(θ).
   sen(θ) = (dh/dt)/v, con h del barómetro suavizado 10 s. Se resta g·sen(θ) y se integra de nuevo.
   Resultado en la simulación: **empeora un poco** (error RMS de ~3,5 m por tramo contra ~1 m sin barómetro),
   porque derivar el barómetro amplifica su ruido y el ZUPT ya quita casi todo el efecto de la
   pendiente. Con datos reales hay que ver cuál de los dos gana.
6. Tabla por tramo (par de pulsos): duración, distancia sin y con barómetro, velocidad máxima y
   media, aceleración máxima, desnivel.
7. **Distancia conocida:** si `estaciones.csv` y `viajes.csv` tienen datos, se calcula el error de
   cada tramo y un factor de escala por mínimos cuadrados, k = Σ(d·L)/Σ(d²), que se aplica a la
   velocidad. No se fuerza cada tramo a su largo exacto, porque así el error saldría 0 por
   construcción y no mediría nada.
8. **Mapa:** x = ∫v·cos(rumbo), y = ∫v·sin(rumbo). Si hay coordenadas, se pasan a metros
   (x = R·Δlon·cos(lat0), y = R·Δlat), se gira la trayectoria para que el primer tramo apunte a la
   segunda estación y se mide la distancia a cada estación real.
9. **Varios viajes:** media y desviación estándar de la distancia de cada tramo. Con `viajes.csv`
   se emparejan por estaciones (A–B y B–A juntas); sin él, por número de tramo.
