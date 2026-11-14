# Firmware del registrador inercial (ESP32 + GY-91 + microSD)

Este programa corre en el ESP32. Lee los sensores del GY-91 y guarda los datos **crudos** en la
microSD, en el mismo formato que usa el programa de Python (`procesamiento/navinercial/formato.py`).
No hace ningún cálculo: todo el procesamiento se hace después en la computadora.

> **Estado:** el código compila, pero todavía **no se ha probado con el dispositivo armado**.
> Todo lo que falta comprobar está marcado con `TODO` en el código y reunido en
> `procesamiento/docs/PENDIENTES_HARDWARE.md`.

## Conexiones

| Módulo | Pin del módulo | Pin del ESP32 |
|---|---|---|
| GY-91 | VIN | 3V3 (TODO: confirmar según el regulador del módulo) |
| GY-91 | GND | GND |
| GY-91 | SDA | G21 |
| GY-91 | SCL | G22 |
| microSD | CS | G5 |
| microSD | SCK | G18 |
| microSD | MOSI | G23 |
| microSD | MISO | G19 |
| microSD | VCC / GND | según el módulo (TODO: confirmar si es de 5 V o de 3,3 V) |
| Botón | un lado a G4, el otro a GND | (usa la resistencia interna, sin resistencia externa) |
| LED | el de la placa | G2 |
| Pilas | 4 AA | V5 (VIN) y GND |

Direcciones I2C: MPU en `0x68`, BMP280 en `0x76` (si no responde se prueba `0x77`), magnetómetro
AK8963 en `0x0C`.

## Archivos

| Archivo | Contenido |
|---|---|
| `platformio.ini` | proyecto de PlatformIO con dos entornos: `registro` y `prueba` |
| `include/configuracion.h` | pines, frecuencias, tamaños de buffer: **todo lo ajustable está aquí** |
| `src/sensores.h/.cpp` | lectura cruda del MPU, del AK8963 y del BMP280 por I2C |
| `src/almacenamiento.h/.cpp` | microSD, carpeta de sesión, `meta.json` y doble buffer |
| `src/main.cpp` | tareas de muestreo y de escritura, botón, LED, modo de prueba |

No se usan librerías externas de sensores: los registros se leen directamente con `Wire`, para
que cada línea del código se pueda explicar con la hoja de datos al lado.

## Instalación en Windows

### Opción A: VS Code + PlatformIO (recomendada)

