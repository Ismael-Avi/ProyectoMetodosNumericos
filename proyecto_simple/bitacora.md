# Bitácora del proyecto: navegación inercial en el Metro de Quito

Métodos Numéricos, EPN. Este archivo es la bitácora escrita, para leer. `bitacora.csv` es el
registro automático que deja `navegacion.py` cada vez que se corre un comando, y se conserva aparte.

Todos los números de este documento salen de los archivos de `datos/` o de correr `navegacion.py`
(corridas del 24/11/2026; las del ascensor, del 26/11/2026). Lo que falta está marcado con **TODO**.

## 1. Integrantes

- Cesar Avila
- Edison Ogonaga
- Sebastian Reyes

## 2. Experimentos

Formato de los datos y configuración del sensor: [`datos/LEEME.md`](datos/LEEME.md).

### 2.1 `sesion_002`: reposo corto de prueba

| Campo | Valor |
|---|---|
| Fecha y hora | 21/11/2026, aprox. 10:15 (el ESP32 no tiene reloj; la carpeta no lleva fecha) |
| Lugar | casa de Cesar |
| Superficie | mesa nivelada |
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
giroscopio tiene unos -4,5 °/s de sesgo en x. No sabemos qué pasó en los instantes en que el
detector marca movimiento; probablemente golpes o movimiento de la mesa.

### 2.2 `reposo_90min_2026-11-21_1915-2049`: reposo largo

| Campo | Valor |
|---|---|
| Fecha y hora | 21/11/2026, de 19:15 a 20:49 |
| Lugar | casa de Ismael |
| Superficie | mesa nivelada (la protoboard estaba inclinada sobre ella) |
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
| Fecha y hora | 24/11/2026, aprox. 18:30 (tercer intento) |
| Lugar | casa de Cesar |
| Superficie | mesa nivelada |
| Montaje | protoboard fijada dentro de una caja |
| Orientación | las seis caras (~1 min cada una) y después 8 posiciones inclinadas (5° a 22°; medido con `caras`: 5,2° a 22,3°) |
| Alimentación | power bank |
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
  No da 9,77 exacto porque las caras quedaron inclinadas 2,8° a 3,7° (calibrado; 2,6° a 4,8° sin
  calibrar). En cada cara, |g| calibrado coincide con 9,77/cos θ: por ejemplo x+ con 3,6° da
  9,7893 (medido 9,7891) e y− con 2,8° da 9,7817 (medido 9,7817).
- **Prueba independiente**, con las 8 posiciones inclinadas que no se usaron para calibrar: |g| sin
  calibrar va de 9,661 a 10,127 m/s²; calibrado, de 9,770 a 9,799 m/s². La desviación estándar
  entre posiciones baja de 0,1693 a 0,0092 m/s² (18 veces menor). Error máximo calibrado:
  0,0286 m/s².
- Sesgo del giroscopio (promedio de las caras): (-4,503; -1,766; -0,204) °/s, con una variación
  entre caras de 0,005 a 0,008 °/s. Coincide con el de los reposos del 21/11.
- Aplicando esta calibración a la aceleración media de los reposos del 21/11 (cálculo aparte, con
  los números de `reposo`): |g| = 9,776 m/s² en `sesion_002` (antes 10,113) y 9,755 m/s² en el
  reposo de 90 min (antes 10,099).

**Figuras y reportes:** `resultados/caras_2026-11-24_caras.png` (|g| antes y después de calibrar
en cada tramo quieto, con la línea de 9,77), `resultados/caras_2026-11-24_senales.png` (se ven las seis caras como
escalones de ±9,8 m/s² en un eje y después las 8 posiciones inclinadas),
`resultados/caras_2026-11-24_caras.txt`, `resultados/caras_2026-11-24_verificar.txt` y
`resultados/calibracion.json`.

**Observaciones:**

