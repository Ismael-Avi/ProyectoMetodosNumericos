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

0→1, 1→3, 3→0, 0→5, 5→1, 1→5, 5→0, 0→3, 3→1, 1→3, 3→5, 5→3, 3→1.

Son 12 recorridos útiles. El 13 se cortó al llegar (se apagó sin reposo final), así que se analiza
la sesión solo hasta t = 305 s:

```
python navegacion.py verificar datos/ascensor_2026-11-26
python navegacion.py ascensor  datos/ascensor_2026-11-26 --hasta 305
```

**Alturas de los pisos** (`datos/pisos.csv`, flexómetro): PB 0,00; 1: 4,90; 2: 7,42; 3: 9,90;
4: 12,34; 5: 14,86 m.

**Pulsos corregidos a mano.** `eventos.csv` tiene 33 pulsaciones y quedan 21 tras quitar los rebotes
(pulsos dobles a 0,2–0,35 s). Además, el primer pulso (0,3 s) fue una marca de inicio y no un
cierre de puerta, y faltan pulsos en los recorridos 10, 12 y 13. Con eso no se pueden armar los
pares. Por eso se hizo `eventos_corregidos.csv` (12 pares cierre/apertura), que el programa usa en
vez de `eventos.csv`; el archivo original no se tocó. Cuatro pulsos son inventados (6,8; 239,3;
248,0 y 283,1 s): salen del arranque y la parada que se ven en el acelerómetro. `paradas.csv` dice
en qué piso estaba cada una de las 13 paradas. Con el "piso más cercano", la última parada (piso 3,
medido 11,4 m) se confundía con el piso 4.

**Números clave:**
- 63 004 muestras del IMU y 7 876 del barómetro, 0 perdidas; 200,000 Hz al inicio y al final.
- Reposo inicial (0 a 5,8 s): |g| calibrado 9,759 m/s², inclinación 7,0°. Ruido del acelerómetro
  **0,095 m/s²**, 5 a 7 veces más que sobre la mesa (0,013–0,018), porque el piso del ascensor
  vibra.
- Velocidad de crucero ~1,25 m/s; recorridos de 8,7 a 20,5 s (entre pulsos).

**Error de altura en las 13 paradas**, contra el piso de `paradas.csv`:

| Método | Error RMS (m) | Error máx. (m) |
|---|---|---|
| Rectángulo sin corrección | 308,3 | 634,9 |
| Trapecio sin corrección | 308,2 | 634,8 |
| Trapecio − sesgo | 68,1 | 147,1 |
| Rectángulo − sesgo + ZUPT | 1,43 | 2,13 |
| Trapecio − sesgo + ZUPT | 1,41 | 2,11 |
| Solo barómetro | 1,00 | 1,73 |
| Fusión acelerómetro + barómetro + ZUPT | **0,99** | 1,70 |

- **Rectángulo y trapecio** dan casi lo mismo (diferencia de 0,02 m con ZUPT). El método de
  integración no importa; lo que importa es corregir el sensor (igual que en `metodos`).
- **Sin ZUPT** el error llega a cientos de metros en 5 min: un sesgo de 0,01 m/s² da
  ½·b·t² ≈ 500 m en 305 s. Restar el sesgo del reposo inicial no basta (147 m), porque el error
  restante no es constante (ver la figura de velocidad).
- **Con ZUPT** el error baja a ~1,4 m sin usar el barómetro.
- Casi todo el error de la fusión (~0,8 m en cada piso sobre PB) viene de la altura PB→1 (ver
  abajo), no del método.

**Cruces de pisos (bisección):** 23 cruces de pisos intermedios, los 23 que tocan: en cada recorrido
se buscan los pisos que hay entre el de salida y el de llegada. Por ejemplo, en el 0→5 (recorrido 4)
cruza los pisos 1, 2, 3 y 4 en 82,4; 84,4; 86,4 y 88,4 s, uno cada ~2,0 s. Con pisos de ~2,5 m
eso da ~1,25 m/s, la velocidad de crucero.

