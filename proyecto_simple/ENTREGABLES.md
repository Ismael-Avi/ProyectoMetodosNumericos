# Entregables del primer parcial

**Navegación inercial en el Metro de Quito**  
Avance del primer parcial: reposo, seis caras y ascensor. Métodos Numéricos, EPN.
Alcance del avance: **hasta el ascensor, solo con datos reales.**

Todas las rutas son relativas a la raíz del repositorio.

## Dónde está cada entregable

| Entregable | Ruta |
|---|---|
| Presentación | `proyecto_simple/presentacion/presentacion.pptx` (se genera con `proyecto_simple/presentacion/generar_presentacion.py`) |
| Bitácora | `proyecto_simple/bitacora.md` (escrita) y `proyecto_simple/bitacora.csv` (una fila automática por cada comando ejecutado) |
| Firmware | `proyecto_simple/firmware/registrador_v01/registrador_v01.ino` |
| Programa que lee y grafica los registros | `proyecto_simple/navegacion.py`. Instalación y comandos: `proyecto_simple/README.md`; explicación del código: `proyecto_simple/EXPLICACION.md`; dependencias: `proyecto_simple/requirements.txt` |
| Datos crudos | `proyecto_simple/datos/sesion_002/`, `proyecto_simple/datos/reposo_90min_2026-11-21_1915-2049/`, `proyecto_simple/datos/caras_2026-11-24v1/`, `proyecto_simple/datos/caras_2026-11-24/`, `proyecto_simple/datos/ascensor_2026-11-26/` (cada una con `meta.json`, `imu.csv`, `baro.csv`, `eventos.csv`) |
| Descripción de los datos | `proyecto_simple/datos/LEEME.md` |
| Fotos del montaje | `proyecto_simple/fotos/01_montaje_protoboard.jpeg`, `proyecto_simple/fotos/02_caja_cerrada.jpeg`, `proyecto_simple/fotos/03_ascensor.jpeg` |

Material de apoyo:

| Qué | Ruta |
|---|---|
| Resultados del avance (resumen para el docente) | `proyecto_simple/RESULTADOS_AVANCE.md` |
| Figuras y reportes de las sesiones reales | `proyecto_simple/resultados/` |
| Componentes, cómo se verificaron y conexiones | `proyecto_simple/COMPONENTES.md` |
| Prueba del hardware (I2C, WHO_AM_I, ID del BMP280, microSD; 18/11) | `proyecto_simple/evidencias/prueba_i2c_sd_2026-11-18.jpeg` |
| Guía de estudio para los integrantes | `proyecto_simple/GUIA_ESTUDIO.md` |
| Representación numérica (tipos de dato en cada etapa) | `proyecto_simple/representacion_numerica.md` |

## Hasta dónde llegamos

**Nivel alcanzado: 4.** Validación en el ascensor frente a las alturas medidas con flexómetro, con
el error cuantificado.

| Nivel | Qué lo demuestra |
|---|---|
| 1 | Fotos (`proyecto_simple/fotos/01_montaje_protoboard.jpeg`, `02_caja_cerrada.jpeg`, `03_ascensor.jpeg`), `proyecto_simple/COMPONENTES.md` (con la prueba del hardware `proyecto_simple/evidencias/prueba_i2c_sd_2026-11-18.jpeg`) y la bitácora (`proyecto_simple/bitacora.md`) |
| 2 | Firmware (`proyecto_simple/firmware/registrador_v01/registrador_v01.ino`), datos crudos (`proyecto_simple/datos/*/`) y `verificar`: `proyecto_simple/resultados/*_verificar.txt` y las figuras `*_senales.png` (en especial `reposo_90min_2026-11-21_1915-2049_senales.png`: 95 min, 0 muestras perdidas, 200,000 Hz) |
| 3 | Reposo (`resultados/reposo_90min_2026-11-21_1915-2049_reposo.png` y `sesion_002_reposo.png`), deriva (`reposo_90min_2026-11-21_1915-2049_deriva.png`), seis caras (`caras_2026-11-24_caras.png`, `caras_2026-11-24v1_caras.png`, `calibracion.json`) y convergencia (`metodos_convergencia.png`) |
| **4** | `proyecto_simple/datos/pisos.csv` (alturas con flexómetro) + `resultados/ascensor_2026-11-26_ascensor.png` + la tabla de errores por desnivel (`resultados/ascensor_2026-11-26_ascensor.txt` y `RESULTADOS_AVANCE.md`, sección 5.2) |

