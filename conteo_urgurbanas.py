import streamlit as st
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Inches
import matplotlib.pyplot as plt
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

# Configuración de la página
st.set_page_config(
    page_title="Analizador de Urgencias Operativas",
    page_icon="📊",
    layout="wide"
)

# --- FUNCIONES DE UTILIDAD ---

def formatear_periodo_es(periodo):
    """Convierte un objeto Period de pandas a string 'Mes Año' en español"""
    if pd.isna(periodo): return ""
    meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    return f"{meses.get(periodo.month, '')} {periodo.year}"

def limpiar_texto(texto):
    """Normaliza texto general"""
    if not isinstance(texto, str):
        return str(texto).lower().strip()
    texto_limpio = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8').lower().strip()
    return texto_limpio

def normalizar_genero(texto):
    """Normaliza género (estricto)"""
    t = limpiar_texto(texto)
    if not t: return None
    if t in ['hombre', 'masculino', 'm', 'varon', 'caballero', 'el', 'masc']: return 'Masculino'
    if t in ['mujer', 'femenino', 'f', 'dama', 'senora', 'srta', 'la', 'fem']: return 'Femenino'
    return None

def limpiar_y_categorizar_edad(valor):
    """Convierte entradas de edad a rangos numéricos"""
    if pd.isna(valor): return None
    
    # Intentar extraer números del texto (ej: "25 años" -> 25)
    s = str(valor)
    numeros = re.findall(r'\d+', s)
    
    if not numeros:
        return None
    
    try:
        edad = int(numeros[0])
    except:
        return None
        
    # Clasificación
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

# --- FUNCIONES DE GRÁFICAS (Matplotlib - Word) ---

def generar_grafica_bar(conteo, titulo, filename):
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
    if datos.empty: return None
    df_plot = datos.reset_index()
    df_plot.columns = ['Periodo', 'Cantidad']
    df_plot = df_plot.sort_values('Periodo')
    etiquetas_x = [formatear_periodo_es(p) for p in df_plot['Periodo']]
    
    plt.figure(figsize=(10, 6))
    plt.plot(etiquetas_x, df_plot['Cantidad'], marker='o', linestyle='-', color='teal', linewidth=2)
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
    if df_long.empty: return None
    plt.figure(figsize=(12, 7))
    grupos = df_long[col_grupo].unique()
    cmap = plt.get_cmap('tab10')
    
    for i, grupo in enumerate(grupos):
        subset = df_long[df_long[col_grupo] == grupo].sort_values(by=col_x)
        x_vals = [formatear_periodo_es(p) for p in subset[col_x]]
        y_vals = subset[col_y]
        color = cmap(i % 10)
        plt.plot(x_vals, y_vals, marker='o', linestyle='-', linewidth=2, label=grupo, color=color)
    
    plt.title(titulo, fontsize=14, fontweight='bold')
    plt.xlabel("Mes", fontweight='bold')
    plt.ylabel(col_y.title(), fontweight='bold')
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize='small')
    plt.tight_layout()
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_linea_porcentaje_genero(df_long, col_periodo, col_pct, col_genero, titulo, filename):
    if df_long.empty: return None
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
    ax.set_xlabel("Mes", fontweight='bold')
    ax.set_ylabel("Porcentaje (%)", fontweight='bold')
    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.grid(True, alpha=0.3, axis='y')
    plt.legend(loc='best', fontsize='medium')
    plt.tight_layout()
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

