# Datos crudos del registrador

Esta carpeta tiene las sesiones **reales** grabadas por el dispositivo (ESP32 + GY-91 con MPU-6500 y
BMP280, firmware `firmware/registrador_v01/registrador_v01.ino`) y los archivos de referencia que
usa `navegacion.py`. Las sesiones de `simulados/` las genera el simulador, solo sirven para probar
el código y no se suben a git.

Los números de la tabla salen de `python navegacion.py verificar datos/<sesion>` (corrida del
24/11/2026). La inclinación sale de `python navegacion.py reposo` y `caras` (ángulo respecto al eje más
cercano, sin calibrar).

## Sesiones

| Carpeta | Fecha y hora | Experimento | Duración | Muestras IMU | Muestras barómetro | Perdidas (IMU / baro) | Frecuencia real IMU (inicio / final) | Frecuencia real baro (inicio / final) | Alimentación | Orientación |
|---|---|---|---|---|---|---|---|---|---|---|
| `sesion_002/` | 21/11/2026, hora: TODO | reposo corto, primera prueba del firmware | 142,4 s (2,4 min) | 28 483 | 3 561 | 0 / 0 | 200,000 / 200,000 Hz | 25,000 / 25,000 Hz | USB de la laptop | sobre una mesa, eje z hacia arriba, inclinada 3,0° |
| `reposo_90min_2026-11-21_1915-2049/` | 21/11/2026, 19:15 a 20:49 | reposo largo (90 min) | 5694,3 s (94,9 min) | 1 138 860 | 142 358 | 0 / 0 | 200,000 / 200,000 Hz | 25,000 / 25,000 Hz | power bank | sobre una mesa, eje z hacia arriba, protoboard inclinada 9,2° |
| `caras_2026-11-24/` | 24/11/2026, hora: TODO | seis caras + 8 posiciones inclinadas (**calibración oficial**) | 746,7 s (12,4 min) | 149 332 | 18 667 | 0 / 0 | 200,000 / 200,000 Hz | 25,000 / 25,000 Hz | cargador de pared | protoboard fijada dentro de una caja; seis caras y 8 posiciones inclinadas de 5,2° a 22,3° |

Otros datos de `verificar`:

- `sesion_002`: periodo medio del IMU 5000,0 µs, jitter 1,3 µs (mín. 4993, máx. 5007 µs). Sin
  pulsaciones de botón. Fue la primera prueba del firmware. El detector marca movimiento en 18,0;
  76,5; 79,0; 105,0 y 142,0 s (ventanas de 0,5 s). TODO: anotar qué pasó en esos instantes. La
  carpeta conserva el nombre que le puso el firmware.
- `reposo_90min_2026-11-21_1915-2049`: periodo medio del IMU 5000,0 µs, jitter 0,8 µs (mín. 4993,
  máx. 5007 µs). Cumple los dos requisitos del enunciado: ≥ 100 Hz y 90 min sin pérdidas.
  `eventos.csv` tiene 3 pulsaciones: en 3,2 s, 5686,2 s y 5686,6 s (tiempo desde la primera
  muestra del IMU). La tercera está a 0,40 s de la segunda: es un rebote del pulsador y
  `navegacion.py` la ignora. La carpeta se renombró a mano con la fecha y la hora de la bitácora.
  TODO: anotar el nombre `sesion_NNN` original que le puso el firmware.
- `caras_2026-11-24`: periodo medio del IMU 5000,0 µs, jitter 1,1 µs (mín. 4994, máx. 5006 µs). Sin
  pulsaciones (no se usó el pulsador). `caras` encuentra 14 tramos quietos: las 6 caras y 8
  posiciones inclinadas. La carpeta se renombró a mano con la fecha. TODO: anotar el nombre
  `sesion_NNN` original y la hora.

Los archivos que vienen de la microSD tienen fecha de modificación 01/01/1980, porque el ESP32 no
sabe la fecha. La fecha y la hora reales se anotan en `../bitacora.md`.

## Formato de cada archivo

Cada sesión es una carpeta con cuatro archivos. Todos los valores son **crudos**: el firmware no
convierte nada. La conversión a unidades físicas la hace `navegacion.py` (`leer_sesion` y `bmp280`).

### `meta.json`

