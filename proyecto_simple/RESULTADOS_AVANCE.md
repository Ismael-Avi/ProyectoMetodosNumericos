# Resultados del avance: caracterización del dispositivo

Navegación inercial en el Metro de Quito. Métodos Numéricos, EPN.

**Alcance del avance:** reposo, calibración de seis caras y ascensor (sección 5). El metro va en el
segundo parcial.

**Dispositivo:** ESP32 + GY-91 (acelerómetro y giroscopio MPU-6500, barómetro BMP280). Guarda los
datos crudos en una microSD: acelerómetro y giroscopio a 200 Hz, barómetro a 25 Hz. Todo se procesa
después con `navegacion.py`. Las figuras están en `resultados/`.

## 1. Reposo corto (`sesion_002`, 21/11/2026, ~10:15)

**Qué se hizo:** primera prueba del firmware. 142 s en reposo sobre una mesa, alimentado por el USB
de la laptop.

**Números clave:**
- 0 muestras perdidas; 200,000 Hz al inicio y al final.
- Sesgo del giroscopio: (-4,496; -1,794; -0,212) °/s.
- Ruido: 0,018 m/s² en el acelerómetro y ~0,06 °/s en el giroscopio.
- Sin calibrar, |a| = 10,113 m/s² en vez de 9,77.

**Figura:** `resultados/sesion_002_reposo.png`.
**Qué mirar:** |a| es una banda plana alrededor de 10,1 m/s², por encima de la línea de 9,77: ese
desfase es el error del acelerómetro que corrige la calibración. Las franjas naranjas (18; 76,5;
79 y 105 s) son los únicos instantes en que el detector vio movimiento: picos cortos; no sabemos qué
fueron, probablemente golpes o movimiento de la mesa. |ω| no está en 0 sino en ~4,8 °/s: es el sesgo del giroscopio.

## 2. Reposo largo (`reposo_90min_2026-11-21_1915-2049`, 21/11/2026, 19:15–20:49)

**Qué se hizo:** 94,9 min en reposo sobre una mesa (protoboard inclinada ~9°), con power bank. El
pulsador marcó el inicio y el fin; se analiza solo lo que hay entre las dos pulsaciones, quitando
5 s a cada lado.

**Números clave:**
- 1 138 860 muestras del IMU, **0 perdidas**; **200,000 Hz al inicio y al final**.
- Detector de quietud: quieto el 100 % del tiempo.
- Sesgo del giroscopio: (-4,513; -1,823; -0,163) °/s. Ruido del acelerómetro: 0,013 m/s².
- Deriva en 95 min:
  - sesgo de gx de -4,452 a -4,540 °/s;
  - presión +0,80 hPa (9,65 m de altura falsa);
  - temperatura del BMP280 -0,78 °C.

**Figuras y qué mirar:**
- `resultados/reposo_90min_2026-11-21_1915-2049_senales.png`: las tres aceleraciones y los tres
  giros son líneas planas durante hora y media. Mirar también la presión, que sube ~80 Pa sin que
  el dispositivo se mueva (es el clima), y la temperatura, que sube ~1 °C en los primeros 2 min y
  se estabiliza hacia el minuto 18.
- `resultados/reposo_90min_2026-11-21_1915-2049_deriva.png`: promedios cada 10 min. Mirar:
  - **gx** (azul, arriba): baja más rápido en los primeros 20 min, cuando cambia la temperatura
    (-0,056 de los -0,088 °/s totales), y después sigue bajando despacio, unos -0,005 °/s cada 10 min;
  - **presión**: sube de forma continua.
- `resultados/reposo_90min_2026-11-21_1915-2049_reposo.png`: no aparece ninguna franja naranja, o
  sea que el programa dice correctamente que el dispositivo no se movió.

## 3. Calibración de seis caras (`caras_2026-11-24`, 24/11/2026). Calibración oficial

**Qué se hizo:** la protoboard fijada dentro de una caja, alimentada con una power bank. Se
apoyó la caja ~1 min en cada una de sus seis caras y después en 8 posiciones inclinadas (5° a 22°).
Las posiciones inclinadas **no se usan para calibrar**: sirven para comprobar la calibración.