- Las 8 posiciones calibradas quedan todas un poco por encima de 9,77 (entre −0,0005 y +0,0286
  m/s², +0,016 en promedio). Causa: en las seis caras el sensor quedó inclinado: 2,6° a 4,8° sin calibrar (2,8° a 3,7° ya calibrado). Así el eje principal no mide g sino g·cos θ, la escala sale un poco baja (por un factor ~cos θ) y todo |g| calibrado queda un poco alto, cerca de 9,77/cos θ. Con el promedio de ~3,3° se predice 9,77·(1/cos θ − 1) ≈ 9,77·(1 − cos θ) ≈ 0,017 m/s², igual a lo
  observado. Con ~4° serían 0,024 m/s². Para que la escala salga bien, las caras tienen que quedar
  más verticales.
- Dentro de la caja, la temperatura del BMP280 subió de 24,6 a 26,0 °C durante los 12 min, y la
  presión subió ~20 Pa (de 73 074,6 a 73 094,1 Pa, promedio del primer y del último minuto).
- **Aprendizaje de los intentos anteriores:** el primero (mediodía del 24/11) se descartó y no está
  en el proyecto: faltó la cara y− y las caras quedaron inclinadas hasta 17°. El segundo (~18:00)
  está en `datos/caras_2026-11-24v1` (sección 2.4): se pudo calibrar, pero con caras inclinadas
  3° a 9° y sin posiciones inclinadas, así que no había cómo comprobar la calibración.
  En el segundo y en el tercero la protoboard ya iba fijada dentro de una caja. En el tercero las
  caras quedaron menos inclinadas (2,6° a 4,8° contra 3° a 9°) y se agregaron las 8 posiciones
  inclinadas para comprobar la calibración.

### 2.4 `caras_2026-11-24v1`: segundo intento de seis caras (comparación)

| Campo | Valor |
|---|---|
| Fecha y hora | 24/11/2026, aprox. 18:00 |
| Lugar | casa de Cesar |
| Superficie | mesa nivelada |
| Montaje | protoboard fijada dentro de una caja |
| Orientación | solo las seis caras, sin posiciones inclinadas. Caras inclinadas 3,0° a 9,0° (sin calibrar) |
| Alimentación | power bank |
| Duración | 481,5 s (8,0 min) |
| Procedimiento | apoyar la caja en cada una de sus seis caras. Sin pulsador |

No es la calibración oficial: se usa para comprobar que la calibración se repite. Al final se volvió a
correr `caras` sobre `caras_2026-11-24`, y `resultados/calibracion.json` quedó idéntico byte a byte
al anterior.

**Comandos:**

```
python navegacion.py verificar datos/caras_2026-11-24v1
python navegacion.py caras     datos/caras_2026-11-24v1
python navegacion.py caras     datos/caras_2026-11-24      (para dejar la calibración oficial)
```

**Resultados principales:**

- Muestras: 96 306 del IMU y 12 039 del barómetro, 0 perdidas. 200,000 Hz al inicio y al final.
- 8 tramos quietos: las 6 caras y 2 repeticiones de caras (z+ y x+). No hay posiciones inclinadas,
  así que no hay prueba independiente de verdad.
- Comparación con la calibración oficial:

  | Eje | Sesgo v1 (m/s²) | Sesgo oficial (m/s²) | Diferencia | Escala v1 | Escala oficial | Diferencia |
  |---|---|---|---|---|---|---|
  | x | +0,1285 | +0,1067 | +0,022 | 0,99268 | 0,99916 | −0,0065 |
  | y | −0,0145 | −0,0178 | +0,003 | 1,00058 | 1,00065 | −0,0001 |
  | z | +0,2280 | +0,2240 | +0,004 | 1,00668 | 1,01109 | −0,0044 |

- Las escalas de x y z salen más bajas en v1 porque sus caras x y z quedaron más inclinadas
  (7,1°–7,6° y 5,8°–7,2° calibrado, contra 3,0°–3,6° en la oficial). Es el mismo efecto de cos θ:
  para x se predice una razón cos 7,35° / cos 3,6° = 0,9937, y se mide 0,99268 / 0,99916 = 0,9935.
  En y, las caras quedaron igual de inclinadas en los dos intentos (~3,5°) y la escala coincide.
