// Registrador inercial: ESP32 + GY-91 (MPU-9250 + BMP280) + microSD.
//
// Graba los datos CRUDOS de los sensores en el formato de procesamiento/navinercial/formato.py:
//
//   /sesion_NNN/meta.json     configuración y coeficientes del BMP280
//   /sesion_NNN/imu.csv       seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz     (200 Hz)
//   /sesion_NNN/baro.csv      seq,t_us,adc_T,adc_P                    (25 Hz)
//   /sesion_NNN/eventos.csv   t_us,evento                             (pulsaciones del botón)
//
// Cómo funciona:
//   1. Un temporizador avisa cada 5 ms (200 Hz) a la TAREA DE MUESTREO.
//   2. La tarea de muestreo lee los sensores, arma la línea de texto y la deja en un buffer
//      en memoria.
//   3. La TAREA DE ESCRITURA guarda los buffers llenos en la microSD y cada 2 s fuerza la
//      escritura real (flush), para perder poco si se corta la energía.
//   4. loop() solo maneja el LED y muestra el estado por el monitor serie.
//
// Uso: encender = empieza a grabar. Pulsación corta = marca un evento. Mantener el botón
// 3 segundos = cerrar los archivos (después se puede apagar sin perder nada).

#include <Arduino.h>
#include <SD.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

#include "almacenamiento.h"
#include "configuracion.h"
#include "sensores.h"

enum Estado {
  ESTADO_INICIANDO,
  ESTADO_GRABANDO,
  ESTADO_TERMINANDO,     // se pidió terminar: falta guardar lo que queda en los buffers
  ESTADO_TERMINADO,      // archivos cerrados: ya se puede apagar
  ESTADO_ERROR_SENSOR,
  ESTADO_ERROR_SD,
};

// "volatile": estas variables las leen y modifican varias tareas o una interrupción.
static volatile Estado estado = ESTADO_INICIANDO;
static volatile uint32_t muestrasDescartadas = 0;   // no cupieron en el buffer
static volatile uint32_t erroresDeLectura = 0;      // el sensor no respondió por I2C
static volatile uint32_t ultimaSeq = 0;
static volatile uint32_t milisUltimoDescarte = 0;

static InfoSensores info;
static BufferDoble bufferImu, bufferBaro, bufferEventos;
static File archivoImu, archivoBaro, archivoEventos;
static TaskHandle_t tareaMuestreo = nullptr;
static TaskHandle_t tareaEscritura = nullptr;
static QueueHandle_t colaPulsaciones = nullptr;     // instantes (t_us) de cada pulsación

// ---------------------------------------------------------------------------
// Botón: interrupción con antirrebote
// ---------------------------------------------------------------------------

// Se ejecuta en cada cambio del pin (al pulsar y al soltar). Un pulsador "rebota": al
// cambiar genera varios flancos muy seguidos. Solo se acepta una pulsación si el pin quedó
// en nivel bajo y pasaron más de ANTIRREBOTE_US desde el flanco anterior.
static void IRAM_ATTR alCambiarBoton() {
  static int64_t instanteFlancoAnterior = 0;
  int64_t ahora = esp_timer_get_time();
  bool pasoSuficienteTiempo = (ahora - instanteFlancoAnterior) > ANTIRREBOTE_US;
  instanteFlancoAnterior = ahora;

  if (pasoSuficienteTiempo && digitalRead(PIN_BOTON) == LOW) {
    BaseType_t despertarTarea = pdFALSE;
    xQueueSendFromISR(colaPulsaciones, &ahora, &despertarTarea);
    if (despertarTarea) {
      portYIELD_FROM_ISR();
    }
  }
}

// ---------------------------------------------------------------------------
// Temporizador de muestreo
// ---------------------------------------------------------------------------

