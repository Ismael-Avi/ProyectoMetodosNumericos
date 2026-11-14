# Contexto del proyecto: Navegación inercial (Metro de Quito)

> **Para Claude Code:** este documento describe un proyecto universitario de Métodos Numéricos.
> Tu tarea es construir **todo el programa de procesamiento en Python que se pueda hacer sin el
> dispositivo físico**, usando datos simulados. El hardware (ESP32 + sensores) todavía no está armado.
> Lee el documento completo antes de empezar y sigue las restricciones de la sección 9.

---

## 1. Qué es el proyecto

Somos un grupo de estudiantes de cuarto semestre de Ingeniería en Computación. Debemos construir un
**sistema de navegación inercial**:

- Un **dispositivo autónomo** (ESP32 + acelerómetro, giroscopio y barómetro) que registra datos
  **crudos** en una microSD.
- Un **programa en Python** que, con esos datos, estima la velocidad y la posición **sin GPS**,
  usando métodos numéricos.

**Objetivo final:** reconstruir viajes en el **Metro de Quito** (donde no hay GPS): la distancia y la
velocidad entre estaciones, y el recorrido dibujado sobre el mapa, comparado con el trazado real.

**Etapas del proyecto:**
1. Prototipo y caracterización: el dispositivo registra datos y se caracterizan sus errores.
2. Validación en un ascensor: movimiento en una sola dirección, con una referencia medible (altura de
   los pisos).
3. Metro de Quito: varios viajes, combinados y comparados con el trazado real.

**Importante para el código:** se permite usar IA, pero **cada integrante debe poder explicar y
justificar todo el código**. El código tiene que ser claro, comentado y sin complejidad innecesaria.

---

## 2. Hardware previsto (aún no disponible)

| Componente | Detalle |
|---|---|
| Microcontrolador | ESP32 DevKit (ESP-WROOM-32) |
| Sensor inercial | GY-91: MPU-9250 (acelerómetro + giroscopio + magnetómetro AK8963) y BMP280 (barómetro). Puede venir con MPU-6500, que **no tiene magnetómetro**: el código debe funcionar con o sin magnetómetro. |
| Almacenamiento | mini módulo microSD (3,3 V) por SPI |
| Energía | 4 pilas AA (6 V) con interruptor, al pin V5 del ESP32 |
| Montaje | placa perforada con los módulos en zócalos (pines hembra), dentro de una caja rígida |
| Marcas | un pulsador que registra eventos (p. ej. "se abrió la puerta", "llegada a estación") |

**Requisitos del dispositivo (del enunciado):**
- Muestreo de 100 Hz o más, con marca de tiempo en cada muestra.
- 90 minutos de registro continuo sin pérdida de muestras.
- Datos **crudos** tal como los entrega el sensor. La conversión a unidades físicas, la calibración y
  el filtrado se hacen **después, en Python** (o sea, en este programa).

---

## 3. Formato de archivos (PROPUESTA v0)

El firmware todavía no existe, así que **este formato es una propuesta**. El simulador debe escribir
exactamente este formato y el lector debe leerlo, para que cuando llegue el firmware real solo haya
que ajustar detalles. Centraliza el formato en un solo módulo para que cambiarlo sea fácil.

Cada sesión de registro es una carpeta:

```
sesion_YYYYMMDD_HHMMSS/
├── meta.json      # configuración del sensor y coeficientes de calibración del BMP280
├── imu.csv        # acelerómetro, giroscopio y magnetómetro (crudos, int16)
├── baro.csv       # barómetro (crudos, ADC de 20 bits)
└── eventos.csv    # pulsaciones del botón
```

**meta.json**
```json
{
  "formato_version": 0,
  "firmware_version": "simulador",
  "chip_whoami": "0x71",
  "tiene_magnetometro": true,
  "fs_imu_nominal_hz": 200,
  "fs_baro_nominal_hz": 25,
  "accel_rango_g": 4,
  "gyro_rango_dps": 500,
  "bmp280_calib": {"dig_T1": 27504, "dig_T2": 26435, "dig_T3": -1000,
                   "dig_P1": 36477, "dig_P2": -10685, "dig_P3": 3024, "dig_P4": 2855,
                   "dig_P5": 140, "dig_P6": -7, "dig_P7": 15500, "dig_P8": -14600, "dig_P9": 6000},
  "notas": ""
}
```