**Figura principal:** `resultados/ascensor_2026-11-26_ascensor.png`.
**Qué mirar:**
- Arriba, la altura: gris el barómetro, naranja la fusión, azul el acelerómetro con ZUPT (sin
  barómetro). Las líneas punteadas son los pisos reales; los puntos negros, los cruces.
  - Las mesetas de la fusión en los pisos 1, 3 y 5 quedan ~0,8 m **por encima** de su línea: es la
    discrepancia PB→1.
  - La azul sigue a las otras dos, pero se separa en tres saltos: en ~40 s (queda en 9,5 m en vez
    de 10,7), en ~67 s (llega a PB en 1,5 m) y en ~273 s (se queda corta en el piso 5). Son los
    recorridos 2, 3 y 11. En ellos el ascensor arrancó **0,3 a 0,5 s antes** del pulso de cierre,
    así que la integración empieza con el ascensor ya en movimiento y pierde 0,17, 0,32 y 0,38 m/s.
    Integrando desde 3 s antes, la velocidad al llegar baja a −0,04 a −0,10 m/s, como en los demás
    recorridos. Los pulsos de esos recorridos son los originales; se dejaron así.
- Abajo, la velocidad. La azul (sin ZUPT) no vuelve a 0 en las paradas. Cada recorrido le deja
  ~−0,07 m/s (de −0,01 a −0,14), y en las paradas sigue bajando despacio (sesgo residual de
  ~−0,004 m/s², unos −0,04 m/s por parada). Ese error se va acumulando. Las otras dos curvas
  vuelven a 0 en cada parada (ZUPT). Crucero de ~±1,25 m/s.

**Figura de apoyo:** `resultados/ascensor_2026-11-26_ascensor_error.png`.
**Qué mirar:** sin restar el sesgo, el error observado (azul) sigue a ½·b·t² (naranja punteada).
Restando el sesgo, el error observado (verde) queda muy por encima de la predicción por ruido
(roja): 154 m contra 21 m al final. El ruido no lo explica: el sesgo que se mide en el reposo
inicial no es el mismo durante toda la sesión, y cada recorrido deja además un poco de velocidad.
Solo 0,003 m/s² de diferencia media ya dan ½·0,003·305² ≈ 140 m.

**Coherencia barómetro vs acelerómetro.** Desnivel de cada recorrido (llegada − salida):

- En 8 de los 12 recorridos, barómetro y acelerómetro con ZUPT coinciden a 0,32 m o menos. Los
  otros cuatro son el 2, el 3 y el 11 (pulso tardío, arriba) y el 8 (0,64 m).
- **1→3 y 3→5 coinciden con la cinta:** recorrido 10 (1→3): real 5,00, barómetro 5,08,
  acelerómetro 5,06 m. Recorrido 9 (3→1): real −5,00, barómetro −4,87, acelerómetro −5,02 m.
  Recorrido 12 (5→3): real −4,96, barómetro −5,17, acelerómetro −5,09 m.
- **PB→1 no coincide:** en el recorrido 1 (0→1) el barómetro da 5,73 m y la cinta 4,90 m. Los dos
  sensores dicen ~5,7 m, y el error de +0,8 m aparece en todos los pisos sobre PB (piso 3 medido
  10,7 m contra 9,90; piso 5, 15,8 contra 14,86). Por eso parece un error en la medida de PB→1 y no
  en los sensores. **Se va a volver a medir PB→1**; por ahora `pisos.csv` deja 4,90 m.

**Deriva del barómetro: ~0,7 m en 5 min.** El mismo piso da alturas distintas con el tiempo: piso 3,
10,70 m a los 40 s y 11,42 m a los 296 s (+0,72 m). Piso 5, 15,77 m a los 98 s y 16,59 m a los
274 s (+0,82 m). Equivale a ~6 Pa (1 Pa ≈ 0,12 m). Por eso los errores de la fusión crecen hacia el
final de la sesión (+1,5 a +1,7 m en las últimas paradas). El ruido de la altura barométrica en
reposo es de 0,26 m (2,2 Pa).
