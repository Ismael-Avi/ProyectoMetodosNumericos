#include "sensores.h"

#include <Wire.h>

#include "configuracion.h"

// ---------------------------------------------------------------------------
// Registros del MPU-9250 / MPU-6500
// Fuente: InvenSense, "MPU-9250 Register Map and Descriptions".
// TODO: confirmar cada dirección con el PDF del mapa de registros.
// ---------------------------------------------------------------------------
const uint8_t MPU_SMPLRT_DIV = 0x19;
const uint8_t MPU_CONFIG = 0x1A;
const uint8_t MPU_GYRO_CONFIG = 0x1B;
const uint8_t MPU_ACCEL_CONFIG = 0x1C;
const uint8_t MPU_ACCEL_CONFIG2 = 0x1D;
const uint8_t MPU_INT_PIN_CFG = 0x37;
const uint8_t MPU_ACCEL_XOUT_H = 0x3B;   // desde aquí: 6 bytes accel, 2 temp, 6 gyro
const uint8_t MPU_USER_CTRL = 0x6A;
const uint8_t MPU_PWR_MGMT_1 = 0x6B;
const uint8_t MPU_WHO_AM_I = 0x75;

const uint8_t WHOAMI_MPU9250 = 0x71;     // con magnetómetro
const uint8_t WHOAMI_MPU9255 = 0x73;     // con magnetómetro
const uint8_t WHOAMI_MPU6500 = 0x70;     // sin magnetómetro

// ---------------------------------------------------------------------------
// Registros del AK8963. Fuente: AKM, hoja de datos del AK8963.
// ---------------------------------------------------------------------------
const uint8_t AK_WIA = 0x00;             // identificación: debe valer 0x48
const uint8_t AK_ST1 = 0x02;             // bit 0 (DRDY): hay una lectura nueva
const uint8_t AK_CNTL1 = 0x0A;
const uint8_t AK_ASAX = 0x10;            // ajuste de sensibilidad de fábrica (3 bytes)
const uint8_t AK_ID_ESPERADO = 0x48;
const uint8_t AK_MODO_APAGADO = 0x00;
const uint8_t AK_MODO_ROM = 0x0F;        // acceso a los valores de fábrica
const uint8_t AK_MODO_16BITS_100HZ = 0x16;   // bit 4 = 16 bits; 0110 = medición continua 2 (100 Hz)
const uint8_t AK_ST2_DESBORDE = 0x08;    // bit 3 (HOFL): el campo saturó el sensor

// ---------------------------------------------------------------------------
// Registros del BMP280. Fuente: Bosch Sensortec, hoja de datos BST-BMP280-DS001.
// ---------------------------------------------------------------------------
const uint8_t BMP_CALIB = 0x88;          // 24 bytes: dig_T1..dig_T3, dig_P1..dig_P9
const uint8_t BMP_ID = 0xD0;
const uint8_t BMP_RESET = 0xE0;
const uint8_t BMP_CTRL_MEAS = 0xF4;
const uint8_t BMP_CONFIG = 0xF5;
const uint8_t BMP_DATOS = 0xF7;          // 3 bytes de presión y 3 de temperatura
const uint8_t BMP_VALOR_RESET = 0xB6;
// ctrl_meas = 001 100 11: sobremuestreo de temperatura x1, de presión x8, modo normal.
// Con esta configuración el sensor mide unas 40 veces por segundo, así que cada lectura a
// 25 Hz es una medición nueva. Filtro IIR apagado y espera de 0,5 ms (config = 0).
// TODO: confirmar el tiempo de medición en la hoja de datos y decidir si conviene x16.
const uint8_t BMP_VALOR_CTRL_MEAS = 0x33;
const uint8_t BMP_VALOR_CONFIG = 0x00;

// ---------------------------------------------------------------------------
// Funciones básicas de I2C
// ---------------------------------------------------------------------------

static bool escribirRegistro(uint8_t direccion, uint8_t registro, uint8_t valor) {
  Wire.beginTransmission(direccion);
  Wire.write(registro);
  Wire.write(valor);
  return Wire.endTransmission() == 0;   // 0 = el sensor respondió
}