**imu.csv**: `seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz`
- `seq`: contador de muestra (entero que aumenta de 1 en 1; un salto indica muestras perdidas).
- `t_us`: tiempo en microsegundos desde el arranque del ESP32 (`esp_timer_get_time()`).
- `ax..gz`: valores crudos int16. `mx..mz`: crudos int16 o vacíos si no hay magnetómetro.
- El magnetómetro muestrea más lento: si no hay lectura nueva, repetir la última o dejar vacío
  (decidir y documentar).

**baro.csv**: `seq,t_us,adc_T,adc_P` (valores crudos de 20 bits del BMP280).

**eventos.csv**: `t_us,evento` (`evento` es un entero; 1 = pulsación del botón).

**Factores de conversión** (verificar contra las hojas de datos y documentar la fuente en el código):
- Acelerómetro ±4 g → 8192 LSB/g.
- Giroscopio ±500 °/s → 65,5 LSB/(°/s).
- Magnetómetro AK8963 en 16 bits → 0,15 µT/LSB (aprox.).
- BMP280: usar la fórmula de compensación de la hoja de datos de Bosch (con los coeficientes
  `dig_*`). La hoja de datos trae un ejemplo con estos mismos coeficientes:
  `adc_T = 519888`, `adc_P = 415148` → T ≈ 25,08 °C y P ≈ 100653,27 Pa. Úsalo como prueba unitaria
  (y verifica los valores con la hoja de datos).

---

## 4. Experimentos que se harán con el dispositivo real

El programa debe estar listo para procesar cada uno. Por ahora se simulan.

1. **Reposo:** al menos 1 hora quieto sobre una superficie firme → sesgo y ruido de cada eje.
2. **Seis caras:** el dispositivo en reposo sobre cada una de sus seis caras, al menos 1 minuto cada
   una → sesgo y escala de cada eje del acelerómetro.
3. **Ascensor:** edificio de al menos 5 pisos, al menos 10 recorridos de subida y bajada con paradas
   intermedias; botón en cada apertura y cierre de puerta; altura real de cada piso medida con
   flexómetro (referencia). Ojo: no todos los pisos tienen la misma altura.
4. **Metro:** al menos 3 viajes de varias estaciones, en distintos días o sentidos; botón en cada
   llegada y salida de estación. Referencia: ubicación de las estaciones y longitud de cada tramo.
5. **Experimento propio:** uno que ponga a prueba un límite del sistema.

**Consideraciones del enunciado que el código debe permitir comprobar:**
- Medir la frecuencia de muestreo real, al inicio y al final de un registro largo.
- Revisar las marcas de tiempo después de más de 1 hora de registro continuo.
- Comprobar que no se pierden muestras.
- En reposo, el programa debería indicar que el dispositivo no se mueve.
- Al girar el dispositivo en reposo, la magnitud de la gravedad no debería cambiar.
- **No usar constantes físicas sin verificar que valen en Quito** (altitud ≈ 2850 m). En particular,
  la gravedad en Quito es ≈ 9,77 m/s², no 9,81. Debe ser un parámetro configurable con un comentario
  `TODO: citar fuente`.
- Una inclinación pequeña también es una medición (afecta la componente de la gravedad).
- Un tramo recto no es necesariamente horizontal.
- Medir la presión en reposo a distintas horas del día (deriva por clima).
- El barómetro y el acelerómetro deben contar la misma historia: compararlos.
- Separar cuánto error aporta el método numérico y cuánto aporta el sensor.

---

## 5. Procesamiento y análisis que pide el enunciado

- **Representación numérica:** documentar el tipo de dato de cada magnitud en cada etapa (sensor,
  firmware, archivo, Python) y qué información se pierde en cada paso (cuantización int16,
  redondeos, float32 vs float64, etc.).
