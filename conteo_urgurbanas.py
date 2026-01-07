import streamlit as st
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Inches
import matplotlib.pyplot as plt
import plotly.express as px
import tempfile
import os
from datetime import datetime
from io import BytesIO
import unicodedata
import base64

# Configuración de la página
st.set_page_config(
    page_title="Analizador de Urgencias Operativas",
    page_icon="📊",
    layout="wide"
)

# --- FUNCIONES ---

def limpiar_texto(texto):
    """
    Normaliza un texto: lo convierte a minúsculas, quita acentos
    y elimina espacios en los extremos.
    """
    if not isinstance(texto, str):
        return texto

    texto_limpio = unicodedata.normalize('NFD', texto) \
                              .encode('ascii', 'ignore') \
                              .decode('utf-8') \
                              .lower() \
                              .strip()
    return texto_limpio

def parsear_fecha(fecha):
    if pd.isna(fecha): 
        return None
    if isinstance(fecha, (datetime, pd.Timestamp)): 
        return fecha
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y'):
        try: 
            return datetime.strptime(str(fecha).strip(), fmt)
        except: 
            continue
    return None

def generar_grafica_bar(conteo, titulo, filename):
    """Genera gráficas de BARRAS usando matplotlib para el reporte Word"""
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    
    plt.figure(figsize=(12, 6))
    colors = plt.cm.viridis(np.linspace(0, 1, len(df_plot)))
    bars = plt.bar(df_plot['Categoría'], df_plot['Cantidad'], color=colors)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel('Categoría', fontweight='bold')
    plt.ylabel('Cantidad', fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    
    return path

def generar_grafica_linea(datos, titulo, xlabel, ylabel, filename):
    """Genera gráficas de LÍNEA usando matplotlib para el reporte Word"""
    # datos debe ser una Serie con índice de fechas/periodos y valores numéricos
    df_plot = datos.reset_index()
    df_plot.columns = ['Fecha', 'Cantidad']
    
    # Convertir a string para asegurar que matplotlib lo grafique bien
    df_plot['Fecha'] = df_plot['Fecha'].astype(str)
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_plot['Fecha'], df_plot['Cantidad'], marker='o', linestyle='-', color='teal', linewidth=2)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel(xlabel, fontweight='bold')
    plt.ylabel(ylabel, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    
    return path

def generar_grafica_plotly(conteo, titulo):
    """Genera gráfica plotly de barras para mostrar en Streamlit"""
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    fig = px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo,
                 color='Cantidad', color_continuous_scale='Viridis')
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=12)
    )
    return fig

def generar_grafica_linea_plotly(datos, titulo, xlabel, ylabel):
    """Genera gráfica plotly de líneas"""
    df_plot = datos.reset_index()
    df_plot.columns = [xlabel, ylabel]
    # Convertir periodo a string para visualización
    df_plot[xlabel] = df_plot[xlabel].astype(str)
    
    fig = px.line(df_plot, x=xlabel, y=ylabel, title=titulo, markers=True)
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    return fig

