# Resumen de las etapas

Un apartado por etapa: qué se hizo, qué decisiones se tomaron y por qué, y qué debe revisar el
grupo. Los comandos se corren desde la carpeta `procesamiento/` con el entorno virtual activado.

---

## Etapa 1: estructura, configuración y formato de archivos

**Qué se hizo**
- Repositorio git en la raíz, con el código de Python en `procesamiento/` y el firmware en `firmware/`.
- `config.py`: gravedad de Quito, factores de conversión con su fuente, configuración nominal.
- `navinercial/formato.py`: única definición del formato de una sesión (nombres de archivos,
  columnas, validación, lectura y escritura de valores crudos).

**Decisiones**
- Dos gravedades distintas: `G_QUITO = 9.77` (gravedad local) y `G_ESTANDAR = 9.80665` (definición
  de la unidad "g" de la hoja de datos, solo para pasar de LSB a m/s²). Mezclarlas produce un error
  de escala falso de 0,4 %.
- Los valores crudos se leen como enteros de 64 bits: con int16, una operación como `ax*ax` se
  desborda sin avisar.
- El magnetómetro deja las celdas vacías cuando no hay lectura nueva (no repite la última).
- `meta.json` solo acepta los chips 0x71 (MPU-9250), 0x73 (MPU-9255) y 0x70 (MPU-6500).

**Qué revisar**
- Los `TODO` de las secciones de las hojas de datos en `config.py`.

---

## Etapa 2: simulador

**Qué se hizo**
- `metodos/raices.py`: bisección. `navinercial/bmp280.py`: compensación del BMP280 e inversión
  numérica con bisección (de presión y temperatura a `adc_P` y `adc_T`).
- `simulador/modelo_sensor.py`: sesgo, error de escala, ruido blanco, deriva del sesgo,
  desalineación opcional, cuantización y saturación a int16, jitter, muestras perdidas,
  magnetómetro y barómetro (ruido, tendencia lineal, marea semidiurna y paseo aleatorio).
- `simulador/escenarios.py`: reposo largo y seis caras. `simulador/generar.py`: línea de comandos.
- Cada sesión simulada guarda además `verdad.csv`, `verdad_baro.csv` y `verdad_parametros.json`.

**Decisiones**
- El simulador muestrea a 199,96 Hz aunque `meta.json` dice 200 Hz, para que la verificación tenga
  algo que encontrar.
- El jitter es del instante de muestreo; la marca de tiempo registra el instante real.
- `t_fine` del BMP280 se deja como número real (la hoja de datos lo trunca) para que la función sea
  continua y se pueda invertir con bisección. Diferencia en presión: menos de 0,01 Pa.
- Todos los parámetros de error (`SIM_*` en `config.py`) son sintéticos y están marcados así.

**Qué revisar**
- Los valores `SIM_*`: son del orden de los típicos de las hojas de datos, pero no son mediciones.
- La convención de ejes (docstring de `escenarios.py`): x = este, y = norte, z = arriba; en reposo
  el acelerómetro mide +g en el eje que apunta hacia arriba.

---

## Etapa 3: lectura y verificación

**Qué se hizo**
- `navinercial/lectura.py`: carga una sesión y la convierte a m/s², rad/s, µT, Pa y °C.
- `navinercial/verificacion.py`: muestras perdidas (por `seq` y por tiempo), frecuencia real en todo
  el registro, al inicio, al final y por ventanas, jitter, y reporte en texto.
- `navinercial/graficas.py` y `scripts/verificar_sesion.py`: reporte y tres gráficas por sesión.

**Resultados con el reposo simulado de 60 min**
- Frecuencia real 199,9600 Hz (nominal 200), igual al inicio y al final (diferencia de 3 ppm).
- Jitter de 70,6 µs (es √2 · 50 µs: cada intervalo es la diferencia de dos instantes con jitter).
- 6 muestras perdidas del IMU y 6 del barómetro, las mismas que quitó el simulador.

**Decisiones**
- La frecuencia se calcula con `seq`: (aumento de `seq`) / (tiempo transcurrido). Así las muestras
  perdidas no la alteran.
- Dos detectores de huecos independientes (contador y reloj). Si no coinciden, el problema del
  firmware es otro (por ejemplo, una pausa sin saltar `seq`).
