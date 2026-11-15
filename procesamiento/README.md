# Procesamiento: navegación inercial (Metro de Quito)

Programa en Python que procesa los datos crudos del dispositivo (ESP32 + GY-91 + microSD) y
estima velocidad y posición sin GPS. Proyecto de Métodos Numéricos.

> **Estado (14 de noviembre de 2026):** el dispositivo todavía no está armado. Todo lo que
> hay aquí funciona y está probado **con datos simulados**. Lo que falta comprobar con el
> hardware está en [docs/PENDIENTES_HARDWARE.md](docs/PENDIENTES_HARDWARE.md).

Otros documentos:

| Documento | Para qué |
|---|---|
| [../CONTEXTO_PROYECTO.md](../CONTEXTO_PROYECTO.md) | enunciado, hardware y formato de los archivos |
| [docs/RESUMEN_ETAPAS.md](docs/RESUMEN_ETAPAS.md) | qué se hizo en cada etapa, por qué, y qué debe revisar el grupo |
| [docs/PENDIENTES_HARDWARE.md](docs/PENDIENTES_HARDWARE.md) | lista ordenada de lo que falta con el dispositivo |
| [docs/representacion_numerica.md](docs/representacion_numerica.md) | tipos de datos, 1 LSB, redondeo y desbordamiento |
| [bitacora/README.md](bitacora/README.md) | cómo llenar la bitácora de los experimentos |
| [../firmware/README.md](../firmware/README.md) | conexiones, cómo cargar el firmware y cómo grabar |

## 1. Instalación en Windows

Se necesita Python 3.10 o superior. Abrir PowerShell en la carpeta `procesamiento/`:

```powershell
py -m venv .venv                      # crea el entorno virtual (solo la primera vez)
.venv\Scripts\Activate.ps1            # activa el entorno (cada vez que se abre la terminal)
pip install -r requirements.txt       # instala numpy, scipy, pandas, matplotlib y pytest
pytest                                # corre las 179 pruebas (unos 30 s)
```

Si PowerShell no deja activar el entorno ("la ejecución de scripts está deshabilitada"),
ejecutar una sola vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Otra opción es usar el Símbolo del sistema (cmd) y activar con `.venv\Scripts\activate.bat`.

**Todos los comandos de este README se corren desde la carpeta `procesamiento/`, con el
entorno activado.**

## 2. Recorrido rápido con datos simulados

En este orden (cada paso usa lo que dejó el anterior):

```powershell
python -m simulador.generar              # 1. crea las 6 sesiones simuladas (tarda 1 a 2 min)
python -m scripts.verificar_sesion       # 2. muestras perdidas y frecuencia real
python -m scripts.caracterizar_reposo    # 3. ruido del sensor y desviación de Allan
python -m scripts.calibrar_seis_caras    # 4. sesgo y escala; guarda calibracion.json
python -m scripts.comparar_metodos       # 5. métodos numéricos contra soluciones exactas
python -m scripts.analizar_ascensor      # 6. altura en el ascensor
python -m scripts.predecir_error_ascensor  # 7. predicción del error contra Monte Carlo
python -m scripts.analizar_metro         # 8. los tres viajes en metro
```

O todo junto (pasos 2, 3, 4, 6 y 8, más un reporte por sesión):

```powershell
python -m scripts.reporte_sesion --simulados
```

Todo lo que se genera queda en `resultados/`. Las carpetas `datos/` y `resultados/` no se
suben a git: cada uno las genera en su computadora.

## 3. Con datos reales

1. Grabar con el dispositivo (ver `../firmware/README.md`).
2. Copiar la carpeta `sesion_NNN` de la microSD a `procesamiento/datos/`.
3. Correr el reporte según el tipo de experimento:

```powershell
python -m scripts.reporte_sesion datos/sesion_001 --tipo reposo
python -m scripts.reporte_sesion datos/sesion_002 --tipo seis_caras
python -m scripts.reporte_sesion datos/sesion_003 --tipo ascensor --pisos datos_referencia/pisos_ascensor.csv --itinerario 0,3,5,0
python -m scripts.reporte_sesion datos/sesion_004 --tipo metro --estaciones "Quitumbe,Morán Valverde"
```