def generar_grafica_muñequitos_edad(df_data, titulo, filename):
    """
    Gráfica de dispersión usando un marcador de texto (muñeco) con tamaño variable.
    """
    if df_data.empty: return None
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Ejes
    colonias = df_data['Colonia'].unique()
    rangos = ["Menor (0-17)", "Joven (18-29)", "Adulto (30-59)", "Mayor (60+)"] # Orden lógico
    
    # Mapeo de colores para rangos
    colors = {'Menor (0-17)': '#FF9999', 'Joven (18-29)': '#66B2FF', 
              'Adulto (30-59)': '#99FF99', 'Mayor (60+)': '#FFCC99'}
    
    ax.set_xlim(-0.5, len(colonias) - 0.5)
    ax.set_ylim(-0.5, len(rangos) - 0.5)
    
    # Mapeo de coordenadas
    col_map = {c: i for i, c in enumerate(colonias)}
    rango_map = {r: i for i, r in enumerate(rangos)}
    
    for _, row in df_data.iterrows():
        c_idx = col_map.get(row['Colonia'])
        r_idx = rango_map.get(row['Rango'])
        
        if c_idx is not None and r_idx is not None:
            pct = row['Porcentaje']
            # Escalar tamaño del muñeco (min 10, max 60)
            font_size = 10 + (pct * 0.5) 
            color = colors.get(row['Rango'], 'grey')
            
            # Dibujar Muñeco
            ax.text(c_idx, r_idx, '👤', ha='center', va='center', 
                    fontsize=font_size, color=color, fontfamily='DejaVu Sans')
            
            # Dibujar Porcentaje encima de la cabeza
            ax.text(c_idx, r_idx + 0.2, f"{pct:.0f}%", ha='center', va='bottom', 
                    fontsize=8, fontweight='bold', color='black')

    ax.set_xticks(range(len(colonias)))
    ax.set_xticklabels(colonias, rotation=45, ha='right')
    ax.set_yticks(range(len(rangos)))
    ax.set_yticklabels(rangos)
    
    ax.set_title(titulo, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.2, linestyle='--')
    plt.tight_layout()
    
    path = os.path.join(tempfile.gettempdir(), filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    return path

# --- FUNCIONES DE GRÁFICAS (Plotly - Pantalla) ---

def generar_grafica_plotly_bar(conteo, titulo):
    if conteo is None or conteo.empty: return px.bar(title="Sin datos")
    df_plot = conteo.reset_index()
    df_plot.columns = ['Categoría', 'Cantidad']
    fig = px.bar(df_plot, x='Categoría', y='Cantidad', title=titulo, color='Cantidad')
    return fig

def generar_grafica_plotly_linea(df_long, col_periodo, col_y, col_color, titulo, es_porcentaje=False):
    if df_long.empty: return px.line(title="Sin datos")
    df_plot = df_long.copy()
    df_plot = df_plot.sort_values(col_periodo)
    df_plot['Mes_Texto'] = df_plot[col_periodo].apply(formatear_periodo_es)
    
    if es_porcentaje:
        df_plot['Etiqueta'] = df_plot[col_y].apply(lambda x: f"{x:.1f}%")
    else:
        df_plot['Etiqueta'] = df_plot[col_y].astype(str)

    color_map = {'Masculino': 'blue', 'Femenino': 'purple'} if (es_porcentaje and col_color) else None

    if col_color:
        fig = px.line(df_plot, x='Mes_Texto', y=col_y, color=col_color, title=titulo, markers=True,
                      text='Etiqueta', color_discrete_map=color_map)
    else:
        fig = px.line(df_plot, x='Mes_Texto', y=col_y, title=titulo, markers=True, text='Etiqueta')
    
    fig.update_traces(textposition="top center")
    if es_porcentaje:
        fig.update_yaxes(range=[0, 115], title="Porcentaje (%)")
        fig.update_traces(hovertemplate='%{y:.1f}%')
    fig.update_xaxes(type='category', title="Mes")
    return fig

def generar_grafica_plotly_muñequitos(df_data, titulo):
    """Gráfica de burbujas usando texto (emoji) como marcador"""
    if df_data.empty: return px.scatter(title="Sin datos")
    
    # Crear columna de texto combinado para el hover
    df_data['Info'] = df_data.apply(lambda x: f"{x['Rango']}: {x['Porcentaje']:.1f}% ({x['Cantidad']} reportes)", axis=1)
    
    # Para Plotly, usamos scatter pero con modo 'text'
    # El tamaño del texto simula el tamaño del muñeco
    # Limitamos el tamaño máximo para que no tape todo
    df_data['Size_Scaled'] = df_data['Porcentaje'].apply(lambda x: 15 + (x * 0.8)) 
    
    # Crear figura base
    fig = px.scatter(df_data, x="Colonia", y="Rango", 
                     title=titulo,
                     color="Rango",
                     color_discrete_map={
                         'Menor (0-17)': '#FF9999', 'Joven (18-29)': '#66B2FF', 
                         'Adulto (30-59)': '#99FF99', 'Mayor (60+)': '#FFCC99'
                     })
    
    # Actualizar trazas para usar el emoji
    fig.update_traces(
        mode="text",
        text="👤",
        textfont_size=df_data['Size_Scaled'], # Tamaño variable
        hovertemplate="<b>%{x}</b><br>%{y}<br>Porcentaje: %{customdata[0]:.1f}%<extra></extra>",
        customdata=df_data[['Porcentaje']]
    )
    
    # Añadir el porcentaje como texto fijo ENCIMA (usando otra traza transparente o anotaciones)
    # Una forma fácil en plotly es añadir otra traza scatter solo con el texto numérico
    fig.add_trace(go.Scatter(
        x=df_data['Colonia'], 
        y=df_data['Rango'],
        mode="text",
        text=df_data['Porcentaje'].apply(lambda x: f"{x:.0f}%"),
        textposition="top center",
        textfont=dict(size=10, color="black", weight="bold"),
        showlegend=False,
        hoverinfo='skip'
    ))

    fig.update_yaxes(categoryorder='array', categoryarray=["Menor (0-17)", "Joven (18-29)", "Adulto (30-59)", "Mayor (60+)"])
    fig.update_layout(height=600, plot_bgcolor='white', xaxis_tickangle=-45)
    
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
    
    doc.add_heading('Resumen de Datos', 1)
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
    
    orden = ['General', 'Comparativa Edades por Colonia', 'Tendencia Porcentaje Género', 
             'Tendencia Incidentes', 'Tendencia Colonias', 
             'Tipos Lluvia', 'Colonias Lluvia', 'Tendencia Tipos Lluvia', 'Tendencia Total Lluvias']
    
    for titulo in orden:
        if titulo in imagenes and os.path.exists(imagenes[titulo]):
             doc.add_heading(titulo, 2)
             try: doc.add_picture(imagenes[titulo], width=Inches(6.5))
             except: doc.add_paragraph("[Error imagen]")
             doc.add_paragraph()
    
    for titulo, path in imagenes.items():
        if titulo not in orden and path and os.path.exists(path):
            doc.add_heading(titulo, 2)
            try: doc.add_picture(path, width=Inches(6.5))
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
        st.info("Sube un archivo.")
        return

    try:
        df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
        st.success(f"Cargado: {len(df)} registros.")
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return

    # 2. CONFIGURACIÓN
    st.header("2. Configuración")
    c1, c2 = st.columns(2)
    col_inc = c1.selectbox("Columna INCIDENTES:", df.columns)
    col_col = c2.selectbox("Columna COLONIAS:", df.columns)
    
    c3, c4 = st.columns(2)
    col_genero = c3.selectbox("Columna GÉNERO (Opcional):", ["No usar"] + list(df.columns))
    if col_genero == "No usar": col_genero = None
    
    col_edad = c4.selectbox("Columna EDAD (Opcional):", ["No usar"] + list(df.columns))
    if col_edad == "No usar": col_edad = None

    col_fecha = st.selectbox("Columna FECHAS (Necesaria para gráficas de línea):", ["No usar"]+list(df.columns))
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
    
    # NUEVO CHECKBOX
    graf_edad_colonia = col_g1.checkbox("Muñequitos: Comparativa Edades por Colonia", value=False)

    # Validaciones
    if (graf_linea_inc or graf_linea_col or graf_pct_genero) and not col_fecha:
         st.warning("⚠️ Las gráficas de línea requieren una Columna de FECHAS.")
    if graf_pct_genero and not col_genero:
         st.warning("⚠️ Requiere Columna GÉNERO.")
    if graf_edad_colonia and not col_edad:
         st.warning("⚠️ Requiere Columna EDAD.")

    # 3. PROCESAR
    if st.button("🚀 Generar Reporte", type="primary"):
        with st.spinner("Procesando..."):
            df_c = df.copy()
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
                    df_c = df_c.dropna(subset=['fecha_p'])
                    df_c['mes'] = df_c['fecha_p'].dt.to_period('M')
            
            conteos = {
                "General": df_c[col_inc].value_counts(),
                "Colonias": df_c[col_col].value_counts()
            }
            imgs = {}

            # Lluvias
            res_lluv = None
            if check_lluvias and col_lluvias:
                res_lluv = analizar_lluvias_manual(df_c, col_lluvias, col_col, col_inc)
                if res_lluv:
                    conteos["Tipos de Incidentes en Lluvias"] = res_lluv['conteo_incidentes']
                    conteos["Colonias Afectadas por Lluvias"] = res_lluv['conteo_colonias']
            
            # Género
            if col_genero:
                 df_c['genero_norm'] = df_c[col_genero].apply(normalizar_genero)
                 conteos["Desglose por Género"] = df_c['genero_norm'].fillna('No id').value_counts()

            # Edad
            if col_edad:
                df_c['edad_cat'] = df_c[col_edad].apply(limpiar_y_categorizar_edad)
                conteos["Desglose por Rango Edad"] = df_c['edad_cat'].value_counts()

            # --- RESULTADOS ---
            st.header("3. Resultados")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total", len(df_c))
            c2.metric("Tipos", df_c[col_inc].nunique())
            if res_lluv: c3.metric("Lluvia", res_lluv['estadisticas']['total_lluvias'])
            
            # Barras General
            st.subheader("Vista General")
            top_gen = conteos["General"].head(15)
            st.plotly_chart(generar_grafica_plotly_bar(top_gen, "Top Incidentes"), use_container_width=True)
            imgs["General"] = generar_grafica_bar(top_gen, "Top Incidentes", "g1.png")

            # --- GRÁFICA MUÑEQUITOS (EDAD POR COLONIA) ---
            if col_edad and graf_edad_colonia:
                st.subheader("👥 Rangos de Edad por Colonia (Top 10)")
                try:
                    # 1. Filtrar top 10 colonias para no saturar
                    top10_c = conteos["Colonias"].head(10).index.tolist()
                    df_edad = df_c[df_c[col_col].isin(top10_c) & df_c['edad_cat'].notna()].copy()
                    
                    if not df_edad.empty:
                        # 2. Agrupar
                        grp_edad = df_edad.groupby([col_col, 'edad_cat']).size().reset_index(name='Cantidad')
                        
                        # 3. Calcular Totales por Colonia para sacar %
                        total_por_colonia = df_edad.groupby(col_col).size().reset_index(name='Total_Col')
                        grp_edad = pd.merge(grp_edad, total_por_colonia, on=col_col)
                        grp_edad['Porcentaje'] = (grp_edad['Cantidad'] / grp_edad['Total_Col']) * 100
                        
                        # Renombrar para facilitar
                        grp_edad.rename(columns={col_col: 'Colonia', 'edad_cat': 'Rango'}, inplace=True)
                        
                        # 4. Graficar
                        st.plotly_chart(generar_grafica_plotly_muñequitos(grp_edad, "Distribución de Edades por Colonia"), use_container_width=True)
                        imgs["Comparativa Edades por Colonia"] = generar_grafica_muñequitos_edad(grp_edad, "Edad por Colonia (Tamaño = %)", "g_edad_doll.png")
                    else:
                        st.warning("No hay datos de edad suficientes en las top 10 colonias.")
                except Exception as e:
                    st.error(f"Error en gráfica de edades: {e}")

            # --- GRÁFICA PORCENTAJE GÉNERO ---
            if valid_fechas and col_genero and graf_pct_genero:
                try:
                    df_gen = df_c[df_c['genero_norm'].isin(['Masculino', 'Femenino'])].copy()
                    if not df_gen.empty:
                        conteo_gen_mes = df_gen.groupby(['mes', 'genero_norm']).size().reset_index(name='cuenta')
                        total_mes = df_gen.groupby('mes').size().reset_index(name='total_mes')
                        df_pct_gen = pd.merge(conteo_gen_mes, total_mes, on='mes')
                        df_pct_gen['porcentaje'] = (df_pct_gen['cuenta'] / df_pct_gen['total_mes']) * 100
                        
                        st.subheader("📈 Género (Hombres vs Mujeres)")
                        st.plotly_chart(generar_grafica_plotly_linea(df_pct_gen, 'mes', 'porcentaje', 'genero_norm', "Evolución % Género", True), use_container_width=True)
                        imgs["Tendencia Porcentaje Género"] = generar_grafica_linea_porcentaje_genero(df_pct_gen, 'mes', 'porcentaje', 'genero_norm', "Solicitantes por Género (%)", "l_pct_gen.png")
                    else:
                         st.warning("Datos de género insuficientes.")
                except Exception as e: st.error(f"Error género: {e}")
            
            # Líneas Tendencia
            if valid_fechas:
                if graf_linea_inc:
                    try:
                        top10_names = conteos["General"].head(10).index.tolist()
                        df_top = df_c[df_c[col_inc].isin(top10_names)].copy()
                        data_linea = df_top.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                        if not data_linea.empty:
                            st.subheader("📈 Tendencia Incidentes")
                            st.plotly_chart(generar_grafica_plotly_linea(data_linea, 'mes', 'conteo', col_inc, "Evolución Incidentes"), use_container_width=True)
                            imgs["Tendencia Incidentes"] = generar_grafica_linea_multiple(data_linea, 'mes', 'conteo', col_inc, "Comparativa Incidentes", "l_inc.png")
                    except: pass
                
                if graf_linea_col:
                    try:
                        top10_cols = conteos["Colonias"].head(10).index.tolist()
                        df_top_c = df_c[df_c[col_col].isin(top10_cols)].copy()
                        data_linea_c = df_top_c.groupby(['mes', col_col]).size().reset_index(name='conteo')
                        if not data_linea_c.empty:
                            st.subheader("📈 Tendencia Colonias")
                            st.plotly_chart(generar_grafica_plotly_linea(data_linea_c, 'mes', 'conteo', col_col, "Evolución Colonias"), use_container_width=True)
                            imgs["Tendencia Colonias"] = generar_grafica_linea_multiple(data_linea_c, 'mes', 'conteo', col_col, "Comparativa Colonias", "l_col.png")
                    except: pass

            # Lluvias
            if res_lluv:
                st.markdown("---")
                st.header("🌧️ Análisis Lluvias")
                top_inc_lluv = res_lluv['conteo_incidentes'].head(15)
                st.plotly_chart(generar_grafica_plotly_bar(top_inc_lluv, "Tipos (Lluvias)"), use_container_width=True)
                imgs["Tipos Lluvia"] = generar_grafica_bar(top_inc_lluv, "Tipos en Lluvias", "g_inc_lluv.png")
                
                top_col_lluv = res_lluv['conteo_colonias'].head(15)
                st.plotly_chart(generar_grafica_plotly_bar(top_col_lluv, "Colonias (Lluvias)"), use_container_width=True)
                imgs["Colonias Lluvia"] = generar_grafica_bar(top_col_lluv, "Colonias en Lluvias", "g_col_lluv.png")
                
                if valid_fechas:
                    df_lluvia_t = res_lluv['df_filtrado'].copy()
                    df_lluvia_t['mes'] = df_lluvia_t['fecha_p'].dt.to_period('M')
                    try:
                        top5_inc_lluvia = res_lluv['conteo_incidentes'].head(5).index.tolist()
                        df_top_lluvia = df_lluvia_t[df_lluvia_t[col_inc].isin(top5_inc_lluvia)]
                        if not df_top_lluvia.empty:
                            data_linea_lluvia = df_top_lluvia.groupby(['mes', col_inc]).size().reset_index(name='conteo')
                            st.subheader("📈 Tendencia Tipos (Lluvias)")
                            st.plotly_chart(generar_grafica_plotly_linea(data_linea_lluvia, 'mes', 'conteo', col_inc, "Evolución Tipos (Lluvias)"), use_container_width=True)
                            imgs["Tendencia Tipos Lluvia"] = generar_grafica_linea_multiple(data_linea_lluvia, 'mes', 'conteo', col_inc, "Evolución Tipos (Lluvias)", "l_tipo_lluv.png")
                    except: pass
                    
                    try:
                        data_total = df_lluvia_t.groupby('mes').size().reset_index(name='conteo')
                        if not data_total.empty:
                            imgs["Tendencia Total Lluvias"] = generar_grafica_linea_simple(data_total.set_index('mes')['conteo'], "Total Lluvias", "Mes", "Cant", "l_total_lluv.png")
                    except: pass

            st.success("✅ Hecho")
            c1, c2 = st.columns(2)
            c1.markdown(get_link(generar_reporte_word(conteos, imgs), "Word"), unsafe_allow_html=True)
            c2.markdown(get_link(generar_txt(conteos), "Txt"), unsafe_allow_html=True)
            for p in imgs.values(): 
                if p and os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    main()
