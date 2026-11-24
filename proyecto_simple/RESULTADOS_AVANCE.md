# Resultados del avance: caracterización del dispositivo

Navegación inercial en el Metro de Quito. Métodos Numéricos, EPN.

**Alcance del avance:** reposo, calibración de seis caras y ascensor. El ascensor todavía no se ha
grabado (ver la última sección). El metro va en el segundo parcial.

**Dispositivo:** ESP32 + GY-91 (acelerómetro y giroscopio MPU-6500, barómetro BMP280). Guarda los
datos crudos en una microSD: acelerómetro y giroscopio a 200 Hz, barómetro a 25 Hz. Todo se procesa
después con `navegacion.py`. Las figuras están en `resultados/`.

## 1. Reposo corto (`sesion_002`, 21/11/2026)

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

**Qué se hizo:** la protoboard fijada dentro de una caja, alimentada con un cargador de pared. Se
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
- **Presión coherente con Quito:** ~731 hPa (732,7; 731,3 y 730,8 hPa en las tres sesiones). A nivel
  del mar serían ~1013 hPa. Con la atmósfera estándar, 731 hPa corresponde a unos 2650–2670 m.
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
- **Calibraciones reproducibles:** TODO. Falta comparar los sesgos y las escalas con los del segundo
  intento de caras (`datos/caras_2026-11-24_intento2/`), que todavía no está en el repositorio.
- **Métodos numéricos verificados:**
  - el BMP280 reproduce el ejemplo de la hoja de datos (25,08 °C y 100 653,27 Pa);
  - el rectángulo converge con orden 1 y el trapecio con orden 2 (`resultados/metodos_convergencia.png`:
    dos rectas, la del trapecio con el doble de pendiente).

## 5. Ascensor: pendiente

El programa (`python navegacion.py ascensor`) ya está hecho y probado con datos simulados. Falta:

- Grabar en un edificio de **al menos 5 pisos**, **al menos 10 recorridos** de subida y bajada con
  paradas intermedias. Primeros 10 s quieto; un pulso del botón al cerrarse la puerta y otro al
  abrirse.
- Medir con flexómetro la **altura real de cada piso** y llenarla en `datos/pisos.csv` (hoy está
  vacío). Sin eso, la altura solo se puede comparar con el barómetro, no con la realidad.
- Soldar el pulsador (hoy rebota) antes de grabar.
- Con esos datos: altura y velocidad con dos métodos de integración, con y sin ZUPT, con y sin
  barómetro, y el error en cada piso.
