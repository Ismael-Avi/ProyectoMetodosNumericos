// Escritura en la microSD: carpeta de la sesión, meta.json y doble buffer.
//
// IDEA DEL DOBLE BUFFER
// Escribir en una microSD normalmente tarda poco, pero de vez en cuando la tarjeta se queda
// ocupada decenas o cientos de milisegundos. Si la misma tarea que lee el sensor esperara a
// la tarjeta, perdería muestras. Por eso hay dos tareas y dos buffers por archivo:
//
//   tarea de muestreo  ->  escribe texto en el buffer ACTIVO (en memoria: es instantáneo)
//   tarea de escritura ->  guarda en la SD el OTRO buffer, el que ya se llenó
//
// Cuando el buffer activo se llena, se intercambian. Solo se pierden muestras si el buffer
// activo se llena antes de que la SD termine de guardar el anterior; en ese caso la muestra
// se descarta y queda un salto en "seq", que la verificación en Python detecta.

#pragma once

#include <Arduino.h>
#include <FS.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "sensores.h"

struct BufferDoble {
  char *datos[2];        // los dos buffers
  size_t usados[2];      // cuántos bytes tiene cada uno
  size_t tamano;         // capacidad de cada buffer
  int activo;            // 0 o 1: en cuál escribe la tarea de muestreo
  bool pendiente;        // true: el otro buffer está esperando que lo guarden en la SD
  SemaphoreHandle_t candado;   // para que las dos tareas no lo modifiquen a la vez
};

bool crearBuffer(BufferDoble &buffer, size_t tamano);

// Tarea de muestreo: agrega texto al buffer activo. Devuelve false si no hubo espacio (la
// muestra se pierde). "bufferLleno" queda en true cuando conviene despertar a la tarea de
// escritura.
bool agregarAlBuffer(BufferDoble &buffer, const char *texto, size_t largo, bool &bufferLleno);

// Tarea de escritura: pide el bloque que está esperando. Con "forzar" también se lleva lo
// que haya en el buffer activo aunque no esté lleno. Devuelve false si no hay nada.
bool tomarBloque(BufferDoble &buffer, bool forzar, const char *&datos, size_t &largo);

// Tarea de escritura: avisa que el bloque ya se guardó y el buffer se puede volver a usar.
void liberarBloque(BufferDoble &buffer);

// Tarjeta y archivos de la sesión.
bool iniciarTarjeta();
bool crearCarpetaDeSesion(char *ruta, size_t largoMaximo);   // p. ej. "/sesion_007"
bool escribirMeta(const char *carpeta, const InfoSensores &info);
bool abrirArchivoConEncabezado(File &archivo, const char *carpeta, const char *nombre,
                               const char *encabezado);