- La lectura no calibra: solo cambia unidades.

**Qué revisar**
- Con el reposo de 60 min el requisito de 90 min no se puede comprobar: generar uno de 90 min con
  `python -m simulador.generar --escenario reposo --duracion-reposo-min 90`.

---

## Etapa 4: caracterización y calibración

**Qué se hizo**
- `navinercial/calibracion.py`:
  - `caracterizar_reposo`: media, desviación total y ruido de cada señal.
  - `desviacion_allan`: estabilidad del sensor según el tiempo de promediado.
  - `detectar_quietud` y `tramos_de_quietud`: detector "el dispositivo está quieto".
  - `detectar_caras`, `calibrar_seis_caras`, `aplicar_calibracion`, guardar y cargar en JSON.
- `scripts/caracterizar_reposo.py` y `scripts/calibrar_seis_caras.py`.

**Resultados con las sesiones simuladas**
- Reposo: ruido del acelerómetro 0,0300 m/s² por eje y del giroscopio 0,00175 rad/s (los valores
  del simulador); el detector de quietud dice "quieto" el 100 % del tiempo.
- Seis caras: error del sesgo menor que 0,001 m/s² y error de la escala menor que 0,00002.
- Magnitud de la gravedad entre caras: sin calibrar varía 0,57 m/s² (de 9,60 a 10,17); calibrada
  vale 9,770 m/s² en las seis caras.

**Decisiones**
- El ruido se estima con las diferencias entre muestras seguidas (σ = desviación de las diferencias
  dividida por √2). Así la deriva lenta no lo infla: en la presión, la desviación total es 3,9 Pa
  por el clima, pero el ruido es 1,3 Pa.
- El detector de quietud trabaja por bloques de 0,5 s y pide tres condiciones: poca variación del
  acelerómetro, poca variación del giroscopio y velocidad angular media pequeña. Los umbrales están
  en `config.py` y son unas 2 veces el ruido del simulador.
- Límite físico del detector: no distingue el reposo de un movimiento con velocidad constante. Por
  eso en el ascensor y en el metro se combina con las marcas del botón.
- En cada cara se descarta 1 s al inicio y al final, y un tramo solo cuenta como cara si un eje mide
  al menos el 80 % de g.
- La escala calculada es `1 + error de escala` (por ejemplo, 1,010). La calibración se aplica como
  `real = (medido − sesgo) / escala`.
- El sesgo del giroscopio es su promedio en los tramos quietos de las seis caras.

**Qué revisar**
- Los umbrales `QUIETUD_*` de `config.py` hay que ajustarlos con el ruido real del dispositivo.
- En reposo, la media de `ax`, `ay`, `az` NO es el sesgo: incluye la gravedad y la inclinación de la
  mesa. El sesgo del acelerómetro solo sale de las seis caras.
- Una mesa inclinada casi no cambia el sesgo calculado, pero sí reduce la escala en cos(inclinación).

---

## Firmware del ESP32 (carpeta `firmware/`)

**Qué se hizo**
- Proyecto de PlatformIO (framework Arduino) con dos entornos: `registro` (graba en la microSD) y
  `prueba` (imprime lecturas convertidas por el monitor serie, sin SD).
- `include/configuracion.h`: pines, direcciones, frecuencias, buffers. Todo lo ajustable está ahí.
- `src/sensores.*`: lectura cruda del MPU, del AK8963 y del BMP280 con `Wire`, sin librerías
  externas de sensores.
- `src/almacenamiento.*`: microSD, carpetas `sesion_NNN`, `meta.json` y doble buffer.
- `src/main.cpp`: temporizador de 200 Hz, tarea de muestreo, tarea de escritura, botón con
  interrupción y antirrebote, LED de estado.
- `firmware/README.md`: instalación en Windows, compilar, cargar, parpadeos del LED y cómo grabar.
- En Python: `formato.py` acepta también carpetas `sesion_NNN`; `lectura.py` aplica el ajuste de
  sensibilidad del magnetómetro (`ak8963_asa`) si viene en `meta.json`.

**Estado**
- Los dos entornos **compilan** sin errores ni avisos (PlatformIO, placa `esp32dev`).
- **No se ha ejecutado en ningún ESP32.** Nada del firmware está probado con hardware.

