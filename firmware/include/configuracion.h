// Configuración del registrador: pines, direcciones, frecuencias y tamaños.
// Todo lo que haya que cambiar al armar el dispositivo está en este archivo.
//
// Las cosas marcadas con TODO hay que confirmarlas con el hardware real.

#pragma once

#include <Arduino.h>

// Para activar el modo de prueba por monitor serie hay dos opciones:
//   1. Compilar con el entorno "prueba" de platformio.ini (recomendado).
//   2. Quitar el comentario de la línea siguiente.
// #define MODO_PRUEBA_SERIE

#define VERSION_FIRMWARE "0.1.0"
#define VERSION_FORMATO 0          // debe coincidir con VERSION_FORMATO de navinercial/formato.py

// ---------------------------------------------------------------------------
// Pines
// ---------------------------------------------------------------------------
const int PIN_I2C_SDA = 21;        // GY-91: SDA
const int PIN_I2C_SCL = 22;        // GY-91: SCL
const int PIN_SD_CS = 5;           // microSD: CS    TODO: G5 es un pin de arranque del ESP32;
                                   //                comprobar que el módulo SD no impide arrancar.
const int PIN_SD_SCK = 18;         // microSD: SCK
const int PIN_SD_MOSI = 23;        // microSD: MOSI
const int PIN_SD_MISO = 19;        // microSD: MISO
const int PIN_BOTON = 4;           // pulsador a GND (se usa la resistencia interna: INPUT_PULLUP)
const int PIN_LED = 2;             // LED de la placa   TODO: confirmar que el LED está en G2 y que
                                   //                   enciende con nivel alto en nuestra placa.

// ---------------------------------------------------------------------------
// Buses
// ---------------------------------------------------------------------------
const uint32_t FRECUENCIA_I2C_HZ = 400000;      // I2C rápido: 400 kHz
const uint32_t FRECUENCIA_SPI_SD_HZ = 10000000; // TODO: 10 MHz es conservador para cables sobre
                                                //       placa perforada; probar 20 MHz.

const uint8_t DIRECCION_MPU = 0x68;             // MPU-9250 / MPU-9255 / MPU-6500
const uint8_t DIRECCION_AK8963 = 0x0C;          // magnetómetro (visible solo en modo bypass)
const uint8_t DIRECCION_BMP280_A = 0x76;        // BMP280: se prueba primero esta dirección
const uint8_t DIRECCION_BMP280_B = 0x77;        // y después esta

// ---------------------------------------------------------------------------
// Muestreo
// ---------------------------------------------------------------------------
const uint32_t FS_IMU_HZ = 200;                 // acelerómetro y giroscopio
const uint32_t PERIODO_IMU_US = 1000000 / FS_IMU_HZ;   // 5000 µs
const uint32_t TICKS_POR_MUESTRA_MAG = 2;       // magnetómetro: 200 / 2 = 100 Hz
const uint32_t TICKS_POR_MUESTRA_BARO = 8;      // barómetro:    200 / 8 = 25 Hz
const uint32_t FS_BARO_HZ = FS_IMU_HZ / TICKS_POR_MUESTRA_BARO;

const int ACCEL_RANGO_G = 4;                    // ±4 g    -> 8192 LSB/g
const int GYRO_RANGO_DPS = 500;                 // ±500 °/s -> 65,5 LSB/(°/s)

// Filtro paso bajo interno del MPU (DLPF). Con DLPF_CFG = 3:
//   giroscopio:   ancho de banda 41 Hz
//   acelerómetro: ancho de banda 41 Hz (44,8 Hz según la revisión del mapa de registros)
// Se eligió 41 Hz porque queda bien por debajo de la mitad de la frecuencia de muestreo
// (100 Hz), y así se evita el aliasing; el movimiento de un ascensor o de un tren es mucho
// más lento que eso.
// TODO: confirmar los anchos de banda en el mapa de registros del MPU-9250 (registros 26 y 29).
const uint8_t MPU_DLPF_CFG = 3;

// ---------------------------------------------------------------------------
// Escritura en la microSD
// ---------------------------------------------------------------------------
// Cada archivo tiene DOS buffers de este tamaño: la tarea de muestreo llena uno mientras la
// tarea de escritura guarda el otro en la SD.
// El IMU produce unos 70 caracteres x 200 Hz = 14 000 bytes por segundo, así que un buffer
// de 16 384 bytes aguanta más de 1 s de SD ocupada sin perder muestras.
const size_t TAMANO_BUFFER_IMU = 16384;
const size_t TAMANO_BUFFER_BARO = 2048;
const size_t TAMANO_BUFFER_EVENTOS = 512;

// Cada cuánto se fuerza la escritura real en la tarjeta (flush). Si se corta la energía se
// pierde, como máximo, este tiempo de datos.
const uint32_t PERIODO_FLUSH_MS = 2000;

const int NUMERO_MAXIMO_DE_SESION = 999;        // carpetas sesion_001 ... sesion_999

// ---------------------------------------------------------------------------
// Botón
// ---------------------------------------------------------------------------
const int64_t ANTIRREBOTE_US = 50000;           // 50 ms: se ignoran flancos más seguidos que esto
                                                // TODO: ajustar con el pulsador real.
const int64_t PULSACION_LARGA_US = 3000000;     // mantener 3 s = terminar el registro
const int CODIGO_EVENTO_BOTON = 1;              // igual que EVENTO_BOTON en formato.py

// ---------------------------------------------------------------------------
// Energía
// ---------------------------------------------------------------------------
// Bajar la frecuencia del procesador de 240 a 80 MHz reduce el consumo. A 80 MHz el I2C y
// la SD funcionan igual.
// TODO: medir el consumo y la duración real de las 4 pilas AA (requisito: 90 minutos).
const uint32_t FRECUENCIA_CPU_MHZ = 80;
