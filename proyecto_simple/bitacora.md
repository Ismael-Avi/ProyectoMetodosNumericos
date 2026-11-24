# Bitácora del proyecto: navegación inercial en el Metro de Quito

Métodos Numéricos, EPN. Este archivo es la bitácora escrita, para leer. `bitacora.csv` es el
registro automático que deja `navegacion.py` cada vez que se corre un comando, y se conserva aparte.

Todos los números de este documento salen de los archivos de `datos/` o de correr `navegacion.py`
(corridas del 24/11/2026). Lo que falta está marcado con **TODO**.

## 1. Integrantes

TODO: nombres

## 2. Experimentos

Formato de los datos y configuración del sensor: [`datos/LEEME.md`](datos/LEEME.md).

### 2.1 `sesion_002`: reposo corto de prueba

| Campo | Valor |
|---|---|
| Fecha y hora | 21/11/2026, hora: TODO (el ESP32 no tiene reloj; la carpeta no lleva fecha) |
| Lugar | TODO: completar |
| Superficie | mesa |
| Orientación | eje z hacia arriba, inclinación de 3,0° respecto a la vertical (medida con `reposo`, sin calibrar) |
| Alimentación | USB de la laptop |
| Duración | 142,4 s (2,4 min) |
| Procedimiento | primera prueba del firmware `registrador_v01`: encenderlo sobre la mesa y dejarlo en reposo ~142 s. Sin pulsaciones de botón (`eventos.csv` vacío) |

**Comandos:**

```
python navegacion.py verificar datos/sesion_002
python navegacion.py reposo    datos/sesion_002 --botones --recorte 5
```

Como no hay pulsaciones, `--botones` no recorta nada y solo se quitan 5 s a cada lado (se usa de
5,0 a 137,4 s).

**Resultados principales:**

- Muestras: 28 483 del IMU y 3 561 del barómetro, 0 perdidas en los dos. Frecuencia real 200,000 Hz
  al inicio y al final (barómetro 25,000 Hz). Jitter del periodo del IMU: 1,3 µs.
- Detector: quieto el 98,5 % del tiempo. Marca movimiento en 18,0; 76,5; 79,0 y 105,0 s (ventanas
  de 0,5 s).
- Sesgo del giroscopio: (-4,496; -1,794; -0,212) °/s. Ruido: (0,0604; 0,0636; 0,0644) °/s.
- Ruido del acelerómetro: (0,0169; 0,0156; 0,0205) m/s², 0,0177 m/s² en total.
- |a| medio 10,1134 m/s², 0,3434 m/s² más que g de Quito (9,77). Es error de escala y sesgo del
  acelerómetro, que se corrige con la calibración de seis caras.
- Presión media 73 271,8 Pa (desviación 2,74 Pa); temperatura de 23,03 a 23,27 °C.
- Deriva: el registro es demasiado corto (hacen falta al menos dos bloques de 10 min).

**Figuras y reportes:** `resultados/sesion_002_senales.png`, `resultados/sesion_002_reposo.png`,
`resultados/sesion_002_verificar.txt`, `resultados/sesion_002_reposo.txt`.

**Observaciones:** fue la primera sesión real que se procesó. Con ella se midió el ruido real que
se usa para fijar los umbrales del detector de quietud (`UMBRAL_ACC`, `UMBRAL_GIRO`) y se vio que el
giroscopio tiene unos -4,5 °/s de sesgo en x. TODO: anotar qué pasó en los instantes en que el
detector marca movimiento (¿golpes en la mesa?).

### 2.2 `reposo_90min_2026-11-21_1915-2049`: reposo largo