- Por la misma razón, en v1 el |g| calibrado de sus propias caras queda en 9,786 a 9,856 m/s²
  (hasta +0,086 sobre 9,77).
- La calibración oficial aplicada a los 8 tramos de v1 (cálculo aparte) da |g| de 9,771 a 9,813 m/s²;
  sin calibrar, iban de 9,645 a 10,156 m/s².
- Sesgo del giroscopio: (-4,560; -1,731; -0,282) °/s, parecido al de la oficial.

**Figuras y reportes:** `resultados/caras_2026-11-24v1_caras.png`,
`resultados/caras_2026-11-24v1_senales.png`, `resultados/caras_2026-11-24v1_caras.txt` y
`resultados/caras_2026-11-24v1_verificar.txt`.

### 2.5 `ascensor_2026-11-26`: ascensor

| Campo | Valor |
|---|---|
| Fecha y hora | 26/11/2026 (TODO: hora) |
| Lugar | edificio de PB + 5 pisos, con acceso solo a PB, 1, 3 y 5 (TODO: nombre del edificio) |
| Superficie | piso del ascensor |
| Montaje | caja apoyada en el piso del ascensor |
| Orientación | inclinación de 7,0° respecto a la vertical (medida con `ascensor`, calibrado) |
| Alimentación | power bank por el pin V5 |
| Duración | 315,0 s (5,3 min); se usa hasta 305 s |
| Procedimiento | un pulso de inicio, reposo, y 13 recorridos con un pulso al cerrarse la puerta y otro al abrirse |

**Los 13 recorridos reales** (detectados con el acelerómetro y el barómetro, no con los pulsos):

| # | Recorrido | # | Recorrido | # | Recorrido |
|---|---|---|---|---|---|
| 1 | 0→1 | 6 | 1→5 | 11 | 3→5 |
| 2 | 1→3 | 7 | 5→0 | 12 | 5→3 |
| 3 | 3→0 | 8 | 0→3 | 13 | 3→1 (cortado, no se usa) |
| 4 | 0→5 | 9 | 3→1 | | |
| 5 | 5→1 | 10 | 1→3 | | |

**Alturas de los pisos** (`datos/pisos.csv`, flexómetro, 26/11/2026): PB 0,00; 1: 4,90; 2: 7,42;
3: 9,90; 4: 12,34; 5: 14,86 m. **Discrepancia en PB→1:** el barómetro y el acelerómetro dicen
que PB→1 mide ~5,7 m (barómetro 5,73 m en el recorrido 1), mientras los tramos 1→3 y 3→5 coinciden
con la cinta a ~0,1 m. Se va a volver a medir PB→1; por ahora `pisos.csv` deja 4,90 m (anotado en
la columna `fuente`).

**Problemas de la sesión y cómo se arreglaron (sin tocar los archivos originales):**

- **El recorrido 13 se cortó al llegar**: se apagó el dispositivo sin reposo final. Se usa la sesión
  solo hasta 305 s (opción nueva `--hasta 305`).
- **El primer pulso (0,3 s) fue marca de inicio**, no cierre de puerta. El ascensor arrancó a 7,8 s.
- **Rebotes:** `eventos.csv` tiene 33 pulsaciones. El filtro de 1 s deja 21, porque hay pulsos
  dobles a 0,2–0,35 s, que pasan el antirrebote de 200 ms del firmware.