# --- FUNCIONES DE ANÁLISIS --- (Sin cambios en lógica de lluvias)
def analizar_lluvias_manual(df, col_lluvias, col_colonias, col_fecha=None, col_hora=None):
    df_lluvias = df.copy()
    df_lluvias[col_lluvias] = df_lluvias[col_lluvias].astype(str).str.lower().str.strip()
    respuestas_afirmativas = ['sí', 'si', 'yes', 'true', 'verdadero', '1', 'x', 'check', 'afirmativo', 'lluvia']
    df_lluvias['es_lluvia'] = df_lluvias[col_lluvias].isin(respuestas_afirmativas)
    reportes_lluvias = df_lluvias[df_lluvias['es_lluvia'] == True]
    
    if len(reportes_lluvias) == 0:
        return None
    
    conteo_colonias_lluvias = reportes_lluvias[col_colonias].value_counts()
    
    if 'col_incidentes' in st.session_state:
        col_incidentes = st.session_state.col_incidentes
        conteo_incidentes_lluvias = reportes_lluvias[col_incidentes].value_counts()
    else:
        conteo_incidentes_lluvias = None
    
    analisis_fecha_hora = None
    if col_fecha:
        try:
            reportes_lluvias['fecha_parseada'] = reportes_lluvias[col_fecha].apply(parsear_fecha)
            reportes_lluvias_fecha = reportes_lluvias.dropna(subset=['fecha_parseada'])
            if not reportes_lluvias_fecha.empty:
                dia_mas_lluvias = reportes_lluvias_fecha['fecha_parseada'].dt.date.value_counts().head(1)
                hora_mas_lluvias = None
                if col_hora:
                    try:
                        reportes_lluvias_fecha['hora_parseada'] = pd.to_datetime(reportes_lluvias_fecha[col_hora], errors='coerce').dt.hour
                        reportes_lluvias_hora = reportes_lluvias_fecha.dropna(subset=['hora_parseada'])
                        if not reportes_lluvias_hora.empty:
                            hora_mas_lluvias = reportes_lluvias_hora['hora_parseada'].value_counts().head(1)
                    except:
                        pass
                analisis_fecha_hora = {
                    'dia_mas_lluvias': dia_mas_lluvias,
                    'hora_mas_lluvias': hora_mas_lluvias,
                    'reportes_con_fecha': reportes_lluvias_fecha
                }
        except:
            analisis_fecha_hora = None
    
    return {
        'columna_lluvias': col_lluvias,
        'reportes_lluvias': reportes_lluvias,
        'conteo_colonias_lluvias': conteo_colonias_lluvias,
        'conteo_incidentes_lluvias': conteo_incidentes_lluvias,
        'analisis_fecha_hora': analisis_fecha_hora,
        'colonia_mas_afectada': conteo_colonias_lluvias.head(1),
        'estadisticas': {
            'total_reportes': len(df),
            'total_lluvias': len(reportes_lluvias),
            'porcentaje_lluvias': (len(reportes_lluvias) / len(df)) * 100
        }
    }

def crear_grafico_lluvias(conteo_colonias, titulo="Colonias más afectadas por lluvias"):
    top_colonias = conteo_colonias.head(10).reset_index()
    top_colonias.columns = ['Colonia', 'Cantidad de Reportes']
    fig = px.bar(top_colonias, x='Cantidad de Reportes', y='Colonia', orientation='h',
                 title=titulo, color='Cantidad de Reportes', color_continuous_scale='blues')
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font=dict(color='black'), height=400,
                      yaxis={'categoryorder': 'total ascending'})
    return fig

def generar_reporte_word(conteos, imagenes):
    """Genera reporte en formato Word con los resultados"""
    doc = Document()
    title = doc.add_heading('Reporte de Urgencias Operativas', 0)
    title.alignment = 1
    doc.add_paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    doc.add_paragraph()
    
    doc.add_heading('Resumen de Incidentes', level=1)
    
    for nombre, conteo in conteos.items():
        doc.add_heading(nombre, level=2)
        tabla = doc.add_table(rows=1, cols=2)
        tabla.style = 'Table Grid'
        hdr_cells = tabla.rows[0].cells
        
        if "Colonias" in nombre:
            hdr_cells[0].text = "Colonia"
        else:
            hdr_cells[0].text = "Tipo de Incidente"
        hdr_cells[1].text = "Cantidad"
        
        # Limitar tabla a 20 filas para no saturar el word si hay muchos
        for tipo, cantidad in list(conteo.items())[:20]:
            row_cells = tabla.add_row().cells
            row_cells[0].text = str(tipo).title()
            row_cells[1].text = str(cantidad)
    
    doc.add_page_break()
    doc.add_heading('Gráficas', level=1)
    
    for titulo, path in imagenes.items():
        if os.path.exists(path):
            doc.add_heading(titulo, level=2)
            doc.add_picture(path, width=Inches(6.0))
            doc.add_paragraph()
    
    output_path = os.path.join(tempfile.gettempdir(), 'reporte_urgencias_operativas.docx')
    doc.save(output_path)
    return output_path

def generar_reporte_txt(conteos):
    texto = ["REPORTE DE URGENCIAS URBANAS", "=" * 50, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""]
    for nombre, conteo in conteos.items():
        texto.append(f"\n{nombre.upper()}")
        texto.append("-" * len(nombre))
        for tipo, cantidad in conteo.items():
            texto.append(f"  {tipo.title()}: {cantidad}")
    
    path_txt = os.path.join(tempfile.gettempdir(), "reporte_urgencias_operativas.txt")
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(texto))
    return path_txt

