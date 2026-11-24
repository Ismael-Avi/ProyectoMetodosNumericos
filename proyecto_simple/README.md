# Navegación inercial, versión simple

Todo el procesamiento está en un solo script, `navegacion.py`. Lee las sesiones que graba el
firmware `firmware/registrador_v01/registrador_v01.ino` (ESP32 + MPU-6500 + BMP280) y calcula
velocidad, altura y trayectoria sin GPS.

## Instalar

```
pip install -r requirements.txt
```

Se probó con Python 3.14, numpy 2.5, pandas 3.1 y matplotlib 3.11. No hace falta scipy.

## Carpetas

```
navegacion.py            todo el procesamiento
firmware/registrador_v01 firmware del dispositivo (copia sin cambios del que ya se probó)
datos/sesion_NNN/        sesiones reales: meta.json, imu.csv, baro.csv, eventos.csv
datos/simulados/         sesiones simuladas, solo para probar el código (no se suben a git)
datos/pisos.csv          altura real de cada piso (flexómetro)       -> VACÍO, falta medir
datos/estaciones.csv     estaciones, coordenadas y largo de cada tramo -> VACÍO, falta llenar
datos/viajes.csv         en qué estación empezó cada viaje y en qué sentido -> VACÍO
resultados/              figuras (.png), reportes (.txt) y calibracion.json
bitacora.csv             una fila por cada comando ejecutado
```

`datos/viajes.csv` no estaba en el plan original. Hace falta porque con solo `eventos.csv` el
programa no sabe por qué estaciones pasó un viaje. Columnas: `sesion,estacion_inicial,sentido`
(`sentido` = 1 si el viaje va en el orden de `estaciones.csv`, -1 si va al revés). El nombre de
la estación se escribe igual que en `estaciones.csv`.

## Comandos

Se corren desde la carpeta `proyecto_simple/`:

| Comando | Qué hace | Ejemplo |
|---|---|---|
| `verificar` | muestras perdidas, frecuencia real al inicio y al final, jitter, gráfica de señales | `python navegacion.py verificar datos/sesion_002` |
| `reposo` | sesgo y ruido de cada eje, detector quieto / en movimiento, inclinación, deriva por bloques de 10 min (giroscopio, acelerómetro, presión, temperatura) con figura `*_deriva.png` | `python navegacion.py reposo datos/sesion_002` |
| `caras` | calibración de seis caras; guarda `resultados/calibracion.json`. Además muestra \|g\| calibrado en cada tramo quieto que no se usó (posiciones inclinadas): prueba de que \|g\| no cambia al girar | `python navegacion.py caras datos/simulados/caras` |
| `metodos` | prueba del BMP280 y de los métodos numéricos contra numpy y contra soluciones exactas | `python navegacion.py metodos` |
| `ascensor` | altura y velocidad con dos métodos, ZUPT, barómetro, fusión, cruces de piso, errores | `python navegacion.py ascensor datos/simulados/ascensor` |
| `metro` | rumbo, velocidad, distancia por tramo, trayectoria y dispersión entre viajes | `python navegacion.py metro datos/simulados/metro_1 datos/simulados/metro_2` |

**Opciones** (sirven con cualquier comando que lee una sesión):

- `--botones`: usa solo desde la primera hasta la última pulsación del botón.
- `--recorte N`: quita N segundos al inicio y al final. Si se combina con `--botones`, se quitan
  después de las pulsaciones (así no entra el movimiento de apretar el botón).

El tiempo conserva el eje original (el segundo 3 sigue siendo el segundo 3). Ejemplo con el reposo
real de 95 min:

```
python navegacion.py verificar datos/reposo_90min_2026-11-21_1915-2049
python navegacion.py reposo    datos/reposo_90min_2026-11-21_1915-2049 --botones --recorte 5
```

`verificar` conviene correrlo sin recorte (las pérdidas y la frecuencia se miden en todo el
registro). Las pulsaciones a menos de 1 s de la anterior se ignoran (rebote del pulsador).

Orden recomendado: `verificar` → `reposo` → `caras` (una vez) → `ascensor` / `metro`.
`ascensor` y `metro` usan la calibración de `caras`. Si no existe, avisan y siguen sin calibrar.

## Cómo hay que grabar (lo que el programa supone)

- **Los primeros 10 s quieto.** Con ese reposo se mide la dirección de la gravedad, el sesgo del
  giroscopio y la presión de referencia. El giroscopio de este MPU-6500 tiene unos -4,5 °/s de
  sesgo en x, así que esto es obligatorio en cada sesión.