**Decisiones**
- Sin librerías de sensores: cada registro que se escribe o se lee está a la vista y se puede
  explicar con la hoja de datos.
- `seq` cuenta los avisos del temporizador, no las filas escritas. Si una muestra se pierde, queda
  un salto en `seq` y `verificar_sesion` lo informa.
- `t_us` se toma con `esp_timer_get_time()` justo antes de leer el sensor.
- Filtro paso bajo interno del MPU: `DLPF_CFG = 3` (≈41 Hz), por debajo de la mitad de la
  frecuencia de muestreo. El simulador sigue usando un ruido algo mayor (pesimista); está explicado
  en `config.py`.
- Barómetro a 25 Hz = una lectura cada 8 muestras del IMU; magnetómetro cada 2 (100 Hz).
- Ejes del magnetómetro reordenados en el firmware a los ejes del acelerómetro (`mx = hy`,
  `my = hx`, `mz = −hz`). El valor sigue siendo crudo.
- Botón: pulsación corta = evento (con el instante en que se pulsó); mantener 3 s = cerrar archivos.
  Encender = empezar a grabar, sin pasos extra.
- `flush` cada 2 s: un corte de energía pierde como máximo 2 s.
- Carpetas `sesion_001`, `sesion_002`...: la fecha real se anota en la bitácora.
- `validar_meta` ahora acepta un chip con magnetómetro que diga `tiene_magnetometro: false` (el
  firmware lo pone si el AK8963 no responde). Lo contrario sigue siendo error.
- `meta.json` lleva tres campos extra: `ak8963_asa`, `mpu_dlpf_cfg`, `bmp280_direccion`.

**Qué revisar**
- Todos los `TODO` de `configuracion.h` y `sensores.cpp` (direcciones de registros, anchos de banda
  del filtro, tiempo de medición del BMP280).
- La versión de la plataforma `espressif32` no está fijada en `platformio.ini`: si otra computadora
  descarga una versión distinta y no compila, fijarla con `platform = espressif32@<versión>`.
- La opción de Arduino IDE del README no se ha probado.
- Lista completa de comprobaciones con hardware: `docs/PENDIENTES_HARDWARE.md`.

---

## Etapa 5: métodos numéricos hechos a mano

**Qué se hizo**
- `navinercial/metodos/integracion.py`: integral acumulada por rectángulo (Euler), trapecio y
  Simpson. Las tres aceptan tiempos con espaciado irregular.
- `navinercial/metodos/interpolacion.py`: interpolación lineal y spline cúbico natural (con el
  sistema tridiagonal resuelto por el algoritmo de Thomas, también a mano).
- `navinercial/metodos/raices.py`: bisección (ya estaba), Newton y secante. Las tres aceptan una
  lista `historial` para contar iteraciones.
- `scripts/comparar_metodos.py`: tablas y gráficas de convergencia en `resultados/metodos/`.
- Pruebas contra soluciones analíticas y contra `numpy`/`scipy` (`cumulative_trapezoid`, `simpson`,
  `np.interp`, `CubicSpline`, `brentq`, `np.linalg.solve`).

**Resultados**
- Orden de convergencia medido: rectángulo 1,00; trapecio 2,00; Simpson 4,00; interpolación lineal
  2,00; spline 4,00. Coinciden con la teoría.
- Con el paso del sensor (0,005 s) e integrando cos(t) durante 10 s, el error del método es
  5·10⁻³ m/s (rectángulo), 2·10⁻⁶ m/s (trapecio) y 2·10⁻¹¹ m/s (Simpson).
- Raíz de x³ − 2x − 5 con paso menor que 10⁻¹³: bisección 44 iteraciones, Newton 6, secante 7.

**Decisiones**
- Simpson acumulativo: las muestras se toman de tres en tres y por cada trío pasa una parábola
  (forma de Newton, diferencias divididas). Así da un valor en CADA muestra, no solo en las pares,
  y funciona con paso irregular. Con paso uniforme es la fórmula clásica h/3·(y0 + 4y1 + y2).
- De numpy solo se usan operaciones básicas de arreglos: restas, productos, `cumsum` (suma
  acumulada) y `searchsorted` (búsqueda del intervalo). Las fórmulas de cada método están escritas
  a mano.