4. Llenar a mano las columnas manuales de `bitacora/bitacora.csv`.

**Importante:** hacer primero las seis caras reales. Ese reporte guarda
`resultados/calibracion/calibracion.json`, que usan el ascensor y el metro. Si se corre
después `calibrar_seis_caras` sin argumentos o `reporte_sesion --simulados`, la calibración
real se reemplaza por la del simulador: hay que volver a correr el reporte de las seis
caras reales.

## 4. Qué hace cada script

Todos aceptan `--help`. Sin argumentos, los scripts de análisis usan la sesión simulada que
les corresponde.

### `simulador.generar`: crear sesiones simuladas

```powershell
python -m simulador.generar                          # todos los escenarios
python -m simulador.generar --escenario seis_caras   # solo uno
python -m simulador.generar --escenario reposo --duracion-reposo-min 10
python -m simulador.generar --sin-magnetometro       # simula un MPU-6500
python -m simulador.generar --semilla 7
```

| Escenario | Carpeta en `datos/simulados/` | Contenido |
|---|---|---|
| `reposo` | `sesion_20260101_080000` | 1 hora quieto |
| `seis_caras` | `sesion_20260101_100000` | el dispositivo apoyado en cada una de sus seis caras |
| `ascensor` | `sesion_20260101_120000` | 21 recorridos en un edificio sintético de 6 plantas |
| `metro_1`, `metro_2` | `sesion_20260102_080000`, `sesion_20260103_080000` | viaje de ida por una ruta sintética de 5 estaciones |
| `metro_3` | `sesion_20260104_180000` | el viaje de vuelta |

Las fechas de las carpetas son ficticias. Las semillas son fijas: los datos salen iguales
cada vez. Además de los cuatro archivos del dispositivo, el simulador guarda la "verdad"
(`verdad.csv`, `verdad_baro.csv`, `verdad_parametros.json`, `verdad_escenario.json`), que el
dispositivo real no escribe: sirve para medir el error de cada paso.

**El edificio, la ruta del metro y los parámetros de ruido son SINTÉTICOS** (inventados y
marcados así en `config.py`). No son datos del Metro de Quito ni del sensor real.

### `scripts.verificar_sesion`: ¿se grabó bien?

```powershell
python -m scripts.verificar_sesion [RUTA_DE_LA_SESION] [--ventana 30]
```

Guarda en `resultados/verificacion/<sesión>/`:

| Archivo | Contenido |
|---|---|
| `reporte.txt` | muestras perdidas, frecuencia real (todo el registro, inicio y final), jitter y requisitos del enunciado |
| `intervalos.png` | intervalo entre muestras en el tiempo (con los huecos marcados) e histograma del jitter |
| `frecuencia.png` | frecuencia de muestreo real en ventanas, comparada con la nominal |
| `senales.png` | acelerómetro, giroscopio, presión, temperatura y magnetómetro en unidades físicas |

### `scripts.caracterizar_reposo`: ruido del sensor

```powershell
python -m scripts.caracterizar_reposo [RUTA_DE_LA_SESION]
```

Guarda en `resultados/caracterizacion/<sesión>/` la media, la desviación y el ruido de cada
señal, el porcentaje de tiempo que el detector de quietud dice "quieto", el histograma del
ruido (`ruido.png`) y la desviación de Allan (`allan.png`).

### `scripts.calibrar_seis_caras`: sesgo y escala del acelerómetro

```powershell
python -m scripts.calibrar_seis_caras [RUTA_DE_LA_SESION]
```

Detecta sola las seis caras, calcula el sesgo y la escala de cada eje con la gravedad de
Quito y guarda `resultados/calibracion/calibracion.json`. Con una sesión simulada, el
reporte compara el resultado con los valores que puso el simulador.

### `scripts.comparar_metodos`: los métodos numéricos, sin sensor

```powershell
python -m scripts.comparar_metodos
```

Usa funciones matemáticas con solución exacta, así que el error que se ve es solo el del
método. Guarda en `resultados/metodos/` el reporte con el orden de convergencia medido y
las gráficas `integracion.png` (rectángulo, trapecio, Simpson), `interpolacion.png` (lineal
y spline cúbico) y `raices.png` (bisección, Newton, secante).