// Se ejecuta cada PERIODO_IMU_US. Solo despierta a la tarea de muestreo. Si la tarea se
// atrasa, los avisos se acumulan y ella sabe cuántos períodos pasaron.
static void alVencerTemporizador(void *) {
  xTaskNotifyGive(tareaMuestreo);
}

// ---------------------------------------------------------------------------
// Tarea de muestreo
// ---------------------------------------------------------------------------

static void guardarLinea(BufferDoble &buffer, const char *linea, int largo) {
  bool bufferLleno = false;
  if (!agregarAlBuffer(buffer, linea, largo, bufferLleno)) {
    muestrasDescartadas = muestrasDescartadas + 1;
    milisUltimoDescarte = millis();
  }
  if (bufferLleno) {
    xTaskNotifyGive(tareaEscritura);   // hay un buffer lleno: despertar a la tarea de escritura
  }
}

static void muestrearImu(uint32_t seq, bool tocaMagnetometro) {
  char linea[96];
  LecturaImu imu;
  int64_t t_us = esp_timer_get_time();   // marca de tiempo, justo antes de leer
  if (!leerImu(imu)) {
    erroresDeLectura = erroresDeLectura + 1;
    return;                              // no se escribe la fila: queda un salto en seq
  }
  int largo = snprintf(linea, sizeof(linea), "%lu,%lld,%d,%d,%d,%d,%d,%d,",
                       (unsigned long)seq, (long long)t_us,
                       imu.ax, imu.ay, imu.az, imu.gx, imu.gy, imu.gz);

  // Magnetómetro: valores si hay lectura nueva; si no, las tres celdas quedan vacías.
  LecturaMag mag;
  if (tocaMagnetometro && leerMagnetometro(mag)) {
    largo += snprintf(linea + largo, sizeof(linea) - largo, "%d,%d,%d\n", mag.mx, mag.my, mag.mz);
  } else {
    largo += snprintf(linea + largo, sizeof(linea) - largo, ",,\n");
  }
  guardarLinea(bufferImu, linea, largo);
}

static void muestrearBarometro(uint32_t seqBaro) {
  char linea[64];
  LecturaBaro baro;
  int64_t t_us = esp_timer_get_time();
  if (!leerBarometro(info.direccionBmp280, baro)) {
    erroresDeLectura = erroresDeLectura + 1;
    return;
  }
  int largo = snprintf(linea, sizeof(linea), "%lu,%lld,%lu,%lu\n",
                       (unsigned long)seqBaro, (long long)t_us,
                       (unsigned long)baro.adc_T, (unsigned long)baro.adc_P);
  guardarLinea(bufferBaro, linea, largo);
}

// Atiende las pulsaciones del botón:
//   - pulsación corta: al soltar se anota el evento, con el instante en que se pulsó.
//   - pulsación de más de 3 s: se termina el registro y no se anota el evento.
static void atenderBoton() {
  static bool hayPulsacion = false;
  static int64_t instantePulsacion = 0;

  int64_t instante;
  while (xQueueReceive(colaPulsaciones, &instante, 0) == pdTRUE) {
    if (!hayPulsacion) {
      hayPulsacion = true;
      instantePulsacion = instante;
    }
  }
  if (!hayPulsacion) {
    return;
  }
  int64_t duracion = esp_timer_get_time() - instantePulsacion;
  if (digitalRead(PIN_BOTON) == HIGH) {   // ya soltaron el botón: fue una pulsación corta
    // Una "pulsación" más corta que el antirrebote no es real: es un rebote al soltar.
    if (duracion > ANTIRREBOTE_US) {
      char linea[40];
      int largo = snprintf(linea, sizeof(linea), "%lld,%d\n",
                           (long long)instantePulsacion, CODIGO_EVENTO_BOTON);
      guardarLinea(bufferEventos, linea, largo);
    }
    hayPulsacion = false;
  } else if (duracion > PULSACION_LARGA_US) {
    hayPulsacion = false;
    estado = ESTADO_TERMINANDO;
    xTaskNotifyGive(tareaEscritura);
  }
}

