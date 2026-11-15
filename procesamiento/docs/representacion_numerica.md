# Representación numérica de los datos

Este documento sigue a cada magnitud desde el sensor hasta el resultado y anota, en cada
paso, con qué tipo de dato se guarda y qué se pierde. La idea central del diseño es:

> **El dispositivo guarda los enteros tal como salen del sensor. Toda la conversión a
> unidades físicas se hace en Python con `float64`.** Así, la única pérdida de información
> que no se puede deshacer es la del propio sensor (cuantización y ruido).

Los ejemplos numéricos usan la configuración actual (`config.py` y
`firmware/include/configuracion.h`): acelerómetro ±4 g, giroscopio ±500 °/s, 200 Hz.
La unidad "g" del sensor es la gravedad estándar (9,80665 m/s²); la gravedad de Quito
(9,77 m/s²) solo se usa después, al restar la gravedad. Los valores de las hojas de datos tienen el mismo `TODO: confirmar`
que en `config.py`.

## 1. Tabla: tipo de dato en cada etapa

| Magnitud | En el sensor | En el firmware (C++) | En el archivo CSV | Al leer en Python | Después de convertir |
|---|---|---|---|---|---|
| Aceleración `ax, ay, az` | entero de 16 bits con signo (complemento a 2), en dos bytes | `int16_t` | texto decimal, por ejemplo `8499` | `int64` | `float64`, en m/s² |
| Velocidad angular `gx, gy, gz` | entero de 16 bits con signo | `int16_t` | texto decimal | `int64` | `float64`, en rad/s |
| Campo magnético `mx, my, mz` | entero de 16 bits con signo (AK8963 en modo de 16 bits) | `int16_t` | texto decimal, o celda vacía si no hubo lectura nueva | `Int64` de pandas (acepta vacíos) | `float64`, en µT (`NaN` donde no hay dato) |
| Presión `adc_P` | entero de 20 bits sin signo, en tres bytes | `uint32_t` | texto decimal | `int64` | `float64`, en Pa |
| Temperatura `adc_T` | entero de 20 bits sin signo | `uint32_t` | texto decimal | `int64` | `float64`, en °C |
| Tiempo `t_us` | (no viene del sensor: es el reloj del ESP32) | `int64_t`, microsegundos desde el encendido | texto decimal | `int64` | `float64`, en s desde la primera muestra |
| Contador `seq` | (lo lleva el firmware) | `uint32_t` | texto decimal | `int64` | se usa como entero |
| Coeficientes del BMP280 `dig_T1…dig_P9` | enteros de 16 bits (con y sin signo) | `uint16_t` / `int16_t` | números en `meta.json` | `int` de Python | `float64` dentro de las fórmulas |
| Ajuste del magnetómetro `ak8963_asa` | entero de 8 bits sin signo | `uint8_t` | números en `meta.json` | `int` de Python | factor `float64` |

## 2. Qué se pierde en cada paso

| Paso | ¿Se pierde algo? | Cuánto |
|---|---|---|
| Magnitud física → entero del sensor | **Sí: cuantización y ruido.** Es la única pérdida real | 1 LSB (ver sección 3) más el ruido del sensor, que es mayor |
| Bytes del sensor → `int16_t` / `uint32_t` | No | Solo se juntan los bytes |
| Entero → texto en el CSV | No | Un entero escrito en decimal se lee exactamente igual |
| Texto → `int64` en Python | No | `int64` guarda exactos todos los enteros de 16, 20 y 64 bits que usa el formato |
| Entero → `float64` en unidades físicas | Prácticamente no | Error relativo de redondeo ≈ 1,1·10⁻¹⁶ (sección 4) |
| Integrar dos veces con `float64` | Redondeo despreciable; lo que domina es el **error del método** y, sobre todo, el **error del sensor** | Sección 5 |
| Resultados → texto en reportes y CSV | Sí, pero a propósito | Se redondea para leer; los cálculos no usan esos textos |