**Cómo se calcula:** con el eje hacia arriba se mide a+ = escala·g + sesgo; hacia abajo,
a− = −escala·g + sesgo. Entonces sesgo = (a+ + a−)/2 y escala = (a+ − a−)/(2g).

**Números clave:**

| Eje | Sesgo (m/s²) | Escala |
|---|---|---|
| x | +0,1067 | 0,99916 |
| y | −0,0178 | 1,00065 |
| z | +0,2240 | 1,01109 |

En las 8 posiciones de prueba:

| | Sin calibrar | Calibrado |
|---|---|---|
| \|g\| (m/s²) | 9,661 a 10,127 | 9,770 a 9,799 |
| Variación entre posiciones (desv. est.) | 0,1693 m/s² | 0,0092 m/s² (18 veces menor) |

**Figura principal:** `resultados/caras_2026-11-24_caras.png` (los números están en
`resultados/caras_2026-11-24_caras.txt`).
**Qué mirar:** cada columna es un tramo quieto: primero las seis caras, después las 8 posiciones
inclinadas ("extra"). Los círculos rojos (sin calibrar) están dispersos entre 9,66 y 10,13 m/s²;
los cuadrados verdes (calibrado) quedan todos juntos, justo encima de la línea de 9,77. Lo
importante son las columnas "extra", que no se usaron para calibrar.

**Por qué los verdes quedan un poco arriba de 9,77 (+0,016 m/s² en promedio):** en las seis caras
el sensor quedó inclinado 2,6° a 4,8° (sin calibrar; 2,8° a 3,7° ya calibrado). El eje principal
no mide g sino g·cos θ, así que la escala sale un poco baja y |g| calibrado queda un poco alto:
9,77·(1 − cos θ) ≈ 0,017 m/s² con θ ≈ 3,3°, y 0,024 m/s² con 4°. Se confirma cara por cara: en x+
(3,6°) se predice 9,7893 y se mide 9,7891.

**Figura de apoyo:** `resultados/caras_2026-11-24_senales.png`.
**Qué mirar:** en la gráfica de aceleración, las seis caras son seis escalones de ~±9,8 m/s², cada
uno en un eje distinto (x, y, z hacia arriba y hacia abajo). Después de ~410 s vienen las 8
posiciones inclinadas: la gravedad se reparte entre dos o tres ejes. Los picos del giroscopio son
los momentos en que se giró la caja; entre picos está quieta.

## 4. Coherencia de los datos

Chequeos que se cumplen con los datos reales:

- **Sin pérdidas en 90 min:** 0 muestras perdidas y 200,000 Hz al inicio y al final en 95 min.
  Cumple el requisito de 90 min de registro continuo (y el de ≥ 100 Hz).
- **Presión coherente con Quito:** ~731 hPa (732,7; 731,3; 730,3 y 730,8 hPa en las cuatro sesiones). A nivel
  del mar serían ~1013 hPa. Con la atmósfera estándar, 731 hPa corresponde a unos 2650–2680 m.
  Es el orden de la altitud de Quito (~2850 m). La atmósfera estándar no representa el clima real
  del día ni el del trópico, y no sabemos la altitud exacta del lugar (TODO).
- **La presión cambia con el clima:** subió 0,80 hPa en 90 min sin mover el dispositivo, unos
  9,7 m de altura falsa. **Por eso se mide la presión de referencia P0 al inicio de cada sesión.**
- **Sesgo del giroscopio repetible:**
  - en x es ~-4,5 °/s en los tres registros: -4,496 °/s (reposo corto), -4,513 °/s (reposo de 90 min)
    y -4,503 °/s (caras, otro día);
  - deriva lento: -0,047 (°/s)/h en el reposo largo.
- **La gravedad no cambia al girar el dispositivo:**
  - sin calibrar, |g| va de 9,66 a 10,13 m/s² según la posición;
  - calibrado, va de 9,770 a 9,799 m/s² en 8 posiciones que no se usaron para calibrar (variación
    18 veces menor);
  - aplicando la misma calibración a los reposos del 21/11 (otro día, otro montaje) da 9,776 y
    9,755 m/s².
