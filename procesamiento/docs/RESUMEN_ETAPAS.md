# Resumen de las etapas

Un apartado por etapa: qué se hizo, qué decisiones se tomaron y por qué, y qué debe revisar el
grupo. Los comandos se corren desde la carpeta `procesamiento/` con el entorno virtual activado.

---

## Etapa 1: estructura, configuración y formato de archivos

**Qué se hizo**
- Repositorio git en la raíz, con el código de Python en `procesamiento/` y el firmware en `firmware/`.
- `config.py`: gravedad de Quito, factores de conversión con su fuente, configuración nominal.
- `navinercial/formato.py`: única definición del formato de una sesión (nombres de archivos,
  columnas, validación, lectura y escritura de valores crudos).

**Decisiones**
- Dos gravedades distintas: `G_QUITO = 9.77` (gravedad local) y `G_ESTANDAR = 9.80665` (definición
  de la unidad "g" de la hoja de datos, solo para pasar de LSB a m/s²). Mezclarlas produce un error
  de escala falso de 0,4 %.
- Los valores crudos se leen como enteros de 64 bits: con int16, una operación como `ax*ax` se
  desborda sin avisar.
- El magnetómetro deja las celdas vacías cuando no hay lectura nueva (no repite la última).
- `meta.json` solo acepta los chips 0x71 (MPU-9250), 0x73 (MPU-9255) y 0x70 (MPU-6500).

**Qué revisar**
- Los `TODO` de las secciones de las hojas de datos en `config.py`.

---

## Etapa 2: simulador

**Qué se hizo**
- `metodos/raices.py`: bisección. `navinercial/bmp280.py`: compensación del BMP280 e inversión
  numérica con bisección (de presión y temperatura a `adc_P` y `adc_T`).
- `simulador/modelo_sensor.py`: sesgo, error de escala, ruido blanco, deriva del sesgo,
  desalineación opcional, cuantización y saturación a int16, jitter, muestras perdidas,
  magnetómetro y barómetro (ruido, tendencia lineal, marea semidiurna y paseo aleatorio).
- `simulador/escenarios.py`: reposo largo y seis caras. `simulador/generar.py`: línea de comandos.
- Cada sesión simulada guarda además `verdad.csv`, `verdad_baro.csv` y `verdad_parametros.json`.

**Decisiones**
- El simulador muestrea a 199,96 Hz aunque `meta.json` dice 200 Hz, para que la verificación tenga
  algo que encontrar.
- El jitter es del instante de muestreo; la marca de tiempo registra el instante real.
- `t_fine` del BMP280 se deja como número real (la hoja de datos lo trunca) para que la función sea
  continua y se pueda invertir con bisección. Diferencia en presión: menos de 0,01 Pa.
- Todos los parámetros de error (`SIM_*` en `config.py`) son sintéticos y están marcados así.

**Qué revisar**
- Los valores `SIM_*`: son del orden de los típicos de las hojas de datos, pero no son mediciones.
- La convención de ejes (docstring de `escenarios.py`): x = este, y = norte, z = arriba; en reposo
  el acelerómetro mide +g en el eje que apunta hacia arriba.

---

## Etapa 3: lectura y verificación

**Qué se hizo**
- `navinercial/lectura.py`: carga una sesión y la convierte a m/s², rad/s, µT, Pa y °C.
- `navinercial/verificacion.py`: muestras perdidas (por `seq` y por tiempo), frecuencia real en todo
  el registro, al inicio, al final y por ventanas, jitter, y reporte en texto.
- `navinercial/graficas.py` y `scripts/verificar_sesion.py`: reporte y tres gráficas por sesión.

**Resultados con el reposo simulado de 60 min**
- Frecuencia real 199,9600 Hz (nominal 200), igual al inicio y al final (diferencia de 3 ppm).
- Jitter de 70,6 µs (es √2 · 50 µs: cada intervalo es la diferencia de dos instantes con jitter).
- 6 muestras perdidas del IMU y 6 del barómetro, las mismas que quitó el simulador.

**Decisiones**
- La frecuencia se calcula con `seq`: (aumento de `seq`) / (tiempo transcurrido). Así las muestras
  perdidas no la alteran.
- Dos detectores de huecos independientes (contador y reloj). Si no coinciden, el problema del
  firmware es otro (por ejemplo, una pausa sin saltar `seq`).
- La lectura no calibra: solo cambia unidades.

**Qué revisar**
- Con el reposo de 60 min el requisito de 90 min no se puede comprobar: generar uno de 90 min con
  `python -m simulador.generar --escenario reposo --duracion-reposo-min 90`.

---

## Etapa 4: caracterización y calibración

**Qué se hizo**
- `navinercial/calibracion.py`:
  - `caracterizar_reposo`: media, desviación total y ruido de cada señal.
  - `desviacion_allan`: estabilidad del sensor según el tiempo de promediado.
  - `detectar_quietud` y `tramos_de_quietud`: detector "el dispositivo está quieto".
  - `detectar_caras`, `calibrar_seis_caras`, `aplicar_calibracion`, guardar y cargar en JSON.
- `scripts/caracterizar_reposo.py` y `scripts/calibrar_seis_caras.py`.

**Resultados con las sesiones simuladas**
- Reposo: ruido del acelerómetro 0,0300 m/s² por eje y del giroscopio 0,00175 rad/s (los valores
  del simulador); el detector de quietud dice "quieto" el 100 % del tiempo.
- Seis caras: error del sesgo menor que 0,001 m/s² y error de la escala menor que 0,00002.
- Magnitud de la gravedad entre caras: sin calibrar varía 0,57 m/s² (de 9,60 a 10,17); calibrada
  vale 9,770 m/s² en las seis caras.

**Decisiones**
- El ruido se estima con las diferencias entre muestras seguidas (σ = desviación de las diferencias
  dividida por √2). Así la deriva lenta no lo infla: en la presión, la desviación total es 3,9 Pa
  por el clima, pero el ruido es 1,3 Pa.
- El detector de quietud trabaja por bloques de 0,5 s y pide tres condiciones: poca variación del
  acelerómetro, poca variación del giroscopio y velocidad angular media pequeña. Los umbrales están
  en `config.py` y son unas 2 veces el ruido del simulador.
- Límite físico del detector: no distingue el reposo de un movimiento con velocidad constante. Por
  eso en el ascensor y en el metro se combina con las marcas del botón.
- En cada cara se descarta 1 s al inicio y al final, y un tramo solo cuenta como cara si un eje mide
  al menos el 80 % de g.
- La escala calculada es `1 + error de escala` (por ejemplo, 1,010). La calibración se aplica como
  `real = (medido − sesgo) / escala`.
- El sesgo del giroscopio es su promedio en los tramos quietos de las seis caras.

**Qué revisar**
- Los umbrales `QUIETUD_*` de `config.py` hay que ajustarlos con el ruido real del dispositivo.
- En reposo, la media de `ax`, `ay`, `az` NO es el sesgo: incluye la gravedad y la inclinación de la
  mesa. El sesgo del acelerómetro solo sale de las seis caras.
- Una mesa inclinada casi no cambia el sesgo calculado, pero sí reduce la escala en cos(inclinación).
