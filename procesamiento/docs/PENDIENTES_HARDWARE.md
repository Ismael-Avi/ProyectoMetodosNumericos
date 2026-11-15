# Pendientes que solo se pueden comprobar con el dispositivo armado

Entrega: **22 de noviembre de 2026**. Escrito el 14 de noviembre, antes de armar el dispositivo.

Hasta ahora **nada se ha probado con hardware**: el firmware solo se ha compilado y todo el
procesamiento se ha probado con datos simulados. Esta lista está ordenada por prioridad: lo
de arriba bloquea a lo de abajo. Cada punto dice cómo comprobarlo y qué hacer si falla.

Resumen del orden:

| Prioridad | Qué | Cuándo |
|---|---|---|
| 1 | Que el dispositivo encienda, lea los sensores y grabe | el día que se arma |
| 2 | Que grabe 90 minutos sin perder datos | al día siguiente, antes de cualquier experimento |
| 3 | Reposo y seis caras reales; ajustar parámetros | antes del ascensor |
| 4 | Experimento del ascensor (con flexómetro) | a mitad de semana |
| 5 | Viajes en metro y datos de referencia | lo antes posible: se necesitan varios viajes |
| 6 | Fuentes y constantes para el informe | en paralelo, no necesita el dispositivo |
| 7 | Mejoras opcionales | solo si sobra tiempo |

---

## Prioridad 1: que encienda, lea y grabe (día del armado)

Usar primero el **modo de prueba** (`pio run -e prueba -t upload` y el monitor serie; ver
`firmware/README.md`). No necesita la microSD.

- [ ] **Voltajes.** Confirmar con qué se alimenta el GY-91 (¿3V3 o VIN de 5 V, según su
      regulador?) y el módulo microSD (¿5 V o 3,3 V?). Están como TODO en la tabla de
      conexiones de `firmware/README.md`. Un módulo SD de 5 V alimentado con 3,3 V puede
      fallar de forma intermitente.
- [ ] **WHO_AM_I del MPU.** El modo de prueba lo imprime. `0x71` o `0x73`: hay magnetómetro.
      `0x70`: es un MPU-6500 y **no hay magnetómetro** (muchos GY-91 vienen así). El
      programa funciona igual, pero la parte del magnetómetro del metro queda sin datos. Si
      sale otro valor, el firmware se detiene con error de sensor: avisar antes de cambiar nada.
- [ ] **BMP280.** Dirección (0x76 o 0x77; el firmware prueba las dos) e id `0x58`. Si el id
      es `0x60` el chip es un BME280 (el firmware solo muestra el id, no lo rechaza). En
      ese caso, confirmar en su hoja de datos que los registros y las fórmulas de presión y
      temperatura son los mismos (TODO) antes de confiar en la altura.
- [ ] **Valores razonables en reposo.** |a| cerca de 1 g (0,996 g en Quito), giroscopio cerca
      de 0 °/s, presión cerca de 72 000 Pa (TODO: comparar con un dato del INAMHI o de un
      teléfono), temperatura creíble.
- [ ] **Ejes.** Poner hacia arriba cada cara y ver qué eje marca +1 g. Anotar en la bitácora
      cómo queda el dispositivo dentro de su caja.
- [ ] **Arranque con la SD en G5.** G5 es un pin de arranque del ESP32. Encender varias veces
      con la tarjeta puesta. Si a veces no arranca, mover CS a otro pin (cambiar `PIN_SD_CS`
      en `configuracion.h`).
- [ ] **LED y botón.** Que el LED esté en G2 y encienda con nivel alto; que una pulsación
      corta dé un solo evento (si da varios, subir `ANTIRREBOTE_US`) y que mantener 3 s
      cierre los archivos.
- [ ] **Primera grabación corta (2 min)** con el firmware normal. Copiar la carpeta
      `sesion_001` a `procesamiento/datos/` y correr
      `python -m scripts.verificar_sesion datos/sesion_001`. Si el lector rechaza el archivo,
      el error dice qué columna o campo no coincide con `navinercial/formato.py`. **Este es
      el punto donde el firmware y Python se encuentran por primera vez.**
- [ ] Anotar qué chip USB tiene la placa (CP2102 o CH340) para el controlador.

## Prioridad 2: 90 minutos sin perder datos

Requisito del enunciado. Hacerlo antes de los experimentos: si falla, hay que tocar el firmware.

- [ ] **Grabación de 90 min en reposo, con las pilas.** Después:
      `python -m scripts.reporte_sesion datos/sesion_00N --tipo reposo`. Mirar en el reporte:
      muestras perdidas (contador `seq`), frecuencia real (se espera muy cerca de 200 Hz),
      jitter y si la frecuencia cambia del inicio al final.
