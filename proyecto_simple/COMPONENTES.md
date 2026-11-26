# Componentes del dispositivo

Registrador inercial del primer parcial (Métodos Numéricos, EPN). Fotos en [`fotos/`](fotos/),
firmware en [`firmware/registrador_v01/registrador_v01.ino`](firmware/registrador_v01/registrador_v01.ino).
Todo se compró en distintas tiendas de electrónica de Quito. La prueba del hardware del 18/11 (monitor
serie) está en [`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg).

## Resumen

| Componente | Modelo | Cómo se verificó | Configuración usada | Dónde se consiguió | Costo |
|---|---|---|---|---|---|
| Microcontrolador | Placa ESP32 DevKit con módulo ESP-WROOM-32; chip **ESP32-D0WDQ6** `esptool`, al cargar el primer programa (17/11): "Chip type: ESP32-D0WDQ6 (revision v1.0)". La captura no se guardó (ver detalle) | 2 núcleos: muestreo en el núcleo 1, escritura en el núcleo 0 (FreeRTOS); WiFi y Bluetooth apagados | tienda de electrónica, Quito | $15,00 (ver nota) |
| Acelerómetro y giroscopio + barómetro | Módulo **GY-91**: **MPU-6500** + **BMP280** | Prueba del 18/11 ([`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg)): responden 0x68 y 0x76; WHO_AM_I = **0x70** (MPU-6500); ID del barómetro = **0x58** (BMP280). Además, el `meta.json` de las 5 sesiones guarda `"chip_whoami": "0x70"` | acelerómetro ±4 g (8192 LSB/g), giroscopio ±500 °/s (65,5 LSB/(°/s)), 200 Hz; barómetro presión ×8 (0,33 Pa), 25 Hz | tienda de electrónica, Quito | $12,00 |
| Lector de microSD | Mini módulo genérico de 6 pines (3V3, CS, MOSI, CLK, MISO, GND), a 3,3 V (foto 01) | prueba del 18/11 ([`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg)): detecta la tarjeta y escribe `prueba.txt`; la sesión de 95 min escribió 60,7 MB sin perder ninguna muestra | SPI: CS G5, SCK G18, MOSI G23, MISO G19; `flush` cada 1 s | tienda de electrónica, Quito | $4,00 |
| Tarjeta microSD | **32 GB**, FAT32 | prueba del 18/11: tarjeta de **29 825 MB** útiles ([`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg)) | una carpeta por sesión | tienda de electrónica, Quito | $9,00 |
| Energía | Power bank de **5000 mAh**, por USB al pin V5 (foto 03); en `sesion_002`, el USB de la laptop | 95 min seguidos sin cortes: una sola carpeta y `seq` continuo | 5 V al pin V5; el regulador de la placa da 3,3 V | propia | $0,00 |
| Botón | Pulsador momentáneo de panel, normalmente abierto, capuchón rojo (fotos 01 y 02) | pulsaciones en `eventos.csv` (ascensor: 33) | G4 a GND, `INPUT_PULLUP`, interrupción en flanco de bajada, antirrebote 200 ms (+ 1 s en Python) | tienda de electrónica, Quito | $0,70 |
| Caja | Caja plástica rígida negra con tapa, base de 6 × 8,5 cm (fotos 01 y 02); en el ascensor, dentro de una caja de cartón junto a la power bank (foto 03) | la protoboard no se movió durante las seis caras: el sesgo del giroscopio varía solo 0,005 a 0,008 °/s entre caras | protoboard fijada dentro de la caja | tienda de electrónica, Quito | $3,00 |
| Protoboard y cables | Mini protoboard con cables jumper (foto 01) | — | — | material propio | $0,00 (propio) |
| **Total** | | | | | **$43,70** |

El total suma los componentes comprados. La power bank, la protoboard y los cables jumper son
material propio y no entran en el total.

**Nota sobre el ESP32:** se usó un ESP32 prestado. Su conector micro-USB se dañó durante el
proyecto, así que se compró uno nuevo ($15) para devolvérselo al dueño. Por eso el costo cuenta como
parte del proyecto. El dispositivo sigue usando el ESP32 dañado, con el micro-USB reparado: ahora
solo da alimentación, no datos (ver abajo).

## Detalle por componente

### Microcontrolador: ESP32