- **Calibraciones reproducibles:** se calibró dos veces el 24/11. La oficial es `caras_2026-11-24`
  (~18:30). La otra es `caras_2026-11-24v1` (~18:00): solo seis caras, más inclinadas (3° a 9°).

  | Eje | Sesgo v1 (m/s²) | Sesgo oficial (m/s²) | Escala v1 | Escala oficial |
  |---|---|---|---|---|
  | x | +0,1285 | +0,1067 | 0,99268 | 0,99916 |
  | y | −0,0145 | −0,0178 | 1,00058 | 1,00065 |
  | z | +0,2280 | +0,2240 | 1,00668 | 1,01109 |

  - Los sesgos coinciden: z y y difieren en 0,004 y 0,003 m/s², x en 0,022 m/s².
  - En v1, las escalas de x y z salen ~0,5 % más bajas porque esas caras quedaron más inclinadas
    (~7° contra ~3,5°). Es el efecto de cos θ: para x se predice 0,9937 y se mide 0,9935. En y la
    inclinación fue igual en los dos intentos y la escala coincide (diferencia 0,0001).
  - Aplicada a los tramos de v1, la calibración oficial da |g| de 9,771 a 9,813 m/s² (sin
    calibrar: 9,645 a 10,156).
  - Figura: `resultados/caras_2026-11-24v1_caras.png`, igual a la de la oficial.
- **Métodos numéricos verificados:**
  - el BMP280 reproduce el ejemplo de la hoja de datos (25,08 °C y 100 653,27 Pa);
  - el rectángulo converge con orden 1 y el trapecio con orden 2 (`resultados/metodos_convergencia.png`:
    dos rectas, la del trapecio con el doble de pendiente).

## 5. Ascensor (`ascensor_2026-11-26`, 26/11/2026)

**Qué se hizo:** la caja en el piso del ascensor, alimentada con una power bank por el pin V5. El
edificio tiene PB y 5 pisos, pero solo hay acceso a PB, 1, 3 y 5. Se hicieron 13 recorridos:

| # | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Pisos | 0→1 | 1→3 | 3→0 | 0→5 | 5→1 | 1→5 | 5→0 | 0→3 | 3→1 | 1→3 | 3→5 | 5→3 | 3→1 |

```
python navegacion.py verificar datos/ascensor_2026-11-26
python navegacion.py ascensor  datos/ascensor_2026-11-26 --hasta 305 --recorridos 1,2,3,4,5,6,7,8,9,11
```

**Alturas de los pisos** (`datos/pisos.csv`, flexómetro): PB 0,00; 1: 4,90; 2: 7,42; 3: 9,90;
4: 12,34; 5: 14,86 m.

### 5.1 Pulsos y recorridos evaluados

`eventos.csv` tiene 33 pulsaciones (21 tras quitar rebotes). El primer pulso (0,3 s) fue una marca
de inicio, faltan pulsos en los recorridos 10, 12 y 13, y en los recorridos 2, 3 y 11 el pulso de
cierre llegó tarde: el ascensor empezó a acelerar 0,26 s, 0,52 s y 0,52 s antes. Por eso se usa
`eventos_corregidos.csv` (12 pares cierre/apertura). El programa lo usa en vez de `eventos.csv`,
que no se tocó.

| Recorrido | Cierre | Apertura | Estado de los pulsos |
|---|---|---|---|
| 1 | 6,8 s, estimado | original | se pulsó, pero al inicio (marca de inicio) |
| 2, 3, 11 | 28,8 / 50,4 / 261,0 s, adelantados | original | se pulsó, pero tarde |
| 4 a 9 | original | original | 100 % originales |
| 10 | 239,3 s, inventado | 248,0 s, inventado | nadie pulsó |
| 12 | 283,1 s, inventado | original | nadie pulsó el cierre |
| 13 | — | — | cortado al llegar: queda fuera con `--hasta 305` |

Los tiempos estimados salen del arranque que se ve en el acelerómetro, menos ~1 s (por ejemplo, en
el recorrido 2 el ascensor arranca a 29,84 s y el cierre se puso en 28,8 s).