- **Faltan pulsos** en los recorridos 10, 12 y 13.
- Con eso no se pueden armar pares cierre/apertura. Se escribió a mano
  `datos/ascensor_2026-11-26/eventos_corregidos.csv`, con 12 pares (segundos desde la primera muestra
  del IMU, `t_us = t_us[0] + s·10⁶`): (6,8; 19,2) (30,1; 40,5) (51,9; 67,4) (78,1; 97,9)
  (108,4; 124,5) (134,9; 150,4) (161,2; 181,7) (192,3; 207,1) (217,8; 229,9) (239,3; 248,0)
  (262,5; 273,7) (283,1; 295,8). **Los pulsos 6,8; 239,3; 248,0 y 283,1 s son inventados:** salen
  del arranque y la parada que se ven en el acelerómetro (para los cierres, ~1 s antes del
  arranque). Los demás son pulsos de `eventos.csv`. Si existe `eventos_corregidos.csv`,
  `navegacion.py` lo usa en vez de `eventos.csv` y lo dice en el reporte.
- **El piso más cercano falla:** la última parada (piso 3, medida a 11,4 m por la deriva del
  barómetro y la discrepancia de PB→1) quedaba asignada al piso 4. Se escribió
  `datos/ascensor_2026-11-26/paradas.csv` con el piso de cada parada: 0, 1, 3, 0, 5, 1, 5, 0, 3, 1,
  3, 5, 3 (la primera es el reposo inicial).

**Comandos:**

```
python navegacion.py verificar datos/ascensor_2026-11-26
python navegacion.py ascensor  datos/ascensor_2026-11-26 --hasta 305
```

`verificar` se corrió sobre todo el registro (las pérdidas se miden en todo el registro).

**Resultados principales** (resumen en `RESULTADOS_AVANCE.md`, sección 5):

- Muestras: 63 004 del IMU y 7 876 del barómetro, 0 perdidas. 200,000 Hz al inicio y al final
  (barómetro 25,000 Hz). Jitter del periodo del IMU: 1,0 µs.
- Reposo inicial de 0 a 5,8 s (hasta 1 s antes del primer cierre). |g| calibrado 9,7592 m/s².
  Sesgo vertical que queda tras calibrar: −0,0108 m/s². **Ruido 0,0948 m/s²**, 5 a 7 veces el de la
  mesa, porque el piso del ascensor vibra.
- Error RMS de altura en las 13 paradas: 308 m sin corrección (rectángulo y trapecio), 68 m
  restando el sesgo, 1,43 m (rectángulo) y 1,41 m (trapecio) con ZUPT, 1,00 m con el barómetro solo
  y **0,99 m con la fusión**.
- 23 cruces de pisos intermedios por bisección: todos los que había que encontrar.
- Barómetro y acelerómetro con ZUPT coinciden a 0,32 m o menos en 8 de los 12 desniveles. 1→3 y
  3→5 coinciden con la cinta. PB→1 no coincide (ver arriba).
- **Deriva del barómetro ~0,7 m en 5 min:** piso 3, de 10,70 m (40 s) a 11,42 m (296 s); piso 5, de
  15,77 m (98 s) a 16,59 m (274 s).

**Figuras y reportes:** `resultados/ascensor_2026-11-26_senales.png`,
`resultados/ascensor_2026-11-26_ascensor.png`, `resultados/ascensor_2026-11-26_ascensor_error.png`,
`resultados/ascensor_2026-11-26_verificar.txt`, `resultados/ascensor_2026-11-26_ascensor.txt`.

**Observaciones:**

- **Pulsos de cierre tardíos en los recorridos 2, 3 y 11.** El ascensor empezó a acelerar a 29,84,
  51,38 y 261,98 s, o sea 0,26, 0,52 y 0,52 s antes de los pulsos de cierre (30,1, 51,9 y 262,5 s).
  La ventana de integración empieza con el ascensor ya en movimiento y pierde 0,17, 0,32 y
  0,38 m/s. Por eso el acelerómetro con ZUPT se equivoca en esos recorridos (4,05 en vez de 5,00 m;
  −7,99 en vez de −9,90; 2,75 en vez de 4,96). Integrando desde 3 s antes del pulso, la velocidad
  al llegar baja a −0,04 a −0,10 m/s, como en los demás recorridos. Se dejaron los pulsos
  originales. **Aprendizaje:** pulsar antes de que se cierre la puerta, no cuando ya se mueve.