1. Instalar [VS Code](https://code.visualstudio.com/).
2. En VS Code, abrir *Extensiones* (Ctrl+Shift+X), buscar **PlatformIO IDE** e instalarla.
   Reiniciar VS Code cuando lo pida.
3. *Archivo > Abrir carpeta...* y elegir la carpeta `firmware/` (no la raíz del repositorio).
4. La primera vez PlatformIO descarga el compilador del ESP32 (varios minutos, hace falta
   internet).
5. Conectar el ESP32 por USB. Si Windows no lo reconoce como puerto COM, instalar el driver del
   chip USB de la placa (CP2102 o CH340, según la placa; TODO: anotar cuál tiene la nuestra).

Botones de la barra inferior de VS Code:

- ✓ (*Build*): compilar.
- → (*Upload*): compilar y cargar al ESP32.
- 🔌 (*Serial Monitor*): ver los mensajes del ESP32 (115200 baudios).
- El entorno (`registro` o `prueba`) se elige en la misma barra, donde dice `env:...`.

Si la carga falla con "Connecting....", mantener pulsado el botón **BOOT** de la placa mientras
aparece ese mensaje.

### Opción B: línea de comandos

```powershell
cd firmware
py -m venv .venv
.venv\Scripts\pip install platformio
.venv\Scripts\pio run -e registro              # compilar
.venv\Scripts\pio run -e registro -t upload    # cargar
.venv\Scripts\pio device monitor               # monitor serie
```

### Opción C: Arduino IDE (por si PlatformIO da problemas)

1. Instalar Arduino IDE 2 y, en *Archivo > Preferencias > URLs adicionales de gestor de placas*,
   agregar `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
2. *Herramientas > Placa > Gestor de placas*: instalar **esp32 by Espressif Systems**.
3. Crear una carpeta `registrador/` y copiar dentro `src/main.cpp` con el nombre
   `registrador.ino`, y también `sensores.h`, `sensores.cpp`, `almacenamiento.h`,
   `almacenamiento.cpp` e `include/configuracion.h` (todos en la misma carpeta).
4. Elegir la placa **ESP32 Dev Module** y el puerto COM, y cargar.
5. Para el modo de prueba, quitar el comentario de `#define MODO_PRUEBA_SERIE` en
   `configuracion.h`.

TODO: probar la opción C al menos una vez; solo se ha compilado con PlatformIO.

## Modo de prueba (sin microSD)

Sirve para comprobar el cableado de los sensores antes de conectar la tarjeta.

1. Elegir el entorno `prueba` y cargar (`pio run -e prueba -t upload`).
2. Abrir el monitor serie. Aparecen 5 líneas por segundo:

```
accel (g):   0.012  -0.004   1.003  |a| = 1.003   gyro (grados/s):   0.41  -0.22   0.10   mag (uT):   12.3  -20.1  -35.0   T = 24.31 C   P = 72105.3 Pa
```

Qué revisar con el dispositivo quieto sobre la mesa:

- `|a|` cerca de 1 g; el eje que apunta hacia arriba marca cerca de +1.
- Giroscopio cerca de 0 °/s (unas décimas es normal: es el sesgo).
- Presión en Quito: alrededor de 72 000 Pa. Temperatura razonable.
- Al arrancar se imprime `WHO_AM_I`: `0x71` o `0x73` = hay magnetómetro; `0x70` = MPU-6500, sin
  magnetómetro (las columnas `mx,my,mz` quedarán vacías).

En este modo el LED parpadea rápido y parejo (2,5 veces por segundo).

## Cómo grabar una sesión

1. Cargar el entorno `registro`. Poner la microSD (formateada en **FAT32**).
2. **Encender** (o pulsar el botón EN/RESET): el LED queda fijo un instante mientras arranca y
   después da **un destello por segundo**: está grabando. Cada encendido crea una carpeta nueva
   en la tarjeta: `sesion_001`, `sesion_002`... (el primer número libre).
3. **Pulsación corta del botón** = marca un evento en `eventos.csv` (por ejemplo: "se abren las
   puertas", "pasamos por el piso 3"). Anotar en la bitácora qué significa cada pulsación.
4. **Mantener el botón 3 segundos** = terminar: se guardan los datos pendientes y se cierran los
   archivos. El LED pasa a parpadeo lento (1 s encendido, 1 s apagado). **Solo entonces apagar.**
5. Para grabar otra sesión: apagar y encender (o pulsar EN/RESET).

Si se apaga sin terminar, se pierden como máximo los últimos 2 segundos (los archivos se
aseguran cada 2 s), pero es mejor terminar siempre con el botón.

Después: copiar la carpeta `sesion_NNN` a `procesamiento/datos/` y verificarla con

```powershell
cd procesamiento
.venv\Scripts\python -m scripts.verificar_sesion datos\sesion_001
```

Como el ESP32 no tiene reloj, la fecha y la hora de cada sesión se anotan en la bitácora.

## Qué significa cada parpadeo del LED

| LED | Significado | Qué hacer |
|---|---|---|
| Fijo (menos de 1 s) | Arrancando | Esperar |
| 1 destello corto por segundo | **Grabando** | Todo bien |
| 2 destellos cortos por segundo | Grabando, pero se perdieron muestras en los últimos 5 s (la SD está lenta) | Anotar en la bitácora; probar otra tarjeta |
| Lento: 1 s encendido, 1 s apagado | Registro terminado, archivos cerrados | Ya se puede apagar |
| Muy rápido y continuo (5 por segundo) | **Error de SD**: no hay tarjeta, no es FAT32, está llena o falló al escribir | Revisar tarjeta y cables |
| 3 destellos y una pausa | **Error de sensor**: el MPU o el BMP280 no responden | Revisar cables del GY-91; ver el mensaje en el monitor serie |
| Parpadeo parejo, 2,5 por segundo | Modo de prueba | Normal en el entorno `prueba` |

Con el cable USB conectado, el monitor serie muestra además el motivo del error y, cada 5 s,
un resumen: número de muestra, muestras descartadas y errores de lectura.

## Cómo funciona por dentro (resumen)

- **Temporizador de 200 Hz** (`esp_timer`): cada 5 ms despierta a la tarea de muestreo.
- **Tarea de muestreo** (núcleo 1, prioridad alta): toma la marca de tiempo `t_us` con
  `esp_timer_get_time()`, lee el MPU, cada 2 vueltas el magnetómetro (100 Hz) y cada 8 el
  barómetro (25 Hz), y deja el texto en un buffer en memoria.
- **Tarea de escritura** (núcleo 0): guarda los buffers llenos en la microSD y hace `flush`
  cada 2 s.
- **Doble buffer**: mientras la SD guarda un buffer, el muestreo llena el otro. Así una pausa
  de la tarjeta no frena el muestreo.
- **`seq`** cuenta los avisos del temporizador, no las filas escritas. Si una muestra se pierde
  (la SD tardó demasiado o el sensor no respondió), queda un salto en `seq` y la verificación
  de Python lo informa.
- **Configuración del MPU**: acelerómetro ±4 g, giroscopio ±500 °/s, filtro paso bajo interno
  `DLPF_CFG = 3` (≈41 Hz) en ambos. Se eligió 41 Hz por estar por debajo de la mitad de la
  frecuencia de muestreo (100 Hz), para evitar aliasing.
- **Magnetómetro**: modo bypass, 16 bits, 100 Hz. Las celdas quedan vacías cuando no hay
  lectura nueva. Los ejes se reordenan para coincidir con los del acelerómetro
  (`mx = hy`, `my = hx`, `mz = −hz`); el valor sigue siendo crudo.
- **BMP280**: sobremuestreo ×1 en temperatura y ×8 en presión, modo normal, sin filtro IIR.
  Los coeficientes `dig_*` se leen al arrancar y se guardan en `meta.json`.
- **`meta.json`** incluye además tres campos informativos: `ak8963_asa` (ajuste de sensibilidad
  de fábrica del magnetómetro, que Python aplica), `mpu_dlpf_cfg` y `bmp280_direccion`.
- WiFi y Bluetooth apagados y procesador a 80 MHz para gastar menos pilas.

## Pendientes

Ver `procesamiento/docs/PENDIENTES_HARDWARE.md`. Los más importantes para el firmware: que
arranque con la SD conectada a G5, frecuencia real de muestreo y muestras perdidas en una
grabación de 90 minutos, duración de las pilas y ejes del magnetómetro.