¿Por qué no convertir a m/s² en el ESP32? Porque habría que escribir decimales en el
archivo. Con pocas cifras se pierde información y con muchas el archivo crece. Además, el
ESP32 solo tiene unidad de punto flotante de precisión simple (`float` de 32 bits, unas 7
cifras). Guardando el entero no hay nada que decidir: es exacto y ocupa poco.

## 3. Cuánto vale 1 LSB

"1 LSB" es el cambio más pequeño que el sensor puede representar: un salto de 1 en el
entero.

**Acelerómetro (±4 g, 8192 LSB por g):**

    1 LSB = 9,80665 / 8192 = 0,001197 m/s²   (1,20 mm/s²)

Ejemplo, primera muestra del ascensor simulado: `az = 8499` →
8499 × 9,80665 / 8192 = 10,174 m/s² (todavía sin calibrar). El valor siguiente posible,
`8500`, es 10,175 m/s². Entre los dos no existe nada.

**Giroscopio (±500 °/s, 65,5 LSB por °/s):**

    1 LSB = 1 / 65,5 = 0,01527 °/s = 2,665·10⁻⁴ rad/s

**Magnetómetro (16 bits):** 1 LSB ≈ 0,15 µT. El campo de la Tierra mide decenas de µT, así
que se representa con unos pocos cientos de pasos.

**Barómetro:** el entero pasa por las fórmulas de compensación, así que el tamaño del paso
depende de los coeficientes de cada sensor. Con los coeficientes del simulador, cerca de
72 000 Pa y 20 °C (calculado sumando 1 al entero y volviendo a compensar):

    1 cuenta de adc_P = 0,170 Pa    →    0,170 / 8,36 Pa/m = 0,020 m de altura
    1 cuenta de adc_T = 0,00031 °C  →    cambia la presión calculada en 0,034 Pa

OJO: el firmware usa sobremuestreo ×8 en presión y ×1 en temperatura. Según la hoja de
datos del BMP280, con eso la resolución real es de 19 y 16 bits (unos 0,33 Pa y 0,005 °C):
los bits más bajos de los 20 no traen información. TODO: confirmar con la hoja de datos
(tabla de resolución según el sobremuestreo) y con datos reales (ver si `adc_T` siempre
salta de 16 en 16).

**El ruido es mayor que 1 LSB.** En el simulador el ruido del acelerómetro es de 0,03 m/s²,
unos 25 LSB, y por eso promediar sirve: el promedio de N muestras en reposo tiene una resolución
mejor que 1 LSB (el ruido "reparte" las lecturas entre los enteros vecinos). Si el sensor
no tuviera ruido, promediar no mejoraría la cuantización.

**Efecto de 1 LSB al integrar.** Si el sesgo quedara mal medido por 1 LSB del acelerómetro
(0,0012 m/s²), el error de posición sería ½·b·t²:

| Tiempo | Error de velocidad (b·t) | Error de posición (½·b·t²) |
|---|---|---|
| 10 s | 0,012 m/s | 0,06 m |
| 60 s | 0,072 m/s | 2,1 m |
| 300 s | 0,36 m/s | 54 m |

Por eso el sesgo se mide en cada parada (ZUPT) en vez de confiar en una sola medición.

## 4. Punto flotante: `float64` y por qué no `float32`

Un `float64` (doble precisión, IEEE 754) tiene 53 bits de mantisa: unas 15 a 16 cifras
decimales. Guarda exactos todos los enteros hasta 2⁵³ ≈ 9·10¹⁵.

- No todos los decimales son exactos: en Python `0.1 + 0.2` da `0.30000000000000004`. Por
  eso las pruebas comparan con tolerancia (`pytest.approx`, `assert_allclose`) y nunca con
  `==` entre flotantes.