Configuración del sensor en el momento de grabar. Lo escribe `crearSesion()` del firmware al
encender.

| Campo | Valor en las sesiones reales | Significado |
|---|---|---|
| `formato_version` | 0 | versión del formato de archivos |
| `firmware_version` | `"0.1"` | versión del firmware |
| `chip_whoami` | `"0x70"` | registro WHO_AM_I del MPU. 0x70 = MPU-6500, sin magnetómetro |
| `tiene_magnetometro` | `false` | por eso `mx, my, mz` van vacíos |
| `fs_imu_nominal_hz` | 200 | frecuencia nominal del acelerómetro y el giroscopio |
| `fs_baro_nominal_hz` | 25 | frecuencia nominal del barómetro |
| `accel_rango_g` | 4 | rango del acelerómetro, ±4 g |
| `gyro_rango_dps` | 500 | rango del giroscopio, ±500 °/s |
| `mpu_dlpf_cfg` | 3 | filtro pasa-bajos interno del giroscopio (registro CONFIG) |
| `mpu_a_dlpf_cfg` | 3 | filtro pasa-bajos interno del acelerómetro (registro ACCEL_CONFIG2) |
| `bmp280_osrs_t` | 1 | sobremuestreo de la temperatura, x1 |
| `bmp280_osrs_p` | 8 | sobremuestreo de la presión, x8 |
| `bmp280_filtro_iir` | 0 | filtro IIR del BMP280 apagado |
| `bmp280_calib` | ver abajo | coeficientes de calibración de fábrica del BMP280 |
| `notas` | texto | aclaraciones del firmware |

`bmp280_calib` tiene los 12 coeficientes que el firmware lee de los registros 0x88 a 0x9F del BMP280
(little-endian). Hacen falta para la fórmula de compensación. En las tres sesiones reales son los
mismos, porque es el mismo chip:

| Coeficiente | Tipo | Valor |
|---|---|---|
| `dig_T1` | uint16 | 27594 |
| `dig_T2` | int16 | 25520 |
| `dig_T3` | int16 | 50 |
| `dig_P1` | uint16 | 37532 |
| `dig_P2` | int16 | -10596 |
| `dig_P3` | int16 | 3024 |
| `dig_P4` | int16 | 7500 |
| `dig_P5` | int16 | -38 |
| `dig_P6` | int16 | -7 |
| `dig_P7` | int16 | 15500 |
| `dig_P8` | int16 | -14600 |
| `dig_P9` | int16 | 6000 |

### `imu.csv`

```
seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz
0,1036452,1318,-220,8364,-291,-111,-13,,,
```

- `seq`: contador de muestra. Aumenta de 1 en 1 aunque la muestra no se escriba, así que un salto
  en `seq` es una muestra perdida.
- `t_us`: microsegundos desde que arrancó el ESP32, tomado justo antes de leer el sensor.
- `ax, ay, az`: acelerómetro, enteros int16 crudos.
- `gx, gy, gz`: giroscopio, enteros int16 crudos.
- `mx, my, mz`: siempre vacíos. El MPU-6500 no tiene magnetómetro. Las columnas se dejaron para
  conservar el formato v0, que también sirve para un MPU-9250.

### `baro.csv`

```
seq,t_us,adc_T,adc_P
0,1037123,523472,488868
```

- `seq`, `t_us`: igual que en `imu.csv`, con su propio contador.
- `adc_T`, `adc_P`: lecturas crudas de 20 bits de temperatura y presión (registros 0xF7 a 0xFC).

Hay una lectura del barómetro cada 8 muestras del IMU (200 / 8 = 25 Hz).

### `eventos.csv`

```
t_us,evento
4192615,1
```

- `t_us`: instante de la pulsación del botón, en microsegundos desde el arranque (mismo reloj que
  `imu.csv`). Se toma dentro de la interrupción.
- `evento`: siempre 1 (pulsación del botón en el pin G4).

## Conversión a unidades físicas