| Campo | Valor |
|---|---|
| Fecha y hora | 21/11/2026, de 19:15 a 20:49 |
| Lugar | TODO: completar |
| Superficie | mesa |
| Orientación | eje z hacia arriba. Protoboard inclinada ~9° (medido con `reposo`: 9,2°, sin calibrar) |
| Alimentación | power bank |
| Duración | 5694,3 s (94,9 min) |
| Procedimiento | encender el dispositivo sobre la mesa, pulsar el botón al inicio (s 3,2) y dejarlo quieto ~95 min. Al final, pulsar el botón (s 5686,2) y apagar. Solo hubo movimiento en los primeros 5 s y en los últimos 10 s |

**Comandos:**

```
python navegacion.py verificar datos/reposo_90min_2026-11-21_1915-2049
python navegacion.py reposo    datos/reposo_90min_2026-11-21_1915-2049 --botones --recorte 5
```

`reposo` usa de 8,2 a 5681,2 s: entre las dos pulsaciones, quitando 5 s a cada lado (94,6 min).

**Resultados principales:**

- Muestras: 1 138 860 del IMU y 142 358 del barómetro, **0 perdidas** en los dos. Frecuencia real
  **200,000 Hz al inicio y al final** (barómetro 25,000 Hz). Jitter del periodo del IMU: 0,8 µs.
  Cumple los dos requisitos del enunciado: ≥ 100 Hz y 90 min sin perder muestras.
- Detector: quieto el 100,0 % del tiempo usado. El programa dice que el dispositivo no se movió.
- Sesgo del giroscopio: **(-4,513; -1,823; -0,163) °/s**. Ruido: (0,0607; 0,0542; 0,0564) °/s.
- Ruido del acelerómetro: (0,0113; 0,0105; 0,0171) m/s², 0,0130 m/s² en total.
- |a| medio 10,0988 m/s², 0,3288 m/s² más que g de Quito. Falta la calibración de seis caras.
- Inclinación respecto al eje z: 9,2°.
- Predicciones con estos números: el ruido hace un paseo aleatorio de la velocidad de 0,0071 m/s en
  60 s y 0,0225 m/s en 10 min. Un sesgo de 4,513 °/s sin restar gira el rumbo 270,8° en 1 min.
- **Deriva por bloques de 10 min** (del primer al último bloque):
  - Sesgo de gx: de -4,452 a -4,540 °/s (-0,088 °/s). Pendiente del sesgo:
    (-0,047; -0,0174; -0,0018) (°/s)/h. Si solo se resta el sesgo medido al inicio, el eje x
    acumularía un error de rumbo de 2,4° en 10 min y 191° en 90 min.
  - Acelerómetro: (+0,0142; -0,0058; +0,0079) m/s²; |a| +0,0102 m/s².
  - **Presión: +0,80 hPa** (de 730,82 a 731,63 hPa). Tendencia +59,5 Pa/h. Si se tomara como
    cambio de altura serían 9,65 m falsos de bajada.
  - Temperatura del BMP280: -0,78 °C entre el primer y el último bloque (rango 25,04 a 26,31 °C).
- **Calentamiento inicial:** la temperatura del BMP280 sube de 25,17 °C (primeros 5 s) a un máximo
  de 26,31 °C en el segundo 139 (~2,3 min). Luego baja y se estabiliza en ~25,1 °C hacia el minuto
  18–20. En ese tramo es donde más cambia el sesgo de gx: -4,452 °/s en el bloque 0–10 min, -4,494
  en el de 10–20 y -4,508 en el de 20–30. Después la temperatura queda plana y gx sigue derivando
  despacio (~-0,005 °/s cada 10 min), así que la deriva no se explica solo con la temperatura.
- **Botón:** `eventos.csv` tiene 3 pulsaciones (3,2 s; 5686,2 s y 5686,6 s). Las dos últimas están a
  0,40 s: es una doble pulsación por rebote del pulsador. Pasó el antirrebote de 200 ms del
  firmware y la quitó el filtro de 1 s de Python.

**Figuras y reportes:**
`resultados/reposo_90min_2026-11-21_1915-2049_senales.png`,
`resultados/reposo_90min_2026-11-21_1915-2049_reposo.png`,
`resultados/reposo_90min_2026-11-21_1915-2049_deriva.png`,
`resultados/reposo_90min_2026-11-21_1915-2049_verificar.txt`,
`resultados/reposo_90min_2026-11-21_1915-2049_reposo.txt`.