**Criterio de selección: se eligieron por la calidad de los pulsos, decidida antes de ver los
errores, no por el error obtenido.** Si el pulso existió pero a destiempo, se corrige su tiempo y
el recorrido se evalúa (1, 2, 3, 11). Si nadie pulsó, el recorrido se descarta (10 y 12). **Se
evalúan 10 recorridos: 1, 2, 3, 4, 5, 6, 7, 8, 9 y 11.** Los recorridos 10 y 12 se siguen
integrando, porque el ascensor sí se movió y la integración tiene que ser continua, pero no entran
en las tablas de error ni en los promedios. (No tenían errores grandes: con trapecio + ZUPT, +0,06 m
en el 10 y −0,13 m en el 12.)

### 5.2 Evaluación por desnivel

Se evalúa el **desnivel de cada recorrido** (altura de llegada − altura de salida), no la altura
absoluta de cada parada. La altura absoluta depende de la altura PB→1 de la cinta, que parece
estar mal (sección 5.4) y no se puede volver a medir. El desnivel entre los pisos 1, 3 y 5 no
depende de PB→1.

- **Validación principal:** los recorridos que no pasan por PB: **2, 5, 6, 9 y 11** (1→3, 5→1,
  1→5, 3→1, 3→5).
- **Aparte:** los que tocan PB (1, 3, 4, 7 y 8). Su desnivel real incluye PB→1 de la cinta.

**Desnivel de los 10 recorridos evaluados** (m; PB = toca la planta baja):

| # | Pisos | PB | Real (cinta) | Barómetro | Trapecio + ZUPT | Rectángulo + ZUPT | Fusión |
|---|---|---|---|---|---|---|---|
| 1 | 0→1 | sí | 4,90 | 5,74 | 5,41 | 5,41 | 5,71 |
| 2 | 1→3 | | 5,00 | 4,96 | 5,02 | 5,02 | 4,94 |
| 3 | 3→0 | sí | −9,90 | −10,30 | −10,48 | −10,47 | −10,28 |
| 4 | 0→5 | sí | 14,86 | 15,37 | 15,49 | 15,51 | 15,32 |
| 5 | 5→1 | | −9,96 | −9,79 | −10,10 | −10,10 | −9,74 |
| 6 | 1→5 | | 9,96 | 9,82 | 10,12 | 10,12 | 9,77 |
| 7 | 5→0 | sí | −14,86 | −15,49 | −15,40 | −15,39 | −15,47 |
| 8 | 0→3 | sí | 9,90 | 10,51 | 9,87 | 9,89 | 10,53 |
| 9 | 3→1 | | −5,00 | −4,87 | −5,02 | −5,02 | −4,85 |
| 11 | 3→5 | | 4,96 | 5,54 | 5,07 | 5,07 | 5,52 |

**Error del desnivel en la validación principal** (recorridos 2, 5, 6, 9 y 11; método − cinta):

| Método | Error medio (m) | Error RMS (m) | Error máx. (m) |
|---|---|---|---|
| Rectángulo sin corrección | −53,24 | 60,23 | 92,61 |
| Trapecio sin corrección | −53,24 | 60,22 | 92,60 |
| Trapecio − sesgo | −12,43 | 14,68 | 23,81 |
| Rectángulo − sesgo + ZUPT | +0,024 | 0,107 | 0,156 |
| **Trapecio − sesgo + ZUPT** | **+0,027** | **0,106** | **0,156** |
| Solo barómetro | +0,141 | 0,283 | 0,578 |
| Fusión acelerómetro + barómetro + ZUPT | +0,137 | 0,293 | 0,562 |

- **Con ZUPT, el acelerómetro mide el desnivel con un error RMS de 0,11 m** (máx. 0,16 m en
  desniveles de 5 a 10 m), sin barómetro.
- **Rectángulo y trapecio dan lo mismo** (0,107 contra 0,106 m). El error del método de
  integración es despreciable frente al error del sensor. Lo que cambia el resultado son las
  correcciones: sin corregir el error es de decenas de metros; restar el sesgo lo baja a ~15 m;
  el ZUPT, a 0,1 m.
