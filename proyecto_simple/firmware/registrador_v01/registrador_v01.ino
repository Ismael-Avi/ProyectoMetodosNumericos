/*
 * ============================================================================
 *  Registrador inercial - firmware v0.1
 *  Proyecto A, Métodos Numéricos: navegación inercial (Metro de Quito)
 * ============================================================================
 *
 *  QUÉ HACE
 *   - Lee el MPU-6500 (acelerómetro + giroscopio) a 200 Hz.
 *   - Lee el BMP280 (presión + temperatura) a 25 Hz.
 *   - Guarda los valores CRUDOS en la microSD (formato v0 de CONTEXTO_PROYECTO.md).
 *     La conversión a unidades físicas se hace después, en Python.
 *   - Guarda las pulsaciones del botón (G4) en eventos.csv.
 *   - LED azul (G2): parpadeo lento = grabando; parpadeo rápido = error.
 *
 *  CÓMO ESTÁ ORGANIZADO (dos tareas que corren en paralelo, una en cada núcleo)
 *   - tareaMuestreo  (núcleo 1): cada 5 ms lee el sensor y mete la muestra en una cola.
 *   - tareaEscritura (núcleo 0): saca las muestras de la cola y las escribe en la tarjeta.
 *   ¿Por qué una cola? Escribir en la microSD a veces tarda decenas de milisegundos.
 *   Si leyéramos y escribiéramos en el mismo lugar, en esos momentos se perderían
 *   muestras. Con la cola, el muestreo nunca espera a la tarjeta.
 *
 *  CÓMO TERMINAR UNA SESIÓN
 *   Apagar el interruptor (o desconectar el USB). Los archivos se guardan en la
 *   tarjeta cada 1 segundo, así que al cortar la energía se pierde como máximo
 *   el último segundo.
 *
 *  ARCHIVOS QUE GENERA (una carpeta por sesión: /sesion_001, /sesion_002, ...)
 *   meta.json    configuración del sensor y coeficientes de calibración del BMP280
 *   imu.csv      seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz   (mx,my,mz vacíos: no hay magnetómetro)
 *   baro.csv     seq,t_us,adc_T,adc_P
 *   eventos.csv  t_us,evento                            (evento 1 = pulsación del botón)
 *
 *   seq  = contador de muestra. Aumenta de 1 en 1 aunque una muestra se pierda,
 *          así que un salto en seq indica una muestra perdida.
 *   t_us = microsegundos desde que arrancó el ESP32 (esp_timer_get_time()),
 *          tomado justo antes de leer el sensor.
 */

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <WiFi.h>
#include "esp_timer.h"

// ----------------------------------------------------------------------------
// Pines (ver la guía de armado)
// ----------------------------------------------------------------------------
const int PIN_SDA   = 21;
const int PIN_SCL   = 22;
const int PIN_SD_CS = 5;
const int PIN_BOTON = 4;
const int PIN_LED   = 2;

// ----------------------------------------------------------------------------
// Direcciones I2C (las que salieron en la prueba del paso 3)
// ----------------------------------------------------------------------------
const uint8_t DIR_MPU = 0x68;
const uint8_t DIR_BMP = 0x76;   // cambiar a 0x77 si el barómetro aparece ahí

// ----------------------------------------------------------------------------
// Frecuencias de muestreo
// ----------------------------------------------------------------------------
const int FS_IMU_HZ      = 200;
const int PERIODO_IMU_MS = 1000 / FS_IMU_HZ;    // 5 ms entre muestras
const int DIVISOR_BARO   = 8;                   // 1 lectura de barómetro cada 8 del IMU
const int FS_BARO_HZ     = FS_IMU_HZ / DIVISOR_BARO;   // 25 Hz