**Observaciones:**

- La temperatura que se registra es la del BMP280. La del MPU-6500 (registros 0x41–0x42) el firmware
  la lee pero no la guarda, así que no se puede comparar directamente el sesgo del giroscopio con la
  temperatura de su propio chip.
- La protoboard no estaba nivelada (9,2°). No afecta el sesgo del giroscopio, pero sí reparte la
  gravedad entre los ejes x y z del acelerómetro.
- El sesgo del giroscopio cambia poco en 95 min, pero no lo suficiente para restar un solo valor en
  un viaje largo. Por eso cada sesión empieza con 10 s quieto.

### 2.3 `caras_2026-11-24`: calibración de seis caras (calibración oficial)

| Campo | Valor |
|---|---|
| Fecha y hora | 24/11/2026, hora: TODO |
| Lugar | TODO: completar |
| Superficie | TODO: completar |
| Montaje | protoboard fijada dentro de una caja |
| Orientación | las seis caras (~1 min cada una) y después 8 posiciones inclinadas (5° a 22°; medido con `caras`: 5,2° a 22,3°) |
| Alimentación | cargador de pared |
| Duración | 746,7 s (12,4 min) |
| Procedimiento | apoyar la caja en cada una de sus seis caras ~1 min, sin tocarla. Luego dejarla quieta en 8 posiciones inclinadas, apoyada contra algo, moviéndola entre una y otra. Sin pulsador |

**Comandos:**

```
python navegacion.py verificar datos/caras_2026-11-24
python navegacion.py caras     datos/caras_2026-11-24
```

**Resultados principales:**

- Muestras: 149 332 del IMU y 18 667 del barómetro, 0 perdidas en los dos. Frecuencia real
  200,000 Hz al inicio y al final (barómetro 25,000 Hz). Jitter del periodo del IMU: 1,1 µs.
- `caras` encuentra 14 tramos quietos: las 6 caras y 8 tramos extra (las posiciones inclinadas).
- Calibración del acelerómetro (`resultados/calibracion.json`):

  | Eje | a+ (m/s²) | a− (m/s²) | Sesgo (m/s²) | Escala |
  |---|---|---|---|---|
  | x | 9,8685 | −9,6552 | +0,1067 | 0,99916 |
  | y | 9,7586 | −9,7942 | −0,0178 | 1,00065 |
  | z | 10,1023 | −9,6543 | +0,2240 | 1,01109 |

- |g| en las seis caras: de 9,667 a 10,121 m/s² sin calibrar; de 9,782 a 9,790 m/s² calibrado.
  (No da 9,77 exacto porque las caras no quedan perfectamente verticales.)
- **Prueba independiente**, con las 8 posiciones inclinadas que no se usaron para calibrar: |g| sin
  calibrar va de 9,661 a 10,127 m/s²; calibrado, de 9,770 a 9,799 m/s². La desviación estándar
  entre posiciones baja de 0,1693 a 0,0092 m/s² (18 veces menor). Error máximo calibrado:
  0,0286 m/s².
- Sesgo del giroscopio (promedio de las caras): (-4,503; -1,766; -0,204) °/s, con una variación
  entre caras de 0,005 a 0,008 °/s. Coincide con el de los reposos del 21/11.
- Aplicando esta calibración a la aceleración media de los reposos del 21/11 (cálculo aparte, con
  los números de `reposo`): |g| = 9,776 m/s² en `sesion_002` (antes 10,113) y 9,755 m/s² en el
  reposo de 90 min (antes 10,099).

**Figuras y reportes:** `resultados/caras_2026-11-24_senales.png` (se ven las seis caras como
escalones de ±9,8 m/s² en un eje y después las 8 posiciones inclinadas),
`resultados/caras_2026-11-24_caras.txt`, `resultados/caras_2026-11-24_verificar.txt` y
`resultados/calibracion.json`. El comando `caras` no genera figura propia.

