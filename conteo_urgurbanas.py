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
import plotly.io as pio
from io import BytesIO
import unicodedata
import base64
import subprocess
import sys

# Intentar instalar Chrome automáticamente
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "kaleido"], check=True)
    # En entornos que lo permitan, instalar Chrome
    try:
        subprocess.run(["plotly_get_chrome"], check=True, capture_output=True)
    except:
        st.info("Chrome no está disponible. Usando matplotlib como respaldo.")
except:
    pass


# --- FUNCIONES ORIGINALES (adaptadas para Streamlit) ---

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
    if pd.isna(fecha): return None
    if isinstance(fecha, (datetime, pd.Timestamp)): return fecha
    for fmt in ('%d/%m/%Y', '%d/%m/%y'):
        try: return datetime.strptime(str(fecha), fmt)
        except: continue
    return None

def generar_grafica_bar(conteo, titulo, filename):
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    fig = px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo,
                 color='Cantidad', color_continuous_scale='Viridis')
    path = os.path.join(tempfile.gettempdir(), filename)
    try:
        fig.write_image(path, engine='kaleido')
    except Exception as e:
        st.warning(f"Error con Kaleido: {str(e)}. Usando matplotlib...")
        plt.figure(figsize=(10, 6))
        df_plot.plot(kind='bar', x='Categoría', y='Cantidad', legend=False)
        plt.title(titulo)
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
    return path

def generar_reporte_word(conteos, imagenes):
    doc = Document()
    doc.add_heading('Reporte de Urgencias Operativas', 0)
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
        
        for tipo, cantidad in conteo.items():
            row_cells = tabla.add_row().cells
            row_cells[0].text = str(tipo)
            row_cells[1].text = str(cantidad)
    
    doc.add_heading('Gráficas', level=1)
    for titulo, path in imagenes.items():
        if os.path.exists(path):
            doc.add_heading(titulo, level=2)
            doc.add_picture(path, width=Inches(5.5))
        else:
            doc.add_paragraph(f"Gráfica no disponible: {titulo}", style='List Bullet')
    
    output_path = os.path.join(tempfile.gettempdir(), 'reporte_urgencias_operativas.docx')
    doc.save(output_path)
    return output_path

def generar_reporte_txt(conteos):
    texto = ["Reporte de Urgencias Urbanas\n", "="*30]
    for nombre, conteo in conteos.items():
        texto.append(f"\n\n--- {nombre.upper()} ---")
        for tipo, cantidad in conteo.items():
            texto.append(f"{tipo}: {cantidad}")
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
    href = f'<a href="data:file/octet-stream;base64,{b64}" download="{os.path.basename(file_path)}">Descargar {file_label}</a>'
    return href

# --- INTERFAZ DE STREAMLIT ---

def main():
    st.title("📊 Analizador de Urgencias Operativas")
    st.markdown("---")
    
    # Carga de archivo
    st.header("1. Carga de Datos")
    uploaded_file = st.file_uploader("Sube tu archivo de datos (CSV o Excel)", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Archivo cargado correctamente. Dimensiones: {df.shape[0]} filas × {df.shape[1]} columnas")
            
            # Mostrar vista previa
            with st.expander("Vista previa de los datos"):
                st.dataframe(df.head())
            
            # Selección de columnas
            st.header("2. Configuración del Análisis")
            col1, col2 = st.columns(2)
            
            with col1:
                col_incidentes = st.selectbox(
                    "Selecciona la columna de INCIDENTES:",
                    options=df.columns,
                    index=None
                )
            
            with col2:
                col_colonias = st.selectbox(
                    "Selecciona la columna de COLONIAS:",
                    options=df.columns,
                    index=None
                )
            
            # Filtro por fechas
            st.subheader("Filtro por Fechas (Opcional)")
            usar_fechas = st.checkbox("Filtrar por rango de fechas")
            
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
                            
                            df['fecha_parseada'] = df[col_fechas].apply(parsear_fecha)
                            df_filtrado = df.dropna(subset=['fecha_parseada'])
                            df_filtrado = df_filtrado[(df_filtrado['fecha_parseada'] >= fecha_inicio) & 
                                                     (df_filtrado['fecha_parseada'] <= fecha_fin)]
                            
                            st.info(f"📅 Datos filtrados: {len(df_filtrado)} registros entre {fecha_inicio.strftime('%d/%m/%Y')} y {fecha_fin.strftime('%d/%m/%Y')}")
                            df = df_filtrado
                            
                        except Exception as e:
                            st.warning(f"⚠️ Error al filtrar fechas: {str(e)}. Se usarán todos los datos.")
            
            # Botón para generar análisis
            if col_incidentes and col_colonias:
                if st.button("🚀 Generar Reporte Completo", type="primary"):
                    with st.spinner("Procesando datos..."):
                        # Aplicar limpieza de texto
                        df[col_incidentes] = df[col_incidentes].apply(limpiar_texto)
                        df[col_colonias] = df[col_colonias].apply(limpiar_texto)
                        
                        # Generar conteos
                        conteos = {}
                        conteos["Conteo General de Incidentes"] = df[col_incidentes].value_counts()
                        if col_colonias in df.columns:
                            top_10_colonias = df[col_colonias].value_counts().head(10)
                            conteos["Top 10 Colonias con Más Afectaciones"] = top_10_colonias
                        
                        # Mostrar resultados en la interfaz
                        st.header("3. Resultados del Análisis")
                        
                        for nombre, conteo in conteos.items():
                            st.subheader(nombre)
                            st.dataframe(conteo.reset_index().rename(
                                columns={'index': 'Categoría', col_incidentes: 'Cantidad'}
                            ))
                        
                        # Generar gráficas
                        st.subheader("Gráficas Generadas")
                        imagenes = {}
                        for k, v in conteos.items():
                            safe_filename = f"grafica_{k.replace(' ', '_').lower()}.png"
                            imagenes[k] = generar_grafica_bar(v, k, safe_filename)
                            
                            # Mostrar gráficas en Streamlit
                            st.plotly_chart(px.bar(
                                v.reset_index(), 
                                x='index', 
                                y=col_incidentes, 
                                title=k,
                                color=col_incidentes,
                                color_continuous_scale='Viridis'
                            ), use_container_width=True)
                        
                        # Generar y ofrecer descarga de reportes
                        st.header("4. Descargar Reportes")
                        
                        # Reporte Word
                        doc_path = generar_reporte_word(conteos, imagenes)
                        st.markdown(get_download_link(doc_path, "Reporte Word"), unsafe_allow_html=True)
                        
                        # Reporte TXT
                        txt_path = generar_reporte_txt(conteos)
                        st.markdown(get_download_link(txt_path, "Reporte Texto"), unsafe_allow_html=True)
                        
                        st.success("🎉 ¡Análisis completado! Puedes descargar los reportes arriba.")
            
            else:
                st.warning("⚠️ Por favor, selecciona ambas columnas (INCIDENTES y COLONIAS) para continuar.")
                
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {str(e)}")
    
    else:
        st.info("👆 Por favor, sube un archivo CSV o Excel para comenzar el análisis.")

if __name__ == "__main__":
    main()