- Fuera del intervalo de datos la interpolación no extrapola: devuelve el valor del extremo.
- Spline "natural" (segunda derivada cero en los extremos): es el más simple de explicar. Cerca de
  los extremos es menos exacto; por eso la comparación se hace en la zona central.

**Qué revisar**
- Que el grupo pueda deducir en la pizarra las dos fórmulas de `_aportes_de_parabola` y la ecuación
  del spline (están en los docstrings).
- Si el profesor exige Simpson solo con paso uniforme, la función ya lo cubre (es un caso
  particular).

---

## Etapa 6: análisis del ascensor

**Qué se hizo**
- Simulador: escenario `ascensor` (edificio SINTÉTICO de 6 plantas con alturas distintas, 21
  recorridos, 42 pulsaciones del botón, dispositivo inclinado 1,8°). El barómetro simulado ahora
  depende de la altura. Se guarda `verdad_escenario.json` con los pisos y el itinerario.
- `navinercial/barometro.py`: fórmula barométrica Δh = (R·T/(M·g))·ln(P_ref/P), con g de Quito.
- `navinercial/correcciones.py`: paradas a partir del botón, sesgo medido en cada parada, ZUPT.
- `navinercial/fusion.py`: filtro complementario y filtro de Kalman 1D (estado: altura y velocidad),
  escritos a mano. El Kalman acepta la altura barométrica y la medición "velocidad = 0" en paradas.
- `navinercial/ascensor.py`: aceleración vertical, integración, todas las estimaciones, error por
  recorrido, cruce de pisos por bisección y secante.
- `navinercial/prediccion_error.py`: fórmulas del crecimiento del error.
- `scripts/analizar_ascensor.py` y `scripts/predecir_error_ascensor.py` (Monte Carlo).
- `datos_referencia/pisos_ascensor.csv`: plantilla VACÍA para las alturas reales (flexómetro).

**Resultados con el ascensor simulado (7,7 min, con calibración de seis caras)**

| Estimación | Error RMS por recorrido | Error RMS de altura |
|---|---|---|
| Inercial, sin correcciones (g nominal) | 1,52 m | 11,5 m |
| Inercial, sesgo del reposo inicial | 0,40 m | 1,9 m |
| Inercial, sesgo en paradas + ZUPT | 0,028 m | 0,053 m |
| Solo barómetro | 0,030 m | 0,23 m |
| Complementario (con barómetro) | 0,032 m | 0,20 m |
| Kalman sin barómetro (ZUPT) | 0,024 m | 0,047 m |
| Kalman con barómetro | 0,034 m | 0,20 m |
| Kalman con barómetro y ZUPT | 0,030 m | 0,19 m |

- Sin calibración de seis caras y sin correcciones el error llega a 42 km (el sesgo de 0,25 m/s² del
  eje z integrado dos veces durante 460 s). Con solo restar el sesgo del reposo inicial baja a 4 m.
- El ZUPT mejora el error por recorrido unas 14 veces respecto a restar solo el sesgo inicial.
- Error solo del método (aceleración exacta, sin sensor): rectángulo 7,7 mm; trapecio 0,013 mm;
  Simpson 0,003 mm. El error del sensor es miles de veces mayor: **el método casi no importa, el
  sensor sí**. Con datos del sensor, Simpson incluso da un resultado algo peor que el trapecio,
  porque pesa las muestras 4/3 y 2/3 y eso amplifica un poco el ruido.
- Cruce de pisos: la bisección encuentra los 35 cruces (18 iteraciones para 0,1 ms); la secante
  falla en 10 de 35 porque parte de un tramo plano (las paradas). Error del instante: hasta 0,2 s.
- Monte Carlo (40 semillas): con ZUPT, el error medio y la dispersión de cada recorrido coinciden
  con las fórmulas (error de escala · desplazamiento; σ·√(dt·T³/12)). Sin ZUPT, la dispersión
  predicha queda entre 7 % y 15 % por debajo de la observada.

**Decisiones**
- Vertical medida en el reposo inicial (promedio del acelerómetro): así una inclinación pequeña del
  dispositivo no importa. Se supone que el dispositivo no gira durante el registro; por eso no se
  usa el giroscopio en el ascensor.