**Observaciones:**

- Las 8 posiciones calibradas quedan todas un poco por encima de 9,77 (entre −0,0005 y +0,0286
  m/s², +0,016 en promedio). TODO: discutir la causa (caras no perfectamente verticales al
  calibrar, ejes no perpendiculares, o el valor de g usado).
- Dentro de la caja, la temperatura del BMP280 subió de 24,6 a 26,0 °C durante los 12 min, y la
  presión subió ~20 Pa (de 73 074,6 a 73 094,1 Pa, promedio del primer y del último minuto).
- **Aprendizaje de los intentos anteriores** (no se guardaron): en el primero faltó la cara y− y
  las caras quedaron inclinadas hasta 17°; en el segundo se pudo calibrar, pero con caras
  inclinadas hasta 9° y sin posiciones inclinadas, así que no había cómo comprobar la calibración.
  Por eso en el tercero se fijó la protoboard dentro de una caja, para apoyar el sensor sobre caras
  planas y mejor alineadas, y se agregaron las 8 posiciones inclinadas.

## 3. Problemas encontrados y cómo se resolvieron

| Problema | Qué pasaba | Cómo se resolvió |
|---|---|---|
| Rebote del pulsador sin soldar | Una pulsación quedaba registrada dos veces. En el reposo de 90 min, la pulsación final aparece dos veces a 0,40 s | Antirrebote de 200 ms en el firmware (interrupción `isrBoton`) y, como no alcanzó, filtro de 1 s en Python (`REBOTE_BOTON_S`): las pulsaciones a menos de 1 s de la anterior se ignoran. Solución definitiva: soldar el pulsador (pendiente) |
| Abrir el Serial Monitor reinicia el ESP32 | Al abrir el monitor serie, el adaptador USB reinicia el ESP32. El firmware empieza a grabar al encender y crea una carpeta `sesion_NNN` nueva en cada arranque, con `t_us` desde cero | TODO: completar cómo lo manejaron (p. ej., abrir el monitor antes de empezar el experimento o no abrirlo durante la grabación) |
| Cortar la energía parte la sesión en dos carpetas | Cada encendido crea una carpeta nueva. Si la energía se corta a mitad de un experimento, quedan dos carpetas y el reloj `t_us` vuelve a empezar | TODO: completar cómo lo manejaron |
| Deriva de la presión por el clima | En el reposo de 90 min la presión subió 0,80 hPa sin mover el dispositivo. Equivale a 9,65 m de altura falsa | Medir P0 (la presión de referencia) en el reposo inicial de cada sesión, en vez de usar un valor fijo |
| Calibración simulada con aspecto de real | La única `resultados/calibracion.json` venía de la sesión **simulada** `caras` (ver `bitacora.csv`), y `ascensor` y `metro` la cargaban sin avisar. Con datos reales se habría aplicado un sesgo y una escala inventados | El 23/11/2026 se movió a `resultados/simulados/calibracion_simulada.json`. `navegacion.py` solo carga `resultados/calibracion.json`, que tiene que salir de una sesión real de `caras`; si falta, `ascensor` y `metro` avisan y siguen sin calibrar. Si `caras` procesa una sesión simulada, guarda en `resultados/simulados/`. Desde el 24/11/2026 `resultados/calibracion.json` sale de la sesión real `caras_2026-11-24` |
| Caras inclinadas o incompletas en la calibración | En el primer intento faltó la cara y− y las caras quedaron inclinadas hasta 17°. En el segundo, inclinadas hasta 9° y sin posiciones para comprobar | Fijar la protoboard dentro de una caja y apoyar la caja en sus caras; agregar posiciones inclinadas. El tercer intento (`caras_2026-11-24`) es la calibración oficial |
| Calentamiento inicial del chip | La temperatura del BMP280 sube ~1,1 °C en los primeros ~2 min y luego baja hasta estabilizarse hacia el minuto 18–20. En ese tramo el sesgo de gx cambia más | Se midió con la deriva por bloques de `reposo`. Se mide el sesgo en el reposo inicial de cada sesión. TODO: decidir si se enciende el dispositivo ~20 min antes de los experimentos |