static bool leerRegistros(uint8_t direccion, uint8_t registro, uint8_t *destino, size_t cantidad) {
  Wire.beginTransmission(direccion);
  Wire.write(registro);
  if (Wire.endTransmission(false) != 0) {   // false = no soltar el bus antes de leer
    return false;
  }
  if (Wire.requestFrom(direccion, cantidad) != cantidad) {
    return false;
  }
  for (size_t i = 0; i < cantidad; i++) {
    destino[i] = Wire.read();
  }
  return true;
}

// Une dos bytes en un entero de 16 bits con signo.
static int16_t unirBytes(uint8_t alto, uint8_t bajo) {
  return (int16_t)(((uint16_t)alto << 8) | bajo);
}

// ---------------------------------------------------------------------------
// Inicio de cada sensor
// ---------------------------------------------------------------------------

static bool iniciarMpu(InfoSensores &info) {
  escribirRegistro(DIRECCION_MPU, MPU_PWR_MGMT_1, 0x80);   // reinicio del chip
  delay(100);
  if (!escribirRegistro(DIRECCION_MPU, MPU_PWR_MGMT_1, 0x01)) {   // despertar, reloj del giroscopio
    return false;
  }
  delay(10);
  if (!leerRegistros(DIRECCION_MPU, MPU_WHO_AM_I, &info.whoami, 1)) {
    return false;
  }

  // Filtro paso bajo interno (ver MPU_DLPF_CFG en configuracion.h).
  escribirRegistro(DIRECCION_MPU, MPU_CONFIG, MPU_DLPF_CFG);          // giroscopio
  escribirRegistro(DIRECCION_MPU, MPU_ACCEL_CONFIG2, MPU_DLPF_CFG);   // acelerómetro
  // Divisor 0: el chip actualiza sus registros 1000 veces por segundo. Nosotros leemos a
  // 200 Hz con nuestro propio temporizador, así que cada lectura tiene como máximo 1 ms.
  escribirRegistro(DIRECCION_MPU, MPU_SMPLRT_DIV, 0);
  escribirRegistro(DIRECCION_MPU, MPU_GYRO_CONFIG, 0x08);    // bits 4:3 = 01 -> ±500 °/s
  escribirRegistro(DIRECCION_MPU, MPU_ACCEL_CONFIG, 0x08);   // bits 4:3 = 01 -> ±4 g
  // Modo bypass: el magnetómetro queda conectado directamente a nuestro bus I2C.
  escribirRegistro(DIRECCION_MPU, MPU_USER_CTRL, 0x00);
  escribirRegistro(DIRECCION_MPU, MPU_INT_PIN_CFG, 0x02);
  delay(10);
  return true;
}

static bool iniciarMagnetometro(InfoSensores &info) {
  uint8_t id = 0;
  if (!leerRegistros(DIRECCION_AK8963, AK_WIA, &id, 1) || id != AK_ID_ESPERADO) {
    return false;
  }
  // Leer el ajuste de sensibilidad de fábrica (hay que pasar por el modo "ROM").
  uint8_t asa[3];
  escribirRegistro(DIRECCION_AK8963, AK_CNTL1, AK_MODO_APAGADO);
  delay(10);
  escribirRegistro(DIRECCION_AK8963, AK_CNTL1, AK_MODO_ROM);
  delay(10);
  if (!leerRegistros(DIRECCION_AK8963, AK_ASAX, asa, 3)) {
    return false;
  }
  escribirRegistro(DIRECCION_AK8963, AK_CNTL1, AK_MODO_APAGADO);
  delay(10);
  escribirRegistro(DIRECCION_AK8963, AK_CNTL1, AK_MODO_16BITS_100HZ);
  delay(10);

  // Se guardan en el mismo orden que las columnas mx, my, mz (ver leerMagnetometro).
  info.asa[0] = asa[1];
  info.asa[1] = asa[0];
  info.asa[2] = asa[2];
  return true;
}