### `scripts.analizar_ascensor`: altura en el ascensor

```powershell
python -m scripts.analizar_ascensor [RUTA] [--pisos datos_referencia/pisos_ascensor.csv] [--itinerario 0,3,5,2,0]
```

Calcula la altura con ocho estimaciones (sin correcciones, sesgo inicial, ZUPT, solo
barómetro, filtro complementario y tres variantes del filtro de Kalman) y las compara.
Guarda en `resultados/ascensor/<sesión>/`: `reporte.txt`, `altura.png`, `errores.png`,
`comparacion.png`, `recorridos.csv` y `cruces.csv` (instante en que se cruza cada piso,
por bisección y por secante).

- `--pisos`: CSV con `piso,altura_m` medidos con flexómetro. Sin referencia se calculan
  alturas y velocidades, pero no errores.
- `--itinerario`: piso de cada parada, según la bitácora.

### `scripts.predecir_error_ascensor`: ¿cuánto debería crecer el error?

```powershell
python -m scripts.predecir_error_ascensor [--cantidad 100]
```

Repite la simulación del ascensor con distintas semillas (Monte Carlo) y compara la
dispersión del error con las fórmulas de `navinercial/prediccion_error.py`. Guarda en
`resultados/prediccion_error/`. Tarda alrededor de un minuto.

### `scripts.analizar_metro`: viajes en metro

```powershell
python -m scripts.analizar_metro [SESION_1 SESION_2 ...] [--estaciones "Quitumbe,Morán Valverde,Solanda"]
```

Para cada viaje: orientación del dispositivo, rumbo con el giroscopio, velocidad a lo largo
de la vía, distancia de cada tramo, mapa del recorrido y confiabilidad del magnetómetro.
Guarda en `resultados/metro/<sesión>/`: `reporte.txt`, `tramos.csv`, `mapa.png`,
`viaje.png`, `rumbo.png`. Con más de un viaje, además `resultados/metro/combinado/` con los
viajes juntos y la dispersión de cada tramo.

`--estaciones`: nombres de las estaciones del viaje, en orden, como están en
`datos_referencia/estaciones_metro.csv`.

### `scripts.reporte_sesion`: todo de una sesión, y la bitácora

```powershell
python -m scripts.reporte_sesion RUTA --tipo reposo|seis_caras|ascensor|metro [opciones del tipo]
python -m scripts.reporte_sesion --simulados
```

Corre la verificación y el análisis del tipo indicado, escribe
`resultados/reportes/<sesión>.md` y actualiza la fila de la sesión en
`bitacora/bitacora.csv` (las sesiones simuladas van a `resultados/bitacora_simulada.csv`).

## 5. Qué hace cada módulo

```
procesamiento/
├── config.py            todas las constantes, con su fuente o un "TODO: citar fuente"
├── navinercial/         el programa de procesamiento
├── simulador/           genera sesiones simuladas con el mismo formato que el dispositivo
├── scripts/             los comandos de la sección 4
├── tests/               pruebas (pytest)
├── datos_referencia/    plantillas para los datos reales medidos por el grupo
├── bitacora/            bitácora de los experimentos
├── docs/                documentación
├── datos/               sesiones (no se sube a git)
└── resultados/          reportes y gráficas (no se sube a git)
```

**`navinercial/`**

