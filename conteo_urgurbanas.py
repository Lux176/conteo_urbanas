import streamlit as st
# --- CORRECCIÓN CRÍTICA PARA QUE NO SE CONGELE ---
import matplotlib
matplotlib.use('Agg') # Fuerza modo sin interfaz gráfica (Backend Agg)
import matplotlib.pyplot as plt
# -------------------------------------------------
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Inches
import matplotlib.ticker as mtick
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import os
from datetime import datetime
from io import BytesIO
import unicodedata
import base64
import re
import traceback

# Configuración de la página
st.set_page_config(
    page_title="Analizador de Urgencias Operativas",
    page_icon="📊",
    layout="wide"
)

# --- FUNCIONES DE UTILIDAD ---

def formatear_periodo_es(periodo):
    if pd.isna(periodo): return ""
    meses = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
             7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    return f"{meses.get(periodo.month, '')} {periodo.year}"

def limpiar_texto(texto):
    if not isinstance(texto, str): return str(texto).lower().strip()
    return unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8').lower().strip()

def normalizar_genero(texto):
    t = limpiar_texto(texto)
    if not t: return None
    if t in ['hombre', 'masculino', 'm', 'varon']: return 'Masculino'
    if t in ['mujer', 'femenino', 'f', 'dama']: return 'Femenino'
    return None

def limpiar_y_categorizar_edad(valor):
    if pd.isna(valor): return None
    s = str(valor)
    numeros = re.findall(r'\d+', s)
    if not numeros: return None
    try: edad = int(numeros[0])
    except: return None
    if edad < 18: return "Menor (0-17)"
    if 18 <= edad <= 29: return "Joven (18-29)"
    if 30 <= edad <= 59: return "Adulto (30-59)"
    if edad >= 60: return "Mayor (60+)"
    return None

def parsear_fecha(fecha):
    if pd.isna(fecha): return None
    if isinstance(fecha, (datetime, pd.Timestamp)): return fecha
    fecha_str = str(fecha).strip()
    formatos = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d']
    for fmt in formatos:
        try: return datetime.strptime(fecha_str.split(' ')[0], fmt)
        except: continue
    try: return pd.to_datetime(fecha, dayfirst=True).to_pydatetime()
    except: return None

# --- FUNCIONES DE GRÁFICAS ESTÁTICAS (WORD) ---
# Nota: Usamos plt.close('all') para liberar memoria explícitamente

def generar_grafica_bar(conteo, titulo, filename):
    if conteo is None or conteo.empty: return None
    try:
        df_plot = conteo.reset_index()
        df_plot.columns = ['Categoría', 'Cantidad']
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.viridis(np.linspace(0, 1, len(df_plot)))
        bars = ax.bar(df_plot['Categoría'].astype(str), df_plot['Cantidad'], color=colors)
        ax.set_title(titulo, fontsize=12, fontweight='bold')
        plt.xticks(rotation=45, ha='right', fontsize=8)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                    f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=8)
        plt.tight_layout()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight') # DPI reducido para velocidad
        plt.close(fig)
        return path
    except Exception as e:
        st.warning(f"Error generando gráfica {titulo}: {e}")
        return None