**Etapas pendientes (segundo parcial):** el Metro de Quito y el experimento propio.

Detalle de cada requisito, por etapa:

### Etapa 1: prototipo y caracterización

| Requisito o resultado | Archivo o gráfica que lo demuestra |
|---|---|
| El dispositivo registra datos crudos en la microSD | `proyecto_simple/datos/*/imu.csv`, `baro.csv`: enteros tal como salen del sensor (formato en `datos/LEEME.md`) |
| Muestreo ≥ 100 Hz con marca de tiempo | `proyecto_simple/resultados/reposo_90min_2026-11-21_1915-2049_verificar.txt`: 200,000 Hz al inicio y al final |
| 90 min sin perder muestras | el mismo reporte: 1 138 860 muestras, **0 perdidas**, en 94,9 min; figura `resultados/reposo_90min_2026-11-21_1915-2049_senales.png` |
| En reposo, el programa dice que no se mueve | `resultados/reposo_90min_2026-11-21_1915-2049_reposo.png` y `_reposo.txt`: quieto el 100 % del tiempo |
| Sesgo y ruido de cada eje | `resultados/reposo_90min_2026-11-21_1915-2049_reposo.txt` y `resultados/sesion_002_reposo.txt` |
| Deriva en el tiempo (sesgo, presión, temperatura) | `resultados/reposo_90min_2026-11-21_1915-2049_deriva.png` |
| Calibración de seis caras (sesgo y escala) | `resultados/calibracion.json`, `resultados/caras_2026-11-24_caras.txt` |
| La gravedad no cambia al girar el dispositivo | `resultados/caras_2026-11-24_caras.png`: \|g\| calibrado de 9,770 a 9,799 m/s² en 8 posiciones que no se usaron para calibrar |
| La calibración se repite | `resultados/caras_2026-11-24v1_caras.png` y `RESULTADOS_AVANCE.md`, sección 4 |
| Métodos numéricos hechos a mano y verificados | `resultados/metodos_convergencia.png` (rectángulo orden 1, trapecio orden 2) y `resultados/metodos.txt` (BMP280, interpolación, bisección) |
| Error del método frente al error del sensor | `resultados/metodos.txt`: el método aporta ~10⁶ veces menos error que un sesgo de 0,05 m/s² |

### Etapa 2: ascensor

| Requisito o resultado | Archivo o gráfica que lo demuestra |
|---|---|
| ≥ 5 pisos, ≥ 10 recorridos con paradas intermedias | `proyecto_simple/datos/ascensor_2026-11-26/` (PB a 5, 13 recorridos, 10 evaluados); lista en `bitacora.md`, sección 2.5 |
| Altura de los pisos medida con flexómetro | `proyecto_simple/datos/pisos.csv` |
| Altura y velocidad en el tiempo, con pisos y marcas del botón | `resultados/ascensor_2026-11-26_ascensor.png` |
| Dos métodos de integración comparados | `resultados/ascensor_2026-11-26_ascensor.txt`: rectángulo 0,107 m y trapecio 0,106 m de error RMS del desnivel |
| Error por corrección (sin corregir, sesgo, ZUPT) | el mismo reporte y `RESULTADOS_AVANCE.md`, sección 5.2: 60 m → 15 m → 0,11 m |
| Con y sin barómetro (fusión) | el mismo reporte: barómetro 0,28 m, fusión 0,29 m, acelerómetro con ZUPT 0,11 m |
| Raíces: cruce de cada piso | el mismo reporte: 23 cruces encontrados por bisección (puntos negros en `_ascensor.png`) |
| Predicción del error frente al observado | `resultados/ascensor_2026-11-26_ascensor_error.png` |
| Barómetro y acelerómetro cuentan la misma historia | `RESULTADOS_AVANCE.md`, secciones 5.2 a 5.4 (desnivel por recorrido y hallazgo de PB→1) |
| Las correcciones de pulsos no sesgan el resultado | `RESULTADOS_AVANCE.md`, sección 5.3 (10 recorridos contra los 6 de pulsos originales) |