- **Calibración:** sesgo y escala de cada eje a partir de las seis caras.
- **Integración numérica:** al menos **dos métodos** para obtener velocidad y posición a partir de la
  aceleración, comparados entre sí.
- **Barómetro:** altura a partir de la presión. Investigar el modelo (fórmula barométrica) y sus
  constantes.
- **Interpolación:** llevar todas las señales a una base de tiempo común.
- **Raíces:** instante en que el ascensor cruza la altura de cada piso.
- **Correcciones:** usar lo que se sabe del problema (p. ej. velocidad cero en las paradas, distancia
  conocida entre estaciones), no solo lo que mide el sensor. Cuantificar la mejora.
- **Fusión de sensores:** combinar acelerómetro y barómetro (filtro complementario y/o Kalman),
  justificar el elegido y comparar resultados **con y sin barómetro**.
- **Trayectoria en el metro:** distancia y velocidad en cada tramo, dirección del recorrido y
  trayectoria sobre el mapa, comparada con el trazado real. Combinar los viajes y comparar su
  dispersión.
- **Predicción del error:** antes de cada etapa, predecir con la caracterización del sensor cómo
  debería crecer el error con el tiempo (p. ej. un sesgo b produce un error de posición ≈ ½·b·t²;
  ruido blanco produce un paseo aleatorio en la velocidad). Después, comparar con lo observado y
  explicar las diferencias.

**Resultados esperados:**
- Ascensor: altura y velocidad en el tiempo, con los pisos reales y las marcas del botón; error de
  cada recorrido, por método y por corrección, con y sin barómetro.
- Metro: recorrido sobre el mapa frente al trazado real, perfil de velocidad y error de distancia en
  cada tramo, con y sin barómetro.
- Bitácora: para cada registro, condiciones, desplazamiento, velocidad y aceleración máximas, y
  duración de cada tramo.

---

## 6. Tu tarea: qué construir ahora

### 6.1 Simulador (el "dispositivo falso")
Genera sesiones en el formato de la sección 3 a partir de un **movimiento conocido** (verdad de
referencia), para poder medir el error de cada etapa. Guarda también la verdad (`verdad.csv`) en
la carpeta de la sesión, aparte de los archivos que escribiría el dispositivo.

Modelo de error del sensor (todos los parámetros configurables y con semilla aleatoria fija):
- Sesgo constante por eje y error de escala por eje.
- Ruido blanco gaussiano.
- Deriva lenta del sesgo (paseo aleatorio), opcional.
- Pequeña desalineación de ejes, opcional.
- Saturación y cuantización a int16 según el rango configurado.
- Jitter en las marcas de tiempo y **muestras perdidas ocasionales** (para probar la detección).
- Barómetro: ruido, deriva lenta de presión por clima y conversión de presión/temperatura a los
  valores crudos `adc_P`/`adc_T`. Para eso hay que **invertir numéricamente** la fórmula de
  compensación del BMP280 (buena oportunidad para usar bisección o Newton y documentarlo).

Escenarios a simular:
1. Reposo largo (configurable, p. ej. 60–90 min).
2. Seis caras (con orientación conocida en cada cara).
3. Ascensor: varios pisos con alturas distintas, perfil de aceleración suave (arranque, velocidad
   constante, frenado), paradas, eventos de botón en puertas.
4. Metro: un recorrido 2D genérico con tramos rectos y curvas, paradas en estaciones, aceleraciones
   típicas de un tren, eventos de botón en llegada y salida. Mientras no tengamos las coordenadas
   reales, usar una ruta inventada **claramente marcada como sintética**.

### 6.2 Lectura y verificación de datos
- Cargar una sesión (meta + imu + baro + eventos).
- Convertir a unidades físicas (m/s², rad/s, µT, Pa, °C).
- Detectar muestras perdidas (saltos en `seq` y en `t_us`), frecuencia real al inicio y al final,
  estadísticas del intervalo entre muestras.
- Reporte de verificación de la sesión (texto + gráficas).