static void cicloDeMuestreo(void *) {
  uint32_t seqSiguiente = 0;
  for (;;) {
    // Espera el aviso del temporizador. "avisos" dice cuántos períodos pasaron: lo normal
    // es 1; si es mayor, la tarea se atrasó y se saltan esos números de seq.
    uint32_t avisos = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    if (estado != ESTADO_GRABANDO) {
      continue;
    }
    uint32_t seq = seqSiguiente + (avisos - 1);
    uint32_t seqAnterior = seqSiguiente - 1;   // en la primera vuelta da un número enorme: no importa
    seqSiguiente = seq + 1;
    ultimaSeq = seq;

    // El magnetómetro se lee cada 2 períodos y el barómetro cada 8. Se compara la división
    // entera para que funcione aunque se haya saltado algún período.
    bool tocaMagnetometro = info.tieneMagnetometro &&
        (seq == 0 || seq / TICKS_POR_MUESTRA_MAG != seqAnterior / TICKS_POR_MUESTRA_MAG);
    bool tocaBarometro =
        (seq == 0 || seq / TICKS_POR_MUESTRA_BARO != seqAnterior / TICKS_POR_MUESTRA_BARO);

    muestrearImu(seq, tocaMagnetometro);
    if (tocaBarometro) {
      // El seq del barómetro es su propio contador: 0, 1, 2... (un salto = muestra perdida).
      muestrearBarometro(seq / TICKS_POR_MUESTRA_BARO);
    }
    atenderBoton();
  }
}

// ---------------------------------------------------------------------------
// Tarea de escritura
// ---------------------------------------------------------------------------

static void guardarBloque(BufferDoble &buffer, File &archivo, bool forzar) {
  const char *datos;
  size_t largo;
  if (!tomarBloque(buffer, forzar, datos, largo)) {
    return;
  }
  if (archivo.write((const uint8_t *)datos, largo) != largo) {
    estado = ESTADO_ERROR_SD;        // tarjeta llena, retirada o dañada
  }
  liberarBloque(buffer);
}

static void guardarTodo(bool forzar) {
  guardarBloque(bufferImu, archivoImu, forzar);
  guardarBloque(bufferBaro, archivoBaro, forzar);
  guardarBloque(bufferEventos, archivoEventos, forzar);
  if (forzar) {
    archivoImu.flush();
    archivoBaro.flush();
    archivoEventos.flush();
  }
}

static void cicloDeEscritura(void *) {
  uint32_t milisUltimoFlush = millis();
  for (;;) {
    // Espera a que haya un buffer lleno, pero no más de 200 ms.
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(200));

    if (estado == ESTADO_TERMINANDO) {
      vTaskDelay(pdMS_TO_TICKS(20));   // deja que la tarea de muestreo termine su última línea
      guardarTodo(true);
      guardarTodo(true);               // segunda pasada, por si quedó algo en el otro buffer
      archivoImu.close();
      archivoBaro.close();
      archivoEventos.close();
      estado = ESTADO_TERMINADO;
      vTaskDelete(nullptr);            // esta tarea ya no hace falta
    }

    bool tocaFlush = millis() - milisUltimoFlush >= PERIODO_FLUSH_MS;
    guardarTodo(tocaFlush);
    if (tocaFlush) {
      milisUltimoFlush = millis();
    }
  }
}

// ---------------------------------------------------------------------------
// LED de estado
// ---------------------------------------------------------------------------

// Devuelve true durante los primeros "encendido" ms de cada ciclo de "periodo" ms.
static bool parpadeo(uint32_t periodo, uint32_t encendido) {
  return (millis() % periodo) < encendido;
}