- Sin ZUPT, la velocidad acumula ~−0,07 m/s en cada recorrido y algo más en las paradas. El error
  observado restando el sesgo (154 m al final) es mucho mayor que el predicho por el ruido (21 m):
  el sesgo cambia durante la sesión.
- El detector de quietud ve como "quieto" solo el 58 % al 92 % de cada parada (vibraciones, gente
  entrando y saliendo). Sin los pulsos, el ZUPT no habría encontrado bien las paradas.

## 3. Problemas encontrados y cómo se resolvieron

| Problema | Qué pasaba | Cómo se resolvió |
|---|---|---|
| Rebote del pulsador sin soldar | Una pulsación quedaba registrada dos veces. En el reposo de 90 min, la pulsación final aparece dos veces a 0,40 s | Antirrebote de 200 ms en el firmware (interrupción `isrBoton`) y, como no alcanzó, filtro de 1 s en Python (`REBOTE_BOTON_S`): las pulsaciones a menos de 1 s de la anterior se ignoran. Solución definitiva: soldar el pulsador (pendiente) |
| Abrir el Serial Monitor reinicia el ESP32 | Al abrir el monitor serie, el adaptador USB reinicia el ESP32. El firmware empieza a grabar al encender y crea una carpeta `sesion_NNN` nueva en cada arranque, con `t_us` desde cero | Por protocolo: no abrir el Serial Monitor durante una grabación. Después de cada grabación se verifica que haya una sola carpeta y que `seq` sea continuo (`verificar`) |
| Cortar la energía parte la sesión en dos carpetas | Cada encendido crea una carpeta nueva. Si la energía se corta a mitad de un experimento, quedan dos carpetas y el reloj `t_us` vuelve a empezar. Pasaba porque la power bank se apagaba al estar descargada | Cargar la power bank antes de grabar. En el reposo de 95 min se verificó que no hubo cortes: una sola carpeta, `seq` continuo (0 muestras perdidas) e intervalo máximo entre muestras de 5,007 ms |
| Deriva de la presión por el clima | En el reposo de 90 min la presión subió 0,80 hPa sin mover el dispositivo. Equivale a 9,65 m de altura falsa | Medir P0 (la presión de referencia) en el reposo inicial de cada sesión, en vez de usar un valor fijo |
| Calibración simulada con aspecto de real | La única `resultados/calibracion.json` venía de la sesión **simulada** `caras` (ver `bitacora.csv`), y `ascensor` y `metro` la cargaban sin avisar. Con datos reales se habría aplicado un sesgo y una escala inventados | El 23/11/2026 se movió a `resultados/simulados/calibracion_simulada.json`. `navegacion.py` solo carga `resultados/calibracion.json`, que tiene que salir de una sesión real de `caras`; si falta, `ascensor` y `metro` avisan y siguen sin calibrar. Si `caras` procesa una sesión simulada, guarda en `resultados/simulados/`. Desde el 24/11/2026 `resultados/calibracion.json` sale de la sesión real `caras_2026-11-24` |
| Caras inclinadas o incompletas en la calibración | En el primer intento faltó la cara y− y las caras quedaron inclinadas hasta 17°. En el segundo (`caras_2026-11-24v1`), inclinadas 3° a 9° y sin posiciones para comprobar | Fijar la protoboard dentro de una caja y apoyar la caja en sus caras (desde el segundo intento); dejar las caras lo más verticales posible y agregar posiciones inclinadas para comprobar. El tercer intento (`caras_2026-11-24`) es la calibración oficial |
| Pulsos faltantes, dobles o de más en el ascensor | En `ascensor_2026-11-26` faltan pulsos en los recorridos 10, 12 y 13, hay rebotes que pasan el filtro del firmware, y el primer pulso fue una marca de inicio. No se pueden armar los pares cierre/apertura | `eventos_corregidos.csv` en la carpeta de la sesión, escrito a mano (4 pulsos sacados del acelerómetro). `navegacion.py` lo usa en vez de `eventos.csv` y lo dice. `eventos.csv` queda tal como salió de la microSD |
| Recorrido cortado al final | El recorrido 13 del ascensor terminó sin reposo final (se apagó al llegar). Sin reposo final el ZUPT no tiene con qué corregir | Opción `--hasta T` para usar la sesión solo hasta T segundos (305 s en el ascensor) |
| Parada asignada al piso equivocado | Con el "piso más cercano", la última parada del ascensor (piso 3, medida a 11,4 m) quedaba en el piso 4 | `paradas.csv` en la carpeta de la sesión, con el piso de cada parada. Si existe, se usa como referencia |
| Pulso de cierre después de que el ascensor arranca | En 3 recorridos se pulsó 0,3–0,5 s tarde; la integración pierde la primera parte de la aceleración (hasta 0,38 m/s) | Se dejó así y se anotó (sección 2.5). Para las próximas grabaciones: pulsar antes de que se cierre la puerta |
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
- **g = 9,77 m/s² para Quito.** Es el valor del enunciado. Lo comprobamos con la gravedad normal GRS80
  en el ecuador (9,7803267715 m/s²; a 0,2° S la corrección por latitud es despreciable) menos la
  corrección de aire libre a 2850 m (0,3086 mGal/m × 2850 m ≈ 0,0088 m/s²): ~9,7715 m/s². La
  diferencia con 9,77 es 0,0015 m/s². El cálculo está en el README.
