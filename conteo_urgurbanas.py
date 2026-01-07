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
    if conteo is None or conteo.empty: return None
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

def generar_grafica_linea_simple(datos, titulo, xlabel, ylabel, filename):
    """Genera gráfica de UNA sola línea para Word"""
    if datos.empty: return None
    
    df_plot = datos.reset_index()
    df_plot.columns = ['Fecha', 'Cantidad']
    df_plot['Fecha'] = df_plot['Fecha'].astype(str)
    
    plt.figure(figsize=(10, 6))
    plt.plot(df_plot['Fecha'], df_plot['Cantidad'], marker='o', linestyle='-', color='blue', linewidth=2)
    
    plt.title(titulo, fontsize=12, fontweight='bold')
    plt.xlabel(xlabel, fontweight='bold')
    plt.ylabel(ylabel, fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_linea_multiple(df_long, col_x, col_y, col_grupo, titulo, filename):
    """Genera gráfica de LÍNEAS COMPARATIVAS (Top 10) para Word"""
    if df_long.empty: return None
    
    plt.figure(figsize=(12, 7))
    grupos = df_long[col_grupo].unique()
    cmap = plt.get_cmap('tab10')
    
    for i, grupo in enumerate(grupos):
        subset = df_long[df_long[col_grupo] == grupo].sort_values(by=col_x)
        x_vals = subset[col_x].astype(str)
        y_vals = subset[col_y]
        color = cmap(i % 10)
        plt.plot(x_vals, y_vals, marker='o', linestyle='-', linewidth=2, label=grupo, color=color)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel("Mes", fontweight='bold')
    plt.ylabel("Cantidad", fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small', title="Categorías")
    plt.tight_layout()
    
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_plotly_bar(conteo, titulo):
    if conteo is None or conteo.empty: return px.bar(title="Sin datos")
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    fig = px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo, color='Cantidad')
    return fig

def generar_grafica_plotly_linea(df_long, col_x, col_y, col_color, titulo):
    if df_long.empty: return px.line(title="Sin datos")
    df_plot = df_long.copy()
    df_plot[col_x] = df_plot[col_x].astype(str)
    if col_color:
        fig = px.line(df_plot, x=col_x, y=col_y, color=col_color, title=titulo, markers=True)
    else:
        fig = px.line(df_plot, x=col_x, y=col_y, title=titulo, markers=True)
    return fig

# --- FUNCIONES AUXILIARES ---
def analizar_lluvias_manual(df, col_lluvias, col_colonias, col_inc):
    if df.empty: return None
    df_l = df.copy()
    
    # Filtrar solo lluvias
    df_l[col_lluvias] = df_l[col_lluvias].astype(str).str.lower().str.strip()
    positivos = ['sí', 'si', 'yes', 'true', '1', 'afirmativo', 'lluvia']
    df_l = df_l[df_l[col_lluvias].isin(positivos)]
    
    if df_l.empty: return None
    
    return {
        'df_filtrado': df_l, # Regresamos el DF filtrado para hacer gráficas de tiempo
        'conteo_colonias': df_l[col_colonias].value_counts(),
        'conteo_incidentes': df_l[col_inc].value_counts(),
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
    
    col_fecha = st.selectbox("Columna FECHAS (Necesaria para gráficas de línea):", ["No usar"]+list(df.columns))
    if col_fecha == "No usar": col_fecha = None
    
    # Lluvias
    st.subheader("🌧️ Análisis de Lluvias")
    check_lluvias = st.checkbox("Analizar Reportes de Lluvias")
    col_lluvias = None
    if check_lluvias:
        col_lluvias = st.selectbox("Columna Indicador Lluvia (Sí/No, 1/0):", df.columns)

    # Filtros extra
    st.markdown("---")
    st.subheader("🛠️ Filtros y Gráficas Avanzadas")
    ignorar_medica = st.checkbox("Ignorar 'Atención Médica'", value=True)
    
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
            
            # Conteos Generales
            conteos = {
                "General": df_c[col_inc].value_counts(),
                "Colonias": df_c[col_col].value_counts()
            }
            imgs = {}

            # ANÁLISIS DE LLUVIAS
            res_lluv = None
            if check_lluvias and col_lluvias:
                res_lluv = analizar_lluvias_manual(df_c, col_lluvias, col_col, col_inc)
                if res_lluv:
                    # Agregar a tablas del reporte
                    conteos["Tipos de Incidentes en Lluvias"] = res_lluv['conteo_incidentes']
                    conteos["Colonias Afectadas por Lluvias"] = res_lluv['conteo_colonias']

            # --- VISUALIZACIÓN ---
            st.header("3. Resultados")
            c1, c2, c3 = st.columns(3)
            c1.metric("Incidentes Totales", len(df_c))
            c2.metric("Tipos Únicos", df_c[col_inc].nunique())
            if res_lluv:
                c3.metric("Reportes Lluvia", res_lluv['estadisticas']['total_lluvias'])
            
            # 1. BARRAS GENERALES
            st.subheader("General")
            top_gen = conteos["General"].head(15)
            st.plotly_chart(generar_grafica_plotly_bar(top_gen, "Top Incidentes"), use_container_width=True)
            imgs["General"] = generar_grafica_bar(top_gen, "Top Incidentes", "g1.png")
            
            # 2. LÍNEAS DE TENDENCIA (GENERALES)
            if valid_fechas:
                if graf_linea_inc:
                    try:
                        top10_names = conteos["General"].head(10).index.tolist()
                        df_top = df_c[df_c[col_inc].isin(top10_names)].copy()
                        df_top['mes'] = df_top['fecha_p'].dt.to_period('M')
                        data_linea = df_top.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                        
                        if not data_linea.empty:
                            st.subheader("📈 Tendencia Incidentes (Top 10)")
                            st.plotly_chart(generar_grafica_plotly_linea(data_linea, 'mes', 'conteo', col_inc, "Evolución Incidentes"), use_container_width=True)
                            imgs["Tendencia Incidentes"] = generar_grafica_linea_multiple(data_linea, 'mes', 'conteo', col_inc, "Comparativa: Top 10 Incidentes", "l_inc.png")
                    except: pass
                
                if graf_linea_col:
                    try:
                        top10_cols = conteos["Colonias"].head(10).index.tolist()
                        df_top_c = df_c[df_c[col_col].isin(top10_cols)].copy()
                        df_top_c['mes'] = df_top_c['fecha_p'].dt.to_period('M')
                        data_linea_c = df_top_c.groupby(['mes', col_col]).size().reset_index(name='conteo')
                        
                        if not data_linea_c.empty:
                            st.subheader("📈 Tendencia Colonias (Top 10)")
                            st.plotly_chart(generar_grafica_plotly_linea(data_linea_c, 'mes', 'conteo', col_col, "Evolución Colonias"), use_container_width=True)
                            imgs["Tendencia Colonias"] = generar_grafica_linea_multiple(data_linea_c, 'mes', 'conteo', col_col, "Comparativa: Top 10 Colonias", "l_col.png")
                    except: pass

            # 3. GRÁFICAS DE LLUVIAS (NUEVO)
            if res_lluv:
                st.markdown("---")
                st.header("🌧️ Análisis Detallado de Lluvias")
                
                # A) Tipos de Reporte en Lluvias
                st.subheader("Tipos de Incidentes durante Lluvias")
                top_inc_lluv = res_lluv['conteo_incidentes'].head(15)
                st.plotly_chart(generar_grafica_plotly_bar(top_inc_lluv, "Tipos de Reporte (Lluvias)"), use_container_width=True)
                # Agregar a Word
                imgs["Tipos Lluvia"] = generar_grafica_bar(top_inc_lluv, "Tipos de Reporte en Lluvias", "g_inc_lluv.png")
                
                # B) Colonias en Lluvias
                st.subheader("Colonias Afectadas por Lluvias")
                top_col_lluv = res_lluv['conteo_colonias'].head(15)
                st.plotly_chart(generar_grafica_plotly_bar(top_col_lluv, "Colonias (Lluvias)"), use_container_width=True)
                imgs["Colonias Lluvia"] = generar_grafica_bar(top_col_lluv, "Colonias en Lluvias", "g_col_lluv.png")
                
                # C) Tendencia de Lluvias (Línea)
                if valid_fechas:
                    df_lluvia_t = res_lluv['df_filtrado'].copy()
                    df_lluvia_t['mes'] = df_lluvia_t['fecha_p'].dt.to_period('M')

                    # --- NUEVO: Gráfica comparativa de TIPOS de reporte EN LLUVIAS ---
                    try:
                        # Top 5 incidentes en lluvias
                        top5_inc_lluvia = res_lluv['conteo_incidentes'].head(5).index.tolist()
                        df_top_lluvia = df_lluvia_t[df_lluvia_t[col_inc].isin(top5_inc_lluvia)]
                        
                        if not df_top_lluvia.empty:
                            data_linea_lluvia = df_top_lluvia.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                            if not data_linea_lluvia.empty:
                                st.subheader("📈 Tendencia por Tipo de Incidente (Solo Lluvias)")
                                st.plotly_chart(generar_grafica_plotly_linea(data_linea_lluvia, 'mes', 'conteo', col_inc, "Evolución Tipos de Reporte (Lluvias)"), use_container_width=True)
                                
                                # Agregar a Word la gráfica MULTILÍNEA
                                imgs["Tendencia Tipos Lluvia"] = generar_grafica_linea_multiple(
                                    data_linea_lluvia, 'mes', 'conteo', col_inc, 
                                    "Evolución Tipos de Reporte (Lluvias)", "l_tipo_lluv.png"
                                )
                    except: pass
                    
                    # Gráfica de volumen TOTAL de lluvias (La que ya tenías)
                    try:
                        data_total_lluvia = df_lluvia_t.groupby('mes').size().reset_index(name='conteo')
                        if not data_total_lluvia.empty:
                            imgs["Tendencia Total Lluvias"] = generar_grafica_linea_simple(data_total_lluvia.set_index('mes')['conteo'], "Volumen Total de Reportes por Lluvia", "Mes", "Cantidad", "l_total_lluv.png")
                    except: pass

            # Descargas
            st.success("✅ Reporte Generado Exitosamente")
            c1, c2 = st.columns(2)
            c1.markdown(get_link(generar_reporte_word(conteos, imgs), "Word"), unsafe_allow_html=True)
            c2.markdown(get_link(generar_txt(conteos), "Txt"), unsafe_allow_html=True)
            
            for p in imgs.values(): 
                if p and os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    main()