### 6.3 Caracterización
- Reposo: sesgo, ruido (desviación estándar) por eje; detector "el dispositivo está quieto".
  Opcional: varianza de Allan.
- Seis caras: sesgo y escala por eje, usando g de Quito:
  `sesgo = (a₊ + a₋)/2`, `escala = (a₊ − a₋)/(2g)`. Detectar automáticamente los tramos de cada cara.
- Aplicar la calibración a cualquier sesión.

### 6.4 Métodos numéricos (implementados a mano)
Implementar con código propio, legible y comentado (ver restricciones):
- Integración: rectángulo/Euler, trapecio y Simpson (acumulativos, para obtener v(t) y x(t)).
- Interpolación: lineal y spline cúbico (para remuestrear a una base de tiempo común).
- Raíces: bisección y Newton o secante (cruce de pisos, inversión del BMP280).
- Validar cada implementación contra `numpy`/`scipy` y contra soluciones analíticas en pruebas.

### 6.5 Análisis del ascensor
- Eje vertical: restar la gravedad, integrar con al menos dos métodos y comparar.
- Altura con la fórmula barométrica (constantes documentadas).
- Instante de cruce de cada piso con un método de raíces.
- Correcciones: resta del sesgo medido y velocidad cero en las paradas (ZUPT) usando los eventos del
  botón y/o el detector de quietud. Cuantificar la mejora.
- Fusión acelerómetro + barómetro: filtro complementario y filtro de Kalman 1D; comparar con y sin
  barómetro.
- **Separar el error del método del error de medición:** integrar una señal sintética sin ruido con
  solución analítica (solo error del método) y compararla con la señal con errores del sensor.
- Predicción del error a partir de la caracterización vs. error observado (incluye simulaciones
  Monte Carlo con varias semillas).

### 6.6 Análisis del metro
- Orientación integrando el giroscopio (rumbo en 2D); usar el magnetómetro si existe, y analizar si
  es confiable (dentro del vagón puede no serlo).
- Velocidad y posición en 2D; segmentación en tramos con los eventos de estación.
- Correcciones: velocidad cero en cada parada; ajuste con la distancia conocida entre estaciones.
- Distancia y velocidad por tramo; error por tramo; combinación de varios viajes y su dispersión.
- Dibujo de la trayectoria sobre un mapa frente al trazado real.

**Datos de referencia del Metro de Quito:** crea `datos_referencia/estaciones_metro.csv` con las
columnas `orden,estacion,lat,lon,fuente` y los nombres de las 15 estaciones (de sur a norte:
Quitumbe, Morán Valverde, Solanda, El Calzado, El Recreo, La Magdalena, San Francisco, La Alameda,
El Ejido, Universidad Central, La Pradera, La Carolina, Iñaquito, Jipijapa, El Labrador; verifica la
lista). **No inventes coordenadas ni longitudes de tramos:** si no puedes obtenerlas de una fuente
verificable (p. ej. OpenStreetMap o datos oficiales del Metro de Quito), deja `lat`/`lon` vacíos con
un `TODO` y que el código funcione igual con la ruta sintética.

### 6.7 Bitácora y reportes
- Plantilla de bitácora (CSV o Markdown): fecha, hora, lugar, condiciones, procedimiento,
  orientación del dispositivo, foto (ruta), y los resultados automáticos: duración, desplazamiento,
  velocidad y aceleración máximas, duración de cada tramo.
- Script que, dada una sesión, genera automáticamente las gráficas y un resumen de resultados.

### 6.8 Documento de representación numérica
`docs/representacion_numerica.md`: tabla con el tipo de dato de cada magnitud en cada etapa (sensor
→ firmware → archivo → Python) y qué se pierde en cada paso, con ejemplos numéricos (resolución en
m/s² de 1 LSB del acelerómetro, del giroscopio, etc.).

---

## 7. Estructura sugerida del repositorio