// ----------------------------------------------------------------------------
// Configuración del MPU-6500 (fuente: "MPU-6500 Register Map", InvenSense)
// ----------------------------------------------------------------------------
const int     ACCEL_RANGO_G   = 4;
const uint8_t ACCEL_CONFIG    = 0x08;  // AFS_SEL=01 -> ±4 g     (8192 LSB/g)
const int     GYRO_RANGO_DPS  = 500;
const uint8_t GYRO_CONFIG     = 0x08;  // FS_SEL=01  -> ±500 °/s (65,5 LSB/(°/s))
// Filtro pasa-bajos interno del sensor. Se deja por debajo de la mitad de la
// frecuencia de muestreo (100 Hz) para evitar aliasing.
const uint8_t DLPF_CFG        = 3;     // giroscopio ≈ 41 Hz
const uint8_t A_DLPF_CFG      = 3;     // acelerómetro ≈ 45 Hz

// ----------------------------------------------------------------------------
// Configuración del BMP280 (fuente: hoja de datos Bosch BMP280)
// ----------------------------------------------------------------------------
// ctrl_meas = osrs_t(3 bits) | osrs_p(3 bits) | modo(2 bits)
//   osrs_t = x1 (001), osrs_p = x8 (100), modo normal (11)  -> 0b00110011 = 0x33
//   Tiempo de medición ≈ 22,5 ms -> unas 44 mediciones/s, suficiente para leer a 25 Hz.
const uint8_t BMP_CTRL_MEAS = 0x33;
// config = t_sb 0,5 ms (000) | filtro IIR apagado (000) -> 0x00 (queremos datos crudos)
const uint8_t BMP_CONFIG    = 0x00;

// ----------------------------------------------------------------------------
// Estructuras de datos que viajan por las colas
// ----------------------------------------------------------------------------
struct MuestraImu {
  uint32_t seq;
  int64_t  t_us;
  int16_t  ax, ay, az;   // crudos del acelerómetro
  int16_t  gx, gy, gz;   // crudos del giroscopio
};

struct MuestraBaro {
  uint32_t seq;
  int64_t  t_us;
  int32_t  adc_T;        // crudo de 20 bits
  int32_t  adc_P;        // crudo de 20 bits
};

struct CalibBmp280 {
  uint16_t T1; int16_t T2, T3;
  uint16_t P1; int16_t P2, P3, P4, P5, P6, P7, P8, P9;
};

// Colas (el tamaño es cuántas muestras pueden esperar antes de escribirse)
QueueHandle_t colaImu;       // 2000 muestras = 10 s de margen
QueueHandle_t colaBaro;
QueueHandle_t colaEventos;

// Archivos de la sesión
File archivoImu, archivoBaro, archivoEventos;
char carpetaSesion[20];

// Contadores para el reporte por el monitor serie
volatile uint32_t perdidasCola = 0;   // muestras descartadas porque la cola estaba llena
volatile uint32_t erroresI2C   = 0;   // lecturas del sensor que fallaron
uint32_t imuEscritas = 0, baroEscritas = 0, eventosEscritos = 0;
uint32_t erroresEscritura = 0;
uint32_t colaMaxima = 0;

// ============================================================================
// Funciones auxiliares de I2C
// ============================================================================

// Escribe un byte en un registro del dispositivo.
bool escribirRegistro(uint8_t dir, uint8_t reg, uint8_t valor) {
  Wire.beginTransmission(dir);
  Wire.write(reg);
  Wire.write(valor);
  return Wire.endTransmission() == 0;
}

// Lee n bytes seguidos a partir de un registro.
bool leerBytes(uint8_t dir, uint8_t reg, uint8_t *buf, size_t n) {
  Wire.beginTransmission(dir);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)dir, n, true) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

// ============================================================================
// Errores: avisa por el monitor serie y deja el LED parpadeando rápido
// ============================================================================
void errorFatal(const char *mensaje) {
  Serial.printf("ERROR: %s\n", mensaje);
  while (true) {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(100);
  }
}

// ============================================================================
// Configuración de los sensores
// ============================================================================