- **Tiempo.** `t_us` es un entero de microsegundos. En `lectura.us_a_segundos` primero se
  resta el instante inicial **con enteros** (exacto) y recién después se multiplica por
  10⁻⁶. Si se convirtiera antes de restar tampoco habría problema con `float64` (a los
  90 min, 5,4·10⁹ µs, el paso entre números vecinos es 10⁻⁶ µs), pero con `float32` sería
  un desastre: cerca de 5,4·10⁹ los `float32` vecinos están separados 512 µs, y el período
  de muestreo es de 5000 µs. Incluso guardando segundos, un `float32` cerca de 5400 s tiene
  pasos de 0,49 ms: el 10 % del período.
- **Restar números parecidos (cancelación).** La aceleración del movimiento sale de restar
  la gravedad: 10,174 − 9,77. Los dos números se parecen, así que el resultado tiene menos
  cifras significativas que los originales. Con `float64` sobran cifras (quedan unas 14).
  Lo que sí importa es que cualquier error en g o en la escala pasa completo al resultado:
  un error de escala del 1 % en 9,77 m/s² son 0,098 m/s², ochenta veces 1 LSB. Por eso se
  calibra con las seis caras.

## 5. Desbordamiento (overflow) de los enteros

| Dato | Tipo | Valor máximo | ¿Cuándo se desbordaría? |
|---|---|---|---|
| `ax…gz`, `mx…mz` | `int16_t` | −32768 … 32767 | Nunca se desborda: **satura**. Si la aceleración pasa de ±4 g el sensor entrega ±32767. `formato.py` valida el rango; ver un valor pegado al máximo indica un golpe |
| `adc_P`, `adc_T` | 20 bits en `uint32_t` | 1 048 575 | No se desborda (el sensor entrega como máximo 20 bits) |
| `seq` | `uint32_t` | 4 294 967 295 | A 200 Hz, después de 248 días |
| `t_us` | `int64_t` | 9,2·10¹⁸ | Después de unos 292 000 años |

Dos decisiones que salen de esta tabla:

- **`t_us` es de 64 bits.** Con 32 bits sin signo se desbordaría a los 71,6 min (2³² µs), y
  con 32 bits con signo a los 35,8 min: menos que los 90 min de grabación que pide el
  proyecto. Por eso el firmware usa `esp_timer_get_time()` (`int64_t`) y no `micros()`.
- **En Python todo se lee como `int64`**, no como `int16`. Con `int16` de numpy, operar
  desborda sin avisar: `20000 + 20000` da `−25536`. Con `int64` no hay ese riesgo al sumar
  o promediar los crudos.

## 6. Los tres tipos de error, comparados

Resultados del ascensor simulado (etapas 5 y 6):

| Fuente del error | Tamaño típico en la altura de un recorrido |
|---|---|
| Redondeo de `float64` | del orden de 10⁻¹³ m: no se nota |
| Método de integración (trapecio a 200 Hz, con datos sin ruido) | 1,3·10⁻⁵ m |
| Sensor sin corregir (sesgo, escala, ruido) | 1,5 m |
| Sensor con calibración y ZUPT | 0,03 m |

Conclusión para la exposición: con `float64` y 200 Hz, **ni el redondeo ni el método de
integración limitan el resultado. El límite lo pone el sensor**, y las correcciones (calibración,
ZUPT, barómetro) son las que más mejoran la estimación.

El valor del redondeo es una estimación de orden de magnitud (épsilon de máquina por el
número de operaciones), no una medición. TODO: si se quiere mostrar, medirlo comparando la
integración en `float64` contra la misma en `float32`.

## 7. Qué revisar con el dispositivo armado

- Que los enteros del archivo sean de verdad los del sensor: en reposo, con el eje z hacia
  arriba, `az` debe estar cerca de 8192 × (9,77 / 9,80665) ≈ 8161 (más el sesgo).
- Si `adc_T` y `adc_P` cambian de 1 en 1 o a saltos (resolución real según el
  sobremuestreo).
- Cuántos LSB mide el ruido real en reposo (script `caracterizar_reposo`).
