// Lectura CRUDA de los sensores del GY-91 por I2C:
//   - MPU-9250 / MPU-9255 / MPU-6500: acelerómetro y giroscopio
//   - AK8963: magnetómetro (solo existe dentro del MPU-9250 y del MPU-9255)
//   - BMP280: barómetro
//
// Aquí no se convierte nada a unidades físicas: eso se hace después, en Python.
// (Las funciones "convertir..." solo las usa el modo de prueba por monitor serie.)

#pragma once

#include <Arduino.h>

struct LecturaImu {
  int16_t ax, ay, az;   // acelerómetro, crudo
  int16_t gx, gy, gz;   // giroscopio, crudo
};

struct LecturaMag {
  int16_t mx, my, mz;   // magnetómetro, crudo, ya en los ejes del acelerómetro
};

struct LecturaBaro {
  uint32_t adc_T;       // temperatura cruda (20 bits)
  uint32_t adc_P;       // presión cruda (20 bits)
};

// Coeficientes de calibración que cada BMP280 trae grabados de fábrica.
struct CalibracionBmp280 {
  uint16_t dig_T1;
  int16_t dig_T2, dig_T3;
  uint16_t dig_P1;
  int16_t dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9;
};

// Lo que se averigua de los sensores al arrancar (se guarda en meta.json).
struct InfoSensores {
  uint8_t whoami;              // registro WHO_AM_I del MPU: 0x71, 0x73 o 0x70
  bool tieneMagnetometro;
  uint8_t asa[3];              // ajuste de sensibilidad del AK8963, en el orden mx, my, mz
  uint8_t direccionBmp280;     // 0x76 o 0x77
  uint8_t idBmp280;            // registro "id" del barómetro (0x58 en un BMP280)
  CalibracionBmp280 calib;
};

// Configura los tres sensores. Devuelve false si falta el MPU o el BMP280; en ese caso
// "mensajeError" apunta a un texto que explica qué falló.
bool iniciarSensores(InfoSensores &info, const char *&mensajeError);

// Cada función devuelve true si la lectura es válida.
bool leerImu(LecturaImu &lectura);
bool leerMagnetometro(LecturaMag &lectura);   // true solo si hay una lectura NUEVA
bool leerBarometro(uint8_t direccion, LecturaBaro &lectura);

// Conversión a unidades físicas, solo para el modo de prueba por monitor serie.
float convertirAccelAG(int16_t crudo);        // g
float convertirGyroADps(int16_t crudo);       // °/s
float convertirMagAMicroteslas(int16_t crudo, uint8_t asa);   // µT
void compensarBmp280(const CalibracionBmp280 &c, uint32_t adc_T, uint32_t adc_P,
                     double &temperaturaC, double &presionPa);