- [ ] **Si se pierden muestras:** casi seguro es la tarjeta, que a veces tarda en escribir.
      Opciones, en orden: otra microSD (mejor una de marca, clase 10), subir
      `TAMANO_BUFFER_IMU`, probar `FRECUENCIA_SPI_SD_HZ` a 20 MHz.
- [ ] **Duración de las pilas.** ¿Llegan a 90 min las 4 AA? Anotar el voltaje al inicio y al
      final. Si no alcanza: pilas alcalinas nuevas o recargables de más capacidad. El
      consumo no está medido (TODO en `configuracion.h`).
- [ ] **Corte de energía.** Quitar las pilas a mitad de una grabación y comprobar que los
      archivos se leen (se debería perder como máximo 2 s, `PERIODO_FLUSH_MS`).
- [ ] **Magnetómetro (si existe):** que las celdas tengan datos a unos 100 Hz y que los ejes
      estén bien. El AK8963 tiene los ejes x e y cambiados respecto al acelerómetro y el z
      invertido; el firmware ya lo corrige, pero **no está comprobado** (TODO en
      `sensores.cpp`). Prueba: girar el dispositivo y ver que el campo gira en el mismo
      sentido que dice el giroscopio.
- [ ] **Barómetro:** en `baro.csv`, ver si `adc_T` y `adc_P` cambian de 1 en 1 o a saltos
      (resolución real con el sobremuestreo ×8/×1; ver `docs/representacion_numerica.md`).

## Prioridad 3: reposo y seis caras reales; ajustar parámetros

Todos los umbrales y ruidos de `config.py` salen del simulador, que a su vez usa valores
supuestos. Con el reposo de 90 min de la prioridad 2 ya se puede hacer casi todo.

- [ ] `python -m scripts.caracterizar_reposo datos/sesion_00N`: anotar el ruido real de cada
      eje y la desviación de Allan. Poner esos valores en `config.py`:
      `SIM_ACCEL_RUIDO_STD_MS2`, `SIM_GYRO_*`, `SIM_BARO_*` (para que el simulador y el Monte
      Carlo se parezcan al sensor real) y `KALMAN_ACCEL_STD_MS2`, `KALMAN_BARO_STD_M`.
- [ ] **Detector de quietud:** los umbrales `QUIETUD_*` están ajustados al ruido simulado. En
      el reposo real debe decir "quieto" casi el 100 % del tiempo; si no, subir los umbrales.
- [ ] **Seis caras real** (unos 30 s por cara, apoyando sobre una mesa nivelada):
      `python -m scripts.reporte_sesion datos/sesion_00N --tipo seis_caras`. Revisar que
      detecte las seis caras y que las escalas salgan cerca de 1 (entre 0,97 y 1,03). OJO:
      este comando guarda `resultados/calibracion/calibracion.json`, que usan el ascensor y
      el metro. Hay que correrlo con la sesión real **antes** de analizar los experimentos.
- [ ] **Deriva de la presión.** Grabar reposo a dos o tres horas distintas del día (mañana,
      mediodía, tarde) y ver cuánto cambia la presión en 10 min. De esto depende si conviene
      fusionar con el barómetro o usar solo ZUPT (ver resumen de la etapa 6). La marea
      barométrica y el "clima" del simulador son SINTÉTICOS.
- [ ] **Temperatura.** El sensor se calienta al encender: ver en el reposo cuánto tardan en
      estabilizarse la temperatura y el sesgo. Si tarda, encender unos minutos antes de cada
      experimento.
- [ ] Volver a correr `python -m scripts.predecir_error_ascensor` con el ruido real.

## Prioridad 4: ascensor

- [ ] **Medir con flexómetro** la altura de cada piso (de piso a piso, en el mismo punto) y
      llenar `datos_referencia/pisos_ascensor.csv`. Está vacío a propósito. Anotar la
      incertidumbre de la medición.
- [ ] **Procedimiento de grabación:** dispositivo apoyado en el piso del ascensor (no en la
      mano), 10 s quieto al inicio, pulsar el botón justo al arrancar y justo al parar, 10 s
      quieto al final. Anotar en la bitácora el piso de cada parada.
- [ ] Analizar:
      `python -m scripts.reporte_sesion datos/sesion_00N --tipo ascensor --pisos datos_referencia/pisos_ascensor.csv --itinerario 0,3,5,0`
- [ ] Revisar: número de paradas detectadas contra la bitácora (una pulsación de más o de
      menos descuadra todo), `ZUPT_MARGEN_S` (0,5 s supuesto) y si la velocidad de crucero es
      creíble.
- [ ] **Comparar con y sin barómetro con datos reales.** En la simulación gana el ZUPT sin
      barómetro; puede ser al revés. Ajustar `COMPLEMENTARIO_TAU_S` y `KALMAN_*`.