- La gravedad que se resta es la MEDIDA en el reposo inicial, no 9,77: eso quita de una vez el
  sesgo y el error de escala sobre g.
- Convención del botón: pulsaciones alternadas salida/llegada (cierre/apertura de puertas); el
  registro empieza y termina parado. Se descarta 0,5 s en cada borde de cada parada.
- ZUPT en dos pasos: (1) el sesgo se mide en cada parada y se interpola entre paradas; (2) el error
  de velocidad se interpola linealmente entre paradas y se resta.
- El detector de quietud no se usa para las paradas del ascensor: a velocidad constante el
  acelerómetro mide lo mismo que en reposo. Se usan las pulsaciones.
- Kalman de 2 estados (altura, velocidad), sin estado de sesgo: es el más simple de explicar. El
  sesgo se quita antes. Limitación: si queda un sesgo, deja un error fijo (no crece).
- El barómetro se usa en el Kalman en sus propios instantes (no interpolado), para no contar la
  misma medición varias veces. Para el complementario sí se interpola a la base de tiempo del IMU.
- Fórmula barométrica isotérmica con la temperatura del BMP280 y g = 9,77. Para decenas de metros
  es equivalente a la fórmula internacional y todas sus constantes se pueden justificar.

**Qué revisar (importante)**
- **Fusión con barómetro vs. ZUPT:** en la simulación, la mejor altura absoluta la da el ZUPT sin
  barómetro, porque el barómetro simulado deriva con el "clima" (unos 0,4 m en 8 min; valores
  SINTÉTICOS de `config.py`). Con datos reales puede ser al revés. Por recorrido, todos dan ≈3 cm.
  Hay que medir la deriva real de la presión (reposo a distintas horas) antes de concluir.
- La comparación "con y sin barómetro" está en las filas Kalman sin barómetro / con barómetro.
- `KALMAN_*` y `COMPLEMENTARIO_TAU_S` en `config.py` están ajustados al simulador.
- La predicción sin ZUPT queda algo por debajo de Monte Carlo; no se encontró la causa exacta
  (probablemente términos cruzados que las fórmulas simples no incluyen). Para el informe: decir
  "coincide dentro de un 15 %".
- El simulador usa la misma fórmula barométrica que el análisis: el error del MODELO barométrico
  no aparece en la simulación. Solo se verá con datos reales y el flexómetro.
- Temperatura: el BMP280 mide la del dispositivo, no la del aire. Un error de 3 K cambia la altura 1 %.
- En el experimento real hay que anotar en la bitácora el piso de cada parada (opción
  `--itinerario`); si no, el programa asigna el piso más cercano.

---

## Etapa 7: análisis del metro, bitácora, reportes y representación numérica

**Qué se hizo**
- Simulador: escenarios `metro_1`, `metro_2` (ida) y `metro_3` (vuelta) sobre una ruta SINTÉTICA de
  5 estaciones ("Sintética A" a "Sintética E"), con rectas, curvas y desniveles. El dispositivo va
  girado 10° respecto al vagón y el magnetómetro se perturba con hierro y con la corriente del motor.
- `navinercial/metro.py`: orientación del dispositivo respecto al vagón, rumbo integrando el
  giroscopio, velocidad a lo largo de la vía con ZUPT, corrección de la pendiente con el barómetro,
  posición en el mapa, ajuste a distancias conocidas, prueba de confiabilidad del magnetómetro,
  proyección de latitud/longitud a metros y combinación de varios viajes.
- `scripts/analizar_metro.py`: reporte y gráficas por viaje (`resultados/metro/<sesión>/`) y
  combinado (`resultados/metro/combinado/`).
- `datos_referencia/estaciones_metro.csv` (nombres de las 15 estaciones, coordenadas VACÍAS) y
  `datos_referencia/tramos_metro.csv` (solo el encabezado).
- `navinercial/bitacora.py`, `bitacora/bitacora.csv` (plantilla) y `bitacora/README.md` (qué va en
  cada columna).
- `scripts/reporte_sesion.py`: verificación + análisis según el tipo + fila en la bitácora +
  `resultados/reportes/<sesión>.md`.
