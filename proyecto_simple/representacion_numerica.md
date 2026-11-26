# Representación numérica

Qué tipo de dato tiene cada magnitud en cada etapa y qué se pierde. Los ejemplos son de la
sesión real `datos/sesion_002` (MPU-6500, ±4 g, ±500 °/s, BMP280 con osrs_p ×8 y osrs_t ×1).

## Tipo de dato en cada etapa

| Magnitud | Sensor | Firmware (ESP32) | Archivo (.csv) | Python |
|---|---|---|---|---|
| aceleración | ADC de 16 bits, complemento a 2 | `int16_t` | texto, entero decimal | `int64` → `float64` en m/s² |
| giroscopio | ADC de 16 bits | `int16_t` | texto, entero | `float64` en rad/s |
| presión, temperatura | ADC de 20 bits (`adc_P`, `adc_T`) | `int32_t` | texto, entero | `float64` en Pa y °C (fórmula de Bosch) |
| coeficientes `dig_*` | registros de 16 bits | `uint16_t` / `int16_t` | meta.json, entero | `int` de Python |
| tiempo | reloj del ESP32 en µs | `int64_t` (`esp_timer_get_time`) | texto, entero | `int64` en µs → `float64` en s |
| contador `seq` | — | `uint32_t` | texto, entero | `int64` |

Pasar de entero a texto y de vuelta no pierde nada: el CSV guarda los enteros exactos.

## Qué se pierde y dónde

1. **Filtro del sensor (antes del ADC).** El firmware pone el filtro pasa-bajos del MPU en ~41 Hz
   (giroscopio) y ~45 Hz (acelerómetro). Lo que vibre más rápido no llega a los datos. A cambio, no
   hay aliasing a 200 Hz.
2. **Cuantización del IMU (int16).** 1 LSB del acelerómetro = 1/8192 g = 0,0012 m/s². 1 LSB del
   giroscopio = 1/65,5 °/s = 0,015 °/s. Es mucho menor que el ruido (0,016 m/s² y 0,065 °/s), así que
   casi no importa. El sesgo del giroscopio (-4,5 °/s = -294 LSB) es mucho mayor que 1 LSB.
3. **Saturación.** Con ±4 g el acelerómetro se satura en ±39 m/s², y con ±500 °/s el giroscopio en
   ±500 °/s. Un ascensor no llega ni a 0,2 g; un golpe fuerte sí podría saturar.
4. **Cuantización del barómetro.** En los datos, `adc_P` cambia de 2 en 2 (19 bits útiles con ×8)
   y `adc_T` de 16 en 16 (16 bits con ×1). En unidades: un paso de presión = 0,33 Pa ≈ **4 cm de
   altura**, y un paso de temperatura = 0,0049 °C. El ruido real de la presión (~2,8 Pa) es mayor
   que el paso.
5. **Fórmula de Bosch en double vs entera.** Con el ejemplo de la hoja de datos, la versión double da
   100653,27 Pa y la entera da 100653 Pa. Usamos double; la diferencia (<1 Pa) es menor que el ruido.
6. **Tiempo en float.** Pasamos `t_us` a segundos en `float64`, que a los 90 min (5400 s) tiene una
   resolución de 9·10⁻¹³ s. Con `float32` la resolución a 5400 s sería 0,49 ms, ¡el 10 % del periodo
   de 5 ms! Por eso nunca se usa float32 para el tiempo.
7. **Redondeo al integrar.** Cada suma en float64 tiene un error relativo de ~10⁻¹⁶. Nuestro trapecio
   y `np.trapezoid` difieren en 2·10⁻¹⁵ (comando `metodos`). Es despreciable frente al error del
   método (10⁻⁵ m) y muchísimo menor que el del sensor (metros).
8. **Muestras perdidas.** Si el firmware pierde una muestra, `seq` salta. La sesión real no tiene
   ninguna (0 de 28 483).