- [ ] El ascensor cambia la presión de la cabina al moverse y al abrir puertas: mirar si la
      altura barométrica tiene saltos en las paradas.
- [ ] Repetir el experimento al menos tres veces para tener dispersión.

## Prioridad 5: metro

Empezar pronto: hacen falta varios viajes y no se pueden repetir el último día.

- [ ] **Cómo fijar el dispositivo.** Apoyado en el piso o en el asiento, sin moverlo en todo
      el viaje y lo más horizontal posible. El análisis supone que no gira respecto al vagón.
      Anotar hacia dónde apunta respecto al sentido de la marcha.
- [ ] **Botón:** pulsar al arrancar y al detenerse en cada estación. Anotar las estaciones.
- [ ] **Datos de referencia (no necesitan el dispositivo, pero sí una fuente):**
      latitud y longitud de cada estación en `datos_referencia/estaciones_metro.csv` y
      longitud de cada tramo en `datos_referencia/tramos_metro.csv`, con la fuente (Metro de
      Quito u OpenStreetMap). Confirmar también la lista y los nombres de las estaciones.
      Sin esto el programa da distancias, pero no puede medir su error.
- [ ] **Rumbo inicial:** hoy es un dato que se le da al programa (TODO en
      `scripts/analizar_metro.py`). Sacarlo de la dirección del túnel en el mapa.
- [ ] Analizar:
      `python -m scripts.reporte_sesion datos/sesion_00N --tipo metro --estaciones "Estación 1,Estación 2,..."`
      y, con varios viajes, `python -m scripts.analizar_metro SESION_1 SESION_2 ...`
- [ ] **Lo que el simulador no tiene y hay que mirar en los datos reales:**
  - vibración del vagón (¿el ruido es mucho mayor que en reposo?);
  - cambios de presión en el túnel al entrar a las estaciones o al cruzarse con otro tren:
    pueden dañar la corrección de la pendiente. Comparar "ZUPT" contra "ZUPT + barómetro";
  - si "adelante" sale bien del primer arranque (ventana `METRO_VENTANA_ARRANQUE_S`);
  - peralte en las curvas (la vía inclinada mete gravedad en el eje lateral);
  - si el magnetómetro sirve de algo (`MAG_VARIACION_MAXIMA_CONFIABLE`). La perturbación
    simulada es inventada.
- [ ] Velocidad máxima real del metro contra los 20 m/s supuestos en el simulador.

## Prioridad 6: fuentes y constantes (para el informe; se puede hacer ya)

Buscar `TODO` en `config.py` y en el firmware. Los que hay que cerrar con un documento en la mano:

- [ ] Gravedad en Quito (9,77 m/s²): citar fuente. Hoy dice "valor del enunciado".
- [ ] Hoja de datos del MPU-9250: sensibilidades (tablas 6.1 y 6.2), densidad de ruido,
      anchos de banda del filtro `MPU_DLPF_CFG = 3` (registros 26 y 29), direcciones de los
      registros usadas en `sensores.cpp`.
- [ ] Hoja de datos del AK8963: 0,15 µT/LSB, fórmula del ajuste ASA y ruido.
- [ ] Hoja de datos del BMP280: sección de las fórmulas de compensación, ruido de presión y
      de temperatura, tiempo de medición y resolución con sobremuestreo ×8.
- [ ] Constantes de la fórmula barométrica (R, masa molar del aire): fuente con página.
- [ ] Radio de la Tierra (6 371 008,8 m, radio medio IUGG): citar.
- [ ] Campo magnético y declinación en Quito (modelo IGRF/WMM): solo si se usa el
      magnetómetro para el rumbo.

## Prioridad 7: opcional

- [ ] Probar la instalación con Arduino IDE (opción C de `firmware/README.md`): nunca se ha
      compilado así.
- [ ] Fijar la versión de la plataforma en `platformio.ini` (hoy `platform = espressif32`
      sin versión) cuando el firmware ya funcione, para que todos compilen lo mismo.
- [ ] Probar el sobremuestreo ×16 del barómetro (menos ruido; confirmar que alcanza a 25 Hz).
- [ ] Medir el error de redondeo comparando `float64` contra `float32`
      (`docs/representacion_numerica.md`, sección 6).
- [ ] Entender por qué la predicción del error sin ZUPT queda 7 % a 15 % por debajo del
      Monte Carlo (resumen de la etapa 6).

---

## Si algo no coincide con el formato

El formato de los archivos está definido en `navinercial/formato.py` y descrito en
`CONTEXTO_PROYECTO.md`. Si el dispositivo real obliga a cambiar algo (una columna, un campo
de `meta.json`), cambiarlo en `formato.py`, en `firmware/src/almacenamiento.cpp` y subir
`VERSION_FORMATO` en los dos lados. Las pruebas (`pytest`) avisan si algo queda desigual en
la parte de Python.
