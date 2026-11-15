# Bitácora de los registros

`bitacora.csv` tiene una fila por sesión grabada con el dispositivo. Se abre con Excel o
con cualquier editor de texto.

## Cómo se llena

1. Después de grabar, copiar la carpeta `sesion_NNN` de la microSD a `procesamiento/datos/`.
2. Correr el reporte (desde `procesamiento/`):

       python -m scripts.reporte_sesion datos/sesion_001 --tipo ascensor

   Eso agrega la fila de la sesión y llena las columnas automáticas.
3. Llenar a mano las columnas manuales de esa fila. Si se vuelve a correr el reporte, lo
   escrito a mano **no se borra**: el programa solo cambia las columnas automáticas.

## Columnas manuales (las llena el grupo)

| Columna | Qué anotar |
|---|---|
| `sesion` | nombre de la carpeta (`sesion_001`); lo pone el programa |
| `tipo` | `reposo`, `seis_caras`, `ascensor` o `metro`; lo pone el programa |
| `fecha`, `hora` | cuándo se grabó. El ESP32 no tiene reloj: solo quedan aquí |
| `lugar` | edificio y ascensor, o estaciones de inicio y fin del viaje |
| `condiciones` | vagón lleno o vacío, de pie o sentado, temperatura aproximada, etc. |
| `procedimiento` | qué se hizo y cuándo se pulsó el botón (por ejemplo, pisos 0-3-5-0) |
| `orientacion_dispositivo` | cómo estaba puesto: qué eje apuntaba hacia arriba y cuál hacia adelante |
| `foto` | nombre del archivo de la foto del montaje |
| `observaciones` | cualquier cosa rara: golpes, pulsaciones de más, paradas no previstas |

## Columnas automáticas (las calcula el programa)

| Columna | Significado |
|---|---|
| `duracion_s` | duración del registro, en s |
| `fs_real_hz` | frecuencia de muestreo real de la IMU, en Hz |
| `muestras_perdidas` | muestras que faltan según el contador `seq` |
| `desplazamiento_m` | suma de lo recorrido en todos los tramos, en m (ascensor y metro) |
| `velocidad_max_ms` | velocidad máxima, en m/s |
| `aceleracion_max_ms2` | aceleración máxima (de la velocidad suavizada 1 s), en m/s² |
| `duracion_tramos_s` | duración de cada tramo entre paradas, en s, separadas por espacios |

Las sesiones del simulador no entran en esta bitácora: van a
`resultados/bitacora_simulada.csv`.