// Configura el MPU-6500. Devuelve el WHO_AM_I leído (0x70 = MPU-6500).
bool configurarMpu(uint8_t &whoami) {
  if (!escribirRegistro(DIR_MPU, 0x6B, 0x80)) return false;  // PWR_MGMT_1: reinicio
  delay(100);
  escribirRegistro(DIR_MPU, 0x6B, 0x01);       // PWR_MGMT_1: despierta, reloj del giroscopio
  delay(50);
  if (!leerBytes(DIR_MPU, 0x75, &whoami, 1)) return false;   // WHO_AM_I
  escribirRegistro(DIR_MPU, 0x19, 0x00);       // SMPLRT_DIV: muestreo interno a 1 kHz
  escribirRegistro(DIR_MPU, 0x1A, DLPF_CFG);   // CONFIG: filtro del giroscopio
  escribirRegistro(DIR_MPU, 0x1B, GYRO_CONFIG);
  escribirRegistro(DIR_MPU, 0x1C, ACCEL_CONFIG);
  escribirRegistro(DIR_MPU, 0x1D, A_DLPF_CFG); // ACCEL_CONFIG2: filtro del acelerómetro
  delay(50);
  return true;
}

// Configura el BMP280 y lee sus coeficientes de calibración de fábrica.
// Los coeficientes se guardan en meta.json porque Python los necesita para
// convertir adc_T y adc_P a temperatura y presión.
bool configurarBmp(CalibBmp280 &c) {
  uint8_t id;
  if (!leerBytes(DIR_BMP, 0xD0, &id, 1)) return false;
  if (id != 0x58 && id != 0x60) return false;      // 0x58 = BMP280, 0x60 = BME280
  escribirRegistro(DIR_BMP, 0xE0, 0xB6);           // reinicio por software
  delay(10);

  uint8_t b[24];
  if (!leerBytes(DIR_BMP, 0x88, b, 24)) return false;
  // Los coeficientes vienen en little-endian (primero el byte bajo)
  c.T1 = (uint16_t)(b[1] << 8 | b[0]);
  c.T2 = (int16_t)(b[3] << 8 | b[2]);
  c.T3 = (int16_t)(b[5] << 8 | b[4]);
  c.P1 = (uint16_t)(b[7] << 8 | b[6]);
  c.P2 = (int16_t)(b[9] << 8 | b[8]);
  c.P3 = (int16_t)(b[11] << 8 | b[10]);
  c.P4 = (int16_t)(b[13] << 8 | b[12]);
  c.P5 = (int16_t)(b[15] << 8 | b[14]);
  c.P6 = (int16_t)(b[17] << 8 | b[16]);
  c.P7 = (int16_t)(b[19] << 8 | b[18]);
  c.P8 = (int16_t)(b[21] << 8 | b[20]);
  c.P9 = (int16_t)(b[23] << 8 | b[22]);

  // Primero config (solo se acepta en modo reposo) y luego ctrl_meas (arranca la medición)
  escribirRegistro(DIR_BMP, 0xF5, BMP_CONFIG);
  escribirRegistro(DIR_BMP, 0xF4, BMP_CTRL_MEAS);
  delay(50);
  return true;
}

// ============================================================================
// Lectura de los sensores
// ============================================================================

// Lee los 14 bytes del MPU a partir de ACCEL_XOUT_H (0x3B):
// ax, ay, az, temperatura, gx, gy, gz (cada uno en 2 bytes, primero el alto).
bool leerImu(MuestraImu &m) {
  uint8_t b[14];
  if (!leerBytes(DIR_MPU, 0x3B, b, 14)) return false;
  m.ax = (int16_t)(b[0] << 8 | b[1]);
  m.ay = (int16_t)(b[2] << 8 | b[3]);
  m.az = (int16_t)(b[4] << 8 | b[5]);
  // b[6], b[7] = temperatura interna del MPU (no se usa)
  m.gx = (int16_t)(b[8] << 8 | b[9]);
  m.gy = (int16_t)(b[10] << 8 | b[11]);
  m.gz = (int16_t)(b[12] << 8 | b[13]);
  return true;
}