- `docs/representacion_numerica.md`: tipo de dato de cada magnitud en cada paso, qué se pierde,
  cuánto vale 1 LSB, por qué `t_us` es de 64 bits y por qué todo se calcula en `float64`.

**Resultados con los tres viajes simulados (7,6 min y unos 3,9 km cada uno)**

| Estimación | Error RMS de velocidad | Error de posición al final |
|---|---|---|
| Sin ZUPT (solo sesgo inicial) | 2,0 a 2,4 m/s | 600 a 720 m |
| ZUPT, sin barómetro | 0,38 a 0,39 m/s | 29 a 37 m |
| ZUPT + pendiente con barómetro | 0,025 a 0,033 m/s | 2 a 10 m |
| Además, ajustado a distancias conocidas | 0,016 a 0,024 m/s | 1 a 9 m |

- El programa encuentra la orientación del dispositivo (entre −10,2° y −10,5°; el valor real es −10°).
- Rumbo por giroscopio: error máximo de 0,34° en todo el viaje.
- Magnetómetro: |B| varía entre 21 % y 32 %, y el programa lo marca como NO confiable.
- Entre los tres viajes, la distancia de cada tramo se repite con una dispersión de 0,3 a 1,7 m.

**Decisiones**
- Modelo del vagón: solo avanza a lo largo de la vía (no se desliza de lado ni salta). Se integra
  una sola aceleración ("adelante") y la dirección la da el giroscopio. Es mucho más estable que
  integrar x e y por separado.
- "Adelante" se saca del primer arranque (ventana de 8 s tras la primera salida): la aceleración
  horizontal de ese momento apunta en la dirección de la vía. Se supone el dispositivo fijo y casi
  horizontal durante todo el viaje.
- Pendiente: en una subida, la gravedad se cuela en el eje "adelante" (g·sen θ) y parece
  aceleración. Se corrige con el barómetro: sen θ = (dh/dt)/v, solo cuando v > 3 m/s. Esta
  corrección es la que más mejora el resultado.
- El rumbo inicial y la posición inicial son DATOS (de la estación de salida). El programa no los
  puede saber sin GPS ni un magnetómetro confiable.
- Misma convención del botón que en el ascensor (salida/llegada alternadas).
- Las sesiones del simulador se anotan en `resultados/bitacora_simulada.csv`, no en la bitácora del
  grupo, para no mezclar datos inventados con experimentos reales.
- Un solo script de reporte con `--tipo`, que reutiliza los scripts de cada análisis.

**Qué revisar (importante)**
- **Todo lo del metro está probado solo con una ruta inventada.** Las curvas reales, las vibraciones
  y los frenazos no están en el simulador. Lo primero con datos reales es mirar si el vagón de
  verdad no tiene aceleración lateral rara y si "adelante" sale bien del primer arranque.
- La perturbación del magnetómetro es SINTÉTICA (`SIM_METRO_MAG_*`). Que salga "no confiable" en la
  simulación no dice nada del metro real: hay que medirlo.
- `estaciones_metro.csv`: faltan latitud y longitud de cada estación, con su fuente. Hay que
  confirmar también los nombres. `tramos_metro.csv`: faltan las longitudes reales de los tramos.
  Sin esos datos el programa da distancias, pero no puede decir cuánto se equivoca.
- Declinación magnética de Quito: no está en `config.py` (TODO). Solo hace falta si se llega a
  usar el magnetómetro para el rumbo.
- Umbrales ajustados al simulador: `METRO_VENTANA_ARRANQUE_S`, `METRO_VENTANA_BARO_S`,
  `METRO_VELOCIDAD_MINIMA_PENDIENTE_MS`, `MAG_VARIACION_MAXIMA_CONFIABLE`.
- En los túneles, la presión cambia al entrar y salir de las estaciones y cuando se cruza otro tren
  (efecto pistón). El simulador no lo incluye y puede dañar la corrección de la pendiente. Comparar
  el resultado con y sin barómetro en los datos reales.
- En el viaje real hay que pulsar el botón justo al arrancar y al parar, y anotar las estaciones.
- `representacion_numerica.md`: confirmar con la hoja de datos la resolución real del BMP280 con el
  sobremuestreo usado (19 y 16 bits). El tamaño del error de redondeo es una estimación.
