"""Genera presentacion/presentacion.pptx (primer parcial) a partir de las figuras reales.

Correr desde proyecto_simple/ (necesita python-pptx: python -m pip install python-pptx):

    python presentacion/generar_presentacion.py

Tambien dibuja presentacion/diagrama_conexiones.png. Los numeros salen de resultados/ y de
RESULTADOS_AVANCE.md; cada diapositiva lleva en las notas lo que hay que decir.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
RES = os.path.join(RAIZ, "resultados")
FOTOS = os.path.join(RAIZ, "fotos")

# Paleta: azul noche (fondo de portada y cierre), ambar (dato clave), verde azulado (apoyo)
NOCHE = RGBColor(0x14, 0x21, 0x3D)
AMBAR = RGBColor(0xE0, 0x8E, 0x2B)
VERDE = RGBColor(0x2A, 0x8C, 0x82)
TEXTO = RGBColor(0x1F, 0x29, 0x33)
GRIS = RGBColor(0x6B, 0x72, 0x80)
TARJETA = RGBColor(0xF1, 0xF4, 0xF8)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
TITULO_FUENTE = "Cambria"
CUERPO_FUENTE = "Calibri"

ANCHO, ALTO = 13.333, 7.5


def diagrama_conexiones(salida):
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    def caja(x, y, w, h, titulo, sub, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                    fc=color, ec="none"))
        ax.text(x + w / 2, y + h - 0.32, titulo, ha="center", va="top", fontsize=12, weight="bold", color="white")
        ax.text(x + w / 2, y + 0.18, sub, ha="center", va="bottom", fontsize=8.5, color="white")

    # Cajas: el ESP32 en el centro; las conexiones son lineas horizontales con su pin encima
    caja(3.9, 0.7, 2.2, 5.3, "ESP32", "ESP-WROOM-32\n(ESP32-D0WDQ6)\nLED: G2", "#14213D")
    caja(0.1, 3.3, 2.2, 2.7, "GY-91", "MPU-6500 (0x68)\nBMP280 (0x76)", "#2A8C82")
    caja(7.7, 3.3, 2.2, 2.7, "microSD", "módulo SPI\nFAT32", "#2A8C82")
    caja(0.1, 0.7, 2.2, 1.7, "Pulsador", "normalmente abierto", "#6B7280")
    caja(7.7, 0.7, 2.2, 1.7, "Power bank", "USB 5 V", "#6B7280")

    def cable(x1, x2, y, texto):
        ax.plot([x1, x2], [y, y], color="#E08E2B", lw=2)
        ax.text((x1 + x2) / 2, y + 0.07, texto, ha="center", va="bottom", fontsize=8.5, color="#1F2933")

    cable(2.3, 3.9, 5.2, "SDA → G21")
    cable(2.3, 3.9, 4.55, "SCL → G22")
    cable(2.3, 3.9, 3.9, "VIN → 3V3*")
    cable(6.1, 7.7, 5.35, "CS → G5")
    cable(6.1, 7.7, 4.85, "SCK → G18")
    cable(6.1, 7.7, 4.35, "MOSI → G23")
    cable(6.1, 7.7, 3.85, "MISO → G19")
    cable(2.3, 3.9, 1.85, "G4 (pull-up)")
    cable(2.3, 3.9, 1.2, "GND")
    cable(6.1, 7.7, 1.85, "V5")
    cable(6.1, 7.7, 1.2, "GND")
    ax.text(0.1, 0.0, "* Alimentación de los módulos (3V3 / GND): por confirmar en el montaje. "
            "Pines de datos: firmware registrador_v01.", fontsize=7.5, color="#6B7280")
    fig.tight_layout()
    fig.savefig(salida, dpi=200)
    plt.close(fig)


def texto(slide, x, y, w, h, contenido, tam=16, color=TEXTO, negrita=False, fuente=CUERPO_FUENTE,
          alinear=PP_ALIGN.LEFT, ancla=MSO_ANCHOR.TOP, cursiva=False):
    """Caja de texto. `contenido` puede ser un texto o una lista de parrafos."""
    caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = caja.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancla
    tf.margin_left = tf.margin_right = Inches(0.05)
    parrafos = contenido if isinstance(contenido, list) else [contenido]
    for i, p in enumerate(parrafos):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = alinear
        run = par.add_run()
        run.text = p
        run.font.size = Pt(tam)
        run.font.bold = negrita
        run.font.italic = cursiva
        run.font.name = fuente
        run.font.color.rgb = color
        par.space_after = Pt(6)
    return caja


def vinetas(slide, x, y, w, h, items, tam=16, color=TEXTO):
    caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = caja.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = par.add_run()
        run.text = "•  " + item
        run.font.size = Pt(tam)
        run.font.name = CUERPO_FUENTE
        run.font.color.rgb = color
        par.space_after = Pt(10)
    return caja


def titulo(slide, t, sub=None):
    texto(slide, 0.6, 0.35, ANCHO - 1.2, 0.8, t, tam=34, negrita=True, fuente=TITULO_FUENTE, color=NOCHE)
    if sub:
        texto(slide, 0.6, 1.1, ANCHO - 1.2, 0.5, sub, tam=16, color=GRIS, cursiva=True)


def imagen(slide, ruta, x, y, w, h):
    """Pone la imagen dentro del rectangulo (x, y, w, h) sin deformarla, centrada."""
    with Image.open(ruta) as im:
        ancho_px, alto_px = im.size
    escala = min(w / ancho_px, h / alto_px)
    wi, hi = ancho_px * escala, alto_px * escala
    return slide.shapes.add_picture(ruta, Inches(x + (w - wi) / 2), Inches(y + (h - hi) / 2), Inches(wi), Inches(hi))


def tarjeta(slide, x, y, w, h, numero, etiqueta, color_num=AMBAR, fondo=TARJETA, color_etq=TEXTO, tam_num=34):
    forma = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    forma.adjustments[0] = 0.12
    forma.fill.solid()
    forma.fill.fore_color.rgb = fondo
    forma.line.fill.background()
    forma.shadow.inherit = False
    texto(slide, x + 0.2, y + 0.12, w - 0.4, h * 0.55, numero, tam=tam_num, negrita=True, color=color_num,
          fuente=TITULO_FUENTE, ancla=MSO_ANCHOR.BOTTOM)
    texto(slide, x + 0.2, y + h * 0.58, w - 0.4, h * 0.42 - 0.08, etiqueta, tam=13, color=color_etq)


def fondo(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def pie(slide, t, color=GRIS):
    texto(slide, 0.6, ALTO - 0.5, ANCHO - 1.2, 0.35, t, tam=10, color=color)


def main():
    diagrama = os.path.join(AQUI, "diagrama_conexiones.png")
    diagrama_conexiones(diagrama)

    prs = Presentation()
    prs.slide_width = Inches(ANCHO)
    prs.slide_height = Inches(ALTO)
    blanco = prs.slide_layouts[6]

    # 1. Portada
    s = prs.slides.add_slide(blanco)
    fondo(s, NOCHE)
    texto(s, 0.8, 1.6, 7.2, 1.8, "Navegación inercial sin GPS", tam=44, negrita=True, color=BLANCO, fuente=TITULO_FUENTE)
    texto(s, 0.8, 3.3, 7.2, 0.9, "Primer parcial: del prototipo al ascensor, con datos reales", tam=20, color=AMBAR)
    texto(s, 0.8, 4.6, 7.2, 1.4, ["Cesar Avila · Edison Ogonaga · Sebastian Reyes",
                                  "Métodos Numéricos, EPN · Noviembre de 2026"], tam=16, color=BLANCO)
    imagen(s, os.path.join(FOTOS, "02_caja_cerrada.jpeg"), 8.6, 0.6, 4.2, 6.3)
    s.notes_slide.notes_text_frame.text = (
        "Objetivo final: reconstruir viajes en el Metro de Quito sin GPS. Este parcial cubre el "
        "dispositivo, su caracterización y la validación en un ascensor. Todo con datos reales; "
        "las simulaciones solo sirvieron para probar el código.")

    # 2. El problema
    s = prs.slides.add_slide(blanco)
    titulo(s, "El problema: medir aceleración e integrar", "Bajo tierra no hay GPS; el sensor solo mide aceleración y giro")
    pasos = [("aceleración", "lo que mide el sensor"), ("velocidad", "∫ a dt"), ("posición", "∫ v dt")]
    for i, (n, d) in enumerate(pasos):
        x = 0.8 + i * 4.1
        tarjeta(s, x, 2.0, 3.4, 1.7, n, d, color_num=NOCHE, tam_num=30)
        if i < 2:
            flecha = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 3.5), Inches(2.6), Inches(0.5), Inches(0.5))
            flecha.fill.solid()
            flecha.fill.fore_color.rgb = AMBAR
            flecha.line.fill.background()
    tarjeta(s, 0.8, 4.3, 5.6, 2.2, "½·b·t²", "un sesgo b se vuelve error de posición que crece con t²: "
            "0,0108 m/s² dan 503 m en 5 min", tam_num=40)
    tarjeta(s, 7.0, 4.3, 5.5, 2.2, "σ·√(dt·t)", "el ruido hace un paseo aleatorio en la velocidad: "
            "crece más lento, pero nunca se borra", color_num=VERDE, tam_num=40)
    s.notes_slide.notes_text_frame.text = (
        "Integrar acumula errores. Sesgo: ½·b·t². Ruido blanco: paseo aleatorio, σ_v = σ·√(dt·t). "
        "Casi todo el trabajo es quitar errores: calibrar, restar el sesgo, velocidad cero en las "
        "paradas (ZUPT) y combinar con el barómetro. El 503 m es la predicción para el ascensor sin "
        "restar el sesgo (resultados/ascensor_2026-11-26_ascensor.txt).")

    # 3. El dispositivo
    s = prs.slides.add_slide(blanco)
    titulo(s, "El dispositivo", "ESP32 + GY-91 (MPU-6500 y BMP280) + microSD + pulsador, en una caja")
    imagen(s, os.path.join(FOTOS, "01_montaje_protoboard.jpeg"), 0.6, 1.7, 3.9, 5.1)
    imagen(s, diagrama, 4.8, 1.7, 7.9, 5.1)
    pie(s, "Acelerómetro ±4 g y giroscopio ±500 °/s a 200 Hz; barómetro a 25 Hz. Datos crudos; todo se convierte en Python.")
    s.notes_slide.notes_text_frame.text = (
        "WHO_AM_I = 0x70: es un MPU-6500, sin magnetómetro (el plan suponía un MPU-9250). Por eso el "
        "rumbo solo sale del giroscopio. Dos tareas de FreeRTOS: una lee cada 5 ms y otra escribe en la "
        "microSD, con una cola de 2000 muestras en medio. Detalle en COMPONENTES.md.")

    # 4. Verificación de 95 min
    s = prs.slides.add_slide(blanco)
    titulo(s, "95 minutos sin perder una muestra", "Reposo del 21/11: 19:15 a 20:49")
    tarjeta(s, 0.6, 1.8, 3.4, 1.5, "1 138 860", "muestras del IMU")
    tarjeta(s, 0.6, 3.5, 3.4, 1.5, "0", "muestras perdidas (seq sin saltos)", color_num=VERDE)
    tarjeta(s, 0.6, 5.2, 3.4, 1.5, "200,000 Hz", "al inicio y al final; jitter 0,8 µs")
    imagen(s, os.path.join(RES, "reposo_90min_2026-11-21_1915-2049_senales.png"), 4.3, 1.6, 8.5, 5.4)
    pie(s, "resultados/reposo_90min_2026-11-21_1915-2049_verificar.txt · requisitos: ≥ 100 Hz y 90 min continuos")
    s.notes_slide.notes_text_frame.text = (
        "Cumple los dos requisitos del enunciado. Mostrar en la figura: aceleración y giro planos; la "
        "presión sube ~80 Pa sin moverse (clima); la temperatura sube 1 °C al encender y se estabiliza "
        "hacia el minuto 20. t_us es de 64 bits: con 32 bits se habría desbordado a los 71,6 min.")

    # 5. Ruido y deriva
    s = prs.slides.add_slide(blanco)
    titulo(s, "Ruido y deriva en reposo", "Lo que el sensor se equivoca estando quieto")
    imagen(s, os.path.join(RES, "reposo_90min_2026-11-21_1915-2049_deriva.png"), 0.5, 1.5, 5.6, 5.6)
    tarjeta(s, 6.5, 1.7, 3.0, 1.5, "0,013 m/s²", "ruido del acelerómetro")
    tarjeta(s, 9.8, 1.7, 3.0, 1.5, "−4,5 °/s", "sesgo del giroscopio en x", color_num=VERDE)
    tarjeta(s, 6.5, 3.4, 3.0, 1.5, "−0,088 °/s", "deriva de gx en 95 min (más en los primeros 20)")
    tarjeta(s, 9.8, 3.4, 3.0, 1.5, "+0,80 hPa", "presión por el clima = 9,65 m falsos", color_num=VERDE)
    texto(s, 6.5, 5.2, 6.3, 1.5, "Por eso cada sesión empieza con 10 s quieta: ahí se miden el sesgo, "
          "la vertical y la presión de referencia.", tam=16, color=TEXTO)
    s.notes_slide.notes_text_frame.text = (
        "Bloques de 10 min. Si solo se resta el sesgo del inicio, la deriva de gx (−0,047 (°/s)/h) "
        "desvía el rumbo 2,4° en 10 min y 191° en 90 min. La deriva es mayor mientras cambia la "
        "temperatura, pero sigue después: no es solo temperatura. Fuente: reposo_..._reposo.txt.")

    # 6. Seis caras
    s = prs.slides.add_slide(blanco)
    titulo(s, "Calibración de seis caras", "sesgo = (a₊ + a₋)/2   ·   escala = (a₊ − a₋)/(2g)")
    imagen(s, os.path.join(RES, "caras_2026-11-24_caras.png"), 0.4, 1.6, 8.6, 4.4)
    tarjeta(s, 9.4, 1.8, 3.4, 1.6, "18×", "menos variación de |g| en las 8 posiciones de prueba")
    tarjeta(s, 9.4, 3.6, 3.4, 1.6, "9,770–9,799", "|g| calibrado en m/s² (antes 9,661–10,127)", color_num=VERDE, tam_num=28)
    texto(s, 0.6, 6.15, 8.4, 0.8, "Rojo: sin calibrar · verde: calibrado · lo que prueba son las columnas «extra».",
          tam=14, color=GRIS)
    s.notes_slide.notes_text_frame.text = (
        "Las caras calibradas dan ~9,77 por construcción; la prueba son los 8 tramos extra. Los verdes "
        "quedan ~0,016 m/s² arriba de 9,77 porque las caras quedaron inclinadas ~3,3°: el eje mide "
        "g·cos θ. En x+ (3,6°) se predice 9,7893 y se mide 9,7891. Una segunda calibración da los "
        "mismos sesgos (diferencias de 0,003 a 0,022 m/s²).")

    # 7. Métodos numéricos
    s = prs.slides.add_slide(blanco)
    titulo(s, "Métodos numéricos hechos a mano", "Integración doble de una señal con solución exacta")
    imagen(s, os.path.join(RES, "metodos_convergencia.png"), 0.5, 1.5, 6.6, 5.4)
    tarjeta(s, 7.5, 1.7, 2.5, 1.5, "1,00", "orden del rectángulo (teoría: 1)")
    tarjeta(s, 10.3, 1.7, 2.5, 1.5, "2,00", "orden del trapecio (teoría: 2)", color_num=VERDE)
    tarjeta(s, 7.5, 3.4, 5.3, 1.6, "~10⁶ veces", "menos error aporta el método que un sesgo de 0,05 m/s² en 30 s")
    texto(s, 7.5, 5.3, 5.3, 1.5, "También verificados: BMP280 contra el ejemplo de Bosch, "
          "interpolación lineal y bisección.", tam=15)
    s.notes_slide.notes_text_frame.text = (
        "Al dividir dt a la mitad, el error del rectángulo baja a la mitad y el del trapecio a la "
        "cuarta parte. Pero el método no es el problema: el error del sensor es un millón de veces "
        "mayor. Mejorar el método no sirve; hay que corregir el sensor. Fuente: resultados/metodos.txt.")

    # 8. Ascensor: figura
    s = prs.slides.add_slide(blanco)
    titulo(s, "Ascensor: altura y velocidad", "26/11 · PB a 5 · 13 recorridos, 10 evaluados (10 y 12 en rojo: sin pulsos reales)")
    imagen(s, os.path.join(RES, "ascensor_2026-11-26_ascensor.png"), 0.5, 1.55, 12.3, 5.4)
    s.notes_slide.notes_text_frame.text = (
        "Gris: barómetro. Naranja: fusión. Azul: acelerómetro con ZUPT, sin barómetro. Puntos negros: "
        "23 cruces de piso por bisección. Abajo: con ZUPT la velocidad vuelve a 0 en cada parada; sin "
        "ZUPT se acumula. Recorridos elegidos por la calidad de los pulsos, decidida antes de ver los "
        "errores: si el pulso existió a destiempo se corrige; si nadie pulsó (10 y 12), se descarta.")

    # 9. Ascensor: tabla
    s = prs.slides.add_slide(blanco)
    titulo(s, "Ascensor: error del desnivel por corrección", "Error RMS de (altura de llegada − altura de salida) contra la cinta")
    filas = [("Corrección", "Sin pasar por PB\n(2, 5, 6, 9, 11)", "Tocando PB\n(1, 3, 4, 7, 8)"),
             ("Sin corrección (rectángulo o trapecio)", "60,2 m", "49,8 m"),
             ("Restando el sesgo", "14,7 m", "11,1 m"),
             ("Rectángulo + ZUPT", "0,107 m", "0,508 m"),
             ("Trapecio + ZUPT", "0,106 m", "0,504 m"),
             ("Solo barómetro", "0,283 m", "0,616 m"),
             ("Fusión acelerómetro + barómetro + ZUPT", "0,293 m", "0,595 m")]
    tabla = s.shapes.add_table(len(filas), 3, Inches(0.6), Inches(1.75), Inches(8.2), Inches(4.6)).table
    tabla.columns[0].width = Inches(4.2)
    tabla.columns[1].width = Inches(2.0)
    tabla.columns[2].width = Inches(2.0)
    for i, fila in enumerate(filas):
        for j, valor in enumerate(fila):
            celda = tabla.cell(i, j)
            celda.text = valor
            celda.fill.solid()
            destacada = (i == 4)
            celda.fill.fore_color.rgb = NOCHE if i == 0 else (RGBColor(0xFC, 0xEB, 0xD5) if destacada else
                                                              (TARJETA if i % 2 else BLANCO))
            for par in celda.text_frame.paragraphs:
                par.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
                for run in par.runs:
                    run.font.size = Pt(14 if i else 13)
                    run.font.name = CUERPO_FUENTE
                    run.font.bold = (i == 0) or destacada
                    run.font.color.rgb = BLANCO if i == 0 else TEXTO
            celda.vertical_anchor = MSO_ANCHOR.MIDDLE
    tarjeta(s, 9.2, 1.75, 3.5, 2.1, "0,106 m", "acelerómetro con ZUPT, sin barómetro (desniveles de 5 a 10 m)")
    tarjeta(s, 9.2, 4.05, 3.5, 2.3, "0,121 m", "lo mismo, solo con los recorridos de pulsos 100 % originales: "
            "corregir los pulsos no sesgó el resultado", color_num=VERDE)
    pie(s, "resultados/ascensor_2026-11-26_ascensor.txt · RESULTADOS_AVANCE.md, secciones 5.2 y 5.3")
    s.notes_slide.notes_text_frame.text = (
        "Cada corrección baja el error: 60 m → 15 m → 0,1 m. Rectángulo y trapecio dan lo mismo: manda "
        "el sensor. El barómetro solo y la fusión quedan peor que el ZUPT porque el barómetro deriva "
        "~0,7 m en 5 min (sobre todo en el recorrido 11). Con PB el error es mayor porque incluye la "
        "altura PB→1 de la cinta (siguiente diapositiva). Predicción del ruido con ZUPT: 0,100 m.")

    # 10. Hallazgo PB->1
    s = prs.slides.add_slide(blanco)
    titulo(s, "Hallazgo: la cinta mide mal PB→1", "Cada recorrido con PB estima PB→1 = |desnivel| − distancia de cinta del piso 1 al otro piso")
    datos = CategoryChartData()
    datos.categories = ["Rec. 1 (0→1)", "Rec. 3 (3→0)", "Rec. 4 (0→5)", "Rec. 7 (5→0)", "Rec. 8 (0→3)"]
    datos.add_series("Barómetro", (5.74, 5.30, 5.41, 5.53, 5.51))
    datos.add_series("Acelerómetro + ZUPT", (5.41, 5.48, 5.53, 5.44, 4.87))
    datos.add_series("Cinta", (4.90, 4.90, 4.90, 4.90, 4.90))
    grafico = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.7), Inches(8.0),
                                 Inches(5.2), datos).chart
    grafico.has_legend = True
    grafico.legend.position = XL_LEGEND_POSITION.BOTTOM
    grafico.legend.include_in_layout = False
    grafico.legend.font.size = Pt(12)
    grafico.legend.font.name = CUERPO_FUENTE
    eje = grafico.value_axis
    eje.minimum_scale = 4.0
    eje.maximum_scale = 6.0
    eje.has_major_gridlines = True
    eje.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xE1, 0xE6)
    eje.tick_labels.font.size = Pt(12)
    eje.tick_labels.font.name = CUERPO_FUENTE
    eje.has_title = True
    eje.axis_title.text_frame.text = "PB→1 (m)"
    eje.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    grafico.category_axis.tick_labels.font.size = Pt(12)
    grafico.category_axis.tick_labels.font.name = CUERPO_FUENTE
    for serie, color in zip(grafico.series, [VERDE, AMBAR, RGBColor(0xA0, 0xA6, 0xB0)]):
        serie.format.fill.solid()
        serie.format.fill.fore_color.rgb = color
    tarjeta(s, 9.0, 1.8, 3.8, 1.5, "5,50 ± 0,16", "barómetro, 5 recorridos (m)", color_num=VERDE, tam_num=30)
    tarjeta(s, 9.0, 3.5, 3.8, 1.5, "5,34 ± 0,27", "acelerómetro, 5 recorridos (m)", tam_num=30)
    tarjeta(s, 9.0, 5.2, 3.8, 1.5, "±0,1 m", "1→3 y 3→5 sí coinciden con la cinta", color_num=NOCHE, tam_num=30)
    s.notes_slide.notes_text_frame.text = (
        "Dos sensores independientes dicen que PB→1 mide ~5,3–5,5 m, no 4,90. El acelerómetro lo dice "
        "en 4 de 5 recorridos (el 8 da 4,87). Los tramos 1→3 y 3→5 coinciden con la cinta: el error "
        "parece de la medición de PB→1. No se pudo volver a medir; por eso la evaluación principal usa "
        "los recorridos que no pasan por PB.")

    # 11. Límites
    s = prs.slides.add_slide(blanco)
    titulo(s, "Límites del sistema", "Qué alcanza y qué no, con nuestros números")
    celdas = [("0,0012 m/s²", "1 LSB del acelerómetro: el ruido (0,013) es 11 veces más; la resolución no limita"),
              ("38 MB/h", "en la microSD (tamaño real de nuestros archivos): 90 min ocupan ~58 MB"),
              ("71,6 min", "es cuando se habría desbordado t_us con 32 bits; con 64 bits no hay límite"),
              ("~1 min", "sin correcciones, la deriva ya deja errores de decenas de metros: es el límite real"),
              ("7 km → 22 m", "metro de 22 km (estimación): sin ZUPT contra ZUPT en cada estación"),
              ("95 min", "con la power bank sin cortes; falta medir la corriente y la capacidad")]
    for i, (n, d) in enumerate(celdas):
        x = 0.6 + (i % 3) * 4.15
        y = 1.75 + (i // 3) * 2.6
        tarjeta(s, x, y, 3.85, 2.3, n, d, color_num=(AMBAR if i % 2 == 0 else VERDE), tam_num=30)
    s.notes_slide.notes_text_frame.text = (
        "Como registrador cumple 90 min. Lo que limita es la deriva al navegar. Estimación del metro "
        "(guia/estimar_error_metro.py): sin ZUPT, 7,3 km de error al final; con ZUPT, ~22 m, dominado "
        "por el error de escala (0,094 %), que se corrige con la distancia conocida entre estaciones. "
        "Detalle en GUIA_ESTUDIO.md, secciones d y e.")

    # 12. Plan
    s = prs.slides.add_slide(blanco)
    fondo(s, NOCHE)
    texto(s, 0.8, 0.6, 11.5, 0.9, "Plan para el segundo parcial", tam=36, negrita=True, color=BLANCO, fuente=TITULO_FUENTE)
    items = [("≥ 3 viajes en metro", "varias estaciones, distintos días o sentidos; pulsar antes de arrancar"),
             ("Coordenadas con fuente", "estaciones y largo de cada tramo, de una fuente verificable"),
             ("ZUPT + distancia conocida", "corregir la escala con los tramos y medir el sesgo del giroscopio en cada parada"),
             ("Experimento propio", "un límite del sistema; idea: 90 min con pilas AA")]
    for i, (n, d) in enumerate(items):
        y = 1.8 + i * 1.32
        circulo = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(y), Inches(0.7), Inches(0.7))
        circulo.fill.solid()
        circulo.fill.fore_color.rgb = AMBAR
        circulo.line.fill.background()
        circulo.text_frame.text = str(i + 1)
        par = circulo.text_frame.paragraphs[0]
        par.alignment = PP_ALIGN.CENTER
        par.runs[0].font.size = Pt(20)
        par.runs[0].font.bold = True
        par.runs[0].font.color.rgb = NOCHE
        texto(s, 1.8, y - 0.08, 5.6, 0.5, n, tam=20, negrita=True, color=BLANCO)
        texto(s, 1.8, y + 0.38, 5.6, 0.7, d, tam=14, color=RGBColor(0xC9, 0xD1, 0xDC))
    imagen(s, os.path.join(FOTOS, "03_ascensor.jpeg"), 7.9, 1.7, 4.8, 4.8)
    s.notes_slide.notes_text_frame.text = (
        "Lo aprendido en el ascensor: pulsar antes de que arranque, no olvidar pulsos, 10 s quieto al "
        "inicio y no apagar antes de detenerse. Montaje final con 4 pilas AA en la caja rígida.")

    salida = os.path.join(AQUI, "presentacion.pptx")
    prs.save(salida)
    print(f"Guardado {salida} ({len(prs.slides)} diapositivas)")


if __name__ == "__main__":
    main()