// Lee los 6 bytes del BMP280 a partir de 0xF7: presión (3 bytes) y temperatura (3 bytes).
// Cada valor tiene 20 bits: msb(8) | lsb(8) | xlsb(4 bits altos).
bool leerBaro(MuestraBaro &m) {
  uint8_t b[6];
  if (!leerBytes(DIR_BMP, 0xF7, b, 6)) return false;
  m.adc_P = ((int32_t)b[0] << 12) | ((int32_t)b[1] << 4) | (b[2] >> 4);
  m.adc_T = ((int32_t)b[3] << 12) | ((int32_t)b[4] << 4) | (b[5] >> 4);
  return true;
}

// ============================================================================
// Botón: interrupción en el flanco de bajada (al presionar, el pin pasa a LOW)
// ============================================================================
volatile int64_t ultimoBoton_us = 0;

void IRAM_ATTR isrBoton() {
  int64_t t = esp_timer_get_time();
  if (t - ultimoBoton_us > 200000) {        // antirrebote: ignora 200 ms después de cada pulsación
    ultimoBoton_us = t;
    BaseType_t despertar = pdFALSE;
    xQueueSendFromISR(colaEventos, &t, &despertar);
    if (despertar) portYIELD_FROM_ISR();
  }
}

// ============================================================================
// Sesión: crea la carpeta y los archivos
// ============================================================================
void crearSesion(uint8_t whoami, const CalibBmp280 &c) {
  // Sin reloj de tiempo real no conocemos la fecha, así que numeramos las carpetas.
  int n = 1;
  do {
    snprintf(carpetaSesion, sizeof(carpetaSesion), "/sesion_%03d", n++);
  } while (SD.exists(carpetaSesion) && n < 1000);
  if (!SD.mkdir(carpetaSesion)) errorFatal("No se pudo crear la carpeta de la sesion");

  char ruta[40];

  // ---- meta.json ----
  snprintf(ruta, sizeof(ruta), "%s/meta.json", carpetaSesion);
  File meta = SD.open(ruta, FILE_WRITE);
  if (!meta) errorFatal("No se pudo crear meta.json");
  meta.printf("{\n");
  meta.printf("  \"formato_version\": 0,\n");
  meta.printf("  \"firmware_version\": \"0.1\",\n");
  meta.printf("  \"chip_whoami\": \"0x%02X\",\n", whoami);
  meta.printf("  \"tiene_magnetometro\": false,\n");
  meta.printf("  \"fs_imu_nominal_hz\": %d,\n", FS_IMU_HZ);
  meta.printf("  \"fs_baro_nominal_hz\": %d,\n", FS_BARO_HZ);
  meta.printf("  \"accel_rango_g\": %d,\n", ACCEL_RANGO_G);
  meta.printf("  \"gyro_rango_dps\": %d,\n", GYRO_RANGO_DPS);
  meta.printf("  \"mpu_dlpf_cfg\": %d,\n", DLPF_CFG);
  meta.printf("  \"mpu_a_dlpf_cfg\": %d,\n", A_DLPF_CFG);
  meta.printf("  \"bmp280_osrs_t\": 1,\n");
  meta.printf("  \"bmp280_osrs_p\": 8,\n");
  meta.printf("  \"bmp280_filtro_iir\": 0,\n");
  meta.printf("  \"bmp280_calib\": {\"dig_T1\": %u, \"dig_T2\": %d, \"dig_T3\": %d,\n",
              c.T1, c.T2, c.T3);
  meta.printf("                   \"dig_P1\": %u, \"dig_P2\": %d, \"dig_P3\": %d, \"dig_P4\": %d,\n",
              c.P1, c.P2, c.P3, c.P4);
  meta.printf("                   \"dig_P5\": %d, \"dig_P6\": %d, \"dig_P7\": %d, \"dig_P8\": %d, \"dig_P9\": %d},\n",
              c.P5, c.P6, c.P7, c.P8, c.P9);
  meta.printf("  \"notas\": \"Sin reloj de tiempo real: carpetas numeradas (sesion_NNN). "
              "Magnetometro no disponible (MPU-6500): mx,my,mz vacios. "
              "t_us tomado justo antes de leer el sensor.\"\n");
  meta.printf("}\n");
  meta.close();

  // ---- archivos de datos con su encabezado ----
  snprintf(ruta, sizeof(ruta), "%s/imu.csv", carpetaSesion);
  archivoImu = SD.open(ruta, FILE_WRITE);
  snprintf(ruta, sizeof(ruta), "%s/baro.csv", carpetaSesion);
  archivoBaro = SD.open(ruta, FILE_WRITE);
  snprintf(ruta, sizeof(ruta), "%s/eventos.csv", carpetaSesion);
  archivoEventos = SD.open(ruta, FILE_WRITE);
  if (!archivoImu || !archivoBaro || !archivoEventos) errorFatal("No se pudieron crear los CSV");

  archivoImu.println("seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz");
  archivoBaro.println("seq,t_us,adc_T,adc_P");
  archivoEventos.println("t_us,evento");
  archivoImu.flush();
  archivoBaro.flush();
  archivoEventos.flush();
}