static void actualizarLed() {
  bool encendido = false;
  switch (estado) {
    case ESTADO_INICIANDO:
      encendido = true;                                  // fijo: arrancando
      break;
    case ESTADO_GRABANDO:
    case ESTADO_TERMINANDO:
      if (millis() - milisUltimoDescarte < 5000 && muestrasDescartadas > 0) {
        // Dos destellos por segundo: se están perdiendo muestras (SD lenta).
        encendido = parpadeo(1000, 60) || (millis() % 1000 >= 200 && millis() % 1000 < 260);
      } else {
        encendido = parpadeo(1000, 60);                  // un destello por segundo: grabando
      }
      break;
    case ESTADO_TERMINADO:
      encendido = parpadeo(2000, 1000);                  // lento: 1 s encendido, 1 s apagado
      break;
    case ESTADO_ERROR_SD:
      encendido = parpadeo(200, 100);                    // muy rápido y continuo
      break;
    case ESTADO_ERROR_SENSOR:
      // Tres destellos y una pausa.
      encendido = (millis() % 2000 < 900) && parpadeo(300, 150);
      break;
  }
  digitalWrite(PIN_LED, encendido ? HIGH : LOW);
}

// ---------------------------------------------------------------------------
// Modo de prueba por monitor serie
// ---------------------------------------------------------------------------

#ifdef MODO_PRUEBA_SERIE
// Imprime 5 veces por segundo las lecturas convertidas a unidades físicas, para comprobar
// los sensores sin la microSD. En reposo: |a| debe valer cerca de 1 g y el giroscopio cerca
// de 0 °/s.
static void imprimirLecturasDePrueba() {
  LecturaImu imu;
  if (!leerImu(imu)) {
    Serial.println("ERROR: no se pudo leer el MPU");
    return;
  }
  float ax = convertirAccelAG(imu.ax), ay = convertirAccelAG(imu.ay), az = convertirAccelAG(imu.az);
  Serial.printf("accel (g): %7.3f %7.3f %7.3f  |a| = %.3f   ", ax, ay, az,
                sqrtf(ax * ax + ay * ay + az * az));
  Serial.printf("gyro (grados/s): %7.2f %7.2f %7.2f   ", convertirGyroADps(imu.gx),
                convertirGyroADps(imu.gy), convertirGyroADps(imu.gz));

  LecturaMag mag;
  if (info.tieneMagnetometro && leerMagnetometro(mag)) {
    Serial.printf("mag (uT): %6.1f %6.1f %6.1f   ",
                  convertirMagAMicroteslas(mag.mx, info.asa[0]),
                  convertirMagAMicroteslas(mag.my, info.asa[1]),
                  convertirMagAMicroteslas(mag.mz, info.asa[2]));
  }

  LecturaBaro baro;
  if (leerBarometro(info.direccionBmp280, baro)) {
    double temperaturaC, presionPa;
    compensarBmp280(info.calib, baro.adc_T, baro.adc_P, temperaturaC, presionPa);
    Serial.printf("T = %.2f C   P = %.1f Pa", temperaturaC, presionPa);
  }
  Serial.println();
}
#endif

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

static void imprimirInfoSensores() {
  Serial.printf("MPU WHO_AM_I = 0x%02x, magnetometro: %s\n", info.whoami,
                info.tieneMagnetometro ? "si" : "no");
  Serial.printf("BMP280 en 0x%02x, id = 0x%02x (un BMP280 tiene id 0x58)\n",
                info.direccionBmp280, info.idBmp280);
}