- **El barómetro solo (0,28 m) y la fusión (0,29 m) quedan peor que el acelerómetro con ZUPT.**
  Casi todo viene del recorrido 11 (barómetro +0,58 m, acelerómetro +0,11 m), cerca del final de
  la sesión, cuando el barómetro ya derivó (sección 5.5). En recorridos de ~10–20 s con paradas en
  medio, el ZUPT corrige mejor que el barómetro.

**Recorridos que tocan PB** (1, 3, 4, 7, 8): error RMS de 0,50 m con trapecio + ZUPT, 0,51 m con
rectángulo + ZUPT, 0,62 m con el barómetro y 0,60 m con la fusión. El error medio con barómetro es
de +0,19 m. Es mayor que sin PB porque incluye la altura PB→1 de la cinta (sección 5.4).

### 5.3 Validación extra: solo los recorridos de pulsos 100 % originales

Se repitió la evaluación solo con los recorridos cuyos dos pulsos están en `eventos.csv`: 4, 5, 6,
7, 8 y 9. El programa los detecta solo, comparando `eventos_corregidos.csv` con `eventos.csv`
(tolerancia 0,1 s). Error RMS del desnivel (m):

| Grupo | Método | 10 evaluados | 6 originales |
|---|---|---|---|
| Sin PB | Trapecio + ZUPT | 0,106 (2, 5, 6, 9, 11) | 0,121 (5, 6, 9) |
| Sin PB | Rectángulo + ZUPT | 0,107 | 0,123 |
| Sin PB | Barómetro | 0,283 | 0,147 |
| Sin PB | Fusión | 0,293 | 0,191 |
| Con PB | Trapecio + ZUPT | 0,504 (1, 3, 4, 7, 8) | 0,477 (4, 7, 8) |
| Con PB | Barómetro | 0,616 | 0,586 |
| Con PB | Fusión | 0,595 | 0,570 |
| Todos | Trapecio + ZUPT | 0,365 | 0,348 |
| Todos | Rectángulo + ZUPT | 0,367 | 0,352 |
| Todos | Barómetro | 0,479 | 0,427 |
| Todos | Fusión | 0,469 | 0,425 |

**Los errores son parecidos: las correcciones de pulsos no sesgaron el resultado.** El
acelerómetro con ZUPT, que es el que depende de los pulsos, da 0,106 m con los 10 y 0,121 m con
los 6 originales. La diferencia más grande es la del barómetro sin PB (0,28 contra 0,15 m), y
viene del recorrido 11 (deriva del barómetro). El desnivel barométrico es el promedio de la presión
en las paradas, así que mover un pulso unas décimas de segundo casi no lo cambia.

### 5.4 Hallazgo: la altura PB→1 de la cinta (4,90 m) parece mal medida

Cada recorrido que toca PB da una estimación de PB→1: el |desnivel medido| menos la distancia de
la cinta entre el piso 1 y el otro piso del recorrido. Esa distancia sí coincide con los sensores
(sección 5.2).

| # | Pisos | Barómetro | Trapecio + ZUPT | Rectángulo + ZUPT | Fusión |
|---|---|---|---|---|---|
| 1 | 0→1 | 5,74 | 5,41 | 5,41 | 5,71 |
| 3 | 3→0 | 5,30 | 5,48 | 5,47 | 5,28 |
| 4 | 0→5 | 5,41 | 5,53 | 5,55 | 5,36 |
| 7 | 5→0 | 5,53 | 5,44 | 5,43 | 5,51 |
| 8 | 0→3 | 5,51 | 4,87 | 4,89 | 5,53 |
| **Media ± desv. est.** | | **5,50 ± 0,16** | **5,34 ± 0,27** | 5,35 ± 0,26 | 5,48 ± 0,17 |