- **Un solo script en Python (`navegacion.py`).** La primera versión (`procesamiento/`) tenía 32
  archivos de Python sin contar las pruebas. Se rehízo en un solo archivo, con comandos (`verificar`, `reposo`, `caras`, `metodos`,
  `ascensor`, `metro`), para que cada integrante pueda leerlo de principio a fin y defenderlo. Los
  métodos numéricos del curso (rectángulo, trapecio, interpolación lineal, bisección) están hechos a
  mano.

## 5. Uso de IA

**Qué se hizo con IA** (en los commits figura Claude como coautor: Claude Fable 5.2 en
`procesamiento/` y en el primer firmware de PlatformIO, `firmware/`; Claude Opus 5.5 en
`proyecto_simple/`. `registrador_v01.ino` está en C++, se escribió con ayuda de IA (Claude) en
Arduino IDE 2.3.11, con el paquete esp32 de Espressif 3.3.12, y se probó en el dispositivo; se copió
sin cambios al repo):

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
- [x] **Ascensor.** Grabado el 26/11/2026 (`ascensor_2026-11-26`, sección 2.5): 12 recorridos
  útiles en un edificio de PB + 5 pisos; `datos/pisos.csv` lleno.
- [ ] **Volver a medir PB→1** (cinta 4,90 m; barómetro y acelerómetro ~5,7 m) y actualizar
  `datos/pisos.csv`.
- [ ] **Fotos del montaje** en `fotos/`.
- [ ] **Presentación** en `presentacion/`. Pendiente: se hará después del ascensor.
- [ ] Completar los TODO de este documento y de `datos/LEEME.md`.

## 7. Plan para el segundo parcial

- **Metro:** ≥ 3 viajes de varias estaciones, en distintos días o sentidos, con el botón en cada
  salida y llegada. Llenar `datos/estaciones.csv` (estaciones, coordenadas y distancia de cada
  tramo, con fuente verificable) y `datos/viajes.csv` (estación inicial y sentido de cada viaje).
- **Experimento propio** que ponga a prueba un límite del sistema. Pendiente: se definirá después
  del ascensor.
- **Montaje definitivo con pilas** (4 pilas AA con interruptor) en la caja rígida.
- **Comparación con el trazado real:** distancia y velocidad por tramo, trayectoria sobre el mapa
  frente a la línea del metro, dispersión entre viajes, con y sin barómetro.
