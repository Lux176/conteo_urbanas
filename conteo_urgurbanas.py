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
    """Genera gráficas usando matplotlib para el reporte Word"""
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    
    # Crear gráfica con matplotlib
    plt.figure(figsize=(12, 6))
    colors = plt.cm.viridis(np.linspace(0, 1, len(df_plot)))
    bars = plt.bar(df_plot['Categoría'], df_plot['Cantidad'], color=colors)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel('Categoría', fontweight='bold')
    plt.ylabel('Cantidad', fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    
    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    
    # Guardar imagen
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    
    return path

def generar_grafica_plotly(conteo, titulo):
    """Genera gráfica plotly para mostrar en Streamlit"""
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
    fig.update_xaxes(title_text="Categoría")
    fig.update_yaxes(title_text="Cantidad")
    return fig

# --- NUEVA FUNCIÓN: ANÁLISIS DE LLUVIAS ---
def analizar_lluvias(df, col_incidentes, col_colonias):
    """
    Realiza análisis especializado de reportes por lluvias
    """
    # Buscar la columna de lluvias (diferentes nombres posibles)
    posibles_nombres = [
        "¿El reporte referente a las lluvias?",
        "reporte referente a las lluvias",
        "lluvias",
        "reporte_lluvias",
        "es_lluvia",
        "por_lluvias",
        "causa_lluvia"
    ]
    
    columna_lluvias = None
    for nombre in posibles_nombles:
        if nombre.lower() in [col.lower() for col in df.columns]:
            # Encontrar el nombre exacto de la columna
            for col in df.columns:
                if col.lower() == nombre.lower():
                    columna_lluvias = col
                    break
            if columna_lluvias:
                break
    
    if columna_lluvias is None:
        return None
    
    # Filtrar solo reportes de lluvias
    df_lluvias = df.copy()
    
    # Normalizar respuestas de lluvias
    df_lluvias[columna_lluvias] = df_lluvias[columna_lluvias].astype(str).str.lower().str.strip()
    
    # Mapear diferentes formatos de respuesta
    respuestas_afirmativas = ['sí', 'si', 'yes', 'true', 'verdadero', '1', 'x', 'check', 'afirmativo']
    df_lluvias['es_lluvia'] = df_lluvias[columna_lluvias].isin(respuestas_afirmativas)
    
    # Filtrar reportes de lluvias
    reportes_lluvias = df_lluvias[df_lluvias['es_lluvia'] == True]
    
    if len(reportes_lluvias) == 0:
        return None
    
    # Análisis por colonia
    conteo_colonias_lluvias = reportes_lluvias[col_colonias].value_counts()
    
    # Análisis por tipo de incidente en lluvias
    conteo_incidentes_lluvias = reportes_lluvias[col_incidentes].value_counts()
    
    # Estadísticas generales
    total_reportes = len(df)
    total_lluvias = len(reportes_lluvias)
    porcentaje_lluvias = (total_lluvias / total_reportes) * 100
    
    return {
        'columna_lluvias': columna_lluvias,
        'reportes_lluvias': reportes_lluvias,
        'conteo_colonias_lluvias': conteo_colonias_lluvias,
        'conteo_incidentes_lluvias': conteo_incidentes_lluvias,
        'estadisticas': {
            'total_reportes': total_reportes,
            'total_lluvias': total_lluvias,
            'porcentaje_lluvias': porcentaje_lluvias
        }
    }

# --- NUEVA FUNCIÓN: CREAR GRÁFICO DE LLUVIAS ---
def crear_grafico_lluvias(conteo_colonias, titulo="Colonias más afectadas por lluvias"):
    """
    Crea un gráfico de barras de las colonias más afectadas por lluvias
    """
    # Tomar las top 10 colonias para mejor visualización
    top_colonias = conteo_colonias.head(10).reset_index()
    top_colonias.columns = ['Colonia', 'Cantidad de Reportes']
    
    fig = px.bar(
        top_colonias,
        x='Cantidad de Reportes',
        y='Colonia',
        orientation='h',
        title=titulo,
        color='Cantidad de Reportes',
        color_continuous_scale='blues'
    )
    
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black'),
        height=400,
        xaxis_title="Número de Reportes",
        yaxis_title="Colonia",
        yaxis={'categoryorder': 'total ascending'}
    )
    
    return fig