| Módulo | Qué hace |
|---|---|
| `formato.py` | define el formato de una sesión (archivos, columnas, `meta.json`); lee, escribe y valida |
| `lectura.py` | convierte los enteros crudos a unidades SI (m/s², rad/s, µT, Pa, °C, s) |
| `bmp280.py` | fórmulas de compensación del barómetro (y sus inversas, para el simulador) |
| `verificacion.py` | muestras perdidas, frecuencia real, jitter |
| `calibracion.py` | estadísticas del reposo, desviación de Allan, detector de quietud, seis caras |
| `metodos/integracion.py` | integral acumulada por rectángulo, trapecio y Simpson, **hechos a mano** |
| `metodos/interpolacion.py` | interpolación lineal y spline cúbico natural (algoritmo de Thomas), a mano |
| `metodos/raices.py` | bisección, Newton y secante, a mano, con el historial de iteraciones |
| `barometro.py` | fórmula barométrica: de presión a diferencia de altura |
| `correcciones.py` | paradas a partir del botón, sesgo medido en cada parada, ZUPT, ajuste por distancia conocida |
| `fusion.py` | filtro complementario y filtro de Kalman 1D (altura y velocidad), a mano |
| `prediccion_error.py` | fórmulas de cómo crece el error al integrar ruido, sesgo y error de escala |
| `ascensor.py` | análisis del ascensor completo |
| `metro.py` | análisis del metro: orientación, rumbo, velocidad, pendiente, mapa, varios viajes |
| `bitacora.py` | lee y actualiza la bitácora |
| `graficas.py` | todas las gráficas |

**`simulador/`**

| Módulo | Qué hace |
|---|---|
| `escenarios.py` | el movimiento ideal de cada escenario (reposo, seis caras, ascensor, metro) |
| `modelo_sensor.py` | le agrega al movimiento ideal los errores del sensor: sesgo, escala, ruido, deriva, cuantización |
| `generar.py` | arma la sesión y la guarda con el formato del dispositivo |

numpy y scipy se usan para operaciones básicas con arreglos y, en las pruebas, para
**validar** los métodos hechos a mano. No se usa ninguna biblioteca de fusión de sensores.

## 6. Formato de los archivos

Una sesión es una carpeta (`sesion_NNN` del dispositivo, `sesion_AAAAMMDD_HHMMSS` del
simulador) con cuatro archivos:

| Archivo | Columnas |
|---|---|
| `meta.json` | versión, chip, rangos, frecuencias, coeficientes de calibración del BMP280 |
| `imu.csv` | `seq,t_us,ax,ay,az,gx,gy,gz,mx,my,mz` (enteros crudos, 200 Hz) |
| `baro.csv` | `seq,t_us,adc_T,adc_P` (enteros crudos, 25 Hz) |
| `eventos.csv` | `t_us,evento` (pulsaciones del botón) |

El formato está definido en un solo lugar: `navinercial/formato.py`. Si el firmware real
cambia algo, solo se modifica ese módulo (y `VERSION_FORMATO` en los dos lados).

**Magnetómetro:** muestrea más lento que el acelerómetro. En las filas de `imu.csv` donde
no hay una lectura nueva, las columnas `mx`, `my`, `mz` quedan **vacías** (no se repite la
última lectura). Si el chip no tiene magnetómetro (MPU-6500), quedan vacías en todo el archivo.

**Botón:** en el ascensor y en el metro se pulsa al arrancar y al detenerse, de forma
alternada. El registro empieza y termina parado.

## 7. Datos de referencia que debe llenar el grupo

Están vacíos a propósito: no se inventan datos reales.

| Archivo | Qué falta |
|---|---|
| `datos_referencia/pisos_ascensor.csv` | altura de cada piso, medida con flexómetro |
| `datos_referencia/estaciones_metro.csv` | latitud y longitud de cada estación, con la fuente |
| `datos_referencia/tramos_metro.csv` | longitud de cada tramo entre estaciones, con la fuente |

## 8. Qué falta cuando llegue el hardware

La lista completa y ordenada está en [docs/PENDIENTES_HARDWARE.md](docs/PENDIENTES_HARDWARE.md).
En resumen:

1. Probar que el dispositivo enciende, lee los sensores y graba (modo de prueba del firmware).
2. Grabar 90 minutos y comprobar con `verificar_sesion` que no se pierden muestras.
3. Reposo y seis caras reales; poner en `config.py` el ruido medido y revisar los umbrales
   (hoy están ajustados al simulador).
4. Ascensor: medir los pisos con flexómetro y repetir el experimento.
5. Metro: varios viajes, y buscar las coordenadas y distancias reales con su fuente.
6. Cerrar los `TODO: citar fuente` de `config.py` para el informe.

Los resultados que aparecen en `docs/RESUMEN_ETAPAS.md` son de datos simulados: **los
números del informe final tienen que salir de los datos reales.**