- **Modelo:** placa de desarrollo ESP32 DevKit con módulo ESP-WROOM-32.
- **Cómo se verificó:** al cargar el primer programa (17/11/2026), `esptool` mostró
  "Chip type: ESP32-D0WDQ6 (revision v1.0)", con Wi-Fi, BT, Dual Core, 240 MHz y cristal de 40 MHz.
  La captura no se guardó, y no se puede repetir: el 26/11 se intentó leer el chip otra vez con
  `esptool` (`chip-id`), pero después de la reparación del micro-USB Windows ya no detecta ningún
  puerto COM. El conector solo da alimentación, no datos. Evidencia indirecta de que el chip
  funciona: el firmware sigue grabando con normalidad (sesión del ascensor, 26/11).
- **Para volver a programarlo** haría falta un adaptador USB-serial conectado a TXD/RXD (bitácora,
  sección 3).
- **Configuración:** el firmware usa dos tareas de FreeRTOS. La de muestreo (núcleo 1, prioridad
  alta) lee el sensor cada 5 ms; la de escritura (núcleo 0) vacía la cola en la microSD. La cola es
  de 2000 muestras del IMU (10 s de margen). El reloj es `esp_timer_get_time()`: microsegundos
  desde el arranque, en un `int64_t`. WiFi y Bluetooth apagados (`WiFi.mode(WIFI_OFF)`, `btStop()`).
- **Evidencia:** 0 muestras perdidas y 200,000 Hz al inicio y al final en las cinco sesiones. Jitter
  del periodo de 0,8 a 1,3 µs (`resultados/*_verificar.txt`).

### Acelerómetro y giroscopio: MPU-6500 (módulo GY-91)

- **Modelo:** MPU-6500. El plan inicial suponía un MPU-9250 con magnetómetro (WHO_AM_I 0x71), pero
  el registro WHO_AM_I dio **0x70**: es un MPU-6500, sin magnetómetro. El valor queda guardado en
  el `meta.json` de cada sesión.
- **Bus:** I2C a 400 kHz, dirección 0x68. SDA en G21, SCL en G22.
- **Configuración** (registros escritos por el firmware; factores de la hoja de datos de InvenSense,
  *MPU-6500 Product Specification*):

  | Magnitud | Rango | Sensibilidad | 1 LSB equivale a | Filtro interno |
  |---|---|---|---|---|
  | Aceleración | ±4 g (±39,2 m/s²) | 8192 LSB/g | 0,0012 m/s² | `A_DLPF_CFG = 3`, ~45 Hz |
  | Velocidad angular | ±500 °/s | 65,5 LSB/(°/s) | 0,0153 °/s | `DLPF_CFG = 3`, ~41 Hz |

- **Muestreo:** 200 Hz (`SMPLRT_DIV = 0`, muestreo interno a 1 kHz y lectura cada 5 ms).
- **Medido:** ruido de 0,013–0,018 m/s² y 0,054–0,064 °/s en reposo. Sesgo del giroscopio
  ~(−4,5; −1,8; −0,2) °/s (`resultados/reposo_90min_2026-11-21_1915-2049_reposo.txt`).

### Barómetro: BMP280 (módulo GY-91)