static bool iniciarBarometro(InfoSensores &info) {
  const uint8_t direcciones[2] = {DIRECCION_BMP280_A, DIRECCION_BMP280_B};
  bool encontrado = false;
  for (uint8_t direccion : direcciones) {
    if (leerRegistros(direccion, BMP_ID, &info.idBmp280, 1)) {
      info.direccionBmp280 = direccion;
      encontrado = true;
      break;
    }
  }
  if (!encontrado) {
    return false;
  }

  escribirRegistro(info.direccionBmp280, BMP_RESET, BMP_VALOR_RESET);
  delay(10);

  // Los coeficientes vienen con el byte bajo primero.
  uint8_t b[24];
  if (!leerRegistros(info.direccionBmp280, BMP_CALIB, b, 24)) {
    return false;
  }
  CalibracionBmp280 &c = info.calib;
  c.dig_T1 = (uint16_t)unirBytes(b[1], b[0]);
  c.dig_T2 = unirBytes(b[3], b[2]);
  c.dig_T3 = unirBytes(b[5], b[4]);
  c.dig_P1 = (uint16_t)unirBytes(b[7], b[6]);
  c.dig_P2 = unirBytes(b[9], b[8]);
  c.dig_P3 = unirBytes(b[11], b[10]);
  c.dig_P4 = unirBytes(b[13], b[12]);
  c.dig_P5 = unirBytes(b[15], b[14]);
  c.dig_P6 = unirBytes(b[17], b[16]);
  c.dig_P7 = unirBytes(b[19], b[18]);
  c.dig_P8 = unirBytes(b[21], b[20]);
  c.dig_P9 = unirBytes(b[23], b[22]);

  escribirRegistro(info.direccionBmp280, BMP_CONFIG, BMP_VALOR_CONFIG);
  return escribirRegistro(info.direccionBmp280, BMP_CTRL_MEAS, BMP_VALOR_CTRL_MEAS);
}