def generar_grafica_linea_multiple(df_long, col_x, col_y, col_grupo, titulo, filename):
    if df_long.empty: return None
    try:
        fig, ax = plt.subplots(figsize=(12, 7))
        grupos = df_long[col_grupo].unique()
        cmap = plt.get_cmap('tab10')
        for i, grupo in enumerate(grupos):
            subset = df_long[df_long[col_grupo] == grupo].sort_values(by=col_x)
            x_vals = [formatear_periodo_es(p) for p in subset[col_x]]
            y_vals = subset[col_y]
            color = cmap(i % 10)
            ax.plot(x_vals, y_vals, marker='o', linestyle='-', linewidth=2, label=grupo, color=color)
        ax.set_title(titulo, fontsize=14, fontweight='bold')
        ax.set_xlabel("Mes", fontweight='bold')
        ax.set_ylabel(col_y.title(), fontweight='bold')
        plt.xticks(rotation=45, ha='right', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small')
        plt.tight_layout()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
    except: return None

def generar_grafica_linea_porcentaje_genero(df_long, col_periodo, col_pct, col_genero, titulo, filename):
    if df_long.empty: return None
    try:
        fig, ax = plt.subplots(figsize=(12, 7))
        color_map = {'Masculino': 'blue', 'Femenino': 'purple'}
        for genero in ['Masculino', 'Femenino']:
            subset = df_long[df_long[col_genero] == genero].sort_values(by=col_periodo)
            if subset.empty: continue
            x_vals = [formatear_periodo_es(p) for p in subset[col_periodo]]
            y_vals = subset[col_pct].values
            color = color_map.get(genero, 'grey')
            ax.plot(x_vals, y_vals, marker='o', linestyle='-', linewidth=3, label=genero, color=color)
            for x, y in zip(x_vals, y_vals):
                ax.annotate(f'{y:.0f}%', xy=(x, y), xytext=(0, 8), textcoords='offset points',
                            ha='center', va='bottom', fontsize=9, fontweight='bold', color=color)
        ax.set_title(titulo, fontsize=14, fontweight='bold')
        ax.set_ylim(0, 115)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        plt.xticks(rotation=45, ha='right', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend(loc='best', fontsize='medium')
        plt.tight_layout()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
    except: return None

def generar_grafica_circulos_edad_word(df_data, titulo, filename):
    if df_data.empty: return None
    try:
        fig, ax = plt.subplots(figsize=(12, 8))
        colonias = df_data['Colonia'].unique()
        rangos = ["Menor (0-17)", "Joven (18-29)", "Adulto (30-59)", "Mayor (60+)"]
        ax.set_xlim(-0.5, len(colonias) - 0.5)
        ax.set_ylim(-0.5, len(rangos) - 0.5)
        col_map = {c: i for i, c in enumerate(colonias)}
        rango_map = {r: i for i, r in enumerate(rangos)}
        for _, row in df_data.iterrows():
            c_idx = col_map.get(row['Colonia'])
            r_idx = rango_map.get(row['Rango'])
            if c_idx is not None and r_idx is not None:
                pct = row['Porcentaje']
                marker_size = pct * 30 
                ax.scatter(c_idx, r_idx, s=marker_size, c='black', alpha=0.9, zorder=3)
                ax.text(c_idx, r_idx, f"{pct:.0f}%", ha='center', va='center', 
                        fontsize=9, fontweight='bold', color='white', zorder=4)
        ax.set_xticks(range(len(colonias)))
        ax.set_xticklabels(colonias, rotation=45, ha='right')
        ax.set_yticks(range(len(rangos)))
        ax.set_yticklabels(rangos)
        ax.set_title(titulo, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.2, linestyle='--', zorder=0)
        plt.tight_layout()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
    except: return None

def generar_mapa_estatico_word(gdf_merged, titulo, filename):
    if gdf_merged.empty: return None
    try:
        fig, ax = plt.subplots(figsize=(10, 10))
        gdf_merged.plot(ax=ax, color='#f0f0f0', edgecolor='grey', linewidth=0.5)
        gdf_merged.plot(column='cantidad', ax=ax, cmap='Reds', legend=True,
                        legend_kwds={'label': "Cantidad", 'orientation': "horizontal"},
                        edgecolor='black', linewidth=0.2, alpha=0.9)
        ax.set_title(titulo, fontsize=14, fontweight='bold')
        ax.set_axis_off()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
    except: return None

def generar_grafica_linea_simple(datos, titulo, xlabel, ylabel, filename):
    if datos.empty: return None
    try:
        df_plot = datos.reset_index()
        df_plot.columns = ['Periodo', 'Cantidad']
        df_plot = df_plot.sort_values('Periodo')
        etiquetas_x = [formatear_periodo_es(p) for p in df_plot['Periodo']]
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(etiquetas_x, df_plot['Cantidad'], marker='o', linestyle='-', color='teal', linewidth=2)
        ax.set_title(titulo, fontsize=12, fontweight='bold')
        ax.set_xlabel(xlabel, fontweight='bold')
        ax.set_ylabel(ylabel, fontweight='bold')
        plt.xticks(rotation=45, ha='right', fontsize=8)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        path = os.path.join(tempfile.gettempdir(), filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return path
    except: return None

# --- FUNCIONES PLOTLY ---
def generar_grafica_plotly_bar(conteo, titulo):
    if conteo is None or conteo.empty: return px.bar(title="Sin datos")
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    return px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo, color='Cantidad')

def generar_grafica_plotly_linea(df_long, col_periodo, col_y, col_color, titulo, es_porcentaje=False):
    if df_long.empty: return px.line(title="Sin datos")
    df_plot = df_long.copy()
    df_plot = df_plot.sort_values(col_periodo)
    df_plot['Mes_Texto'] = df_plot[col_periodo].apply(formatear_periodo_es)
    if es_porcentaje: df_plot['Etiqueta'] = df_plot[col_y].apply(lambda x: f"{x:.1f}%")
    else: df_plot['Etiqueta'] = df_plot[col_y].astype(str)
    color_map = {'Masculino': 'blue', 'Femenino': 'purple'} if (es_porcentaje and col_color) else None
    
    if col_color:
        fig = px.line(df_plot, x='Mes_Texto', y=col_y, color=col_color, title=titulo, markers=True,
                      text='Etiqueta', color_discrete_map=color_map)
    else:
        fig = px.line(df_plot, x='Mes_Texto', y=col_y, title=titulo, markers=True, text='Etiqueta')
    
    fig.update_traces(textposition="top center")
    if es_porcentaje:
        fig.update_yaxes(range=[0, 115], title="Porcentaje (%)")
    fig.update_xaxes(type='category', title="Mes")
    return fig

def generar_grafica_plotly_circulos_edad(df_data, titulo):
    if df_data.empty: return px.scatter(title="Sin datos")
    df_data['Texto_Pct'] = df_data['Porcentaje'].apply(lambda x: f"{x:.0f}%")
    fig = px.scatter(df_data, x="Colonia", y="Rango", size="Porcentaje", text="Texto_Pct",
                     title=titulo, color_discrete_sequence=['black'], opacity=0.9)
    fig.update_traces(mode='markers+text', textposition='middle center', 
                      textfont=dict(color='white', weight='bold'), marker=dict(line=dict(width=0)))
    fig.update_yaxes(categoryorder='array', categoryarray=["Menor (0-17)", "Joven (18-29)", "Adulto (30-59)", "Mayor (60+)"], title="Rango")
    fig.update_layout(height=600, plot_bgcolor='white', xaxis_tickangle=-45, yaxis_gridcolor='lightgrey')
    return fig

# --- ANÁLISIS ---
def analizar_lluvias_manual(df, col_lluvias, col_colonias, col_inc):
    if df.empty: return None
    df_l = df.copy()
    df_l[col_lluvias] = df_l[col_lluvias].astype(str).str.lower().str.strip()
    positivos = ['sí', 'si', 'yes', 'true', '1', 'afirmativo', 'lluvia']
    df_l = df_l[df_l[col_lluvias].isin(positivos)]
    if df_l.empty: return None
    return {
        'df_filtrado': df_l,
        'conteo_colonias': df_l[col_colonias].value_counts(),
        'conteo_incidentes': df_l[col_inc].value_counts(),
        'estadisticas': {'total_lluvias': len(df_l), 'porcentaje': (len(df_l)/len(df))*100}
    }

def generar_reporte_word(conteos, imagenes):
    doc = Document()
    doc.add_heading('Reporte de Urgencias Operativas', 0).alignment = 1
    doc.add_paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    for nombre, conteo in conteos.items():
        if conteo is None or conteo.empty: continue
        doc.add_heading(nombre, 2)
        tabla = doc.add_table(rows=1, cols=2)
        tabla.style = 'Table Grid'
        tabla.rows[0].cells[0].text = "Categoría"
        tabla.rows[0].cells[1].text = "Cantidad"
        for k, v in list(conteo.items())[:20]:
            row = tabla.add_row().cells
            row[0].text = str(k).title()
            row[1].text = str(v)
            
    doc.add_page_break()
    doc.add_heading('Gráficas Visuales', 1)
    
    orden = ['General', 'Mapa de Calor (Colonias)', 'Rango de Edad Dominante por Colonia', 
             'Tendencia Porcentaje Género', 'Tendencia Incidentes', 'Tendencia Colonias', 
             'Tipos Lluvia', 'Colonias Lluvia', 'Tendencia Tipos Lluvia', 'Tendencia Total Lluvias']
    
    for titulo in orden:
        if titulo in imagenes and os.path.exists(imagenes[titulo]):
             doc.add_heading(titulo, 2)
             try: doc.add_picture(imagenes[titulo], width=Inches(6.0))
             except: pass
             doc.add_paragraph()
    
    # Resto de imágenes
    for titulo, path in imagenes.items():
        if titulo not in orden and path and os.path.exists(path):
            doc.add_heading(titulo, 2)
            try: doc.add_picture(path, width=Inches(6.0))
            except: pass
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
    
    # 1. CARGA
    st.header("1. Datos")
    f = st.file_uploader("Archivo (CSV/Excel)", type=['csv','xlsx'])
    
    if not f:
        st.info("Sube un archivo para comenzar.")
        return

    try:
        df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
        st.success(f"Cargado: {len(df)} registros.")
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    # 2. CONFIGURACIÓN
    st.header("2. Configuración")
    c1, c2, c3 = st.columns(3)
    col_inc = c1.selectbox("Columna INCIDENTES:", df.columns)
    col_col = c2.selectbox("Columna COLONIAS:", df.columns)
    col_genero = c3.selectbox("Columna GÉNERO (Opcional):", ["No usar"] + list(df.columns))
    if col_genero == "No usar": col_genero = None
    
    c4, c5 = st.columns(2)
    col_edad = c4.selectbox("Columna EDAD (Opcional):", ["No usar"] + list(df.columns))
    if col_edad == "No usar": col_edad = None

    col_fecha = c5.selectbox("Columna FECHAS (Necesaria para gráficas de línea):", ["No usar"]+list(df.columns))
    if col_fecha == "No usar": col_fecha = None
    
    st.subheader("🌧️ Análisis de Lluvias")
    check_lluvias = st.checkbox("Analizar Reportes de Lluvias")
    col_lluvias = None
    if check_lluvias:
        col_lluvias = st.selectbox("Columna Indicador Lluvia (Sí/No, 1/0):", df.columns)

    st.markdown("---")
    st.subheader("🛠️ Filtros y Gráficas Avanzadas")
    ignorar_medica = st.checkbox("Ignorar 'Atención Médica'", value=True)
    
    col_g1, col_g2 = st.columns(2)
    graf_top10 = col_g1.checkbox("Barras: Top 10 Incidentes", value=True)
    graf_pct_genero = col_g2.checkbox("Línea: Porcentaje Género", value=False)
    
    graf_linea_inc = col_g1.checkbox("Línea: Tendencia Top 10 Incidentes", value=False)
    graf_linea_col = col_g2.checkbox("Línea: Tendencia Top 10 Colonias", value=False)
    graf_edad_colonia = col_g1.checkbox("Círculos: Rango de Edad Dominante por Colonia", value=False)
    
    # HEATMAP
    graf_heatmap = False
    geo_file = None
    col_geo_nombre = None
    
    # Import condicional seguro dentro del flujo
    if 'geopandas' in globals() or 'geopandas' in locals():
        # Verificación doble por si el import falló silenciosamente
        try:
            import geopandas as gpd
            import folium
            from streamlit_folium import st_folium
            HAS_GEO = True
        except:
            HAS_GEO = False
    else:
        try:
            import geopandas as gpd
            import folium
            from streamlit_folium import st_folium
            HAS_GEO = True
        except:
            HAS_GEO = False

    if HAS_GEO:
        st.subheader("🗺️ Mapa de Calor (Heatmap)")
        graf_heatmap = st.checkbox("Generar Mapa de Calor por Colonia", value=False)
        if graf_heatmap:
            st.info("Sube el archivo GeoJSON con los límites de las colonias.")
            geo_file = st.file_uploader("Archivo GeoJSON", type=['geojson', 'json'])
            if geo_file:
                try:
                    gdf_temp = gpd.read_file(geo_file)
                    st.success("GeoJSON cargado correctamente.")
                    col_geo_nombre = st.selectbox("Selecciona la columna del GeoJSON con el NOMBRE de la colonia:", gdf_temp.columns)
                    geo_file.seek(0)
                except Exception as e:
                    st.error(f"Error leyendo GeoJSON: {e}")
    else:
        st.warning("⚠️ Funciones de mapas deshabilitadas (faltan librerías geopandas/folium).")

    # 3. PROCESAR
    if st.button("🚀 Generar Reporte", type="primary"):
        # USAMOS TRY EXCEPT GENERAL PARA CAPTURAR CUALQUIER CRASH
        try:
            status = st.status("Procesando datos...", expanded=True)
            
            status.write("Limpiando datos...")
            df_c = df.copy()
            df_c[col_inc] = df_c[col_inc].apply(limpiar_texto)
            df_c[col_col] = df_c[col_col].apply(limpiar_texto)
            
            if ignorar_medica:
                df_c = df_c[df_c[col_inc] != "atencion medica"]
            
            if df_c.empty:
                status.update(label="Error: Sin datos", state="error")
                st.error("Sin datos tras filtros.")
                return

            status.write("Procesando fechas...")
            valid_fechas = False
            if col_fecha:
                df_c['fecha_p'] = df_c[col_fecha].apply(parsear_fecha)
                if df_c['fecha_p'].notna().sum() > 0:
                    valid_fechas = True
                    df_c = df_c.dropna(subset=['fecha_p'])
                    df_c['mes'] = df_c['fecha_p'].dt.to_period('M')
            
            conteos = {
                "General": df_c[col_inc].value_counts(),
                "Colonias": df_c[col_col].value_counts()
            }
            imgs = {}

            if check_lluvias and col_lluvias:
                res_lluv = analizar_lluvias_manual(df_c, col_lluvias, col_col, col_inc)
                if res_lluv:
                    conteos["Tipos de Incidentes en Lluvias"] = res_lluv['conteo_incidentes']
                    conteos["Colonias Afectadas por Lluvias"] = res_lluv['conteo_colonias']
                else: res_lluv = None
            else: res_lluv = None
            
            if col_genero:
                 df_c['genero_norm'] = df_c[col_genero].apply(normalizar_genero)
                 conteos["Desglose por Género"] = df_c['genero_norm'].fillna('No id').value_counts()

            if col_edad:
                df_c['edad_cat'] = df_c[col_edad].apply(limpiar_y_categorizar_edad)
                conteos["Desglose por Rango Edad"] = df_c['edad_cat'].value_counts()

            # RESULTADOS
            status.write("Generando visualizaciones...")
            st.header("3. Resultados")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total", len(df_c))
            c2.metric("Tipos", df_c[col_inc].nunique())
            if res_lluv: c3.metric("Lluvia", res_lluv['estadisticas']['total_lluvias'])
            
            # MAPA
            if graf_heatmap and HAS_GEO and geo_file and col_geo_nombre:
                try:
                    conteo_cols = df_c[col_col].value_counts().reset_index()
                    conteo_cols.columns = ['nombre_norm', 'cantidad']
                    gdf = gpd.read_file(geo_file)
                    gdf['nombre_norm'] = gdf[col_geo_nombre].apply(limpiar_texto)
                    gdf_merged = gdf.merge(conteo_cols, on='nombre_norm', how='left')
                    gdf_merged['cantidad'] = gdf_merged['cantidad'].fillna(0)
                    
                    st.subheader("🗺️ Mapa de Calor")
                    m = folium.Map(location=[gdf_merged.geometry.centroid.y.mean(), gdf_merged.geometry.centroid.x.mean()], zoom_start=13)
                    folium.Choropleth(
                        geo_data=gdf_merged, name="Choropleth", data=gdf_merged,
                        columns=['nombre_norm', 'cantidad'], key_on='feature.properties.nombre_norm',
                        fill_color='Reds', fill_opacity=0.8, line_opacity=0.2, legend_name='Reportes'
                    ).add_to(m)
                    st_folium(m, width=800, height=500)
                    imgs["Mapa de Calor (Colonias)"] = generar_mapa_estatico_word(gdf_merged, "Densidad de Reportes", "mapa_calor.png")
                except Exception as e: st.error(f"Error mapa: {e}")

            st.subheader("Gráficas")
            top_gen = conteos["General"].head(15)
            st.plotly_chart(generar_grafica_plotly_bar(top_gen, "Top Incidentes"), use_container_width=True)
            imgs["General"] = generar_grafica_bar(top_gen, "Top Incidentes", "g1.png")

            # EDAD
            if col_edad and graf_edad_colonia:
                try:
                    top10_c = conteos["Colonias"].head(10).index.tolist()
                    df_edad = df_c[df_c[col_col].isin(top10_c) & df_c['edad_cat'].notna()].copy()
                    if not df_edad.empty:
                        grp_edad = df_edad.groupby([col_col, 'edad_cat']).size().reset_index(name='Cantidad')
                        total_por_colonia = df_edad.groupby(col_col).size().reset_index(name='Total_Col')
                        grp_edad = pd.merge(grp_edad, total_por_colonia, on=col_col)
                        grp_edad['Porcentaje'] = (grp_edad['Cantidad'] / grp_edad['Total_Col']) * 100
                        grp_edad.rename(columns={col_col: 'Colonia', 'edad_cat': 'Rango'}, inplace=True)
                        grp_edad = grp_edad.sort_values(['Colonia', 'Porcentaje'], ascending=[True, False])
                        grp_edad_max = grp_edad.drop_duplicates(subset=['Colonia'], keep='first')
                        
                        st.plotly_chart(generar_grafica_plotly_circulos_edad(grp_edad_max, "Rango de Edad Dominante"), use_container_width=True)
                        imgs["Rango de Edad Dominante por Colonia"] = generar_grafica_circulos_edad_word(grp_edad_max, "Rango Edad Dominante", "g_edad_circ.png")
                except Exception as e: st.error(f"Error edad: {e}")

            # GÉNERO
            if valid_fechas and col_genero and graf_pct_genero:
                try:
                    df_gen = df_c[df_c['genero_norm'].isin(['Masculino', 'Femenino'])].copy()
                    if not df_gen.empty:
                        conteo_gen = df_gen.groupby(['mes', 'genero_norm']).size().reset_index(name='cuenta')
                        total_mes = df_gen.groupby('mes').size().reset_index(name='total_mes')
                        df_pct = pd.merge(conteo_gen, total_mes, on='mes')
                        df_pct['porcentaje'] = (df_pct['cuenta'] / df_pct['total_mes']) * 100
                        st.plotly_chart(generar_grafica_plotly_linea(df_pct, 'mes', 'porcentaje', 'genero_norm', "Género %", True), use_container_width=True)
                        imgs["Tendencia Porcentaje Género"] = generar_grafica_linea_porcentaje_genero(df_pct, 'mes', 'porcentaje', 'genero_norm', "Género %", "l_pct.png")
                except Exception as e: st.error(f"Error género: {e}")

            # TENDENCIAS
            if valid_fechas:
                if graf_linea_inc:
                    try:
                        top10 = conteos["General"].head(10).index.tolist()
                        df_top = df_c[df_c[col_inc].isin(top10)].copy()
                        dl = df_top.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                        if not dl.empty:
                            st.plotly_chart(generar_grafica_plotly_linea(dl, 'mes', 'conteo', col_inc, "Evolución Incidentes"), use_container_width=True)
                            imgs["Tendencia Incidentes"] = generar_grafica_linea_multiple(dl, 'mes', 'conteo', col_inc, "Evolución", "l_inc.png")
                    except: pass
                if graf_linea_col:
                    try:
                        top10 = conteos["Colonias"].head(10).index.tolist()
                        df_top = df_c[df_c[col_col].isin(top10)].copy()
                        dl = df_top.groupby(['mes', col_col]).size().reset_index(name='conteo')
                        if not dl.empty:
                            st.plotly_chart(generar_grafica_plotly_linea(dl, 'mes', 'conteo', col_col, "Evolución Colonias"), use_container_width=True)
                            imgs["Tendencia Colonias"] = generar_grafica_linea_multiple(dl, 'mes', 'conteo', col_col, "Evolución", "l_col.png")
                    except: pass

            # LLUVIAS
            if res_lluv:
                st.markdown("---")
                st.subheader("Lluvias")
                st.plotly_chart(generar_grafica_plotly_bar(res_lluv['conteo_incidentes'].head(10), "Tipos (Lluvias)"), use_container_width=True)
                imgs["Tipos Lluvia"] = generar_grafica_bar(res_lluv['conteo_incidentes'].head(10), "Tipos", "g_inc_l.png")
                st.plotly_chart(generar_grafica_plotly_bar(res_lluv['conteo_colonias'].head(10), "Colonias (Lluvias)"), use_container_width=True)
                imgs["Colonias Lluvia"] = generar_grafica_bar(res_lluv['conteo_colonias'].head(10), "Colonias", "g_col_l.png")
                
                if valid_fechas:
                    df_lt = res_lluv['df_filtrado'].copy()
                    df_lt['mes'] = df_lt['fecha_p'].dt.to_period('M')
                    try:
                        top5 = res_lluv['conteo_incidentes'].head(5).index.tolist()
                        df_top = df_lt[df_lt[col_inc].isin(top5)]
                        if not df_top.empty:
                            dl = df_top.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                            st.plotly_chart(generar_grafica_plotly_linea(dl, 'mes', 'conteo', col_inc, "Tendencia Tipos (Lluvia)"), use_container_width=True)
                            imgs["Tendencia Tipos Lluvia"] = generar_grafica_linea_multiple(dl, 'mes', 'conteo', col_inc, "Tendencia", "l_t_l.png")
                    except: pass
                    try:
                        dt = df_lt.groupby('mes').size().reset_index(name='conteo')
                        if not dt.empty:
                            imgs["Tendencia Total Lluvias"] = generar_grafica_linea_simple(dt.set_index('mes')['conteo'], "Total Lluvia", "Mes", "Cant", "l_tot_l.png")
                    except: pass

            status.update(label="¡Completado!", state="complete", expanded=False)
            st.success("✅ Reporte Generado")
            
            c1, c2 = st.columns(2)
            c1.markdown(get_link(generar_reporte_word(conteos, imgs), "Word"), unsafe_allow_html=True)
            c2.markdown(get_link(generar_txt(conteos), "Txt"), unsafe_allow_html=True)
            
            for p in imgs.values(): 
                if p and os.path.exists(p): os.remove(p)

        except Exception as e:
            st.error(f"❌ Ocurrió un error inesperado: {str(e)}")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