- **Modelo:** BMP280. El firmware lee el registro de ID (0xD0) al arrancar y se detiene si no es
  0x58 (BMP280) o 0x60 (BME280). Los integrantes leyeron **0x58**. El firmware no imprime ni guarda
  ese ID (solo escribe "BMP280 listo"), pero la prueba del 18/11 lo leyó directamente: **0x58** en
  la dirección 0x76, y nada en 0x77 (devuelve 0xFFFFFFFF) ([`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg)).
- **Bus:** I2C, dirección 0x76 (mismo bus que el MPU).
- **Configuración** (`ctrl_meas = 0x33`, `config = 0x00`; hoja de datos de Bosch BST-BMP280-DS001):
  presión ×8 (19 bits, resolución 0,33 Pa ≈ 4 cm de altura en Quito), temperatura ×1 (16 bits,
  0,005 °C), modo normal, filtro IIR apagado para guardar datos crudos. Una medición tarda ~22,5 ms;
  se lee a 25 Hz (una vez cada 8 lecturas del IMU).
- **Coeficientes de fábrica** `dig_T1`…`dig_P9`: en el `meta.json` de cada sesión, iguales en las
  cinco (es el mismo chip). Detalle en [`datos/LEEME.md`](datos/LEEME.md).
- **Medido:** ruido de 2,2 a 2,7 Pa (0,26 a 0,33 m) en reposo; presión ~731 hPa en Quito.

### Almacenamiento: microSD

- **Modelo:** mini módulo lector de microSD genérico, de 6 pines (3V3, CS, MOSI, CLK, MISO, GND), que
  trabaja a 3,3 V (el módulo azul de la foto 01), y una tarjeta de **32 GB** en FAT32.
- **Cómo se verificó:** en la prueba del 18/11 el ESP32 detectó una tarjeta de 29 825 MB útiles y
  escribió el archivo `prueba.txt` ([`evidencias/prueba_i2c_sd_2026-11-18.jpeg`](evidencias/prueba_i2c_sd_2026-11-18.jpeg)).
- **Conexión:** CS en G5 (`SD.begin(5)`); SCK, MOSI y MISO en los pines SPI por defecto del ESP32
  (G18, G23 y G19).
- **Formato:** una carpeta por sesión con `meta.json`, `imu.csv`, `baro.csv` y `eventos.csv`.
- **Uso real:** la sesión de 95 min ocupa 56,3 MB (`imu.csv`) + 4,4 MB (`baro.csv`), unos
  10,7 kB/s o 38 MB por hora. Con los 29 825 MB útiles alcanza para ~800 h de registro. Cálculo en
  [`GUIA_ESTUDIO.md`](GUIA_ESTUDIO.md), sección d.

### Energía

- **Usada:** una power bank propia de **5000 mAh**, por USB al pin V5 (foto 03; en el ascensor,
  dentro de la caja de cartón). En `sesion_002`, el USB de la laptop.
- **Consumo:** **no se midió**. Se estima en 80–120 mA, según la guía de armado; es una estimación,
  no una medición. Con eso, la power bank duraría ~26 a 39 h ([`GUIA_ESTUDIO.md`](GUIA_ESTUDIO.md),
  sección d).
- **Evidencia:** 95 min seguidos sin cortes. Cuando la power bank estaba descargada, se apagaba y la
  sesión quedaba partida en dos carpetas (bitácora, sección 3).
- **Plan:** 4 pilas AA (6 V) con interruptor, al pin V5 (`../CONTEXTO_PROYECTO.md`).

### Botón

- **Modelo:** pulsador momentáneo de panel, normalmente abierto, con capuchón rojo, montado en la
  pared de la caja (fotos 01 y 02). Los cables están enrollados, **sin soldar**, y por eso rebota.
- **Conexión:** un terminal a G4 y el otro a GND. El firmware usa la resistencia de pull-up interna
  y una interrupción en el flanco de bajada (`isrBoton`), con 200 ms de antirrebote. En Python se
  ignoran además las pulsaciones a menos de 1 s de la anterior.

### LED

- El LED azul de la placa, en G2: parpadeo lento mientras graba, rápido si hay un error.

### Caja

- **Modelo:** caja plástica rígida negra, con tapa (fotos 01 y 02). Base de 6 × 8,5 cm; la altura no
  se registró.
- **Montaje:** la protoboard va fijada dentro de la caja desde el segundo intento de las seis caras
  (24/11). En el ascensor, la caja negra iba dentro de una caja de cartón, apoyada en el piso,
  junto a la power bank (foto 03).

## Conexiones

| Módulo | Pin del módulo | Pin del ESP32 | Fuente |
|---|---|---|---|
| GY-91 (MPU-6500 + BMP280) | SDA | G21 | firmware (`PIN_SDA`) |
| GY-91 | SCL | G22 | firmware (`PIN_SCL`) |
| GY-91 | VIN / GND | 3V3 / GND | comprobado en el montaje; el módulo responde en la prueba del 18/11 |
| microSD | CS | G5 | firmware (`PIN_SD_CS`) |
| microSD | CLK / MOSI / MISO | G18 / G23 / G19 | pines SPI por defecto del ESP32 (`SD.begin`) |
| microSD | 3V3 / GND | 3V3 / GND | comprobado en el montaje; el módulo responde en la prueba del 18/11 |
| Botón | un terminal / el otro | G4 / GND | firmware (`PIN_BOTON`, `INPUT_PULLUP`) |
| LED | el de la placa | G2 | firmware (`PIN_LED`) |
| Power bank | USB 5 V | V5 / GND | integrantes |

El diagrama de conexiones está en la presentación (diapositiva 3) y en
[`presentacion/diagrama_conexiones.png`](presentacion/diagrama_conexiones.png).
