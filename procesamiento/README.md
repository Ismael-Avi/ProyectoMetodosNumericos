# Procesamiento: navegación inercial (Metro de Quito)

Programa en Python que procesa los datos crudos del dispositivo (ESP32 + GY-91 + microSD).
Mientras el dispositivo no esté armado, se trabaja con sesiones simuladas.

> Este README es provisional. Se completa en la etapa 8 con el uso de cada script.

## Instalación en Windows

Se necesita Python 3.10 o superior. Abrir PowerShell en la carpeta `procesamiento/` y ejecutar:

```powershell
py -m venv .venv                      # crea el entorno virtual (solo la primera vez)
.venv\Scripts\Activate.ps1            # activa el entorno (cada vez que se abre la terminal)
pip install -r requirements.txt       # instala las dependencias (solo la primera vez)
pytest                                # corre las pruebas
```

Si PowerShell no deja activar el entorno ("la ejecución de scripts está deshabilitada"), ejecutar
una sola vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Otra opción es usar el Símbolo del sistema (cmd) y activar con `.venv\Scripts\activate.bat`.

## Generar sesiones simuladas

Con el entorno activado, desde la carpeta `procesamiento/`:

```powershell
python -m simulador.generar                          # todos los escenarios (tarda unos 25 s)
python -m simulador.generar --escenario seis_caras   # solo uno
python -m simulador.generar --escenario reposo --duracion-reposo-min 10
python -m simulador.generar --sin-magnetometro       # simula un MPU-6500
```

Las sesiones quedan en `datos/simulados/` (esa carpeta no se sube a git; cada uno la genera):

| Escenario | Carpeta |
|---|---|
| Reposo largo (1 hora) | `datos/simulados/sesion_20260101_080000` |
| Seis caras | `datos/simulados/sesion_20260101_100000` |

Las fechas de las carpetas simuladas son ficticias. Además de los cuatro archivos del dispositivo,
el simulador guarda `verdad.csv`, `verdad_baro.csv` y `verdad_parametros.json`, que el dispositivo
real no escribe: sirven para medir el error de cada etapa del procesamiento.

## Verificar una sesión

```powershell
python -m scripts.verificar_sesion                                           # reposo simulado
python -m scripts.verificar_sesion datos/simulados/sesion_20260101_100000    # otra sesión
python -m scripts.verificar_sesion RUTA_DE_LA_SESION --ventana 30
```

Muestra el reporte en pantalla y guarda en `resultados/verificacion/<nombre de la sesión>/`:

| Archivo | Contenido |
|---|---|
| `reporte.txt` | muestras perdidas, frecuencia real (todo el registro, inicio y final), jitter y requisitos del enunciado |
| `intervalos.png` | intervalo entre muestras en el tiempo (con los huecos marcados) e histograma del jitter |
| `frecuencia.png` | frecuencia de muestreo real en ventanas de 60 s, comparada con la nominal |
| `senales.png` | acelerómetro, giroscopio, presión, temperatura y magnetómetro en unidades físicas |

Con los datos reales se usa igual: solo cambia la ruta de la sesión.

## Formato de los archivos

El formato de una sesión está definido en un solo lugar: `navinercial/formato.py`. Si el firmware
real cambia algo (una columna, un nombre de archivo), solo se modifica ese módulo.

**Magnetómetro:** muestrea más lento que el acelerómetro y el giroscopio. En las filas de `imu.csv`
donde no hay una lectura nueva, las columnas `mx`, `my`, `mz` quedan **vacías** (no se repite la
última lectura). Así se distingue una lectura nueva de una repetida. Si el chip no tiene
magnetómetro (MPU-6500), las tres columnas quedan vacías en todo el archivo.