## 4. Decisiones y por qué

- **Datos crudos en el firmware y conversión en Python.** El enunciado pide guardar los datos tal
  como los entrega el sensor. Así, si cambia la calibración o se encuentra un error en la
  conversión, se vuelve a procesar sin repetir el experimento. Además el firmware queda más
  simple: solo lee y escribe enteros.
- **200 Hz en el IMU y 25 Hz en el barómetro.** El enunciado pide 100 Hz o más; 200 Hz da margen.
  Con 200 Hz el filtro interno del MPU (~41 Hz en el giroscopio, ~45 Hz en el acelerómetro) queda
  por debajo de la mitad de la frecuencia de muestreo (100 Hz), y no hay aliasing. Leer el MPU por
  I2C a 400 kHz tarda ~0,4 ms, muy por debajo de los 5 ms entre muestras. El BMP280 con presión x8
  tarda ~22,5 ms por medición (~44 por segundo), así que 25 Hz alcanza y es un divisor entero de
  200 (una lectura cada 8 del IMU). En el reposo de 95 min no se perdió ninguna muestra.
- **Dos tareas de FreeRTOS con una cola de 2000 muestras.** Escribir en la microSD a veces tarda
  decenas de milisegundos. Si la lectura y la escritura estuvieran en el mismo lazo, en esos momentos
  se perderían muestras. La tarea de muestreo (núcleo 1, prioridad alta) solo lee y mete la muestra
  en la cola; la de escritura (núcleo 0) la vacía. 2000 muestras son 10 s de margen.
- **La grabación empieza al encender y el botón solo marca eventos.** No hace falta ningún paso
  extra para empezar a grabar, y el botón queda libre para marcar puertas y estaciones. Para
  terminar se apaga el dispositivo; el `flush` cada 1 s limita la pérdida a como máximo el último
  segundo. La contra es que cada encendido o reinicio crea una carpeta nueva (ver problemas).
- **g = 9,77 m/s² para Quito.** Es el valor del enunciado. A 2850 m de altura y cerca del ecuador, la
  gravedad es menor que 9,81. TODO: citar fuente.
- **Un solo script en Python (`navegacion.py`).** La primera versión (`procesamiento/`) tenía 32
  archivos de Python sin contar las pruebas. Se rehízo en un solo archivo, con comandos (`verificar`, `reposo`, `caras`, `metodos`,
  `ascensor`, `metro`), para que cada integrante pueda leerlo de principio a fin y defenderlo. Los
  métodos numéricos del curso (rectángulo, trapecio, interpolación lineal, bisección) están hechos a
  mano.

## 5. Uso de IA

**Qué se hizo con IA** (en los commits figura Claude como coautor: Claude Fable 5.2 en
`procesamiento/` y en el primer firmware de PlatformIO, `firmware/`; Claude Opus 5.5 en
`proyecto_simple/`. TODO: anotar con qué herramienta se escribió `registrador_v01.ino`, que se
copió sin cambios al repo):

- Firmware en C++ del ESP32 (`firmware/registrador_v01/registrador_v01.ino`).
- Procesamiento en Python (`navegacion.py`) y el simulador que se usó para probarlo antes de tener
  el hardware.
- Planificación: el documento de contexto del proyecto (`../CONTEXTO_PROYECTO.md`), el formato de
  archivos y el orden de las etapas.
- Esta bitácora y `datos/LEEME.md`, a partir de los archivos y de la salida de `navegacion.py`.

**Cómo se verificó:**

