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
    """Normaliza texto: minúsculas, sin acentos, sin espacios extra."""
    if not isinstance(texto, str):
        return str(texto).lower().strip()

    texto_limpio = unicodedata.normalize('NFD', texto) \
                              .encode('ascii', 'ignore') \
                              .decode('utf-8') \
                              .lower() \
                              .strip()
    return texto_limpio

def parsear_fecha(fecha):
    if pd.isna(fecha): return None
    if isinstance(fecha, (datetime, pd.Timestamp)): return fecha
    
    fecha_str = str(fecha).strip()
    formatos = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%y', '%d-%m-%y', '%m/%d/%Y']
    
    for fmt in formatos:
        try: 
            return datetime.strptime(fecha_str.split(' ')[0], fmt)
        except: continue
            
    try: return pd.to_datetime(fecha, dayfirst=True).to_pydatetime()
    except: return None

def generar_grafica_bar(conteo, titulo, filename):
    """Gráfica de BARRAS para Word"""
    if conteo.empty: return None
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    
    plt.figure(figsize=(10, 6))
    colors = plt.cm.viridis(np.linspace(0, 1, len(df_plot)))
    bars = plt.bar(df_plot['Categoría'].astype(str), df_plot['Cantidad'], color=colors)
    
    plt.title(titulo, fontsize=12, fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    for bar in bars:
        plt.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_linea_multiple(df_long, col_x, col_y, col_grupo, titulo, filename):
    """Genera gráfica de LÍNEAS COMPARATIVAS (Top 10) para Word"""
    if df_long.empty: return None
    
    plt.figure(figsize=(12, 7)) # Más ancho para la leyenda
    
    # Obtener grupos únicos (Top 10)
    grupos = df_long[col_grupo].unique()
    
    # Colores distintos
    cmap = plt.get_cmap('tab10') # Paleta de 10 colores
    
    for i, grupo in enumerate(grupos):
        subset = df_long[df_long[col_grupo] == grupo].sort_values(by=col_x)
        # Convertir periodo a string para graficar
        x_vals = subset[col_x].astype(str)
        y_vals = subset[col_y]
        
        color = cmap(i % 10)
        plt.plot(x_vals, y_vals, marker='o', linestyle='-', linewidth=2, label=grupo, color=color)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel("Mes", fontweight='bold')
    plt.ylabel("Cantidad", fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.grid(True, alpha=0.3)
    
    # Leyenda fuera de la gráfica para no tapar datos
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small', title="Top 10")
    
    plt.tight_layout()
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_plotly_bar(conteo, titulo):
    if conteo.empty: return px.bar(title="Sin datos")
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    fig = px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo, color='Cantidad')
    return fig

def generar_grafica_plotly_linea(df_long, col_x, col_y, col_color, titulo):
    """Gráfica de líneas interactiva comparativa"""
    if df_long.empty: return px.line(title="Sin datos")
    # Convertir periodo a string
    df_plot = df_long.copy()
    df_plot[col_x] = df_plot[col_x].astype(str)
    
    fig = px.line(df_plot, x=col_x, y=col_y, color=col_color, title=titulo, markers=True)
    return fig

# --- FUNCIONES AUXILIARES ---
def analizar_lluvias_manual(df, col_lluvias, col_colonias, col_fecha=None, col_hora=None):
    if df.empty: return None
    df_l = df.copy()
    df_l[col_lluvias] = df_l[col_lluvias].astype(str).str.lower().str.strip()
    positivos = ['sí', 'si', 'yes', 'true', '1', 'afirmativo', 'lluvia']
    df_l = df_l[df_l[col_lluvias].isin(positivos)]
    if df_l.empty: return None
    
    return {
        'conteo_colonias': df_l[col_colonias].value_counts(),
        'conteo_incidentes': df_l[st.session_state.col_incidentes].value_counts() if 'col_incidentes' in st.session_state else None,
        'estadisticas': {'total_lluvias': len(df_l), 'porcentaje': (len(df_l)/len(df))*100}
    }

def generar_reporte_word(conteos, imagenes):
    doc = Document()
    doc.add_heading('Reporte de Urgencias Operativas', 0).alignment = 1
    doc.add_paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Tablas
    doc.add_heading('Resumen de Datos', 1)
    for nombre, conteo in conteos.items():
        if conteo is None or conteo.empty: continue
        doc.add_heading(nombre, 2)
        tabla = doc.add_table(rows=1, cols=2)
        tabla.style = 'Table Grid'
        tabla.rows[0].cells[0].text = "Categoría"
        tabla.rows[0].cells[1].text = "Cantidad"
        for k, v in list(conteo.items())[:15]:
            row = tabla.add_row().cells
            row[0].text = str(k).title()
            row[1].text = str(v)
            
    # Gráficas
    doc.add_page_break()
    doc.add_heading('Gráficas Visuales', 1)
    for titulo, path in imagenes.items():
        if path and os.path.exists(path):
            doc.add_heading(titulo, 2)
            try: doc.add_picture(path, width=Inches(6.0))
            except: doc.add_paragraph("[Error imagen]")
            doc.add_paragraph()
            
    out = os.path.join(tempfile.gettempdir(), 'reporte.docx')
    doc.save(out)
    return out

def generar_txt(conteos):
    txt = [f"REPORTE {datetime.now()}", "="*30]
    for k, v in conteos.items():
        if v is None: continue
        txt.append(f"\n{k.upper()}\n{'-'*len(k)}")
        for i, j in v.items(): txt.append(f"{i}: {j}")
    path = os.path.join(tempfile.gettempdir(), 'reporte.txt')
    with open(path, 'w', encoding='utf-8') as f: f.write("\n".join(txt))
    return path

def get_link(path, label):
    with open(path, "rb") as f: b64 = base64.b64encode(f.read()).decode()
    return f'<a href="data:file/octet;base64,{b64}" download="{os.path.basename(path)}">📥 {label}</a>'

# --- MAIN ---
def main():
    st.title("📊 Analizador de Urgencias Operativas")
    
    # 1. Carga
    st.header("1. Datos")
    f = st.file_uploader("Archivo (CSV/Excel)", type=['csv','xlsx'])
    if not f: 
        st.info("Sube un archivo.")
        return

    try:
        df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
        st.success(f"Cargado: {len(df)} registros.")
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    # 2. Configuración
    st.header("2. Configuración")
    c1, c2 = st.columns(2)
    col_inc = c1.selectbox("Columna INCIDENTES:", df.columns)
    col_col = c2.selectbox("Columna COLONIAS:", df.columns)
    if col_inc: st.session_state.col_incidentes = col_inc
    
    col_fecha = st.selectbox("Columna FECHAS (Necesaria para gráficas de línea):", ["No usar"]+list(df.columns))
    if col_fecha == "No usar": col_fecha = None
    
    # Lluvias
    check_lluvias = st.checkbox("Analizar Lluvias")
    col_lluvias = st.selectbox("Columna Lluvia:", df.columns) if check_lluvias else None

    # Filtros extra
    st.markdown("---")
    st.subheader("🛠️ Filtros y Gráficas")
    ignorar_medica = st.checkbox("Ignorar 'Atención Médica'", value=True)
    
    # Checkboxes Gráficas Avanzadas
    graf_top10 = st.checkbox("Gráfica Top 10 Incidentes (Barras)", value=True)
    graf_linea_inc = st.checkbox("Comparativa Línea de Tiempo: Top 10 Incidentes", value=False)
    graf_linea_col = st.checkbox("Comparativa Línea de Tiempo: Top 10 Colonias", value=False)
    
    if graf_linea_inc or graf_linea_col:
        if not col_fecha: st.warning("⚠️ Necesitas seleccionar una Columna de FECHAS arriba.")

    # 3. Procesar
    if st.button("🚀 Generar Reporte", type="primary"):
        with st.spinner("Procesando..."):
            df_c = df.copy()
            # Limpieza
            df_c[col_inc] = df_c[col_inc].apply(limpiar_texto)
            df_c[col_col] = df_c[col_col].apply(limpiar_texto)
            
            if ignorar_medica:
                df_c = df_c[df_c[col_inc] != "atencion medica"]
            
            if df_c.empty:
                st.error("Sin datos tras filtros.")
                return

            # Fechas
            valid_fechas = False
            if col_fecha:
                df_c['fecha_p'] = df_c[col_fecha].apply(parsear_fecha)
                if df_c['fecha_p'].notna().sum() > 0:
                    valid_fechas = True
                else:
                    st.error("No se pudieron leer las fechas.")
            
            # Conteos
            conteos = {
                "General": df_c[col_inc].value_counts(),
                "Colonias": df_c[col_col].value_counts()
            }
            
            # Lluvias
            res_lluv = analizar_lluvias_manual(df_c, col_lluvias, col_col) if (check_lluvias and col_lluvias) else None
            if res_lluv:
                conteos["Lluvias (Colonia)"] = res_lluv['conteo_colonias']

            # --- RESULTADOS ---
            st.header("3. Resultados")
            c1, c2 = st.columns(2)
            c1.metric("Incidentes", len(df_c))
            c2.metric("Tipos", df_c[col_inc].nunique())

            imgs = {}
            
            # A) Barras General
            st.subheader("Top Incidentes")
            top_gen = conteos["General"].head(15)
            st.plotly_chart(generar_grafica_plotly_bar(top_gen, "Top Incidentes"), use_container_width=True)
            imgs["General"] = generar_grafica_bar(top_gen, "Top Incidentes", "g1.png")
            
            # B) Línea Comparativa Incidentes (Top 10)
            if graf_linea_inc and valid_fechas:
                st.subheader("📈 Tendencia Top 10 Incidentes")
                try:
                    # 1. Identificar Top 10
                    top10_nombres = conteos["General"].head(10).index.tolist()
                    # 2. Filtrar DF original
                    df_top = df_c[df_c[col_inc].isin(top10_nombres)].copy()
                    df_top['mes'] = df_top['fecha_p'].dt.to_period('M')
                    # 3. Agrupar
                    data_linea = df_top.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                    
                    if not data_linea.empty:
                        # Streamlit
                        st.plotly_chart(generar_grafica_plotly_linea(data_linea, 'mes', 'conteo', col_inc, "Evolución Top 10 Incidentes"), use_container_width=True)
                        # Word
                        imgs["Tendencia Incidentes"] = generar_grafica_linea_multiple(
                            data_linea, 'mes', 'conteo', col_inc, "Comparativa Mensual: Top 10 Incidentes", "linea_inc.png"
                        )
                except Exception as e:
                    st.error(f"Error en gráfica línea incidentes: {e}")

            # C) Línea Comparativa Colonias (Top 10)
            if graf_linea_col and valid_fechas:
                st.subheader("📈 Tendencia Top 10 Colonias")
                try:
                    top10_cols = conteos["Colonias"].head(10).index.tolist()
                    df_top_c = df_c[df_c[col_col].isin(top10_cols)].copy()
                    df_top_c['mes'] = df_top_c['fecha_p'].dt.to_period('M')
                    
                    data_linea_c = df_top_c.groupby(['mes', col_col]).size().reset_index(name='conteo')
                    
                    if not data_linea_c.empty:
                        st.plotly_chart(generar_grafica_plotly_linea(data_linea_c, 'mes', 'conteo', col_col, "Evolución Top 10 Colonias"), use_container_width=True)
                        imgs["Tendencia Colonias"] = generar_grafica_linea_multiple(
                            data_linea_c, 'mes', 'conteo', col_col, "Comparativa Mensual: Top 10 Colonias", "linea_col.png"
                        )
                except Exception as e:
                    st.error(f"Error en gráfica línea colonias: {e}")

            # Lluvias
            if res_lluv:
                st.subheader("Lluvias")
                top_lluv = res_lluv['conteo_colonias'].head(10)
                st.plotly_chart(generar_grafica_plotly_bar(top_lluv, "Lluvias por Colonia"), use_container_width=True)
                imgs["Lluvias"] = generar_grafica_bar(top_lluv, "Lluvias", "g_lluv.png")

            # Descargas
            st.success("✅ Hecho")
            c1, c2 = st.columns(2)
            c1.markdown(get_link(generar_reporte_word(conteos, imgs), "Word"), unsafe_allow_html=True)
            c2.markdown(get_link(generar_txt(conteos), "Txt"), unsafe_allow_html=True)
            
            for p in imgs.values(): 
                if p and os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    main()