// ============================================================================
// Tarea de muestreo (núcleo 1): lee el sensor cada 5 ms exactos
// ============================================================================
void tareaMuestreo(void *arg) {
  uint32_t seqImu = 0, seqBaro = 0;
  TickType_t ultimoDespertar = xTaskGetTickCount();

  while (true) {
    // Espera hasta completar 5 ms desde la vez anterior (no 5 ms desde "ahora"),
    // así el periodo no se va alargando por el tiempo que tarda la lectura.
    vTaskDelayUntil(&ultimoDespertar, pdMS_TO_TICKS(PERIODO_IMU_MS));

    MuestraImu mi;
    mi.seq  = seqImu++;              // aumenta siempre: si la muestra se pierde, queda el salto
    mi.t_us = esp_timer_get_time();
    if (leerImu(mi)) {
      if (xQueueSend(colaImu, &mi, 0) != pdTRUE) perdidasCola++;
    } else {
      erroresI2C++;
    }

    if (mi.seq % DIVISOR_BARO == 0) {
      MuestraBaro mb;
      mb.seq  = seqBaro++;
      mb.t_us = esp_timer_get_time();
      if (leerBaro(mb)) {
        if (xQueueSend(colaBaro, &mb, 0) != pdTRUE) perdidasCola++;
      } else {
        erroresI2C++;
      }
    }
  }
}

// ============================================================================
// Tarea de escritura (núcleo 0): vacía las colas en la microSD
// ============================================================================
void escribirLinea(File &archivo, const char *linea, int n) {
  if (archivo.write((const uint8_t *)linea, n) != (size_t)n) erroresEscritura++;
}

