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

## Formato de los archivos

El formato de una sesión está definido en un solo lugar: `navinercial/formato.py`. Si el firmware
real cambia algo (una columna, un nombre de archivo), solo se modifica ese módulo.

**Magnetómetro:** muestrea más lento que el acelerómetro y el giroscopio. En las filas de `imu.csv`
donde no hay una lectura nueva, las columnas `mx`, `my`, `mz` quedan **vacías** (no se repite la
última lectura). Así se distingue una lectura nueva de una repetida. Si el chip no tiene
magnetómetro (MPU-6500), las tres columnas quedan vacías en todo el archivo.