def generar_reporte_word(conteos, imagenes):
    """Genera reporte en formato Word con los resultados"""
    doc = Document()
    
    # Título principal
    title = doc.add_heading('Reporte de Urgencias Operativas', 0)
    title.alignment = 1  # Centrado
    
    # Fecha de generación
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
            hdr_cells[1].text = "Cantidad de Afectaciones"
        else:
            hdr_cells[0].text = "Tipo de Incidente"
            hdr_cells[1].text = "Cantidad"
        
        # Añadir filas con datos
        for tipo, cantidad in conteo.items():
            row_cells = tabla.add_row().cells
            row_cells[0].text = str(tipo).title()
            row_cells[1].text = str(cantidad)
    
    doc.add_page_break()
    doc.add_heading('Gráficas', level=1)
    
    for titulo, path in imagenes.items():
        if os.path.exists(path):
            doc.add_heading(titulo, level=2)
            doc.add_picture(path, width=Inches(6.0))
            doc.add_paragraph()  # Espacio entre gráficas
    
    output_path = os.path.join(tempfile.gettempdir(), 'reporte_urgencias_operativas.docx')
    doc.save(output_path)
    return output_path

def generar_reporte_txt(conteos):
    """Genera reporte en formato de texto simple"""
    texto = []
    texto.append("REPORTE DE URGENCIAS URBANAS")
    texto.append("=" * 50)
    texto.append(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    texto.append("")
    
    for nombre, conteo in conteos.items():
        texto.append(f"\n{nombre.upper()}")
        texto.append("-" * len(nombre))
        for tipo, cantidad in conteo.items():
            texto.append(f"  {tipo.title()}: {cantidad}")
    
    contenido = "\n".join(texto)
    path_txt = os.path.join(tempfile.gettempdir(), "reporte_urgencias_operativas.txt")
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(contenido)
    return path_txt

def get_download_link(file_path, file_label):
    """Genera un enlace de descarga para el archivo"""
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    file_name = os.path.basename(file_path)
    href = f'<a href="data:file/octet-stream;base64,{b64}" download="{file_name}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px; margin: 5px;">📥 {file_label}</a>'
    return href

# --- INTERFAZ PRINCIPAL ---

def main():
    st.title("📊 Analizador de Urgencias Operativas")
    st.markdown("---")
    
    # Carga de archivo
    st.header("1. Carga de Datos")
    uploaded_file = st.file_uploader("Sube tu archivo de datos (CSV o Excel)", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        try:
            # Leer archivo
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Archivo cargado correctamente. Dimensiones: {df.shape[0]} filas × {df.shape[1]} columnas")
            
            # Mostrar vista previa
            with st.expander("📋 Vista previa de los datos (primeras 10 filas)"):
                st.dataframe(df.head(10))
                st.write(f"**Total de columnas:** {len(df.columns)}")
                st.write(f"**Total de registros:** {len(df)}")
            
            # Selección de columnas
            st.header("2. Configuración del Análisis")
            col1, col2 = st.columns(2)
            
            with col1:
                col_incidentes = st.selectbox(
                    "Selecciona la columna de INCIDENTES:",
                    options=df.columns,
                    index=None,
                    help="Columna que contiene los tipos de incidentes"
                )
            
            with col2:
                col_colonias = st.selectbox(
                    "Selecciona la columna de COLONIAS:",
                    options=df.columns,
                    index=None,
                    help="Columna que contiene los nombres de las colonias"
                )
            
            # --- NUEVA SECCIÓN: ANÁLISIS DE LLUVIAS ---
            st.subheader("🌧️ Análisis de Reportes por Lluvias")
            analizar_lluvias_check = st.checkbox("Incluir análisis específico de reportes por lluvias")
            
            # Filtro por fechas
            st.subheader("🗓️ Filtro por Fechas (Opcional)")
            usar_fechas = st.checkbox("Activar filtro por fechas")
            
            fecha_inicio = None
            fecha_fin = None
            
            if usar_fechas and col_incidentes and col_colonias:
                col_fechas = st.selectbox(
                    "Selecciona la columna de FECHAS:",
                    options=df.columns,
                    index=None
                )
                
                if col_fechas:
                    col3, col4 = st.columns(2)
                    with col3:
                        fecha_inicio_str = st.text_input("Fecha de inicio (d/m/AAAA):", placeholder="01/01/2024")
                    with col4:
                        fecha_fin_str = st.text_input("Fecha de fin (d/m/AAAA):", placeholder="31/12/2024")
                    
                    if fecha_inicio_str and fecha_fin_str:
                        try:
                            fecha_inicio = datetime.strptime(fecha_inicio_str.strip(), '%d/%m/%Y')
                            fecha_fin = datetime.strptime(fecha_fin_str.strip(), '%d/%m/%Y')
                            
                            if fecha_inicio > fecha_fin:
                                st.error("❌ La fecha de inicio no puede ser mayor que la fecha de fin")
                            else:
                                st.info(f"📅 Rango seleccionado: {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}")
                                
                        except ValueError:
                            st.error("❌ Formato de fecha incorrecto. Use el formato d/m/AAAA (ej: 01/01/2024)")
            
            # Botón para generar análisis
            if col_incidentes and col_colonias:
                st.markdown("---")
                if st.button("🚀 Generar Reporte Completo", type="primary", use_container_width=True):
                    
                    with st.spinner("Procesando datos..."):
                        # Crear copia para no modificar el original
                        df_clean = df.copy()
                        
                        # Aplicar limpieza de texto
                        df_clean[col_incidentes] = df_clean[col_incidentes].apply(limpiar_texto)
                        df_clean[col_colonias] = df_clean[col_colonias].apply(limpiar_texto)
                        
                        # Aplicar filtro de fechas si está activado
                        if usar_fechas and fecha_inicio and fecha_fin and col_fechas:
                            df_clean['fecha_parseada'] = df_clean[col_fechas].apply(parsear_fecha)
                            df_filtrado = df_clean.dropna(subset=['fecha_parseada'])
                            df_filtrado = df_filtrado[
                                (df_filtrado['fecha_parseada'] >= fecha_inicio) & 
                                (df_filtrado['fecha_parseada'] <= fecha_fin)
                            ]
                            st.info(f"📊 Datos filtrados: {len(df_filtrado)} registros de {len(df_clean)} originales")
                            df_clean = df_filtrado
                        
                        # Verificar que hay datos después del filtrado
                        if df_clean.empty:
                            st.error("❌ No hay datos después del filtrado. Ajusta los criterios de filtro.")
                            return
                        
                        # Generar conteos
                        conteos = {}
                        conteos["Conteo General de Incidentes"] = df_clean[col_incidentes].value_counts()
                        
                        if col_colonias in df_clean.columns:
                            top_10_colonias = df_clean[col_colonias].value_counts().head(10)
                            conteos["Top 10 Colonias con Más Afectaciones"] = top_10_colonias
                        
                        # --- NUEVO: ANÁLISIS DE LLUVIAS ---
                        if analizar_lluvias_check:
                            with st.spinner("Analizando reportes por lluvias..."):
                                resultado_lluvias = analizar_lluvias(df_clean, col_incidentes, col_colonias)
                                
                                if resultado_lluvias is not None:
                                    # Agregar conteos de lluvias a los resultados principales
                                    conteos["Incidentes Relacionados con Lluvias"] = resultado_lluvias['conteo_incidentes_lluvias']
                                    conteos["Colonias más Afectadas por Lluvias"] = resultado_lluvias['conteo_colonias_lluvias'].head(10)
                        
                        # Mostrar resultados en la interfaz
                        st.header("3. 📈 Resultados del Análisis")
                        
                        # Métricas rápidas
                        col_met1, col_met2, col_met3 = st.columns(3)
                        with col_met1:
                            total_incidentes = len(df_clean)
                            st.metric("Total de Incidentes", total_incidentes)
                        with col_met2:
                            tipos_incidentes = len(conteos["Conteo General de Incidentes"])
                            st.metric("Tipos de Incidentes", tipos_incidentes)
                        with col_met3:
                            total_colonias = df_clean[col_colonias].nunique()
                            st.metric("Colonias Afectadas", total_colonias)
                        
                        # Mostrar métricas de lluvias si se analizaron
                        if analizar_lluvias_check and resultado_lluvias is not None:
                            col_met4, col_met5, col_met6 = st.columns(3)
                            with col_met4:
                                st.metric("Reportes por Lluvias", resultado_lluvias['estadisticas']['total_lluvias'])
                            with col_met5:
                                st.metric("% por Lluvias", f"{resultado_lluvias['estadisticas']['porcentaje_lluvias']:.1f}%")
                            with col_met6:
                                st.metric("Columna detectada", resultado_lluvias['columna_lluvias'])
                        
                        # Mostrar tablas y gráficas
                        for nombre, conteo in conteos.items():
                            st.subheader(nombre)
                            
                            # Mostrar tabla
                            df_display = conteo.reset_index()
                            if "Colonias" in nombre:
                                df_display.columns = ['Colonia', 'Cantidad de Afectaciones']
                            else:
                                df_display.columns = ['Tipo de Incidente', 'Cantidad']
                            
                            st.dataframe(df_display, use_container_width=True)
                            
                            # Mostrar gráfica interactiva
                            fig = generar_grafica_plotly(conteo, nombre)
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # --- NUEVO: GRÁFICO ESPECIALIZADO DE LLUVIAS ---
                        if analizar_lluvias_check and resultado_lluvias is not None:
                            st.subheader("🌧️ Análisis Detallado de Reportes por Lluvias")
                            
                            # Gráfico especializado de colonias afectadas por lluvias
                            fig_lluvias = crear_grafico_lluvias(
                                resultado_lluvias['conteo_colonias_lluvias'],
                                "Top 10 Colonias más Afectadas por Lluvias"
                            )
                            st.plotly_chart(fig_lluvias, use_container_width=True)
                            
                            # Mostrar tabla detallada de incidentes por lluvias
                            st.subheader("📋 Tipos de Incidentes durante Lluvias")
                            df_incidentes_lluvias = resultado_lluvias['conteo_incidentes_lluvias'].reset_index()
                            df_incidentes_lluvias.columns = ['Tipo de Incidente', 'Cantidad durante Lluvias']
                            st.dataframe(df_incidentes_lluvias, use_container_width=True)
                        
                        # Generar gráficas para el reporte Word
                        st.header("4. 📄 Generando Reportes Descargables")
                        with st.spinner("Generando gráficas para el reporte..."):
                            imagenes = {}
                            for k, v in conteos.items():
                                safe_filename = f"grafica_{k.replace(' ', '_').replace('/', '_').lower()}.png"
                                imagenes[k] = generar_grafica_bar(v, k, safe_filename)
                        
                        # Generar y ofrecer descarga de reportes
                        st.success("✅ Reportes generados correctamente")
                        
                        col_dl1, col_dl2 = st.columns(2)
                        
                        with col_dl1:
                            with st.spinner("Generando reporte Word..."):
                                doc_path = generar_reporte_word(conteos, imagenes)
                                st.markdown(get_download_link(doc_path, "Descargar Reporte Word (.docx)"), unsafe_allow_html=True)
                        
                        with col_dl2:
                            with st.spinner("Generando reporte de texto..."):
                                txt_path = generar_reporte_txt(conteos)
                                st.markdown(get_download_link(txt_path, "Descargar Reporte Texto (.txt)"), unsafe_allow_html=True)
                        
                        # Limpiar archivos temporales
                        for path in imagenes.values():
                            try:
                                if os.path.exists(path):
                                    os.remove(path)
                            except:
                                pass
            
            else:
                st.warning("⚠️ Por favor, selecciona ambas columnas (INCIDENTES y COLONIAS) para continuar.")
                
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {str(e)}")
            st.info("💡 **Sugerencias:** Verifica que el archivo no esté dañado y que tenga el formato correcto.")
    
    else:
        st.info("👆 Por favor, sube un archivo CSV o Excel para comenzar el análisis.")
        st.markdown("""
        ### 📝 Instrucciones:
        1. **Sube tu archivo** de datos (CSV o Excel)
        2. **Selecciona las columnas** correspondientes a incidentes y colonias
        3. **Configura los filtros** si es necesario
        4. **Genera el reporte** y descarga los resultados
        
        ### 🌧️ Nueva funcionalidad:
        - **Análisis de reportes por lluvias**: Activa la opción para ver análisis específico de incidentes relacionados con lluvias
        - **Detección automática**: El sistema detectará automáticamente si tu dataset contiene información sobre lluvias
        - **Métricas específicas**: Porcentaje de reportes por lluvias y colonias más afectadas
        """)

if __name__ == "__main__":
    main()