```
procesamiento/
├── README.md                  # cómo instalar, cómo correr cada script, qué hace cada módulo
├── requirements.txt
├── config.py                  # constantes y parámetros (g de Quito, rangos, etc.) con fuentes
├── navinercial/
│   ├── formato.py             # definición única del formato de archivos (sección 3)
│   ├── lectura.py             # carga y conversión a unidades físicas
│   ├── verificacion.py        # muestras perdidas, frecuencia real, jitter
│   ├── bmp280.py              # compensación e inversión numérica
│   ├── metodos/
│   │   ├── integracion.py
│   │   ├── interpolacion.py
│   │   └── raices.py
│   ├── calibracion.py         # reposo y seis caras
│   ├── correcciones.py        # ZUPT, resta de sesgo, ajuste por distancia conocida
│   ├── fusion.py              # complementario y Kalman
│   ├── ascensor.py
│   ├── metro.py
│   ├── prediccion_error.py
│   └── graficas.py
├── simulador/
│   ├── modelo_sensor.py
│   ├── escenarios.py          # reposo, seis caras, ascensor, metro
│   └── generar.py             # CLI: genera sesiones de ejemplo
├── scripts/                   # un script por análisis, que guarda figuras en resultados/
├── datos_referencia/
├── datos/                     # sesiones (simuladas ahora, reales después); ignorar en git si pesan mucho
├── resultados/
├── docs/
└── tests/                     # pytest
```

Puedes ajustar la estructura si tienes una razón, pero mantenla simple.

---

## 8. Criterios de terminado

- `python -m simulador.generar` crea sesiones de ejemplo de los 4 escenarios.
- Cada script de `scripts/` corre sin errores sobre las sesiones simuladas y guarda sus figuras.
- `pytest` pasa: pruebas de cada método numérico contra soluciones analíticas, del BMP280 contra el
  ejemplo de la hoja de datos, de la detección de muestras perdidas, de la calibración de seis caras
  (debe recuperar el sesgo y la escala que puso el simulador, dentro de una tolerancia razonable).
- En el ascensor simulado, el sistema recupera la altura de los pisos y se ve claramente la mejora
  con ZUPT y con barómetro.
- El README explica en español cómo usar todo y qué falta hacer cuando llegue el hardware.
- Un archivo `docs/PENDIENTES_HARDWARE.md` lista todo lo que depende del dispositivo real (formato
  final, rangos reales, chip real, coordenadas del metro, fuentes por citar).

---

## 9. Restricciones y estilo

- **Python 3.10+**, librerías: `numpy`, `scipy`, `pandas`, `matplotlib`, `pytest`. Opcional:
  `folium` o similar para el mapa. Evita dependencias pesadas.
- **Los métodos numéricos del curso (integración, interpolación, raíces) se implementan a mano**;
  `numpy`/`scipy` solo se usan para validar o para operaciones básicas de arreglos.
- **No uses librerías de fusión de sensores ya hechas** (AHRS, filtros de Kalman de terceros) para los
  resultados; si quieres, úsalas solo como comparación.
- Código y comentarios **en español**, nombres de variables claros, funciones cortas con docstrings
  que expliquen la idea matemática y las unidades. Este código lo tienen que defender estudiantes de
  cuarto semestre ante el profesor: prioriza la claridad sobre la elegancia.
- Unidades SI en todo el procesamiento; deja explícito el cambio de unidades.
- No pongas constantes "mágicas": todas en `config.py` con su fuente o un `TODO: citar fuente`.
- **No inventes datos de referencia reales** (coordenadas, distancias, alturas): si falta algo, deja
  un `TODO` y una ruta sintética.
- Fija las semillas aleatorias para que los resultados sean reproducibles.
- Trabaja por etapas y haz commits pequeños con mensajes claros (formato → simulador → lectura y
  verificación → métodos numéricos → calibración → ascensor → metro → reportes).
- Al terminar cada etapa, resume brevemente qué hiciste, qué decisiones tomaste y por qué.

---

## 10. Fuera de alcance por ahora

- El firmware del ESP32 (lo haremos aparte).
- Procesar datos reales (no existen todavía).
- Los datos de aplicaciones de celular (p. ej. phyphox) **no reemplazan** los del dispositivo; si se
  agrega un lector para ellos, debe ser solo para probar el código.