// Prepara la tarjeta, la carpeta de la sesión, los archivos y los buffers.
// (Las dos funciones siguientes no se usan en el modo de prueba; "maybe_unused" evita el aviso.)
[[maybe_unused]] static bool prepararAlmacenamiento() {
  char carpeta[24];
  if (!iniciarTarjeta() || !crearCarpetaDeSesion(carpeta, sizeof(carpeta))) {
    return false;
  }
  Serial.printf("Grabando en %s\n", carpeta);
  return escribirMeta(carpeta, info)
      && abrirArchivoConEncabezado(archivoImu, carpeta, "imu.csv",
                                   "seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz")
      && abrirArchivoConEncabezado(archivoBaro, carpeta, "baro.csv", "seq,t_us,adc_T,adc_P")
      && abrirArchivoConEncabezado(archivoEventos, carpeta, "eventos.csv", "t_us,evento")
      && crearBuffer(bufferImu, TAMANO_BUFFER_IMU)
      && crearBuffer(bufferBaro, TAMANO_BUFFER_BARO)
      && crearBuffer(bufferEventos, TAMANO_BUFFER_EVENTOS);
}

// Crea las dos tareas, la interrupción del botón y el temporizador de 200 Hz.
[[maybe_unused]] static void iniciarTareas() {
  colaPulsaciones = xQueueCreate(8, sizeof(int64_t));

  // Prioridades: el muestreo (5) es más importante que la escritura (2) y que loop() (1).
  // Cada tarea va en un núcleo distinto del ESP32, para que la SD no frene el muestreo.
  xTaskCreatePinnedToCore(cicloDeEscritura, "escritura", 8192, nullptr, 2, &tareaEscritura, 0);
  xTaskCreatePinnedToCore(cicloDeMuestreo, "muestreo", 4096, nullptr, 5, &tareaMuestreo, 1);

  attachInterrupt(digitalPinToInterrupt(PIN_BOTON), alCambiarBoton, CHANGE);

  esp_timer_create_args_t opciones = {};
  opciones.callback = alVencerTemporizador;
  opciones.name = "muestreo";
  esp_timer_handle_t temporizador;
  esp_timer_create(&opciones, &temporizador);
  esp_timer_start_periodic(temporizador, PERIODO_IMU_US);
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  digitalWrite(PIN_LED, HIGH);
  Serial.begin(115200);
  Serial.printf("\nRegistrador inercial, firmware %s\n", VERSION_FIRMWARE);

  // Ahorro de pilas: sin WiFi, sin Bluetooth y con el procesador más lento.
  WiFi.mode(WIFI_OFF);
  btStop();
  setCpuFrequencyMhz(FRECUENCIA_CPU_MHZ);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, FRECUENCIA_I2C_HZ);
  Wire.setTimeOut(20);   // ms: si un sensor no responde, no bloquear el programa

  const char *mensajeError = "";
  if (!iniciarSensores(info, mensajeError)) {
    Serial.printf("ERROR DE SENSOR: %s\n", mensajeError);
    estado = ESTADO_ERROR_SENSOR;
    return;
  }
  imprimirInfoSensores();

#ifdef MODO_PRUEBA_SERIE
  Serial.println("MODO DE PRUEBA: no se graba en la SD.");
  return;
#else
  if (!prepararAlmacenamiento()) {
    Serial.println("ERROR DE SD: no se pudo preparar la tarjeta o los archivos");
    estado = ESTADO_ERROR_SD;
    return;
  }
  iniciarTareas();
  estado = ESTADO_GRABANDO;
#endif
}

void loop() {
#ifdef MODO_PRUEBA_SERIE
  if (estado != ESTADO_ERROR_SENSOR) {
    digitalWrite(PIN_LED, parpadeo(400, 200) ? HIGH : LOW);
    imprimirLecturasDePrueba();
    delay(200);
    return;
  }
#endif

  actualizarLed();

  // Cada 5 s, un resumen por el monitor serie (útil mientras se prueba con el cable USB).
  static uint32_t milisUltimoResumen = 0;
  if (millis() - milisUltimoResumen >= 5000) {
    milisUltimoResumen = millis();
    Serial.printf("estado %d   seq %lu   descartadas %lu   errores de lectura %lu\n",
                  (int)estado, (unsigned long)ultimaSeq, (unsigned long)muestrasDescartadas,
                  (unsigned long)erroresDeLectura);
  }
  delay(10);
}