- **Botón en pares.** Ascensor: un pulso al cerrarse la puerta (antes de moverse) y otro al
  abrirse (ya detenido). Metro: un pulso al salir de la estación y otro al llegar. Cada par
  (salida, llegada) es un tramo; entre pares el dispositivo está parado y se aplica ZUPT. Si el
  número de pulsos es impar, el programa usa el detector de quietud, que no distingue una parada
  de una velocidad constante. Por eso conviene no olvidar ningún pulso.
- **Ascensor:** empezar en el piso 0 de `pisos.csv` (las alturas son relativas a ese piso).
- **Metro:** el dispositivo va fijo al vagón, en cualquier orientación. La dirección "adelante"
  se saca del primer arranque.
- **Caras:** al menos 10 s quieto en cada una de las seis caras. En la misma grabación, dejar
  el dispositivo quieto al menos 5 s en varias posiciones inclinadas (apoyado contra algo, en
  ángulos cualquiera), moviéndolo entre posición y posición. Esos tramos no se usan para calibrar:
  sirven para comprobar la calibración. Si una sesión no tiene las 6 caras, `caras` no calibra,
  pero revisa sus tramos quietos con la calibración guardada.

## Fuentes de las constantes

| Constante | Valor | Fuente |
|---|---|---|
| `G` (gravedad en Quito) | 9,77 m/s² | valor del enunciado. **TODO: citar una fuente** (p. ej. un modelo de gravedad a 2850 m, latitud 0,2° S) |
| `G_ESTANDAR` | 9,80665 m/s² | definición de 1 g (3.ª CGPM, 1901). Solo sirve para pasar de "g" a m/s², no es la gravedad de Quito |
| `LSB_POR_G[4]` | 8192 LSB/g | InvenSense, *MPU-6500 Product Specification*, tabla de especificaciones del acelerómetro (Sensitivity Scale Factor, AFS_SEL=1) |
| `LSB_POR_DPS[500]` | 65,5 LSB/(°/s) | misma hoja, tabla del giroscopio (FS_SEL=1) |
| fórmula del BMP280 | `bmp280()` | Bosch, *BMP280 datasheet* BST-BMP280-DS001: fórmula de compensación en punto flotante (double) y ejemplo de cálculo (adc_T=519888, adc_P=415148 → 25,08 °C y 100653,27 Pa). TODO: anotar el número de sección del PDF que usen |
| `R_GAS` | 8,314462618 J/(mol·K) | constante de los gases, valor exacto del SI (2019) |
| `M_AIRE` | 0,0289644 kg/mol | masa molar del aire seco, *U.S. Standard Atmosphere 1976* |
| `RADIO_TIERRA` | 6 371 000 m | radio medio de la Tierra (IUGG). Solo para pasar lat/lon a metros en distancias cortas |

Parámetros elegidos por nosotros (no son constantes físicas):

| Parámetro | Valor | Por qué |
|---|---|---|
| `UMBRAL_ACC`, `UMBRAL_GIRO` | 0,06 m/s², 0,3 °/s | desviación estándar en ventanas de 0,5 s. En reposo real (sesion_002) el ruido es ~0,016 m/s² y ~0,065 °/s; un golpe en la mesa da ~0,06–0,08 |
| `REPOSO_INICIAL_S` | 10 s | reposo al inicio de cada sesión |
| `REBOTE_BOTON_S` | 1 s | dos pulsaciones más juntas que esto cuentan como una (rebote; el firmware solo filtra 200 ms) |
| `BLOQUE_DERIVA_S` | 600 s | tamaño de los bloques para estudiar la deriva en `reposo` |
| `CARA_MINIMA_S`, `QUIETO_MINIMO_S` | 10 s, 3 s | duración mínima (sin contar 1 s de margen a cada lado) de una cara y de un tramo quieto extra |
| `TAU_FILTRO_S` | 3 s | filtro complementario: por debajo de ~3 s manda el acelerómetro, por encima el barómetro |
| `SUAVIZADO_BARO_S` | 10 s | ventana para derivar la altura barométrica en el metro (pendiente). Con 2 s la pendiente sale muy ruidosa |
| `PRUEBA_SESGO`, `PRUEBA_RUIDO` | 0,05 y 0,02 m/s² | valores de prueba del comando `metodos`, del orden del ruido medido en sesion_002 |

## Lo que todavía no se puede hacer

- Los errores contra la realidad salen en cuanto se llenen `pisos.csv` y `estaciones.csv` (y `viajes.csv`).
  Mientras estén vacíos, el ascensor se compara contra el barómetro y el metro no tiene error.
- Sin coordenadas reales, el mapa del metro se dibuja con el eje x en la dirección inicial de cada viaje.
- Como trazado real se usa la línea recta entre estaciones. No tenemos la forma de la vía.
- Sin magnetómetro (MPU-6500), el rumbo sale solo del giroscopio y su error crece con el tiempo.