bool iniciarSensores(InfoSensores &info, const char *&mensajeError) {
  info = InfoSensores();   // todo en cero

  if (!iniciarMpu(info)) {
    mensajeError = "El MPU no responde en la direccion 0x68";
    return false;
  }
  bool chipConMagnetometro = (info.whoami == WHOAMI_MPU9250 || info.whoami == WHOAMI_MPU9255);
  if (!chipConMagnetometro && info.whoami != WHOAMI_MPU6500) {
    mensajeError = "WHO_AM_I desconocido (se esperaba 0x71, 0x73 o 0x70)";
    return false;
  }
  // Si el chip debería tener magnetómetro pero el AK8963 no responde, se sigue sin él.
  // meta.json dirá "tiene_magnetometro": false y las columnas mx, my, mz quedarán vacías
  // (el lector de Python acepta ese caso).
  // TODO: si pasa con el dispositivo real, revisar el modo bypass y la dirección 0x0C.
  info.tieneMagnetometro = chipConMagnetometro && iniciarMagnetometro(info);

  if (!iniciarBarometro(info)) {
    mensajeError = "El BMP280 no responde en 0x76 ni en 0x77";
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Lecturas
// ---------------------------------------------------------------------------

bool leerImu(LecturaImu &lectura) {
  uint8_t b[14];
  if (!leerRegistros(DIRECCION_MPU, MPU_ACCEL_XOUT_H, b, 14)) {
    return false;
  }
  // El MPU entrega primero el byte alto. Los bytes 6 y 7 son la temperatura del chip
  // (no se guarda).
  lectura.ax = unirBytes(b[0], b[1]);
  lectura.ay = unirBytes(b[2], b[3]);
  lectura.az = unirBytes(b[4], b[5]);
  lectura.gx = unirBytes(b[8], b[9]);
  lectura.gy = unirBytes(b[10], b[11]);
  lectura.gz = unirBytes(b[12], b[13]);
  return true;
}

bool leerMagnetometro(LecturaMag &lectura) {
  // Una sola lectura de 8 bytes: ST1, 6 bytes de datos y ST2. Leer ST2 es obligatorio:
  // le avisa al sensor que ya se leyó la medición.
  uint8_t b[8];
  if (!leerRegistros(DIRECCION_AK8963, AK_ST1, b, 8)) {
    return false;
  }
  bool hayLecturaNueva = b[0] & 0x01;
  bool desborde = b[7] & AK_ST2_DESBORDE;
  if (!hayLecturaNueva || desborde) {
    return false;
  }
  // El AK8963 entrega primero el byte bajo (al revés que el MPU).
  int16_t hx = unirBytes(b[2], b[1]);
  int16_t hy = unirBytes(b[4], b[3]);
  int16_t hz = unirBytes(b[6], b[5]);

  // Dentro del MPU-9250 el magnetómetro está montado con otros ejes: su X es el Y del
  // acelerómetro, su Y es el X del acelerómetro y su Z apunta al revés. Aquí se pasan a
  // los ejes del acelerómetro para que todas las columnas del archivo usen los mismos
  // ejes. Sigue siendo el valor crudo (solo se reordena y se cambia un signo).
  // TODO: comprobar con el dispositivo real (girándolo) que los ejes quedan bien.
  lectura.mx = hy;
  lectura.my = hx;
  lectura.mz = -hz;
  return true;
}

bool leerBarometro(uint8_t direccion, LecturaBaro &lectura) {
  uint8_t b[6];
  if (!leerRegistros(direccion, BMP_DATOS, b, 6)) {
    return false;
  }
  // Cada valor ocupa 20 bits repartidos en 3 bytes: 8 + 8 + los 4 bits altos del tercero.
  lectura.adc_P = ((uint32_t)b[0] << 12) | ((uint32_t)b[1] << 4) | (b[2] >> 4);
  lectura.adc_T = ((uint32_t)b[3] << 12) | ((uint32_t)b[4] << 4) | (b[5] >> 4);
  return true;
}

// ---------------------------------------------------------------------------
// Conversiones (solo para el modo de prueba por monitor serie)
// ---------------------------------------------------------------------------

float convertirAccelAG(int16_t crudo) {
  return crudo / 8192.0f;           // ±4 g: 8192 LSB por g
}

float convertirGyroADps(int16_t crudo) {
  return crudo / 65.5f;             // ±500 °/s: 65,5 LSB por °/s
}

float convertirMagAMicroteslas(int16_t crudo, uint8_t asa) {
  // 0,15 µT por LSB en 16 bits, corregido con el ajuste de sensibilidad de fábrica.
  float ajuste = (asa - 128) / 256.0f + 1.0f;
  return crudo * 0.15f * ajuste;
}

// Fórmula de compensación de la hoja de datos del BMP280 (versión de punto flotante).
// Es la misma que navinercial/bmp280.py.
void compensarBmp280(const CalibracionBmp280 &c, uint32_t adc_T, uint32_t adc_P,
                     double &temperaturaC, double &presionPa) {
  double var1 = (adc_T / 16384.0 - c.dig_T1 / 1024.0) * c.dig_T2;
  double diferencia = adc_T / 131072.0 - c.dig_T1 / 8192.0;
  double var2 = diferencia * diferencia * c.dig_T3;
  double t_fine = var1 + var2;
  temperaturaC = t_fine / 5120.0;

  var1 = t_fine / 2.0 - 64000.0;
  var2 = var1 * var1 * c.dig_P6 / 32768.0;
  var2 = var2 + var1 * c.dig_P5 * 2.0;
  var2 = var2 / 4.0 + c.dig_P4 * 65536.0;
  var1 = (c.dig_P3 * var1 * var1 / 524288.0 + c.dig_P2 * var1) / 524288.0;
  var1 = (1.0 + var1 / 32768.0) * c.dig_P1;
  if (var1 == 0.0) {
    presionPa = 0.0;                // evita dividir por cero con un sensor defectuoso
    return;
  }
  double p = 1048576.0 - adc_P;
  p = (p - var2 / 4096.0) * 6250.0 / var1;
  var1 = c.dig_P9 * p * p / 2147483648.0;
  var2 = p * c.dig_P8 / 32768.0;
  presionPa = p + (var1 + var2 + c.dig_P7) / 16.0;
}