- Compensación del BMP280 contra el ejemplo de la hoja de datos de Bosch. `python navegacion.py
  metodos` da T = 25,0825 °C (esperado ~25,08) y P = 100 653,2668 Pa (esperado ~100 653,27).
- Pruebas del comando `metodos`: el orden observado del error es 1,00 para el rectángulo y 2,00
  para el trapecio (teoría: 1 y 2). El trapecio propio difiere de `np.trapezoid` en 2,44·10⁻¹⁵ m/s.
  La interpolación lineal tiene un error máximo de 1,97·10⁻³, igual a la cota h²/8·max|f''|. La
  bisección de x³ − 2x − 5 coincide con `np.roots` en 2,6·10⁻¹¹.
- Datos reales: 0 muestras perdidas y 200,000 Hz al inicio y al final en 95 min. Las pruebas del
  simulador solo dicen que el código hace lo que se espera con datos inventados; los datos reales
  dicen si el firmware funciona.

**Errores de la IA que comprobamos:**

1. **El chip no era el que suponía el plan.** El plan inicial hecho con IA (`CONTEXTO_PROYECTO.md`,
   sección 2 y el `meta.json` de ejemplo con `"chip_whoami": "0x71"`) suponía que el GY-91 traía un
   MPU-9250 con magnetómetro AK8963 (WHO_AM_I = 0x71). Leímos el registro WHO_AM_I y dio **0x70**:
   es un MPU-6500, **sin magnetómetro**. Así que el rumbo solo puede salir del giroscopio, y su error
   crece con el tiempo. Las dos sesiones reales tienen `"chip_whoami": "0x70"` en `meta.json`.
2. **Carpetas con fecha sin reloj.** El mismo plan proponía nombrar cada sesión
   `sesion_YYYYMMDD_HHMMSS` (`CONTEXTO_PROYECTO.md`, sección 3). El ESP32 no tiene reloj de tiempo
   real, así que no sabe la fecha. Se cambió a carpetas numeradas `sesion_NNN` en el commit
   `094b716` ("Formato: carpetas sesion_NNN..."), y la fecha se anota en la bitácora. Por lo mismo,
   los archivos de la microSD tienen fecha 01/01/1980.
3. **El antirrebote del firmware no alcanzó.** El firmware hecho con IA filtra 200 ms en la
   interrupción del botón. Con el pulsador sin soldar hubo una doble pulsación a 0,40 s, que pasó
   ese filtro. Se agregó el filtro de 1 s en Python.

## 6. Pendientes del avance

- [x] **Seis caras.** Hecho el 24/11/2026 (`caras_2026-11-24`, sección 2.3). Es la calibración
  oficial: `resultados/calibracion.json`.
- [ ] **Soldar el pulsador.** La protoboard ya va fijada dentro de una caja (sesión de caras), pero
  el pulsador sigue sin soldar (rebote).
- [ ] **Ascensor:** edificio de ≥ 5 pisos, ≥ 10 recorridos de subida y bajada con paradas
  intermedias, botón en cada cierre y apertura de puerta. Medir la altura de cada piso con
  flexómetro y llenar `datos/pisos.csv`.
- [ ] **Fotos del montaje** en `fotos/`.
- [ ] Completar los TODO de este documento y de `datos/LEEME.md`.

## 7. Plan para el segundo parcial

- **Metro:** ≥ 3 viajes de varias estaciones, en distintos días o sentidos, con el botón en cada
  salida y llegada. Llenar `datos/estaciones.csv` (estaciones, coordenadas y distancia de cada
  tramo, con fuente verificable) y `datos/viajes.csv` (estación inicial y sentido de cada viaje).
- **Experimento propio** que ponga a prueba un límite del sistema. TODO: elegir cuál.
- **Montaje definitivo con pilas** (4 pilas AA con interruptor) en la caja rígida.
- **Comparación con el trazado real:** distancia y velocidad por tramo, trayectoria sobre el mapa
  frente a la línea del metro, dispersión entre viajes, con y sin barómetro.