void tareaEscritura(void *arg) {
  char linea[100];
  MuestraImu mi;
  MuestraBaro mb;
  int64_t tEvento;
  uint32_t ultimoFlush = millis(), ultimoLed = millis(), ultimoReporte = millis();

  while (true) {
    uint32_t enCola = uxQueueMessagesWaiting(colaImu);
    if (enCola > colaMaxima) colaMaxima = enCola;

    while (xQueueReceive(colaImu, &mi, 0) == pdTRUE) {
      int n = snprintf(linea, sizeof(linea), "%lu,%lld,%d,%d,%d,%d,%d,%d,,,\n",
                       (unsigned long)mi.seq, (long long)mi.t_us,
                       mi.ax, mi.ay, mi.az, mi.gx, mi.gy, mi.gz);
      escribirLinea(archivoImu, linea, n);
      imuEscritas++;
    }
    while (xQueueReceive(colaBaro, &mb, 0) == pdTRUE) {
      int n = snprintf(linea, sizeof(linea), "%lu,%lld,%ld,%ld\n",
                       (unsigned long)mb.seq, (long long)mb.t_us,
                       (long)mb.adc_T, (long)mb.adc_P);
      escribirLinea(archivoBaro, linea, n);
      baroEscritas++;
    }
    while (xQueueReceive(colaEventos, &tEvento, 0) == pdTRUE) {
      int n = snprintf(linea, sizeof(linea), "%lld,1\n", (long long)tEvento);
      escribirLinea(archivoEventos, linea, n);
      eventosEscritos++;
      Serial.println("Boton presionado");
    }

    uint32_t ahora = millis();

    // Cada 1 s se fuerza la escritura física en la tarjeta (por si se corta la energía)
    if (ahora - ultimoFlush >= 1000) {
      archivoImu.flush();
      archivoBaro.flush();
      archivoEventos.flush();
      ultimoFlush = ahora;
    }

    // LED: parpadeo lento mientras graba
    if (ahora - ultimoLed >= 500) {
      digitalWrite(PIN_LED, !digitalRead(PIN_LED));
      ultimoLed = ahora;
    }

    // Reporte cada 5 s por el monitor serie (útil en la prueba de 90 minutos)
    if (ahora - ultimoReporte >= 5000) {
      Serial.printf("t=%lus imu=%lu baro=%lu eventos=%lu | perdidas=%lu errI2C=%lu errSD=%lu colaMax=%lu\n",
                    (unsigned long)(ahora / 1000),
                    (unsigned long)imuEscritas, (unsigned long)baroEscritas,
                    (unsigned long)eventosEscritos, (unsigned long)perdidasCola,
                    (unsigned long)erroresI2C, (unsigned long)erroresEscritura,
                    (unsigned long)colaMaxima);
      ultimoReporte = ahora;
    }

    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ============================================================================
// setup: se ejecuta una vez al encender
// ============================================================================
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);   // botón suelto = HIGH, presionado = LOW

  // Radios apagadas: no se usan y así las pilas duran más
  WiFi.mode(WIFI_OFF);
  btStop();
  delay(500);
  Serial.println("\n=== Registrador inercial v0.1 ===");

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);              // I2C rápido (400 kHz): leer el MPU tarda ~0,4 ms

  uint8_t whoami = 0;
  if (!configurarMpu(whoami)) errorFatal("No responde el MPU (revisar SDA/SCL/VIN/GND)");
  Serial.printf("MPU listo, WHO_AM_I = 0x%02X\n", whoami);

  CalibBmp280 calib;
  if (!configurarBmp(calib)) errorFatal("No responde el BMP280 (revisar la direccion 0x76/0x77)");
  Serial.println("BMP280 listo");

  if (!SD.begin(PIN_SD_CS)) errorFatal("No se pudo iniciar la microSD (tarjeta, FAT32, cables)");
  crearSesion(whoami, calib);
  Serial.printf("Grabando en %s\n", carpetaSesion);

  colaImu     = xQueueCreate(2000, sizeof(MuestraImu));
  colaBaro    = xQueueCreate(300,  sizeof(MuestraBaro));
  colaEventos = xQueueCreate(50,   sizeof(int64_t));
  if (!colaImu || !colaBaro || !colaEventos) errorFatal("Sin memoria para las colas");

  attachInterrupt(digitalPinToInterrupt(PIN_BOTON), isrBoton, FALLING);

  // Muestreo con prioridad alta en el núcleo 1; escritura con prioridad menor en el núcleo 0
  xTaskCreatePinnedToCore(tareaMuestreo,  "muestreo",  4096, NULL, 5, NULL, 1);
  xTaskCreatePinnedToCore(tareaEscritura, "escritura", 8192, NULL, 2, NULL, 0);
}

// El loop de Arduino no se usa: todo el trabajo lo hacen las dos tareas.
void loop() {
  vTaskDelete(NULL);
}