def get_download_link(file_path, file_label):
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    file_name = os.path.basename(file_path)
    return f'<a href="data:file/octet-stream;base64,{b64}" download="{file_name}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; margin: 5px;">📥 {file_label}</a>'

# --- INTERFAZ PRINCIPAL ---

def main():
    st.title("📊 Analizador de Urgencias Operativas")
    st.markdown("---")
    
    # 1. Carga de Datos
    st.header("1. Carga de Datos")
    uploaded_file = st.file_uploader("Sube tu archivo de datos (CSV o Excel)", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Archivo cargado correctamente. Dimensiones: {df.shape[0]} filas × {df.shape[1]} columnas")
            
            with st.expander("📋 Vista previa de los datos"):
                st.dataframe(df.head())
            
            # 2. Configuración
            st.header("2. Configuración del Análisis")
            col1, col2 = st.columns(2)
            with col1:
                col_incidentes = st.selectbox("Columna de INCIDENTES:", options=df.columns, index=None)
                if col_incidentes: st.session_state.col_incidentes = col_incidentes
            with col2:
                col_colonias = st.selectbox("Columna de COLONIAS:", options=df.columns, index=None)
            
            # Columna de fechas (Necesaria para gráficas de tiempo)
            col_fechas = st.selectbox("Columna de FECHAS (Requerida para gráficas de línea):", options=["No usar"] + list(df.columns), index=0)
            if col_fechas == "No usar": col_fechas = None

            # Análisis de Lluvias
            st.subheader("🌧️ Análisis de Lluvias (Opcional)")
            analizar_lluvias_check = st.checkbox("Activar análisis de lluvias")
            col_lluvias, col_fecha_lluvias, col_hora_lluvias = None, None, None
            if analizar_lluvias_check:
                c1, c2, c3 = st.columns(3)
                col_lluvias = c1.selectbox("Columna LLUVIAS:", df.columns, index=None)
                col_fecha_lluvias = c2.selectbox("Columna FECHA Lluvia:", ["No usar"]+list(df.columns))
                if col_fecha_lluvias == "No usar": col_fecha_lluvias = None
                col_hora_lluvias = c3.selectbox("Columna HORA Lluvia:", ["No usar"]+list(df.columns))
                if col_hora_lluvias == "No usar": col_hora_lluvias = None
            
            # Filtro fechas
            st.subheader("🗓️ Filtro de Rango de Fechas (Opcional)")
            usar_fechas = st.checkbox("Filtrar por rango de fechas")
            fecha_inicio, fecha_fin = None, None
            if usar_fechas and col_fechas:
                c1, c2 = st.columns(2)
                fi = c1.text_input("Fecha inicio (d/m/AAAA):", "01/01/2024")
                ff = c2.text_input("Fecha fin (d/m/AAAA):", "31/12/2024")
                try:
                    fecha_inicio = datetime.strptime(fi, '%d/%m/%Y')
                    fecha_fin = datetime.strptime(ff, '%d/%m/%Y')
                except:
                    st.error("Formato de fecha inválido")

            st.markdown("---")
            
            # --- NUEVA SECCIÓN: GRÁFICAS AVANZADAS ---
            st.subheader("📊 Configuración de Gráficas Avanzadas")
            st.info("Selecciona qué gráficas adicionales deseas incluir en el análisis y en el reporte Word.")
            
            graf_top_10 = st.checkbox("Generar gráfica Top 10 Reportes Más Recurrentes", value=True)
            
            graf_linea_incidente = st.checkbox("Generar gráfica comparativa mensual del Incidente Más Recurrente", value=False)
            if graf_linea_incidente and not col_fechas:
                st.warning("⚠️ Debes seleccionar una 'Columna de FECHAS' arriba para usar esta gráfica.")
                
            graf_linea_colonia = st.checkbox("Generar gráfica comparativa mensual de la Colonia Más Recurrente", value=False)
            if graf_linea_colonia and not col_fechas:
                st.warning("⚠️ Debes seleccionar una 'Columna de FECHAS' arriba para usar esta gráfica.")

            # Filtro Atención Médica
            st.subheader("🛠️ Filtros Adicionales")
            ignorar_atencion_medica = st.checkbox("Ignorar reportes de tipo 'Atención Médica'", value=True)

            # Botón Generar
            if col_incidentes and col_colonias:
                if st.button("🚀 Generar Reporte Completo", type="primary", use_container_width=True):
                    with st.spinner("Procesando datos..."):
                        df_clean = df.copy()
                        df_clean[col_incidentes] = df_clean[col_incidentes].apply(limpiar_texto)
                        df_clean[col_colonias] = df_clean[col_colonias].apply(limpiar_texto)
                        
                        if ignorar_atencion_medica:
                            df_clean = df_clean[df_clean[col_incidentes] != "atencion medica"]

                        # Parsear fecha si se seleccionó columna, independientemente del filtro de rango
                        if col_fechas:
                            df_clean['fecha_parseada'] = df_clean[col_fechas].apply(parsear_fecha)
                            # Eliminar filas donde la fecha no se pudo leer si se van a usar gráficas de tiempo
                            if graf_linea_incidente or graf_linea_colonia:
                                df_clean = df_clean.dropna(subset=['fecha_parseada'])

                        # Aplicar filtro de rango si aplica
                        if usar_fechas and fecha_inicio and fecha_fin and col_fechas:
                            df_clean = df_clean[(df_clean['fecha_parseada'] >= fecha_inicio) & 
                                                (df_clean['fecha_parseada'] <= fecha_fin)]
                        
                        if df_clean.empty:
                            st.error("No hay datos tras los filtros.")
                            return

                        # Conteos Básicos
                        conteos = {}
                        conteos["Conteo General"] = df_clean[col_incidentes].value_counts()
                        conteos["Conteo Colonias"] = df_clean[col_colonias].value_counts()
                        
                        # Lluvias
                        res_lluvias = None
                        if analizar_lluvias_check and col_lluvias:
                            res_lluvias = analizar_lluvias_manual(df_clean, col_lluvias, col_colonias, col_fecha_lluvias, col_hora_lluvias)
                            if res_lluvias:
                                conteos["Lluvias por Incidente"] = res_lluvias['conteo_incidentes_lluvias']
                                conteos["Lluvias por Colonia"] = res_lluvias['conteo_colonias_lluvias'].head(10)

                        # --- MOSTRAR RESULTADOS ---
                        st.header("3. 📈 Resultados")
                        
                        # Métricas
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Total Incidentes", len(df_clean))
                        c2.metric("Tipos Únicos", df_clean[col_incidentes].nunique())
                        c3.metric("Colonias Únicas", df_clean[col_colonias].nunique())

                        # Diccionario para imágenes de Word
                        imagenes_word = {}

                        # 1. Gráficas Básicas (Conteo General)
                        st.subheader("Distribución General")
                        st.dataframe(conteos["Conteo General"].reset_index(), use_container_width=True)
                        fig_gen = generar_grafica_plotly(conteos["Conteo General"].head(15), "Top Incidentes (General)")
                        st.plotly_chart(fig_gen, use_container_width=True)
                        # Guardar para word
                        imagenes_word["General"] = generar_grafica_bar(conteos["Conteo General"].head(15), "Resumen Incidentes", "graf_gen.png")

                        # --- GRÁFICAS AVANZADAS SOLICITADAS ---
                        
                        # A) TOP 10 REPORTES
                        if graf_top_10:
                            st.subheader("🏆 Top 10 Reportes Más Recurrentes")
                            top_10_data = conteos["Conteo General"].head(10)
                            
                            # Streamlit
                            fig_top10 = generar_grafica_plotly(top_10_data, "Top 10 Reportes")
                            st.plotly_chart(fig_top10, use_container_width=True)
                            
                            # Word
                            imagenes_word["Top 10 Reportes"] = generar_grafica_bar(top_10_data, "Top 10 Reportes Más Recurrentes", "graf_top10.png")

                        # B) LÍNEA TIEMPO: REPORTE MÁS RECURRENTE
                        if graf_linea_incidente:
                            if col_fechas and 'fecha_parseada' in df_clean.columns:
                                st.subheader("📈 Comparación Mensual: Reporte Más Recurrente")
                                try:
                                    # Encontrar el top 1
                                    top_incidente = conteos["Conteo General"].idxmax()
                                    st.info(f"El reporte más recurrente es: **{top_incidente.upper()}**")
                                    
                                    # Filtrar datos
                                    df_top_inc = df_clean[df_clean[col_incidentes] == top_incidente].copy()
                                    # Agrupar por mes
                                    df_top_inc['mes_anio'] = df_top_inc['fecha_parseada'].dt.to_period('M')
                                    trend_incidente = df_top_inc.groupby('mes_anio').size()
                                    
                                    # Streamlit
                                    fig_line_inc = generar_grafica_linea_plotly(trend_incidente, f"Tendencia Mensual: {top_incidente.title()}", "Mes", "Cantidad")
                                    st.plotly_chart(fig_line_inc, use_container_width=True)
                                    
                                    # Word
                                    imagenes_word[f"Tendencia {top_incidente}"] = generar_grafica_linea(
                                        trend_incidente, 
                                        f"Tendencia Mensual: {top_incidente.title()}", 
                                        "Mes", "Cantidad", "graf_linea_inc.png"
                                    )
                                except Exception as e:
                                    st.warning(f"No se pudo generar la gráfica de línea de incidentes: {e}")
                            else:
                                st.error("No se puede generar la gráfica de línea sin una columna de fechas válida.")

                        # C) LÍNEA TIEMPO: COLONIA MÁS RECURRENTE
                        if graf_linea_colonia:
                            if col_fechas and 'fecha_parseada' in df_clean.columns:
                                st.subheader("📈 Comparación Mensual: Colonia Más Recurrente")
                                try:
                                    # Encontrar top 1 colonia
                                    top_colonia = conteos["Conteo Colonias"].idxmax()
                                    st.info(f"La colonia con más reportes es: **{top_colonia.upper()}**")
                                    
                                    # Filtrar
                                    df_top_col = df_clean[df_clean[col_colonias] == top_colonia].copy()
                                    # Agrupar
                                    df_top_col['mes_anio'] = df_top_col['fecha_parseada'].dt.to_period('M')
                                    trend_colonia = df_top_col.groupby('mes_anio').size()
                                    
                                    # Streamlit
                                    fig_line_col = generar_grafica_linea_plotly(trend_colonia, f"Tendencia Mensual: {top_colonia.title()}", "Mes", "Cantidad")
                                    st.plotly_chart(fig_line_col, use_container_width=True)
                                    
                                    # Word
                                    imagenes_word[f"Tendencia {top_colonia}"] = generar_grafica_linea(
                                        trend_colonia, 
                                        f"Tendencia Mensual: {top_colonia.title()}", 
                                        "Mes", "Cantidad", "graf_linea_col.png"
                                    )
                                except Exception as e:
                                    st.warning(f"No se pudo generar la gráfica de línea de colonias: {e}")
                            else:
                                st.error("No se puede generar la gráfica de línea sin una columna de fechas válida.")

                        # Gráficas de Lluvias (si aplica)
                        if res_lluvias:
                            st.subheader("🌧️ Lluvias")
                            fig_lluv = crear_grafico_lluvias(res_lluvias['conteo_colonias_lluvias'], "Top Colonias (Lluvias)")
                            st.plotly_chart(fig_lluv, use_container_width=True)
                            imagenes_word["Lluvias"] = generar_grafica_bar(res_lluvias['conteo_colonias_lluvias'].head(10), "Lluvias por Colonia", "graf_lluvias.png")

                        # DESCARGAS
                        st.header("4. 📄 Descargar Reportes")
                        st.success("✅ Reportes generados.")
                        
                        # Generar Word con TODAS las imágenes (básicas + avanzadas)
                        doc_path = generar_reporte_word(conteos, imagenes_word)
                        st.markdown(get_download_link(doc_path, "Descargar Reporte Word (.docx)"), unsafe_allow_html=True)
                        
                        txt_path = generar_reporte_txt(conteos)
                        st.markdown(get_download_link(txt_path, "Descargar Reporte Texto (.txt)"), unsafe_allow_html=True)

                        # Limpieza
                        for path in imagenes_word.values():
                            if os.path.exists(path): os.remove(path)

            else:
                st.warning("Selecciona las columnas de Incidentes y Colonias para continuar.")

        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.info("Sube un archivo para comenzar.")

if __name__ == "__main__":
    main()