Dos sensores independientes dicen que PB→1 mide ~5,3–5,5 m, no 4,90 m: el barómetro en los 5
recorridos (5,30 a 5,74 m) y el acelerómetro en 4 de los 5 (5,41 a 5,53 m; el recorrido 8 da
4,87). En el recorrido directo 0→1, el barómetro mide 5,74 m y el acelerómetro 5,41 m. En cambio,
los tramos 1→3 y 3→5 coinciden con la cinta a ~0,1 m. Lo más probable es un error al medir PB→1
con la cinta. No se puede volver a medir, así que `pisos.csv` deja 4,90 m y la evaluación
principal no usa PB.

### 5.5 Cruces de pisos, ruido y deriva del barómetro

- **Cruces de pisos (bisección):** se encontraron 23 cruces de pisos intermedios, todos los que
  había (se buscan los pisos entre el de salida y el de llegada). Por ejemplo, en el 0→5
  (recorrido 4) cruza los pisos 1, 2, 3 y 4 en 82,4; 84,4; 86,4 y 88,4 s: uno cada ~2,0 s, o sea
  ~1,25 m/s con pisos de ~2,5 m, que es la velocidad de crucero.
- **Datos:** 63 004 muestras del IMU y 7 876 del barómetro, 0 perdidas; 200,000 Hz al inicio y al
  final.
- **Ruido del acelerómetro en el ascensor: 0,095 m/s²** (reposo inicial de 0 a 5,8 s), 5 a 7 veces
  más que sobre la mesa (0,013–0,018), porque el piso del ascensor vibra. |g| calibrado
  9,759 m/s², inclinación 7,0°.
- **Deriva del barómetro: ~0,7 m en 5 min.** El mismo piso da alturas distintas con el tiempo:
  - piso 3: 10,70 m a los 40 s y 11,42 m a los 296 s (+0,72 m);
  - piso 5: 15,77 m a los 98 s y 16,59 m a los 274 s (+0,82 m).

  Equivale a ~6 Pa (1 Pa ≈ 0,12 m). El ruido de la altura barométrica en reposo es de 0,26 m
  (2,2 Pa).

### 5.6 Figuras

**`resultados/ascensor_2026-11-26_ascensor.png`** (figura principal). **Qué mirar:**
- Arriba, la altura: gris el barómetro, naranja la fusión, azul el acelerómetro con ZUPT (sin
  barómetro). Las líneas punteadas son los pisos de la cinta y los puntos negros, los cruces.
  Arriba de todo va el número de cada recorrido. Los recorridos 10 y 12, que no se evalúan, están
  en rojo y con fondo rosado.
  - En cada recorrido, las tres curvas suben o bajan lo mismo: es el desnivel de la tabla.
  - En las paradas sobre PB, la naranja y la gris quedan por encima de su línea, cada vez más
    hacia el final: es PB→1 más la deriva del barómetro. La azul no usa el barómetro y queda más
    cerca de las líneas.
- Abajo, la velocidad. La naranja y la verde vuelven a 0 en cada parada (ZUPT); el crucero es de
  ~±1,25 m/s. La azul (sin ZUPT) no vuelve a 0: cada recorrido le deja ~−0,07 m/s y en las paradas
  sigue bajando despacio (sesgo residual de ~−0,004 m/s²). Ese error se acumula: por eso, sin ZUPT,
  el desnivel sale con errores de metros a decenas de metros.

**`resultados/ascensor_2026-11-26_ascensor_error.png`**. **Qué mirar:** sin restar el sesgo, el
error de altura observado (azul) sigue a la predicción ½·b·t² (naranja punteada). Restando el sesgo,
el observado (verde) queda muy por encima de la predicción por ruido (roja): 154 m contra 21 m al
final. El sesgo medido en el reposo inicial no se mantiene igual toda la sesión. Una diferencia
media de solo 0,003 m/s² ya da ½·0,003·305² ≈ 140 m.

**`resultados/ascensor_2026-11-26_senales.png`** (de `verificar`, todo el registro): aceleración,
giroscopio, presión y temperatura. Se ven los 13 recorridos como pulsos de aceleración y escalones
de presión (la presión baja al subir, ~20 Pa por cada piso de ~2,5 m). El 13 está al final,
cortado: la presión sube y el registro termina antes de la meseta. La temperatura del BMP280 sube
0,9 °C en los 5 min, porque el dispositivo acababa de encenderse.
