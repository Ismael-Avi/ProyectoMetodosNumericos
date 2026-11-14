#include "almacenamiento.h"

#include <SD.h>
#include <SPI.h>

#include "configuracion.h"

// ---------------------------------------------------------------------------
// Doble buffer
// ---------------------------------------------------------------------------

bool crearBuffer(BufferDoble &buffer, size_t tamano) {
  buffer.datos[0] = (char *)malloc(tamano);
  buffer.datos[1] = (char *)malloc(tamano);
  buffer.usados[0] = 0;
  buffer.usados[1] = 0;
  buffer.tamano = tamano;
  buffer.activo = 0;
  buffer.pendiente = false;
  buffer.candado = xSemaphoreCreateMutex();
  return buffer.datos[0] != nullptr && buffer.datos[1] != nullptr && buffer.candado != nullptr;
}

// Deja el buffer activo en espera de ser guardado y empieza a usar el otro.
// Solo se llama con el candado tomado y con "pendiente" en false.
static void intercambiar(BufferDoble &buffer) {
  buffer.pendiente = true;
  buffer.activo = 1 - buffer.activo;
  buffer.usados[buffer.activo] = 0;
}

bool agregarAlBuffer(BufferDoble &buffer, const char *texto, size_t largo, bool &bufferLleno) {
  bool agregado = false;
  bufferLleno = false;
  xSemaphoreTake(buffer.candado, portMAX_DELAY);

  bool cabe = buffer.usados[buffer.activo] + largo <= buffer.tamano;
  if (!cabe && !buffer.pendiente) {
    intercambiar(buffer);      // el activo está lleno y el otro está libre
    bufferLleno = true;
    cabe = true;
  }
  if (cabe) {
    memcpy(buffer.datos[buffer.activo] + buffer.usados[buffer.activo], texto, largo);
    buffer.usados[buffer.activo] += largo;
    agregado = true;
  }
  // Si no cabe y el otro buffer todavía se está guardando, la muestra se pierde.

  xSemaphoreGive(buffer.candado);
  return agregado;
}

bool tomarBloque(BufferDoble &buffer, bool forzar, const char *&datos, size_t &largo) {
  xSemaphoreTake(buffer.candado, portMAX_DELAY);
  if (!buffer.pendiente && forzar && buffer.usados[buffer.activo] > 0) {
    intercambiar(buffer);
  }
  bool hayBloque = buffer.pendiente;
  if (hayBloque) {
    int enEspera = 1 - buffer.activo;
    datos = buffer.datos[enEspera];
    largo = buffer.usados[enEspera];
  }
  xSemaphoreGive(buffer.candado);
  return hayBloque;
}

void liberarBloque(BufferDoble &buffer) {
  xSemaphoreTake(buffer.candado, portMAX_DELAY);
  buffer.pendiente = false;
  xSemaphoreGive(buffer.candado);
}

// ---------------------------------------------------------------------------
// Tarjeta y archivos
// ---------------------------------------------------------------------------

bool iniciarTarjeta() {
  SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, PIN_SD_CS);
  return SD.begin(PIN_SD_CS, SPI, FRECUENCIA_SPI_SD_HZ);
}

// El ESP32 no tiene fecha ni hora, así que las carpetas se numeran: sesion_001,
// sesion_002... Se usa el primer número que todavía no existe en la tarjeta.
bool crearCarpetaDeSesion(char *ruta, size_t largoMaximo) {
  for (int numero = 1; numero <= NUMERO_MAXIMO_DE_SESION; numero++) {
    snprintf(ruta, largoMaximo, "/sesion_%03d", numero);
    if (!SD.exists(ruta)) {
      return SD.mkdir(ruta);
    }
  }
  return false;   // la tarjeta ya tiene 999 sesiones
}

bool abrirArchivoConEncabezado(File &archivo, const char *carpeta, const char *nombre,
                               const char *encabezado) {
  char ruta[48];
  snprintf(ruta, sizeof(ruta), "%s/%s", carpeta, nombre);
  archivo = SD.open(ruta, FILE_WRITE);
  if (!archivo) {
    return false;
  }
  archivo.print(encabezado);
  archivo.print("\n");
  archivo.flush();
  return true;
}

// Escribe meta.json con los mismos campos que navinercial/formato.py (CAMPOS_META).
// Los tres últimos campos son información extra que el lector de Python acepta.
bool escribirMeta(const char *carpeta, const InfoSensores &info) {
  char ruta[48];
  snprintf(ruta, sizeof(ruta), "%s/meta.json", carpeta);
  File archivo = SD.open(ruta, FILE_WRITE);
  if (!archivo) {
    return false;
  }
  const CalibracionBmp280 &c = info.calib;
  archivo.printf("{\n");
  archivo.printf("  \"formato_version\": %d,\n", VERSION_FORMATO);
  archivo.printf("  \"firmware_version\": \"%s\",\n", VERSION_FIRMWARE);
  archivo.printf("  \"chip_whoami\": \"0x%02x\",\n", info.whoami);
  archivo.printf("  \"tiene_magnetometro\": %s,\n", info.tieneMagnetometro ? "true" : "false");
  archivo.printf("  \"fs_imu_nominal_hz\": %u,\n", (unsigned)FS_IMU_HZ);
  archivo.printf("  \"fs_baro_nominal_hz\": %u,\n", (unsigned)FS_BARO_HZ);
  archivo.printf("  \"accel_rango_g\": %d,\n", ACCEL_RANGO_G);
  archivo.printf("  \"gyro_rango_dps\": %d,\n", GYRO_RANGO_DPS);
  archivo.printf("  \"bmp280_calib\": {\"dig_T1\": %u, \"dig_T2\": %d, \"dig_T3\": %d,\n",
                 c.dig_T1, c.dig_T2, c.dig_T3);
  archivo.printf("                   \"dig_P1\": %u, \"dig_P2\": %d, \"dig_P3\": %d, "
                 "\"dig_P4\": %d,\n", c.dig_P1, c.dig_P2, c.dig_P3, c.dig_P4);
  archivo.printf("                   \"dig_P5\": %d, \"dig_P6\": %d, \"dig_P7\": %d, "
                 "\"dig_P8\": %d, \"dig_P9\": %d},\n",
                 c.dig_P5, c.dig_P6, c.dig_P7, c.dig_P8, c.dig_P9);
  archivo.printf("  \"notas\": \"\",\n");
  archivo.printf("  \"ak8963_asa\": [%u, %u, %u],\n", info.asa[0], info.asa[1], info.asa[2]);
  archivo.printf("  \"mpu_dlpf_cfg\": %u,\n", MPU_DLPF_CFG);
  archivo.printf("  \"bmp280_direccion\": \"0x%02x\"\n", info.direccionBmp280);
  archivo.printf("}\n");
  archivo.close();
  return true;
}