| Magnitud | Conversión | Fuente |
|---|---|---|
| aceleración | `a [g] = crudo / 8192` (±4 g = 8192 LSB/g); `a [m/s²] = a [g] · 9,80665` | InvenSense, *MPU-6500 Product Specification*, AFS_SEL=1 |
| velocidad angular | `ω [°/s] = crudo / 65,5` (±500 °/s = 65,5 LSB/(°/s)); luego se pasa a rad/s | misma hoja, FS_SEL=1 |
| tiempo | `t [s] = (t_us − t_us de la primera muestra del IMU) / 10⁶` | — |
| temperatura y presión | fórmula de compensación de Bosch (abajo) | Bosch, *BMP280 datasheet* BST-BMP280-DS001 |

9,80665 m/s² es la definición de 1 g, no la gravedad de Quito: solo sirve para pasar de "g" a
m/s². La gravedad de Quito (9,77 m/s²) se usa después, al comparar |a| o al restar la gravedad.

Fórmula de compensación del BMP280 en punto flotante (función `bmp280()` de `navegacion.py`):

```
var1   = (adc_T/16384 − dig_T1/1024) · dig_T2
var2   = (adc_T/131072 − dig_T1/8192)² · dig_T3
t_fine = var1 + var2
T [°C] = t_fine / 5120

var1 = t_fine/2 − 64000
var2 = var1² · dig_P6 / 32768
var2 = var2 + var1 · dig_P5 · 2
var2 = var2/4 + dig_P4 · 65536
var1 = (dig_P3 · var1² / 524288 + dig_P2 · var1) / 524288
var1 = (1 + var1/32768) · dig_P1
p    = 1048576 − adc_P
p    = (p − var2/4096) · 6250 / var1
var1 = dig_P9 · p² / 2147483648
var2 = p · dig_P8 / 32768
P [Pa] = p + (var1 + var2 + dig_P7) / 16
```

`python navegacion.py metodos` prueba esta función con el ejemplo de la hoja de datos.

## Configuración del sensor

Tomada de `firmware/registrador_v01/registrador_v01.ino`:

- **IMU (MPU-6500):** lectura cada 5 ms, o sea 200 Hz, con `vTaskDelayUntil` en una tarea del
  núcleo 1. `SMPLRT_DIV = 0`: muestreo interno a 1 kHz. Filtro pasa-bajos interno
  `DLPF_CFG = 3`: unos 41 Hz en el giroscopio. `A_DLPF_CFG = 3`: unos 45 Hz en el acelerómetro.
  Los dos quedan por debajo de la mitad de 200 Hz para evitar aliasing. I2C a 400 kHz.
- **Barómetro (BMP280):** 25 Hz, una lectura cada 8 del IMU. `ctrl_meas = 0x33`: `osrs_t` x1,
  `osrs_p` x8, modo normal. `config = 0x00`: t_sb 0,5 ms y filtro IIR apagado, para guardar datos
  crudos. El firmware estima unos 22,5 ms por medición (~44 mediciones/s), así que alcanza para
  leer a 25 Hz.
- **Tiempo:** `t_us` viene de `esp_timer_get_time()`, que devuelve un `int64_t` (64 bits) en
  microsegundos desde el arranque. En el firmware se guarda en `int64_t t_us` (structs
  `MuestraImu` y `MuestraBaro`) y se escribe con `%lld`. Con 64 bits no hay desborde en la
  práctica (un `uint32_t` en µs se desbordaría a los ~71,6 min, antes de los 90 min que pide el
  enunciado).
- **Botón:** interrupción en el flanco de bajada del pin G4, con antirrebote de 200 ms en el
  firmware. En Python se ignoran además las pulsaciones a menos de 1 s de la anterior.
- **Escritura:** cola de 2000 muestras del IMU (10 s de margen) entre la tarea de muestreo y la de
  escritura en la microSD. `flush` cada 1 s: si se corta la energía se pierde como máximo el
  último segundo.

## Archivos de referencia

| Archivo | Columnas | Estado |
|---|---|---|
| `pisos.csv` | `piso,altura_m,fuente` | **vacío** (solo encabezado). Falta medir la altura de cada piso con flexómetro |
| `estaciones.csv` | `orden,estacion,lat,lon,distancia_al_siguiente_m,fuente` | **vacío** (solo encabezado). Faltan las estaciones del Metro con fuente verificable |
| `viajes.csv` | `sesion,estacion_inicial,sentido` | **vacío** (solo encabezado). Se llena con cada viaje en metro |

`sentido` = 1 si el viaje va en el orden de `estaciones.csv`, -1 si va al revés (ver `../README.md`).
