
# imdc_web_blindado_ANTIDUP_FIXED_v3_PARQUET_CORR_v8.py
# ============================================================
# IMDC — Dashboard Ejecutivo (LOCAL) — Ferretería El Cedro
#
# v8 (Visual-only revamp, lógica de datos ya correcta):
# - Modo técnico en sidebar (oculta debug por default)
# - Gráfica mensual estática (12 meses) con highlight del rango DE/A
# - Formato global en tablas ($, %, meses con nombre) + columnas YoY con flechas (verde/rojo fuerte)
# - Reorganización por pestañas:
#   1) Resumen Ejecutivo: Ventas & Rentabilidad
#   2) Mix: KPIs m² + Top 20 Familias + Top 20 Marcas + Treemap Familia→Marca
#   3) Productividad: KPIs por empleado + Top vendedores (barras apiladas Cred/Cont + línea Utilidad)
#      + Matriz 2×2 (cuadrantes) + Tabla
#   4) Insights: tarjetas/alertas + top movers vs LY (respeta filtro actual)
# - Catálogo fijo de Familias (Opción B): Datos/CAT_FAMILIA.xlsx (hoja CAT_FAMILIA) o CSV equivalente
#
# IMPORTANTÍSIMO:
# - NO se cambia la lógica anti-duplicado por documento.
# - Ventas CON IVA = Total_alloc (usa Total directo cuando ya viene por línea; si viene repetido por doc, asigna alloc)
# - Transacciones = DOC_KEY únicos
# ============================================================

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# Imports adicionales para mejoras visuales
# ============================================================
from datetime import datetime, timedelta
import calendar



# ============================================================
# SISTEMA DE FAVORITOS
# ============================================================

def inicializar_favoritos():
    """Inicializa sistema de favoritos en session_state"""
    if 'favoritos' not in st.session_state:
        st.session_state.favoritos = {}
    
    # Favoritos por defecto
    if len(st.session_state.favoritos) == 0:
        st.session_state.favoritos = {
            "📊 Vista General": {
                'sucursal': 'CONSOLIDADO',
                'familia': 'TODAS',
                'marca': 'TODAS',
                'ventas_con_iva': True,
                'include_rem': False
            },
            "🏪 General por Familia": {
                'sucursal': 'GENERAL',
                'familia': 'TODAS',
                'marca': 'TODAS',
                'ventas_con_iva': True,
                'include_rem': False
            }
        }


def guardar_favorito():
    """Guarda la configuración actual como favorito"""
    nombre = st.session_state.get('nombre_favorito', '')
    
    if nombre and nombre.strip():
        st.session_state.favoritos[nombre] = {
            'sucursal': st.session_state.filtros_globales.get('sucursal', 'CONSOLIDADO'),
            'familia': st.session_state.filtros_globales.get('familia', 'TODAS'),
            'marca': st.session_state.filtros_globales.get('marca', 'TODAS'),
            'ventas_con_iva': st.session_state.filtros_globales.get('ventas_con_iva', True),
            'include_rem': st.session_state.filtros_globales.get('include_rem', False)
        }
        st.success(f"✅ Favorito '{nombre}' guardado")
        st.session_state.nombre_favorito = ""


def cargar_favorito(nombre: str):
    """Carga un favorito y actualiza filtros"""
    if nombre in st.session_state.favoritos:
        config = st.session_state.favoritos[nombre]
        st.session_state.filtros_globales.update(config)
        st.rerun()


def eliminar_favorito(nombre: str):
    """Elimina un favorito"""
    if nombre in st.session_state.favoritos:
        del st.session_state.favoritos[nombre]
        st.rerun()


def mostrar_panel_favoritos():
    """Muestra panel de favoritos en sidebar"""
    
    inicializar_favoritos()
    
    with st.expander("⭐ Favoritos", expanded=False):
        st.markdown("### Vistas Guardadas")
        
        # Mostrar favoritos existentes
        if st.session_state.favoritos:
            for nombre in list(st.session_state.favoritos.keys()):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if st.button(f"📌 {nombre}", key=f"load_{nombre}", use_container_width=True):
                        cargar_favorito(nombre)
                
                with col2:
                    if st.button("🗑️", key=f"del_{nombre}"):
                        eliminar_favorito(nombre)
        
        st.markdown("---")
        st.markdown("### Guardar Vista Actual")
        
        nombre_nuevo = st.text_input(
            "Nombre del favorito:",
            key="nombre_favorito",
            placeholder="Ej: Eléctricos General"
        )
        
        if st.button("💾 Guardar", use_container_width=True, type="primary"):
            guardar_favorito()

# ============================================================
# EXPORTAR DASHBOARD A PDF
# ============================================================

def generar_pdf_dashboard():
    """
    Genera PDF del dashboard usando kaleido para gráficas plotly
    y reportlab para layout
    """
    from io import BytesIO
    
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib import colors
    except ImportError:
        st.error("⚠️ Instalar: pip install reportlab kaleido")
        return None
    
    # Buffer para PDF
    buffer = BytesIO()
    
    # Crear documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2563EB'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Contenido del PDF
    story = []
    
    # PORTADA
    story.append(Paragraph("FERRETERÍA EL CEDRO", title_style))
    story.append(Paragraph("Dashboard Ejecutivo", styles['Heading2']))
    story.append(Spacer(1, 0.3*inch))
    
    # Información de filtros aplicados
    filtros_text = f"""
    <b>Período:</b> {st.session_state.filtros_globales.get('year', 'N/A')}<br/>
    <b>Sucursal:</b> {st.session_state.filtros_globales.get('sucursal', 'N/A')}<br/>
    <b>Familia:</b> {st.session_state.filtros_globales.get('familia', 'TODAS')}<br/>
    <b>Marca:</b> {st.session_state.filtros_globales.get('marca', 'TODAS')}<br/>
    <b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}
    """
    story.append(Paragraph(filtros_text, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    # KPIs PRINCIPALES (si están disponibles)
    if 'k_cur' in locals() or 'k_cur' in globals():
        story.append(Paragraph("INDICADORES CLAVE", heading_style))
        
        # Tabla de KPIs
        kpi_data = [
            ['Métrica', 'Valor'],
            ['Ventas Totales', money_fmt(st.session_state.get('kpi_ventas', 0))],
            ['Utilidad Total', money_fmt(st.session_state.get('kpi_utilidad', 0))],
            ['Margen', pct_fmt(st.session_state.get('kpi_margen', 0))],
            ['Transacciones', num_fmt(st.session_state.get('kpi_txns', 0))]
        ]
        
        kpi_table = Table(kpi_data, colWidths=[3*inch, 2*inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(kpi_table)
        story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    
    # NOTA: Exportar gráficas requeriría capturar cada figura plotly
    # y convertirla a imagen con kaleido
    
    story.append(Paragraph("📊 Dashboard Completo", heading_style))
    story.append(Paragraph(
        "Las gráficas interactivas están disponibles en la versión web del dashboard.",
        styles['Normal']
    ))
    
    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def mostrar_boton_exportar_pdf():
    """Muestra botón de exportar PDF en sidebar"""
    
    with st.expander("📄 Exportar", expanded=False):
        st.markdown("### Exportar Dashboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 PDF Simple", use_container_width=True):
                with st.spinner("Generando PDF..."):
                    pdf_buffer = generar_pdf_dashboard()
                    
                    if pdf_buffer:
                        st.download_button(
                            label="⬇️ Descargar PDF",
                            data=pdf_buffer,
                            file_name=f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
        
        with col2:
            if st.button("📊 Excel", use_container_width=True):
                st.info("Función Excel en desarrollo")
        
        st.caption("💡 El PDF incluye KPIs y resumen. Para gráficas interactivas usa la versión web.")

# ============================================================
# DARK/LIGHT MODE
# ============================================================

def inicializar_tema():
    """Inicializa tema en session_state"""
    if 'tema' not in st.session_state:
        st.session_state.tema = 'dark'  # Por defecto dark


def toggle_tema():
    """Alterna entre dark y light mode"""
    st.session_state.tema = 'light' if st.session_state.tema == 'dark' else 'dark'


def aplicar_tema():
    """Aplica CSS según tema seleccionado"""
    
    inicializar_tema()
    
    if st.session_state.tema == 'light':
        # TEMA CLARO
        tema_css = """
        <style>
            /* Light Mode */
            .stApp {
                background: linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 100%);
            }
            
            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%);
                border-right: 1px solid rgba(100, 116, 139, 0.2);
            }
            
            .kpi-card, .kpi-card-enhanced {
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(241, 245, 249, 0.9) 100%);
                border: 1px solid rgba(100, 116, 139, 0.2);
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                color: #1E293B !important;
            }
            
            .kpi-title {
                color: #64748B !important;
            }
            
            .kpi-value {
                color: #0F172A !important;
            }
            
            .stTabs [data-baseweb="tab-list"] {
                background: linear-gradient(90deg, rgba(255, 255, 255, 0.9) 0%, rgba(241, 245, 249, 0.9) 100%);
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            }
            
            .stTabs [data-baseweb="tab"] {
                color: #475569;
            }
            
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
                color: white !important;
            }
            
            .dataframe {
                background: white;
            }
            
            .dataframe thead tr th {
                background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%) !important;
                color: white !important;
            }
            
            .dataframe tbody tr {
                color: #1E293B;
            }
            
            .dataframe tbody tr:nth-child(even) {
                background-color: #F8FAFC !important;
            }
            
            .dataframe tbody tr:hover {
                background-color: #E0F2FE !important;
            }
            
            h1, h2, h3, h4, h5, h6 {
                color: #0F172A !important;
            }
            
            p, span, div {
                color: #334155 !important;
            }
            
            .hero-section {
                background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
            }
        </style>
        """
    else:
        # TEMA OSCURO (mantener el actual)
        tema_css = ""
    
    st.markdown(tema_css, unsafe_allow_html=True)


def mostrar_toggle_tema():
    """Muestra toggle de tema en sidebar"""
    
    inicializar_tema()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### 🎨 Tema")
    
    with col2:
        tema_actual = st.session_state.tema
        emoji = "🌙" if tema_actual == "dark" else "☀️"
        
        if st.button(emoji, key="toggle_tema_btn"):
            toggle_tema()
            st.rerun()
    
    st.caption(f"Modo: {'Oscuro' if st.session_state.tema == 'dark' else 'Claro'}")






APP_VERSION = "IMDC_v9_MEJORADO_2026-02-11"

# ============================================================
# SISTEMA DE OPTIMIZACIÓN DE PERFORMANCE
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_datos_cached(parquet_glob: str, datos_dir: Path):
    """Caché agresivo de carga de datos - 1 hora"""
    return load_parquet_data(parquet_glob, datos_dir)


@st.cache_data(ttl=1800, show_spinner=False)
def filtrar_datos_cached(df: pd.DataFrame, year: int, m_start: int, m_end: int, 
                         sucursal: str, familia: str, marca: str, include_rem: bool):
    """Caché de filtros para evitar recálculos"""
    return apply_filters(df, year, m_start, m_end, sucursal, familia, marca, include_rem)


@st.cache_data(ttl=1800, show_spinner=False)
def calcular_kpis_cached(df: pd.DataFrame, ventas_con_iva: bool, m2: float):
    """Caché de cálculo de KPIs"""
    return kpis_from_df(df, ventas_con_iva, m2)


@st.cache_data(ttl=1800, show_spinner=False)
def resumen_mensual_cached(df: pd.DataFrame, ventas_con_iva: bool):
    """Caché de resumen mensual"""
    return monthly_summary(df, ventas_con_iva)


@st.cache_data(ttl=3600, show_spinner=False)
def procesar_catalogo_cached(cat_path: Path):
    """Caché de catálogos"""
    if cat_path.exists():
        return pd.read_excel(cat_path, sheet_name="CAT_FAMILIA", engine="openpyxl")
    return pd.DataFrame()


def optimizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Optimiza memoria del DataFrame"""
    if df.empty:
        return df
    
    df_opt = df.copy()
    
    # Convertir object a category cuando tiene pocos valores únicos
    for col in df_opt.select_dtypes(include=['object']).columns:
        num_unique = df_opt[col].nunique()
        num_total = len(df_opt[col])
        
        if num_unique / num_total < 0.5:  # Si menos del 50% son únicos
            df_opt[col] = df_opt[col].astype('category')
    
    # Downcasting de números
    for col in df_opt.select_dtypes(include=['float64']).columns:
        df_opt[col] = pd.to_numeric(df_opt[col], downcast='float')
    
    for col in df_opt.select_dtypes(include=['int64']).columns:
        df_opt[col] = pd.to_numeric(df_opt[col], downcast='integer')
    
    return df_opt


def lazy_load_widget(widget_func, *args, **kwargs):
    """Carga diferida de widgets pesados"""
    placeholder = st.empty()
    
    with placeholder.container():
        with st.spinner("Cargando..."):
            widget_func(*args, **kwargs)


def paginar_dataframe(df: pd.DataFrame, page_size: int = 50, key_prefix: str = ""):
    """Paginación de tablas grandes"""
    
    if df.empty:
        st.warning("No hay datos para mostrar")
        return
    
    total_rows = len(df)
    total_pages = (total_rows - 1) // page_size + 1
    
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col2:
        page = st.number_input(
            f"Página (de {total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1,
            key=f"{key_prefix}_page"
        )
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)
    
    st.dataframe(
        df.iloc[start_idx:end_idx],
        use_container_width=True,
        height=400
    )
    
    st.caption(f"Mostrando {start_idx + 1}-{end_idx} de {total_rows} filas")


# ============================================================
# BOTÓN DE LIMPIAR CACHÉ
# ============================================================

def mostrar_control_cache():
    """Muestra controles de caché en sidebar"""
    
    with st.sidebar.expander("⚡ Optimización", expanded=False):
        st.markdown("### Control de Caché")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Limpiar caché", use_container_width=True):
                st.cache_data.clear()
                st.success("Caché limpiado")
                st.rerun()
        
        with col2:
            if st.button("📊 Ver memoria", use_container_width=True):
                import sys
                cache_info = st.cache_data.get_cache_stats()
                st.info(f"Cache entries: {cache_info}")
        
        # Mostrar tamaño de datos en memoria
        if 'df_all' in st.session_state:
            memory_mb = st.session_state.df_all.memory_usage(deep=True).sum() / 1024**2
            st.caption(f"💾 Datos en memoria: {memory_mb:.1f} MB")



# ============================================================
# Imports para gráficos mejorados
# ============================================================
try:
    from graficos_mejorados import (
        fig_grafica_mensual_mejorada,
        fig_top20_barras_mejoradas,
        fig_treemap_mejorado,
        fig_top_vendedores_mejorada,
        fig_quadrants_mejorada,
        COLORS
    )
    GRAFICOS_MEJORADOS = True
    print("✅ Gráficos mejorados cargados correctamente")
except ImportError:
    print("⚠️  graficos_mejorados.py no encontrado - usando gráficos originales")
    GRAFICOS_MEJORADOS = False

# ------------------------------------------------------------
# Page
# ------------------------------------------------------------
st.set_page_config(page_title="IMDC — Panel Ejecutivo", layout="wide")

# Anti-Translate (Chrome/Google Translate)
components.html(
    """
    <meta name="google" content="notranslate">
    <meta name="robots" content="notranslate">
    <style>
      * { translate: no !important; }
      .notranslate { translate: no !important; }

      /* KPI Card Enhanced con sparkline */
      .kpi-card-enhanced {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(59, 130, 246, 0.03) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 16px;
        padding: 18px 16px;
        min-height: 145px;
        height: auto;
        position: relative;
        overflow: visible;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }
      
      .kpi-card-enhanced:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.25);
        border-color: rgba(59, 130, 246, 0.5);
      }
      
      .kpi-card-enhanced::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 4px; height: 100%;
        background: linear-gradient(180deg, var(--primary-blue), var(--primary-blue-light));
      }
      
      /* Hero Section */
      .hero-section {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        border-radius: 20px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 10px 40px rgba(37, 99, 235, 0.3);
      }
      
      .hero-title {
        font-size: 2rem;
        font-weight: 800;
        color: white;
        margin-bottom: 10px;
      }
      
      .hero-subtitle {
        font-size: 1rem;
        color: rgba(255, 255, 255, 0.8);
      }
      
      /* Filtros avanzados */
      .filter-section {
        background: rgba(37, 99, 235, 0.05);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
      }
      
      /* Iconos para KPIs */
      .kpi-icon {
        font-size: 2rem;
        margin-bottom: 10px;
        opacity: 0.8;
      }
      
      /* Badges de estado */
      .badge-success {
        background: rgba(16, 185, 129, 0.2);
        color: #10B981;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        margin: 5px 0;
      }
      
      .badge-warning {
        background: rgba(245, 158, 11, 0.2);
        color: #F59E0B;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        margin: 5px 0;
      }
      
      .badge-danger {
        background: rgba(239, 68, 68, 0.2);
        color: #EF4444;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        margin: 5px 0;
      }


      /* ============================================ */
      /* DISEÑO INSPIRADO EN TABLEAU/LOOKER/MODE */
      /* ============================================ */
      
      /* Sidebar moderno */
      section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
        border-right: 1px solid rgba(59, 130, 246, 0.2);
      }
      
      /* Botones principales */
      .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        border: none;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        transition: all 0.3s ease;
      }
      
      .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6);
      }
      
      /* Selectbox mejorado */
      .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
      }
      
      /* Tabs estilo Looker */
      .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(90deg, rgba(15, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.8) 100%);
        border-radius: 12px;
        padding: 8px;
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2);
      }
      
      .stTabs [data-baseweb="tab"] {
        height: 55px;
        border-radius: 10px;
        padding: 0 28px;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }
      
      .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        transform: scale(1.05);
      }
      
      /* Dataframes estilo Tableau */
      .dataframe {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
      }
      
      .dataframe thead tr th {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.3), rgba(59, 130, 246, 0.2)) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 14px 12px !important;
      }
      
      .dataframe tbody tr {
        transition: background 0.2s ease;
      }
      
      .dataframe tbody tr:hover {
        background-color: rgba(59, 130, 246, 0.12) !important;
        transform: scale(1.01);
      }
      
      /* Loading spinner personalizado */
      .stSpinner > div {
        border-top-color: #2563EB !important;
      }
      
      /* Métricas estilo Mode */
      [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(59, 130, 246, 0.03) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 12px;
        padding: 16px;
        transition: all 0.3s ease;
      }
      
      [data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.2);
        border-color: rgba(59, 130, 246, 0.5);
      }
      
      /* Info boxes mejorados */
      .stAlert {
        border-radius: 12px;
        border-left: 4px solid #2563EB;
        background: linear-gradient(90deg, rgba(37, 99, 235, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%);
      }
      
      /* Tooltips personalizados */
      [data-baseweb="tooltip"] {
        background: #1E293B !important;
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
      }

    </style>
    <script>
      (function(){
        try {
          document.documentElement.lang = 'es';
          document.documentElement.translate = 'no';
          document.documentElement.setAttribute('translate','no');
          document.body.classList.add('notranslate');
          
          // Forzar atributo translate=no en todos los elementos
          const obs = new MutationObserver(() => {
            document.querySelectorAll('*').forEach(el => {
              if(!el.hasAttribute('translate')) el.setAttribute('translate', 'no');
            });
          });
          obs.observe(document.body, {childList: true, subtree: true});
        } catch(e) {}
      })();
    </script>
    """,
    height=0,
)

# ------------------------------------------------------------
# ------------------------------------------------------------
# Styles - MEJORADOS v2
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      :root {
        --primary-blue: #2563EB;
        --primary-blue-light: #3B82F6;
        --success-green: #10B981;
        --danger-red: #EF4444;
        --warning-amber: #F59E0B;
      }
      
      .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 2rem !important;
        max-width: 100% !important;
      }

      .kpi-card {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(59, 130, 246, 0.03) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 16px;
        padding: 18px 16px;
        min-height: 145px;
        height: auto;
        position: relative;
        overflow: visible;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }
      
      .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.15);
      }
      
      .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 4px; height: 100%;
        background: linear-gradient(180deg, var(--primary-blue), var(--primary-blue-light));
      }
      
      .kpi-title { 
        font-size: 0.8rem; font-weight: 600;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 10px; letter-spacing: 0.3px;
        text-transform: uppercase; line-height: 1.3;
      }
      
      .kpi-value { 
        font-size: 2rem; font-weight: 800; 
        line-height: 1.15; color: #FFFFFF;
        margin-bottom: 8px; white-space: nowrap;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace !important;
        letter-spacing: -0.5px;
      }

      .pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1.5px solid rgba(16, 185, 129, 0.5);
        color: var(--success-green);
        padding: 5px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 700;
        white-space: nowrap;
      }
      
      .pill.red {
        background: rgba(239, 68, 68, 0.15);
        border: 1.5px solid rgba(239, 68, 68, 0.5);
        color: var(--danger-red);
      }
      
      .pill.gray {
        background: rgba(156, 163, 175, 0.15);
        border: 1.5px solid rgba(156, 163, 175, 0.3);
        color: rgba(255, 255, 255, 0.6);
      }

      h3 {
        font-size: 1.25rem !important;
        margin-top: 1.5rem !important;
        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
        padding-bottom: 0.5rem;
      }

      .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(17, 24, 39, 0.5);
        border-radius: 12px;
        padding: 6px;
      }
      
      .stTabs [data-baseweb="tab"] {
        height: 50px; border-radius: 8px;
        padding: 0 24px; font-weight: 600;
        transition: all 0.3s ease;
      }
      
      .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary-blue), var(--primary-blue-light));
        color: white !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
      }

      .dataframe thead tr th {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.2), rgba(59, 130, 246, 0.1)) !important;
        color: #FFFFFF !important; font-weight: 700 !important;
      }
      
      .dataframe tbody tr:nth-child(even) {
        background-color: rgba(255, 255, 255, 0.02) !important;
      }
      
      .dataframe tbody tr:hover {
        background-color: rgba(59, 130, 246, 0.08) !important;
      }

      .tiny { font-size: 0.8rem; opacity: 0.75; }
      .hint { opacity: 0.65; font-size: 0.875rem; }
      
      @media (max-width: 1400px) {
        .kpi-value { font-size: 1.7rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Constantes & paths
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Soporte Streamlit Cloud: si IMDC_DATA_DIR está definido, leer de ahí
import os as _os
_cloud_data_dir = _os.environ.get("IMDC_DATA_DIR", "")

if _cloud_data_dir and Path(_cloud_data_dir).exists():
    OUTPUT_DIR = Path(_cloud_data_dir)
else:
    OUTPUT_DIR = BASE_DIR / "output"

DATOS_DIR = BASE_DIR / "Datos"
PARQUET_GLOB = "*.parquet"  # En cloud acepta cualquier nombre

CATALOGO_SUCURSALES = [
    "CONSOLIDADO",
    "GENERAL",
    "EXPRESS",
    "SAN AGUST",
    "ADELITAS",
    "H ILUSTRES",
]
CANON_VALIDOS = set(CATALOGO_SUCURSALES)

M2_MAP = {
    "GENERAL": 1538,
    "EXPRESS": 369,
    "SAN AGUST": 870,
    "ADELITAS": 348,
    "H ILUSTRES": 100,
    "CONSOLIDADO": 3225,
}

MONTHS_FULL = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}
MONTHS_ABBR = {k: v[:3] for k, v in MONTHS_FULL.items()}

# ------------------------------------------------------------
# Utils (text cleaning / math)
# ------------------------------------------------------------
_ZW_CHARS_RE = re.compile(r"[\u200B-\u200D\u2060\uFEFF]")
_NON_ALNUM_SPACE_RE = re.compile(r"[^A-Z0-9 ]+")
_MULTI_SPACE_RE = re.compile(r"\s+")

def _strip_accents(text: str) -> str:
    nkfd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nkfd if not unicodedata.combining(ch))

def _clean_text_scalar(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return ""
    s = str(v)
    s = (
        s.replace("\u00A0", " ")
         .replace("\u2007", " ")
         .replace("\u202F", " ")
    )
    s = _ZW_CHARS_RE.sub("", s)
    s = _strip_accents(s).upper()
    s = s.replace(".", " ").replace("-", " ").replace("_", " ").replace("/", " ")
    s = _NON_ALNUM_SPACE_RE.sub(" ", s)
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    return s

def _clean_text_series(s: pd.Series) -> pd.Series:
    return s.astype("string").fillna("").map(_clean_text_scalar)


def _normalize_id_series(s: pd.Series) -> pd.Series:
    """Normaliza IDs que a veces vienen como float (1.0) o string ('1.0').
    Regla:
      - si es numérico entero -> '1'
      - si no, deja string limpio
    """
    ss = s.astype("string").fillna("").str.strip()
    # intento numérico
    num = pd.to_numeric(ss.str.replace(",", ".", regex=False), errors="coerce")
    is_int = num.notna() & np.isfinite(num) & (np.abs(num - np.round(num)) < 1e-9)
    out = ss.copy()
    out.loc[is_int] = np.round(num.loc[is_int]).astype("int64").astype("string")
    # limpia cosas tipo '001' -> '1' solo si era numérico
    return out

def normalize_almacen(s: pd.Series) -> pd.Series:
    x = _clean_text_series(s)
    def canon_one(t: str) -> str:
        if "SAN AGUST" in t:
            return "SAN AGUST"
        if "ILUST" in t:
            return "H ILUSTRES"
        if "EXPRES" in t:
            return "EXPRESS"
        if t.startswith("H "):
            return "H ILUSTRES"
        if t in ("GRAL", "GENERAL"):
            return "GENERAL"
        return t
    return x.map(canon_one)

def safe_div(a: float, b: float) -> float:
    try:
        a = float(a); b = float(b)
        if b == 0 or math.isnan(b) or math.isinf(b):
            return float("nan")
        return a / b
    except Exception:
        return float("nan")

def yoy(cur: float, prev: float) -> float:
    r = safe_div(cur, prev)
    if isinstance(r, float) and (math.isnan(r) or math.isinf(r)):
        return float("nan")
    return r - 1.0

def money_fmt(x: float) -> str:
    """Formato de moneda - siempre con 1 decimal en millones"""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "$0.0"
    
    abs_x = abs(x)
    sign = "-" if x < 0 else ""
    
    # Millones: SIEMPRE 1 decimal
    if abs_x >= 1_000_000:
        return f"{sign}${abs_x/1_000_000:.1f}M"
    # Miles
    elif abs_x >= 100_000:
        return f"{sign}${abs_x/1_000:,.0f}K"
    elif abs_x >= 10_000:
        return f"{sign}${abs_x/1_000:,.1f}K"
    elif abs_x >= 1_000:
        return f"{sign}${abs_x:,.0f}"
    else:
        if abs(x - round(x)) < 1e-9:
            return f"{sign}${abs_x:,.0f}"
        return f"{sign}${abs_x:,.1f}"


def pct_fmt(x: float) -> str:
    """Formato de porcentaje mejorado"""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    
    pct = x * 100
    
    if abs(pct) < 1:
        return f"{pct:.2f}%"
    elif abs(pct - round(pct)) < 0.01:
        return f"{pct:.0f}%"
    else:
        return f"{pct:.1f}%"


def num_fmt(x: float) -> str:
    """Formato de números - con 1 decimal en millones"""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "0"
    
    abs_x = abs(x)
    sign = "-" if x < 0 else ""
    
    if abs_x >= 1_000_000:
        return f"{sign}{abs_x/1_000_000:.1f}M"
    elif abs_x >= 100_000:
        return f"{sign}{abs_x/1_000:,.0f}K"
    elif abs_x >= 10_000:
        return f"{sign}{abs_x/1_000:,.1f}K"
    elif abs_x >= 1_000:
        return f"{sign}{abs_x:,.0f}"
    else:
        if abs(x - round(x)) < 1e-9:
            return f"{sign}{abs_x:.0f}"
        return f"{sign}{abs_x:.1f}"


# ------------------------------------------------------------
# UI epoch (para reset de widgets si hace falta)
# ------------------------------------------------------------
def _ui_epoch() -> int:
    if "ui_epoch" not in st.session_state:
        st.session_state["ui_epoch"] = 0
    return int(st.session_state["ui_epoch"])

def _bump_ui_epoch():
    st.session_state["ui_epoch"] = _ui_epoch() + 1

def make_key(name: str) -> str:
    return f"{name}__e{_ui_epoch()}"

# ------------------------------------------------------------
# Catálogo Familias (Opción B)
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_cat_familia() -> Optional[pd.DataFrame]:
    """
    Busca en ./Datos un catálogo de familias. Soporta:
    - CAT_FAMILIA.xlsx (hoja CAT_FAMILIA)
    - CAT_FAMILIA.csv
    Devuelve DF con columnas: Familia_ID (string), Familia_Nombre (string)
    """
    candidates = [
        DATOS_DIR / "Datos.xlsx",          # (build_anual.py) catálogo maestro
        DATOS_DIR / "datos.xlsx",
        DATOS_DIR / "CAT_FAMILIA.xlsx",
        DATOS_DIR / "cat_familia.xlsx",
        DATOS_DIR / "CAT_FAMILIA.csv",
        DATOS_DIR / "cat_familia.csv",
    ]
    fp = next((p for p in candidates if p.exists()), None)
    if fp is None:
        return None

    try:
        if fp.suffix.lower() == ".xlsx":
            df = pd.read_excel(fp, sheet_name="CAT_FAMILIA")
        else:
            df = pd.read_csv(fp, encoding="utf-8", low_memory=False)
    except Exception:
        # fallback: primer sheet o lectura simple
        try:
            if fp.suffix.lower() == ".xlsx":
                df = pd.read_excel(fp)
            else:
                df = pd.read_csv(fp, low_memory=False)
        except Exception:
            return None

    cols = {c: _clean_text_scalar(c) for c in df.columns}
    df = df.rename(columns={c: cols[c] for c in df.columns})

    # heurística: ID y nombre
    id_col = None
    name_col = None
    for c in df.columns:
        cc = _clean_text_scalar(c)
        if cc in ("ID", "IDFAMILIA", "ID FAMILIA", "FAMILIAID", "ID_FAMILIA"):
            id_col = c
        if cc in ("FAMILIA", "NOMBRE", "NOMBRE FAMILIA", "DESCRIPCION", "DESC", "DESCFAMILIA", "DESC FAMILIA"):
            name_col = c
    # si no detectó, usa 1a y 2a columna si hay al menos 2
    if id_col is None and len(df.columns) >= 1:
        id_col = df.columns[0]
    if name_col is None and len(df.columns) >= 2:
        name_col = df.columns[1]

    out = pd.DataFrame()
    out["Familia_ID"] = _normalize_id_series(df[id_col])
    out["Familia_Nombre"] = df[name_col].astype("string").str.strip()
    out = out.dropna(subset=["Familia_ID", "Familia_Nombre"])
    out = out[out["Familia_ID"] != ""]
    return out

def attach_familia_nombre(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza el tema de Familias para que la web sea robusta ante 2 escenarios:

    ESCENARIO A (antes):
      - "Familia" trae el ID (ej. 11) o viene vacío y existe algún ID alterno.
      - Se usa el catálogo (Datos.xlsx hoja CAT_FAMILIA) para obtener el nombre.

    ESCENARIO B (nuevo, tu ajuste en Parquet):
      - "ID Familia" trae el ID (ej. 11)
      - "Familia" YA trae el nombre (ej. PINTURA)
      - En este caso NO debemos tratar "Familia" como ID porque rompe el mapeo y todo cae en OTROS.

    Salida:
      - Familia_ID (string)
      - Familia_Nombre (string)
    """
    if df is None or df.empty:
        df["Familia_ID"] = ""
        df["Familia_Nombre"] = "SIN FAMILIA"
        return df

    # ------------------------------------------------------------
    # Detectar columna ID (prioridad alta a "ID Familia")
    # ------------------------------------------------------------
    id_candidates = [
        "ID Familia", "ID_FAMILIA", "ID FAMILIA", "IDFAMILIA",
        "Familia_ID", "FamiliaID", "Cse_prod",
    ]
    name_candidates = ["Familia", "Familia_Nombre", "FAMILIA"]

    id_col = next((c for c in id_candidates if c in df.columns), None)
    name_col = next((c for c in name_candidates if c in df.columns), None)

    cat = load_cat_familia()

    # ------------------------------------------------------------
    # Helper: decide si una serie "parece ID" (numérica) o "parece nombre"
    # ------------------------------------------------------------
    def _is_mostly_numeric_like(s: pd.Series, thr: float = 0.80) -> bool:
        ss = s.astype("string").fillna("").str.strip()
        nn = ss.replace("", pd.NA).dropna()
        if len(nn) == 0:
            return False
        numlike = nn.str.fullmatch(r"\d+(?:\.0+)?").fillna(False)
        return float(numlike.mean()) >= float(thr)

    # ------------------------------------------------------------
    # Caso 1: tenemos ID explícito ("ID Familia", etc.)
    # ------------------------------------------------------------
    if id_col is not None:
        df["Familia_ID"] = _normalize_id_series(df[id_col])

        # Si además existe una columna de nombre ("Familia") y NO parece ID, úsala tal cual.
        if name_col is not None and name_col != id_col and not _is_mostly_numeric_like(df[name_col]):
            df["Familia_Nombre"] = df[name_col].astype("string").fillna("").str.strip()
            df["Familia_Nombre"] = df["Familia_Nombre"].replace("", pd.NA).fillna("SIN FAMILIA")
            return df

        # Si no, intenta mapear por catálogo
        if cat is None or cat.empty:
            df["Familia_Nombre"] = df["Familia_ID"].replace("", pd.NA).fillna("SIN FAMILIA")
            return df

        m = dict(zip(cat["Familia_ID"].astype("string"), cat["Familia_Nombre"].astype("string")))
        df["Familia_Nombre"] = df["Familia_ID"].map(m).astype("string")
        df["Familia_Nombre"] = df["Familia_Nombre"].fillna("OTROS")
        df.loc[df["Familia_ID"].eq(""), "Familia_Nombre"] = "SIN FAMILIA"
        return df

    # ------------------------------------------------------------
    # Caso 2: NO hay ID explícito. Usa "Familia" como:
    #   - ID si parece numérica
    #   - nombre si parece texto
    # ------------------------------------------------------------
    if name_col is None:
        df["Familia_ID"] = ""
        df["Familia_Nombre"] = "SIN FAMILIA"
        return df

    if _is_mostly_numeric_like(df[name_col]):
        # Trata "Familia" como ID
        df["Familia_ID"] = _normalize_id_series(df[name_col])
        if cat is None or cat.empty:
            df["Familia_Nombre"] = df["Familia_ID"].replace("", pd.NA).fillna("SIN FAMILIA")
            return df
        m = dict(zip(cat["Familia_ID"].astype("string"), cat["Familia_Nombre"].astype("string")))
        df["Familia_Nombre"] = df["Familia_ID"].map(m).astype("string").fillna("OTROS")
        df.loc[df["Familia_ID"].eq(""), "Familia_Nombre"] = "SIN FAMILIA"
        return df

    # Trata "Familia" como NOMBRE
    df["Familia_Nombre"] = df[name_col].astype("string").fillna("").str.strip()
    df["Familia_Nombre"] = df["Familia_Nombre"].replace("", pd.NA).fillna("SIN FAMILIA")

    # Opcional: si existe catálogo, intenta derivar Familia_ID por nombre (reverse map)
    if cat is not None and not cat.empty:
        # normaliza nombre para matching robusto
        cat2 = cat.copy()
        cat2["_NORM"] = _clean_text_series(cat2["Familia_Nombre"])
        rev = dict(zip(cat2["_NORM"].astype("string"), cat2["Familia_ID"].astype("string")))
        df["Familia_ID"] = _clean_text_series(df["Familia_Nombre"]).map(rev).astype("string").fillna("")
    else:
        df["Familia_ID"] = ""

    return df

    df["Familia_ID"] = _normalize_id_series(df[fam_col])
    cat = load_cat_familia()
    if cat is None or cat.empty:
        # fallback: mostrar ID como "nombre"
        df["Familia_Nombre"] = df["Familia_ID"].replace("", pd.NA).fillna("SIN FAMILIA")
        return df

    m = dict(zip(cat["Familia_ID"].astype("string"), cat["Familia_Nombre"].astype("string")))
    df["Familia_Nombre"] = df["Familia_ID"].map(m).astype("string")
    df["Familia_Nombre"] = df["Familia_Nombre"].fillna("OTROS")
    # Si viene vacío, marcarlo explícitamente
    df.loc[df["Familia_ID"].eq(""), "Familia_Nombre"] = "SIN FAMILIA"
    return df

# ------------------------------------------------------------
# Anti-duplicado / Ventas CON IVA
# ------------------------------------------------------------
def _safe_total_per_key(df: pd.DataFrame, col: str, key: str) -> pd.Series:
    """
    Suma segura por documento:
      - si el total está repetido por línea, toma 1 vez por doc
      - si no está repetido, suma normal
    """
    g = df.groupby(key)[col]
    size = g.size()
    nun = g.nunique(dropna=False)
    first = g.first()
    summ = g.sum(min_count=1)

    rep = (nun == 1) & (size > 1)
    approx = (summ - first * size).abs() <= (first.abs() * 1e-9 + 1e-6)
    rep = rep & approx

    out = summ.copy()
    out.loc[rep] = first.loc[rep]
    return out

def add_total_alloc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Crea Total_alloc:
      - Si Total ya viene por línea (NO repetido por doc) -> Total_alloc = Total
      - Si Total viene repetido por doc -> prorratea vía Sub Total (Factor IVA)
    Requiere DOC_KEY.
    """
    if df.empty:
        df["Total_alloc"] = 0.0
        return df

    if "DOC_KEY" not in df.columns:
        df["Total_alloc"] = pd.to_numeric(df.get("Total", 0.0), errors="coerce").fillna(0.0)
        return df

    total_col = "Total"
    sub_col = "Sub Total"
    if total_col not in df.columns:
        df["Total_alloc"] = 0.0
        return df
    if sub_col not in df.columns:
        df[sub_col] = 0.0

    df[total_col] = pd.to_numeric(df[total_col], errors="coerce").fillna(0.0)
    df[sub_col] = pd.to_numeric(df[sub_col], errors="coerce").fillna(0.0)

    # Detecta si Total está repetido por doc
    nun = df.groupby("DOC_KEY")[total_col].nunique(dropna=False)
    rep_share = float((nun == 1).mean()) if len(nun) else 1.0

    if rep_share >= 0.90:
        # Casi todo repetido -> prorratear
        total_doc = df.groupby("DOC_KEY")[total_col].first()
        sub_doc = df.groupby("DOC_KEY")[sub_col].sum().replace(0, np.nan)
        factor = (total_doc / sub_doc).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["Total_alloc"] = (df[sub_col] * df["DOC_KEY"].map(factor)).astype(float)
    else:
        # Total ya viene a nivel línea -> usar directo
        df["Total_alloc"] = df[total_col].astype(float)

    return df

# ------------------------------------------------------------
# Carga
# ------------------------------------------------------------
CSV_USECOLS = [
    "Año","Mes","Hora",
    "Almacen","Vendedor","Cliente","Tipo",
    "Documento",
    "Familia","Marca",
    "Cantidad","Costo Entrada",
    "Sub Total","Total",
    "Descuento $","Utilidad $",
    "es_rem","factura_del_dia","nota_facturada","cancelado",
]

def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    # Asegurar columnas clave aunque falten
    for c in ["Descuento $","Utilidad $","es_rem","factura_del_dia","nota_facturada","cancelado"]:
        if c not in df.columns:
            df[c] = 0
    return df

def _coerce_base_types(df: pd.DataFrame) -> pd.DataFrame:
    for c in ["Año","Mes"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["Sub Total","Total","Descuento $","Utilidad $"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in ["es_rem","factura_del_dia","nota_facturada","cancelado"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

@st.cache_data(show_spinner=False)
def load_all() -> Tuple[pd.DataFrame, List[int], List[str], List[str]]:
    """
    Lee todos los parquets en ./output/cedro_*.parquet
    Devuelve: df_all, years, familias (display), marcas
    """
    files = sorted(OUTPUT_DIR.glob(PARQUET_GLOB))
    
    if not files:
        return pd.DataFrame(), [], [], []

    dfs = []
    for fp in files:
        try:
            # leer todas las columnas disponibles necesarias (intersección)
            # Pandas requiere pyarrow en el entorno del usuario (ya lo tienen en Windows)
            df = pd.read_parquet(fp)
        except Exception:
            continue
        df = _ensure_cols(df)
        df = _coerce_base_types(df)

        # Canon almacen
        if "Almacen" in df.columns:
            df["Almacen_CANON"] = normalize_almacen(df["Almacen"])
        else:
            df["Almacen_CANON"] = ""

        # Tipo2 (CONTADO/CREDITO)
        if "Tipo" in df.columns:
            t = df["Tipo"].astype("string").fillna("")
            df["Tipo2"] = np.where(_clean_text_series(t).str.contains("CRED", na=False), "CREDITO", "CONTADO")
        else:
            df["Tipo2"] = "CONTADO"

        # Documento string
        if "Documento" in df.columns:
            df["Documento"] = df["Documento"].astype("string").fillna("").str.strip()
        else:
            df["Documento"] = ""

        # DOC_KEY real: Año|Mes|Almacen|Documento|Tipo2
        df["DOC_KEY"] = (
            df["Año"].astype("string").fillna("") + "|" +
            df["Mes"].astype("string").fillna("") + "|" +
            df["Almacen_CANON"].astype("string").fillna("") + "|" +
            df["Documento"].astype("string").fillna("") + "|" +
            df["Tipo2"].astype("string").fillna("")
        )

        # Utilidad (SIN IVA) por línea: preferir "Utilidad $" -> columna "Utilidad"
        df["Utilidad"] = pd.to_numeric(df.get("Utilidad $", 0.0), errors="coerce").fillna(0.0)

        # Total_alloc (CON IVA) correcto
        df = add_total_alloc(df)

        # Flags inteligentes si faltan
        if "es_rem" not in df.columns:
            df["es_rem"] = 0
        df["incluye_base"] = 1
        df["incluye_kpi_rem_on"] = 1
        df["incluye_kpi_rem_off"] = np.where(df["es_rem"].astype(int) == 1, 0, 1)

        # Catálogo familia
        df = attach_familia_nombre(df)

        # Marca normalizada texto (display)
        if "Marca" in df.columns:
            df["Marca"] = df["Marca"].astype("string").fillna("").str.strip()
            df["Marca_Nombre"] = df["Marca"].replace("", pd.NA).fillna("SIN MARCA")
        else:
            df["Marca_Nombre"] = "SIN MARCA"

        # Vendedor normalizado (display)
        if "Vendedor" in df.columns:
            df["Vendedor"] = df["Vendedor"].astype("string").fillna("").str.strip()
            df["Vendedor_Nombre"] = df["Vendedor"].replace("", pd.NA).fillna("SIN VENDEDOR")
        else:
            df["Vendedor_Nombre"] = "SIN VENDEDOR"

        # SKU key (para SKUs por ticket)
        sku_col = None
        for cand in ["Articulo", "Cve_prod", "SKU", "Clave", "Codbar", "Descripcion"]:
            if cand in df.columns:
                sku_col = cand
                break
        if sku_col:
            df["SKU_KEY"] = df[sku_col].astype("string").fillna("").str.strip()
            df["SKU_KEY"] = df["SKU_KEY"].replace("", pd.NA)
        else:
            df["SKU_KEY"] = pd.NA

        dfs.append(df)

    if not dfs:
        return pd.DataFrame(), [], [], []

    df_all = pd.concat(dfs, ignore_index=True)

    # Limpieza: algunas filas traen "Familia_Nombre" como número (ej. 95, 106.0) por catálogos incompletos.
    # Para evitar "basura" en filtros/visuales, las marcamos como NA (siguen contando en TODAS, pero no aparecen como opción).
    fam_num_mask = (
        df_all["Familia_Nombre"].astype(str).str.strip()
        .str.fullmatch(r"\d+(?:\.0+)?")
        .fillna(False)
    )
    if fam_num_mask.any():
        df_all.loc[fam_num_mask, "Familia_Nombre"] = pd.NA

    years = sorted(df_all["Año"].dropna().astype(int).unique().tolist()) if "Año" in df_all.columns else []
    familias = sorted(df_all["Familia_Nombre"].dropna().astype(str).unique().tolist()) if "Familia_Nombre" in df_all.columns else []
    # Limpieza: evita "basura" numérica en el selector (IDs sin catálogo)
    familias = [x for x in familias if not re.fullmatch(r"\d+(?:\.0+)?", x.strip())]
    marcas = sorted(df_all["Marca_Nombre"].dropna().astype(str).unique().tolist()) if "Marca_Nombre" in df_all.columns else []

    return df_all, years, familias, marcas

# ------------------------------------------------------------
# Filters
# ------------------------------------------------------------
def apply_filters(df: pd.DataFrame,
                  year: int,
                  m_start: int,
                  m_end: int,
                  sucursal: str,
                  familia: str,
                  marca: str,
                  include_rem: bool,
                  excluir_credito: bool = False) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    out = out[out["Año"].astype(int) == int(year)]
    out = out[out["Mes"].astype(int).between(int(m_start), int(m_end))]

    if sucursal != "CONSOLIDADO":
        out = out[out["Almacen_CANON"] == sucursal]

    if familia != "TODAS":
        out = out[out["Familia_Nombre"] == familia]

    if marca != "TODAS":
        out = out[out["Marca_Nombre"] == marca]

    # REM filter
    if not include_rem and "es_rem" in out.columns:
        out = out[out["es_rem"].astype(int) == 0]
    
    # Excluir crédito filter
    if excluir_credito and "Tipo2" in out.columns:
        out = out[out["Tipo2"] == "CONTADO"]

    return out

def apply_filters_year(df: pd.DataFrame,
                       year: int,
                       sucursal: str,
                       familia: str,
                       marca: str,
                       include_rem: bool,
                       excluir_credito: bool = False) -> pd.DataFrame:
    """Mismos filtros pero sin recortar meses (para histórico anual)."""
    return apply_filters(df, year, 1, 12, sucursal, familia, marca, include_rem, excluir_credito)

def _ventas_col(ventas_con_iva: bool) -> str:
    return "Total_alloc" if ventas_con_iva else "Sub Total"

def count_vendedores_activos(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    s = df.get("Vendedor_Nombre", pd.Series([], dtype="string")).astype("string").fillna("").str.strip()
    s = s.replace("TODOS", "", regex=False).replace("", pd.NA)
    return int(s.dropna().nunique())

# ------------------------------------------------------------
# KPIs core
# ------------------------------------------------------------
def kpis_from_df(df: pd.DataFrame, ventas_con_iva: bool, m2: float) -> Dict[str, float]:
    if df.empty:
        return dict(
            ventas=0.0, ventas_cont=0.0, ventas_cred=0.0,
            utilidad=0.0, subtotal=0.0, margen=np.nan,
            txns=0.0, ticket=np.nan,
            descdol=0.0, descpct=np.nan,
            vendedores=0.0,
            ventas_m2=np.nan, utilidad_m2=np.nan,
        )
    ventas_col = _ventas_col(ventas_con_iva)
    ventas = float(df[ventas_col].sum())
    ventas_cont = float(df.loc[df["Tipo2"]=="CONTADO", ventas_col].sum()) if "Tipo2" in df.columns else ventas
    ventas_cred = float(df.loc[df["Tipo2"]=="CREDITO", ventas_col].sum()) if "Tipo2" in df.columns else 0.0

    subtotal = float(df["Sub Total"].sum()) if "Sub Total" in df.columns else 0.0
    utilidad = float(df["Utilidad"].sum()) if "Utilidad" in df.columns else 0.0
    margen = safe_div(utilidad, subtotal)

    txns = float(df["DOC_KEY"].nunique()) if "DOC_KEY" in df.columns else 0.0
    ticket = safe_div(ventas, txns) if ventas_con_iva else safe_div(subtotal, txns)

    descdol = float(df["Descuento $"].sum()) if "Descuento $" in df.columns else 0.0
    descpct = safe_div(descdol, subtotal) if subtotal > 0 else float("nan")

    vend = float(count_vendedores_activos(df))
    ventas_m2 = safe_div(ventas, m2) if m2 else float("nan")
    utilidad_m2 = safe_div(utilidad, m2) if m2 else float("nan")

    return dict(
        ventas=ventas, ventas_cont=ventas_cont, ventas_cred=ventas_cred,
        utilidad=utilidad, subtotal=subtotal, margen=margen,
        txns=txns, ticket=ticket,
        descdol=descdol, descpct=descpct,
        vendedores=vend,
        ventas_m2=ventas_m2, utilidad_m2=utilidad_m2,
    )

# ------------------------------------------------------------
# KPI cards
# ------------------------------------------------------------
def _pill_pct(yv: float) -> Tuple[str, str]:
    if yv != yv:
        return ("pill gray", "—")
    up = yv >= 0
    cls = "pill" if up else "pill red"
    arrow = "▲" if up else "▼"
    return (cls, f"{arrow} {pct_fmt(abs(yv))} vs LY")

def _pill_pp(pp_points: float) -> Tuple[str, str]:
    # pp_points viene en puntos (ej. 1.25 = 1.25pp)
    if pp_points != pp_points:
        return ("pill gray", "—")
    up = pp_points >= 0
    cls = "pill" if up else "pill red"
    arrow = "▲" if up else "▼"
    return (cls, f"{arrow} {abs(pp_points):,.2f}".rstrip("0").rstrip(".") + " pp vs LY")


# ============================================================
# NUEVAS FUNCIONES PARA WIDGETS AVANZADOS
# ============================================================

def create_sparkline(values: list, color: str = "#10B981") -> str:
    """Genera SVG de sparkline para KPIs"""
    if not values or len(values) < 2:
        return ""
    
    width, height = 60, 20
    max_val = max(values) if max(values) > 0 else 1
    min_val = min(values)
    
    # Normalizar valores
    normalized = [(v - min_val) / (max_val - min_val) if max_val > min_val else 0.5 for v in values]
    
    # Crear puntos
    points = []
    step = width / (len(values) - 1)
    for i, v in enumerate(normalized):
        x = i * step
        y = height - (v * height * 0.8) - (height * 0.1)
        points.append(f"{x},{y}")
    
    polyline = " ".join(points)
    
    svg_code = f'<svg width="{width}" height="{height}" style="margin-left: 10px;">'
    svg_code += f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    svg_code += '</svg>'
    
    return svg_code


def kpi_card_with_sparkline(title: str, value: str, pill_text: str, pill_cls: str, 
                             sparkline_values: list = None, trend_color: str = "#10B981"):
    """KPI card mejorado con sparkline"""
    sparkline_svg = create_sparkline(sparkline_values, trend_color) if sparkline_values else ""
    
    st.markdown(
        f"""
        <div class="kpi-card-enhanced notranslate" translate="no">
          <div class="kpi-title notranslate" translate="no">{title}</div>
          <div style="display: flex; align-items: center;">
            <div class="kpi-value notranslate" translate="no">{value}</div>
            {sparkline_svg}
          </div>
          <div class="{pill_cls} notranslate" translate="no">{pill_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def create_gauge_chart(value: float, max_value: float, title: str, threshold: float = None) -> go.Figure:
    """Crea un gráfico tipo gauge/medidor"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 16, 'color': '#F8FAFC'}},
        number = {'suffix': "%", 'font': {'size': 28, 'color': '#FFFFFF'}},
        gauge = {
            'axis': {'range': [None, max_value * 100], 'tickcolor': '#F8FAFC'},
            'bar': {'color': "#10B981" if not threshold or value >= threshold else "#F59E0B"},
            'bgcolor': "rgba(255,255,255,0.1)",
            'borderwidth': 2,
            'bordercolor': "rgba(59, 130, 246, 0.3)",
            'steps': [
                {'range': [0, (max_value * 100) * 0.5], 'color': "rgba(239, 68, 68, 0.2)"},
                {'range': [(max_value * 100) * 0.5, (max_value * 100) * 0.8], 'color': "rgba(245, 158, 11, 0.2)"},
                {'range': [(max_value * 100) * 0.8, max_value * 100], 'color': "rgba(16, 185, 129, 0.2)"}
            ],
            'threshold': {
                'line': {'color': "#EF4444", 'width': 4},
                'thickness': 0.75,
                'value': threshold * 100 if threshold else (max_value * 100) * 0.8
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0, 0, 0, 0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        font={'color': "#F8FAFC"},
        height=200,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig


def create_heatmap_performance(df_summary: pd.DataFrame) -> go.Figure:
    """Crea heatmap de rendimiento mensual"""
    
    # Calcular % de objetivo (asumiendo objetivo = promedio * 1.1)
    if df_summary.empty:
        return go.Figure()
    
    df = df_summary.copy()
    avg_ventas = df['Ventas_Total'].mean()
    df['Performance'] = (df['Ventas_Total'] / avg_ventas) * 100
    
    # Crear matriz para heatmap
    z_values = [df['Performance'].tolist()]
    x_labels = df['Mes'].tolist()
    
    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=x_labels,
        y=['Rendimiento'],
        colorscale=[
            [0, '#EF4444'],      # Rojo
            [0.5, '#F59E0B'],    # Amarillo
            [0.8, '#10B981'],    # Verde claro
            [1, '#059669']       # Verde oscuro
        ],
        text=[[f"{v:.0f}%" for v in z_values[0]]],
        texttemplate="%{text}",
        textfont={"size": 12, "color": "white"},
        hovertemplate='<b>%{x}</b><br>Rendimiento: %{z:.1f}%<extra></extra>',
        showscale=True,
        colorbar=dict(
            title="% vs Promedio",
            ticksuffix="%",
            tickfont=dict(color='#F8FAFC')
        )
    ))
    
    fig.update_layout(
        title=dict(
            text='<b>📊 Rendimiento Mensual vs Promedio</b>',
            font=dict(size=16, color='#F8FAFC'),
            x=0.02
        ),
        paper_bgcolor='rgba(0, 0, 0, 0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        font=dict(color='#F8FAFC'),
        height=150,
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(side='bottom', tickfont=dict(size=10)),
        yaxis=dict(showticklabels=False)
    )
    
    return fig


def create_waterfall_chart(k_cur: dict, k_prev: dict) -> go.Figure:
    """Crea gráfica waterfall de cambios en utilidad"""
    
    inicial = k_prev.get('utilidad', 0)
    final = k_cur.get('utilidad', 0)
    delta = final - inicial
    
    # Componentes del cambio (simplificado)
    # En producción, estos vendrían de análisis detallado
    componentes = {
        'Inicial': inicial,
        'Volumen': delta * 0.4,
        'Margen': delta * 0.3,
        'Eficiencia': delta * 0.3,
        'Final': final
    }
    
    fig = go.Figure(go.Waterfall(
        name = "Utilidad",
        orientation = "v",
        measure = ["absolute", "relative", "relative", "relative", "total"],
        x = list(componentes.keys()),
        y = list(componentes.values()),
        text = [money_fmt(v) for v in componentes.values()],
        textposition = "outside",
        connector = {"line":{"color":"rgba(255, 255, 255, 0.3)"}},
        increasing = {"marker":{"color":"#10B981"}},
        decreasing = {"marker":{"color":"#EF4444"}},
        totals = {"marker":{"color":"#2563EB"}}
    ))
    
    fig.update_layout(
        title=dict(
            text='<b>💰 Evolución de Utilidad (YoY)</b>',
            font=dict(size=16, color='#F8FAFC'),
            x=0.02
        ),
        paper_bgcolor='rgba(0, 0, 0, 0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        font=dict(color='#F8FAFC'),
        showlegend=False,
        height=300,
        margin=dict(l=60, r=60, t=60, b=60),
        xaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.06)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.06)', tickformat='$,.0f')
    )
    
    return fig


def create_bullet_chart(actual: float, target: float, title: str) -> str:
    """Crea un bullet chart HTML/CSS"""
    
    pct = (actual / target * 100) if target > 0 else 0
    color = "#10B981" if pct >= 100 else "#F59E0B" if pct >= 80 else "#EF4444"
    
    return f"""
    <div style="margin: 10px 0;">
        <div style="font-size: 0.85rem; color: rgba(255,255,255,0.7); margin-bottom: 5px;">
            {title}
        </div>
        <div style="background: rgba(255,255,255,0.1); border-radius: 10px; height: 20px; position: relative; overflow: hidden;">
            <div style="background: {color}; width: {min(pct, 100)}%; height: 100%; border-radius: 10px; transition: width 0.3s ease;"></div>
            <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; color: white;">
                {money_fmt(actual)} / {money_fmt(target)} ({pct:.0f}%)
            </div>
        </div>
    </div>
    """

def kpi_card(title: str, value: str, pill_text: str, pill_cls: str):
    st.markdown(
        f"""
        <div class="kpi-card notranslate" translate="no">
          <div class="kpi-title notranslate" translate="no">{title}</div>
          <div class="kpi-value notranslate" translate="no">{value}</div>
          <div class="{pill_cls} notranslate" translate="no">{pill_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ------------------------------------------------------------
# Tablas: formato global + YoY flechas
# ------------------------------------------------------------
def _arrow_color(x: float) -> str:
    if x != x:
        return "color: rgba(255,255,255,0.55);"
    return "color: #18A957; font-weight: 900;" if x >= 0 else "color: #D64545; font-weight: 900;"

def _arrow_str_pct(x: float) -> str:
    if x != x:
        return "—"
    arrow = "▲" if x >= 0 else "▼"
    return f"{arrow} {pct_fmt(abs(x))}"

def _arrow_str_pp(pp_points: float) -> str:
    if pp_points != pp_points:
        return "—"
    arrow = "▲" if pp_points >= 0 else "▼"
    return f"{arrow} {abs(pp_points):,.2f}".rstrip("0").rstrip(".") + " pp"

def render_table(df: pd.DataFrame,
                 money_cols: List[str] = None,
                 pct_cols: List[str] = None,
                 int_cols: List[str] = None,
                 yoy_pct_cols: List[str] = None,
                 yoy_pp_cols: List[str] = None,
                 height: int = 420):
    money_cols = money_cols or []
    pct_cols = pct_cols or []
    int_cols = int_cols or []
    yoy_pct_cols = yoy_pct_cols or []
    yoy_pp_cols = yoy_pp_cols or []

    sty = df.style

    fmt_map = {}
    for c in money_cols:
        if c in df.columns:
            fmt_map[c] = money_fmt
    for c in pct_cols:
        if c in df.columns:
            fmt_map[c] = lambda x: pct_fmt(x) if pd.notna(x) else "—"
    for c in int_cols:
        if c in df.columns:
            fmt_map[c] = lambda x: f"{int(x):,}" if pd.notna(x) else "0"

    # YoY columns displayed as arrows + small font
    for c in yoy_pct_cols:
        if c in df.columns:
            fmt_map[c] = _arrow_str_pct
            sty = sty.applymap(lambda v: _arrow_color(v) + "font-size: 0.82rem;", subset=[c])
    for c in yoy_pp_cols:
        if c in df.columns:
            fmt_map[c] = _arrow_str_pp
            sty = sty.applymap(lambda v: _arrow_color(v) + "font-size: 0.82rem;", subset=[c])

    if fmt_map:
        sty = sty.format(fmt_map, na_rep="—")

    st.dataframe(sty, use_container_width=True, height=height)

# ------------------------------------------------------------
# Agregados mensuales (12 meses) + YoY
# ------------------------------------------------------------
def monthly_summary(df_year: pd.DataFrame, ventas_con_iva: bool) -> pd.DataFrame:
    """
    Devuelve DF con meses 1..12 aunque no existan filas:
      MesNum, Mes, Ventas_Cont, Ventas_Cred, Ventas_Total, Utilidad, SubTotal, Margen, TXNS, Ticket, DescPct, Vendedores
    """
    base = pd.DataFrame({"MesNum": list(range(1, 13))})
    if df_year.empty:
        out = base.copy()
        out["Mes"] = out["MesNum"].map(MONTHS_FULL)
        # IMPORTANTE: Ordenar ascendente para que más reciente esté a la derecha
        out = out.sort_values("MesNum", ascending=True)
        for c in ["Ventas_Cont","Ventas_Cred","Ventas_Total","Utilidad","SubTotal","Margen","TXNS","Ticket","DescPct","Vendedores"]:
            out[c] = 0.0
        out["Margen"] = np.nan
        out["Ticket"] = np.nan
        out["DescPct"] = np.nan
        return out

    ventas_col = _ventas_col(ventas_con_iva)

    g_type = (
        df_year.groupby(["Mes","Tipo2"], observed=True)
              .agg(Ventas=(ventas_col,"sum"), SubTotal=("Sub Total","sum"))
              .reset_index()
    )
    pv = g_type.pivot(index="Mes", columns="Tipo2", values="Ventas").fillna(0.0)
    v_cont = pv.get("CONTADO", pd.Series(0.0, index=pv.index))
    v_cred = pv.get("CREDITO", pd.Series(0.0, index=pv.index))

    g = (
        df_year.groupby("Mes", observed=True)
              .agg(
                  Utilidad=("Utilidad","sum"),
                  SubTotal=("Sub Total","sum"),
                  DescDol=("Descuento $","sum"),
                  TXNS=("DOC_KEY","nunique"),
                  Vendedores=("Vendedor_Nombre", lambda s: s.astype("string").fillna("").str.strip().replace("TODOS","").replace("", pd.NA).dropna().nunique())
              )
              .reset_index()
              .set_index("Mes")
    )

    out = base.copy()
    out["Ventas_Cont"] = out["MesNum"].map(v_cont).fillna(0.0)
    out["Ventas_Cred"] = out["MesNum"].map(v_cred).fillna(0.0)
    out["Ventas_Total"] = out["Ventas_Cont"] + out["Ventas_Cred"]
    out["Utilidad"] = out["MesNum"].map(g["Utilidad"]).fillna(0.0)
    out["SubTotal"] = out["MesNum"].map(g["SubTotal"]).fillna(0.0)
    out["Margen"] = out.apply(lambda r: safe_div(r["Utilidad"], r["SubTotal"]), axis=1)
    out["TXNS"] = out["MesNum"].map(g["TXNS"]).fillna(0.0)
    out["Ticket"] = out.apply(lambda r: safe_div(r["Ventas_Total"], r["TXNS"]) if ventas_con_iva else safe_div(r["SubTotal"], r["TXNS"]), axis=1)
    out["DescPct"] = out.apply(lambda r: safe_div(float(g["DescDol"].get(r["MesNum"], 0.0)), r["SubTotal"]) if r["SubTotal"] > 0 else float("nan"), axis=1)
    out["Vendedores"] = out["MesNum"].map(g["Vendedores"]).fillna(0.0)

    out["Mes"] = out["MesNum"].map(MONTHS_FULL)
    # IMPORTANTE: Ordenar ascendente para que más reciente esté a la derecha
    out = out.sort_values("MesNum", ascending=True)
    # ORDEN DESCENDENTE: más reciente a la derecha
    out = out.sort_values("MesNum", ascending=True)
    return out

def add_yoy_monthly(df_cur: pd.DataFrame, df_prev: pd.DataFrame) -> pd.DataFrame:
    out = df_cur.copy()
    prev = df_prev.set_index("MesNum")
    out["YoY_Ventas_Total"] = out["Ventas_Total"].map(lambda v: np.nan)
    out["YoY_Ventas_Cont"] = out["Ventas_Cont"].map(lambda v: np.nan)
    out["YoY_Ventas_Cred"] = out["Ventas_Cred"].map(lambda v: np.nan)
    out["YoY_Utilidad"] = out["Utilidad"].map(lambda v: np.nan)
    out["YoY_TXNS"] = out["TXNS"].map(lambda v: np.nan)
    out["YoY_Ticket"] = out["Ticket"].map(lambda v: np.nan)
    out["YoY_DescPct_pp"] = out["DescPct"].map(lambda v: np.nan)
    out["YoY_Margen_pp"] = out["Margen"].map(lambda v: np.nan)

    for i, r in out.iterrows():
        m = int(r["MesNum"])
        if m not in prev.index:
            continue
        pr = prev.loc[m]
        out.at[i, "YoY_Ventas_Total"] = yoy(float(r["Ventas_Total"]), float(pr["Ventas_Total"]))
        out.at[i, "YoY_Ventas_Cont"] = yoy(float(r["Ventas_Cont"]), float(pr["Ventas_Cont"]))
        out.at[i, "YoY_Ventas_Cred"] = yoy(float(r["Ventas_Cred"]), float(pr["Ventas_Cred"]))
        out.at[i, "YoY_Utilidad"] = yoy(float(r["Utilidad"]), float(pr["Utilidad"]))
        out.at[i, "YoY_TXNS"] = yoy(float(r["TXNS"]), float(pr["TXNS"]))
        out.at[i, "YoY_Ticket"] = yoy(float(r["Ticket"]), float(pr["Ticket"])) if (pd.notna(r["Ticket"]) and pd.notna(pr["Ticket"])) else np.nan
        # % y margen como pp (delta directo)
        out.at[i, "YoY_DescPct_pp"] = (float(r["DescPct"]) - float(pr["DescPct"])) * 100 if (pd.notna(r["DescPct"]) and pd.notna(pr["DescPct"])) else np.nan
        out.at[i, "YoY_Margen_pp"] = (float(r["Margen"]) - float(pr["Margen"])) * 100 if (pd.notna(r["Margen"]) and pd.notna(pr["Margen"])) else np.nan

    return out

# ------------------------------------------------------------
# Charts
# ------------------------------------------------------------
def fig_hist_static(df_month: pd.DataFrame,
                    ventas_con_iva: bool,
                    m_start: int,
                    m_end: int) -> go.Figure:
    """
    Barras apiladas Cred/Cont (hasta 13 meses) + línea Utilidad.
    Muestra TODOS los meses en df_month (que puede cruzar años).
    """
    # Usar directamente los nombres de mes del DataFrame
    # porque ya vienen en orden cronológico correcto
    x = df_month["Mes"].tolist()
    
    y_cred = df_month["Ventas_Cred"]
    y_cont = df_month["Ventas_Cont"]
    y_util = df_month["Utilidad"]

    # Todos los meses tienen opacidad completa (ya están filtrados)
    cred_colors = ["rgba(31,119,180,1.0)"] * len(x)
    cont_colors = ["rgba(44,160,44,1.0)"] * len(x)

    fig = go.Figure()
    fig.add_bar(x=x, y=y_cred, name="Crédito", marker_color=cred_colors)
    fig.add_bar(x=x, y=y_cont, name="Contado", marker_color=cont_colors)
    fig.add_trace(go.Scatter(
        x=x,
        y=y_util,
        name="Utilidad",
        mode="lines+markers",
        yaxis="y2",
        line=dict(color="#e67e22", width=2.5),
        marker=dict(color="#e67e22", size=6),
    ))

    fig.update_layout(
        title=dict(text="Histórico mensual — Ventas (Crédito + Contado) y Utilidad (Últimos 13 meses)", x=0, xanchor="left"),
        barmode="stack",
        height=340,
        margin=dict(l=40, r=30, t=70, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(tickangle=0, type='category'),  # Importante: type='category' para mantener orden
        yaxis=dict(title="Ventas" + (" (CON IVA)" if ventas_con_iva else " (SIN IVA)"), tickformat="~s"),
        yaxis2=dict(title="Utilidad (SIN IVA)", overlaying="y", side="right", tickformat="~s"),
    )
    return fig

def fig_bars_line_rank(df_rank: pd.DataFrame, dim_label: str, ventas_con_iva: bool, title: str) -> go.Figure:
    x = df_rank[dim_label].astype(str).tolist()
    y = df_rank["Ventas"].astype(float).tolist()
    u = df_rank["Utilidad"].astype(float).tolist()
    fig = go.Figure()
    fig.add_bar(x=x, y=y, name="Ventas")
    fig.add_trace(go.Scatter(x=x, y=u, name="Utilidad", mode="lines+markers", yaxis="y2"))
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left"),
        height=520,
        margin=dict(l=40, r=30, t=70, b=140),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(tickangle=-45),
        yaxis=dict(title="Ventas" + (" (CON IVA)" if ventas_con_iva else " (SIN IVA)"), tickformat="~s"),
        yaxis2=dict(title="Utilidad (SIN IVA)", overlaying="y", side="right", tickformat="~s"),
    )
    fig.update_xaxes(type="category")
    return fig

def fig_top_vendedores(df_v: pd.DataFrame, ventas_con_iva: bool) -> go.Figure:
    x = df_v["Vendedor"].astype(str).tolist()
    fig = go.Figure()
    fig.add_bar(x=x, y=df_v["Ventas_Cred"].astype(float), name="Crédito")
    fig.add_bar(x=x, y=df_v["Ventas_Cont"].astype(float), name="Contado")
    fig.add_trace(go.Scatter(x=x, y=df_v["Utilidad"].astype(float), name="Utilidad", mode="lines+markers", yaxis="y2"))
    fig.update_layout(
        title=dict(text="Top vendedores — Ventas (Crédito+Contado) y Utilidad", x=0, xanchor="left"),
        barmode="stack",
        height=520,
        margin=dict(l=40, r=30, t=70, b=140),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(tickangle=-45),
        yaxis=dict(title="Ventas" + (" (CON IVA)" if ventas_con_iva else " (SIN IVA)"), tickformat="~s"),
        yaxis2=dict(title="Utilidad (SIN IVA)", overlaying="y", side="right", tickformat="~s"),
    )
    return fig

def fig_quadrants(df_q: pd.DataFrame) -> go.Figure:
    # Matriz 2x2 con medianas (sin etiquetas)
    x = df_q["TXNS"].astype(float)
    y = df_q["Ticket"].astype(float)
    size = df_q["Ventas"].astype(float).clip(lower=0.0)
    # escalar tamaño
    s = np.sqrt(size / (size.max() if size.max() > 0 else 1.0)) * 45 + 8

    med_x = float(np.nanmedian(x)) if len(x) else 0.0
    med_y = float(np.nanmedian(y)) if len(y) else 0.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="markers",
        marker=dict(size=s, sizemode="diameter", opacity=0.70),
        text=df_q["Vendedor"].astype(str),
        hovertemplate="<b>%{text}</b><br>TXNS=%{x:,.0f}<br>Ticket=%{y:,.0f}<br>Ventas=%{customdata[0]:,.0f}<br>Utilidad=%{customdata[1]:,.0f}<extra></extra>",
        customdata=np.stack([df_q["Ventas"].astype(float), df_q["Utilidad"].astype(float)], axis=1)
    ))

    fig.add_shape(type="line", x0=med_x, x1=med_x, y0=float(np.nanmin(y)) if len(y) else 0, y1=float(np.nanmax(y)) if len(y) else 1,
                  line=dict(dash="dash"))
    fig.add_shape(type="line", y0=med_y, y1=med_y, x0=float(np.nanmin(x)) if len(x) else 0, x1=float(np.nanmax(x)) if len(x) else 1,
                  line=dict(dash="dash"))

    fig.update_layout(
        title=dict(text="Matriz 2×2 — Transacciones vs Ticket (tamaño=Ventas)", x=0, xanchor="left"),
        height=520,
        margin=dict(l=50, r=30, t=70, b=60),
        xaxis=dict(title="Transacciones"),
        yaxis=dict(title="Ticket promedio"),
    )
    return fig

# ------------------------------------------------------------
# Breakdown helpers (Top N con YoY)
# ------------------------------------------------------------
def breakdown_dim(df_cur: pd.DataFrame, df_prev: pd.DataFrame, dim_col: str, ventas_con_iva: bool, top_n: int = 20) -> pd.DataFrame:
    ventas_col = _ventas_col(ventas_con_iva)
    if df_cur.empty:
        return pd.DataFrame(columns=[dim_col,"Ventas","Utilidad","SubTotal","Margen","TXNS",
                                     "YoY_Ventas","YoY_Utilidad","YoY_TXNS","YoY_Margen_pp"])

    cur = (
        df_cur.groupby(dim_col, observed=True)
              .agg(Ventas=(ventas_col,"sum"), Utilidad=("Utilidad","sum"), SubTotal=("Sub Total","sum"), TXNS=("DOC_KEY","nunique"))
              .reset_index()
    )
    cur["Margen"] = cur.apply(lambda r: safe_div(r["Utilidad"], r["SubTotal"]), axis=1)

    prev = (
        df_prev.groupby(dim_col, observed=True)
              .agg(Ventas_LY=(ventas_col,"sum"), Utilidad_LY=("Utilidad","sum"), SubTotal_LY=("Sub Total","sum"), TXNS_LY=("DOC_KEY","nunique"))
              .reset_index()
    )
    prev["Margen_LY"] = prev.apply(lambda r: safe_div(r["Utilidad_LY"], r["SubTotal_LY"]), axis=1)

    out = cur.merge(prev, on=dim_col, how="left")
    out["YoY_Ventas"] = out.apply(lambda r: yoy(float(r["Ventas"]), float(r["Ventas_LY"])) if pd.notna(r["Ventas_LY"]) else np.nan, axis=1)
    out["YoY_Utilidad"] = out.apply(lambda r: yoy(float(r["Utilidad"]), float(r["Utilidad_LY"])) if pd.notna(r["Utilidad_LY"]) else np.nan, axis=1)
    out["YoY_TXNS"] = out.apply(lambda r: yoy(float(r["TXNS"]), float(r["TXNS_LY"])) if pd.notna(r["TXNS_LY"]) else np.nan, axis=1)
    out["YoY_Margen_pp"] = out.apply(lambda r: (float(r["Margen"]) - float(r["Margen_LY"])) * 100 if (pd.notna(r["Margen"]) and pd.notna(r["Margen_LY"])) else np.nan, axis=1)

    out = out.sort_values("Ventas", ascending=False).head(int(top_n)).reset_index(drop=True)
    return out

def vendor_metrics(df_cur: pd.DataFrame, df_prev: pd.DataFrame, ventas_con_iva: bool, top_n: int = 30) -> pd.DataFrame:
    ventas_col = _ventas_col(ventas_con_iva)
    if df_cur.empty:
        return pd.DataFrame(columns=["Vendedor","Ventas","Ventas_Cont","Ventas_Cred","Utilidad","SubTotal","Margen","TXNS","Ticket",
                                     "YoY_Ventas","YoY_Utilidad","YoY_TXNS","YoY_Ticket","YoY_Margen_pp"])

    cur = (
        df_cur.groupby("Vendedor_Nombre", observed=True)
              .agg(
                  Ventas=(ventas_col,"sum"),
                  Ventas_Cont=(ventas_col, lambda s: float(df_cur.loc[s.index].loc[df_cur.loc[s.index]["Tipo2"]=="CONTADO", ventas_col].sum()) if "Tipo2" in df_cur.columns else float(s.sum())),
                  Ventas_Cred=(ventas_col, lambda s: float(df_cur.loc[s.index].loc[df_cur.loc[s.index]["Tipo2"]=="CREDITO", ventas_col].sum()) if "Tipo2" in df_cur.columns else 0.0),
                  Utilidad=("Utilidad","sum"),
                  SubTotal=("Sub Total","sum"),
                  TXNS=("DOC_KEY","nunique"),
                  Lineas=("DOC_KEY","size"),
                  SKU_UNQ=("SKU_KEY", lambda s: s.dropna().nunique()),
              )
              .reset_index()
              .rename(columns={"Vendedor_Nombre":"Vendedor"})
    )
    cur["Margen"] = cur.apply(lambda r: safe_div(r["Utilidad"], r["SubTotal"]), axis=1)
    cur["Ticket"] = cur.apply(lambda r: safe_div(r["Ventas"], r["TXNS"]) if ventas_con_iva else safe_div(r["SubTotal"], r["TXNS"]), axis=1)
    # SKUs por ticket: si no hay SKU, usa líneas por ticket
    cur["SKUs_x_Ticket"] = cur.apply(lambda r: safe_div(r["SKU_UNQ"] if r["SKU_UNQ"] > 0 else r["Lineas"], r["TXNS"]), axis=1)

    prev = (
        df_prev.groupby("Vendedor_Nombre", observed=True)
              .agg(
                  Ventas_LY=(ventas_col,"sum"),
                  Utilidad_LY=("Utilidad","sum"),
                  SubTotal_LY=("Sub Total","sum"),
                  TXNS_LY=("DOC_KEY","nunique"),
              )
              .reset_index()
              .rename(columns={"Vendedor_Nombre":"Vendedor"})
    )
    prev["Margen_LY"] = prev.apply(lambda r: safe_div(r["Utilidad_LY"], r["SubTotal_LY"]), axis=1)
    prev["Ticket_LY"] = prev.apply(lambda r: safe_div(r["Ventas_LY"], r["TXNS_LY"]) if ventas_con_iva else safe_div(r["SubTotal_LY"], r["TXNS_LY"]), axis=1)

    out = cur.merge(prev, on="Vendedor", how="left")
    out["YoY_Ventas"] = out.apply(lambda r: yoy(float(r["Ventas"]), float(r["Ventas_LY"])) if pd.notna(r.get("Ventas_LY")) else np.nan, axis=1)
    out["YoY_Utilidad"] = out.apply(lambda r: yoy(float(r["Utilidad"]), float(r["Utilidad_LY"])) if pd.notna(r.get("Utilidad_LY")) else np.nan, axis=1)
    out["YoY_TXNS"] = out.apply(lambda r: yoy(float(r["TXNS"]), float(r["TXNS_LY"])) if pd.notna(r.get("TXNS_LY")) else np.nan, axis=1)
    out["YoY_Ticket"] = out.apply(lambda r: yoy(float(r["Ticket"]), float(r["Ticket_LY"])) if pd.notna(r.get("Ticket_LY")) else np.nan, axis=1)
    out["YoY_Margen_pp"] = out.apply(lambda r: (float(r["Margen"]) - float(r["Margen_LY"])) * 100 if (pd.notna(r.get("Margen")) and pd.notna(r.get("Margen_LY"))) else np.nan, axis=1)

    out = out.sort_values("Ventas", ascending=False).head(int(top_n)).reset_index(drop=True)
    return out

# ------------------------------------------------------------
# Insights
# ------------------------------------------------------------
def insight_cards(k_cur: Dict[str,float], k_prev: Dict[str,float], ventas_con_iva: bool):
    # Crea 6-8 tarjetas rápidas
    def card(title, value, delta_txt, cls):
        st.markdown(
            f"""
            <div class="kpi-card" style="height: 110px;">
              <div class="kpi-title">{title}</div>
              <div class="kpi-value" style="font-size: 1.8rem;">{value}</div>
              <div class="{cls}">{delta_txt}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    cols = st.columns(4)
    y_sales = yoy(k_cur["ventas"], k_prev["ventas"])
    y_profit = yoy(k_cur["utilidad"], k_prev["utilidad"])
    d_margin_pp = (k_cur["margen"] - k_prev["margen"]) * 100 if (pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"])) else np.nan
    d_desc_pp = (k_cur["descpct"] - k_prev["descpct"]) * 100 if (pd.notna(k_cur["descpct"]) and pd.notna(k_prev["descpct"])) else np.nan
    y_txns = yoy(k_cur["txns"], k_prev["txns"])
    y_ticket = yoy(k_cur["ticket"], k_prev["ticket"])

    with cols[0]:
        cls, txt = _pill_pct(y_sales)
        card("Ventas (rango)", money_fmt(k_cur["ventas"]), txt, cls)
    with cols[1]:
        cls, txt = _pill_pct(y_profit)
        card("Utilidad (rango)", money_fmt(k_cur["utilidad"]), txt, cls)
    with cols[2]:
        cls, txt = _pill_pp(d_margin_pp)
        card("Margen (rango)", pct_fmt(k_cur["margen"]) if pd.notna(k_cur["margen"]) else "—", txt, cls)
    with cols[3]:
        cls, txt = _pill_pp(d_desc_pp)
        card("% Descuento (rango)", pct_fmt(k_cur["descpct"]) if pd.notna(k_cur["descpct"]) else "—", txt, cls)

    cols2 = st.columns(4)
    with cols2[0]:
        cls, txt = _pill_pct(y_txns)
        card("Transacciones", num_fmt(k_cur["txns"]), txt, cls)
    with cols2[1]:
        cls, txt = _pill_pct(y_ticket)
        card("Ticket promedio", money_fmt(k_cur["ticket"]) if ventas_con_iva else money_fmt(k_cur["ticket"]), txt, cls)
    # Crédito share
    cred_share = safe_div(k_cur["ventas_cred"], k_cur["ventas"])
    cred_share_prev = safe_div(k_prev["ventas_cred"], k_prev["ventas"])
    d_cred_pp = (cred_share - cred_share_prev) * 100 if (pd.notna(cred_share) and pd.notna(cred_share_prev)) else np.nan
    with cols2[2]:
        cls, txt = _pill_pp(d_cred_pp)
        card("Participación crédito", pct_fmt(cred_share) if pd.notna(cred_share) else "—", txt, cls)
    # Calidad de crecimiento
    qual = y_sales - y_profit if (pd.notna(y_sales) and pd.notna(y_profit)) else np.nan
    with cols2[3]:
        if qual != qual:
            cls, txt = ("pill gray", "—")
        else:
            # si ventas crece más que utilidad => rojo
            cls = "pill red" if qual > 0 else "pill"
            arrow = "▲" if qual <= 0 else "▼"
            txt = f"{arrow} {abs(qual)*100:,.2f}".rstrip("0").rstrip(".") + " pp (calidad)"
        card("Ventas vs Utilidad", "Calidad", txt, cls)

# ------------------------------------------------------------
# Sidebar (filtros)
# ------------------------------------------------------------
with st.sidebar:
    # Aplicar tema
    aplicar_tema()
    
    # Toggle de tema
    mostrar_toggle_tema()
    
    st.markdown("---")
    
    st.markdown("### IMDC — Filtros")
    modo_tecnico = st.toggle("Modo técnico", value=False, key="modo_tecnico")

    df_all, years, familias, marcas = load_all()

    if df_all.empty:
        st.error("No se encontraron archivos Parquet en la carpeta ./output (cedro_*.parquet).")
        st.stop()

    year = st.selectbox("Año", options=years, index=len(years)-1 if years else 0, key=make_key("year"))
    # mes default: último mes con datos en ese año
    df_y = df_all[df_all["Año"].astype(int) == int(year)]
    last_month = int(df_y["Mes"].dropna().astype(int).max()) if not df_y.empty else 12
    # ⚡ AUTOMÁTICO: Últimos 13 meses (puede cruzar años)
    meses_disponibles = sorted([int(m) for m in df_y["Mes"].dropna().unique()])
    if meses_disponibles:
        ultimo_mes = max(meses_disponibles)
        m_start = ultimo_mes - 12  # 13 meses hacia atrás
        m_end = ultimo_mes
        
        # Si m_start < 1, significa que cruza al año anterior
        if m_start < 1:
            year_inicio = int(year) - 1
            m_start_display = m_start + 12  # Convertir a mes del año anterior
        else:
            year_inicio = int(year)
            m_start_display = m_start
            
        st.info(f"📊 Mostrando últimos 13 meses: {MONTHS_FULL[m_start_display if m_start > 0 else m_start + 12]} {year_inicio} - {MONTHS_FULL[m_end]} {year}")
    else:
        m_start, m_end = 1, 12

    sucursal = st.selectbox("Sucursal", options=CATALOGO_SUCURSALES, index=0, key=make_key("sucursal"))
    familia = st.selectbox("Familia", options=(["TODAS"] + familias), index=0, key=make_key("familia"))
    marca = st.selectbox("Marca", options=(["TODAS"] + marcas), index=0, key=make_key("marca"))

    ventas_con_iva = st.toggle("Ventas CON IVA", value=True, key=make_key("iva"))
    include_rem = st.toggle("Incluir REM", value=False, key=make_key("rem"))
    
    st.markdown("---")
    st.markdown("#### 🎯 Filtros Avanzados")
    excluir_credito = st.checkbox("Excluir ventas de CRÉDITO", value=False, key=make_key("excluir_credito"))
    if excluir_credito:
        st.info("📊 Solo se mostrarán ventas de CONTADO")

    if modo_tecnico:
        st.markdown("---")
        if st.button("Recargar datos (limpiar caché)"):
            st.cache_data.clear()
            _bump_ui_epoch()
            st.rerun()
        st.markdown(f"<div class='tiny'>Versión: {APP_VERSION} | UI epoch: {_ui_epoch()}</div>", unsafe_allow_html=True)
        # Diagnósticos rápidos
        st.caption(f"Parquets detectados: {len(list(OUTPUT_DIR.glob(PARQUET_GLOB)))} en {OUTPUT_DIR}")


    # Control de caché
    mostrar_control_cache()

# ------------------------------------------------------------
# Main computations
# ------------------------------------------------------------
# Datos del rango
# Mostrar progreso durante filtrado
with st.spinner("Aplicando filtros..."):
    df_kpi = apply_filters(df_all, int(year), int(m_start), int(m_end), sucursal, familia, marca, include_rem, excluir_credito)
df_prev = apply_filters(df_all, int(year)-1, int(m_start), int(m_end), sucursal, familia, marca, include_rem, excluir_credito)

# Datos del año completo (para gráfico histórico)
df_year = apply_filters_year(df_all, int(year), sucursal, familia, marca, include_rem, excluir_credito)
df_year_prev = apply_filters_year(df_all, int(year)-1, sucursal, familia, marca, include_rem, excluir_credito)

# m2 según sucursal
m2 = float(M2_MAP.get(sucursal, M2_MAP["CONSOLIDADO"])) if sucursal in M2_MAP else float(M2_MAP["CONSOLIDADO"])

k_cur = calcular_kpis_cached(df_kpi, ventas_con_iva, m2)
k_prev = calcular_kpis_cached(df_prev, ventas_con_iva, m2)

# mensual 12 meses + YoY (mes-a-mes)

# ============================================================
# FIX: COMBINAR DATOS MULTI-AÑO CORRECTAMENTE
# ============================================================

# Si m_start es negativo, significa que cruza al año anterior
if m_start < 1:
    # Caso complejo: cruza años (13 meses hacia atrás desde mes actual)
    # Ejemplo: Si estamos en Ene 2026 (m_end=1), m_start=-11
    # Queremos: Feb 2025 a Ene 2026 (13 meses)
    
    m_start_prev = m_start + 12  # Convertir a mes del año anterior (-11 + 12 = 1)
    
    # Tomar meses del año anterior (desde m_start_prev hasta 12)
    df_prev_months = df_year_prev[df_year_prev["Mes"].astype(int) >= m_start_prev].copy()
    
    # Tomar meses del año actual (desde 1 hasta m_end)
    df_curr_months = df_year[df_year["Mes"].astype(int) <= m_end].copy()
    
    # IMPORTANTE: Crear resúmenes separados para evitar que se mezclen los meses
    # Por ejemplo, Enero 2025 y Enero 2026 no deben sumarse
    ms_prev_part = resumen_mensual_cached(df_prev_months, ventas_con_iva)
    ms_curr_part = resumen_mensual_cached(df_curr_months, ventas_con_iva)
    
    # Filtrar solo los meses que necesitamos de cada año
    ms_prev_part = ms_prev_part[ms_prev_part["MesNum"] >= m_start_prev]
    ms_curr_part = ms_curr_part[ms_curr_part["MesNum"] <= m_end]
    
    # Concatenar en orden cronológico: primero año anterior, luego año actual
    ms_cur = pd.concat([ms_prev_part, ms_curr_part], ignore_index=True)
    
    # Ordenar por MesNum ascendente para mantener orden cronológico
    ms_cur = ms_cur.sort_values("MesNum", ascending=True).reset_index(drop=True)
    
else:
    # Caso simple: todos los meses dentro del mismo año
    df_combined = df_year[df_year["Mes"].astype(int).between(m_start, m_end)].copy()
    ms_cur = resumen_mensual_cached(df_combined, ventas_con_iva)
    
    # Filtrar solo los meses en el rango
    ms_cur = ms_cur[ms_cur["MesNum"].between(m_start, m_end)]

# Crear resumen mensual del año anterior completo (para comparaciones YoY)
ms_prev = resumen_mensual_cached(df_year_prev, ventas_con_iva)
ms = add_yoy_monthly(ms_cur, ms_prev)



# ============================================================
# FUNCIONALIDADES TIPO POWER BI
# ============================================================


# ============================================================
# CONSTRUCTOR DE TABLAS CON DRAG & DROP
# ============================================================

def tabla_drag_drop_builder(df: pd.DataFrame, nombre_tabla: str = "Tabla Personalizada"):
    """
    Constructor de tablas con drag & drop simulado (usando selectbox ordenados)
    """
    
    if df.empty:
        st.warning("No hay datos disponibles")
        return
    
    st.markdown(f"### 🔧 {nombre_tabla}")
    st.markdown("*Arrastra (selecciona) las columnas que quieres ver en tu tabla*")
    
    # Obtener columnas disponibles
    columnas_disponibles = df.columns.tolist()
    
    # Filtros adicionales
    st.markdown("#### 🎛️ Filtros")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    # Obtener valores únicos para filtros
    sucursales = ['TODAS']
    familias = ['TODAS']
    marcas = ['TODAS']
    
    if 'Almacen_CANON' in df.columns:
        sucursales += sorted(df['Almacen_CANON'].dropna().unique().tolist())
    
    if 'Familia_Nombre' in df.columns:
        familias += sorted(df['Familia_Nombre'].dropna().unique().tolist())
    
    if 'Marca_Nombre' in df.columns:
        marcas += sorted(df['Marca_Nombre'].dropna().unique().tolist())
    
    with col_f1:
        filtro_sucursal = st.selectbox(
            "🏪 Sucursal:",
            sucursales,
            key=f"filtro_suc_{nombre_tabla}"
        )
    
    with col_f2:
        filtro_familia = st.selectbox(
            "📦 Familia:",
            familias,
            key=f"filtro_fam_{nombre_tabla}"
        )
    
    with col_f3:
        filtro_marca = st.selectbox(
            "🏷️ Marca:",
            marcas,
            key=f"filtro_mar_{nombre_tabla}"
        )
    
    with col_f4:
        num_filas = st.number_input(
            "📊 Filas:",
            min_value=10,
            max_value=500,
            value=50,
            step=10,
            key=f"filas_{nombre_tabla}"
        )
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if filtro_sucursal != 'TODAS' and 'Almacen_CANON' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Almacen_CANON'] == filtro_sucursal]
    
    if filtro_familia != 'TODAS' and 'Familia_Nombre' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Familia_Nombre'] == filtro_familia]
    
    if filtro_marca != 'TODAS' and 'Marca_Nombre' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Marca_Nombre'] == filtro_marca]
    
    st.markdown("---")
    st.markdown("#### 📋 Constructor de Columnas (Drag & Drop)")
    st.caption("💡 Selecciona las columnas en el orden que quieres verlas")
    
    # 7 columnas para arrastrar
    cols_builder = st.columns(7)
    
    columnas_seleccionadas = []
    
    for i, col_builder in enumerate(cols_builder):
        with col_builder:
            st.markdown(f"**Col {i+1}**")
            
            col_seleccionada = st.selectbox(
                f"Columna {i+1}:",
                ['[Vacía]'] + columnas_disponibles,
                key=f"col_{i}_{nombre_tabla}",
                label_visibility="collapsed"
            )
            
            if col_seleccionada != '[Vacía]':
                columnas_seleccionadas.append(col_seleccionada)
    
    st.markdown("---")
    
    if not columnas_seleccionadas:
        st.info("👆 Selecciona al menos una columna arriba")
        return
    
    # Filtrar columnas seleccionadas que existen
    columnas_validas = [c for c in columnas_seleccionadas if c in df_filtrado.columns]
    
    if not columnas_validas:
        st.warning("No hay columnas válidas seleccionadas")
        return
    
    # Crear tabla con columnas seleccionadas
    df_resultado = df_filtrado[columnas_validas].head(int(num_filas))
    
    # Botones de acción
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    
    with col_btn1:
        if st.button("📥 CSV", use_container_width=True, key=f"csv_{nombre_tabla}"):
            csv = df_resultado.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Descargar",
                csv,
                f"{nombre_tabla}.csv",
                "text/csv",
                key=f"download_{nombre_tabla}"
            )
    
    with col_btn2:
        if st.button("🔄 Reset", use_container_width=True, key=f"reset_{nombre_tabla}"):
            st.rerun()
    
    # Mostrar tabla
    st.dataframe(
        df_resultado,
        use_container_width=True,
        height=min(600, len(df_resultado) * 35 + 38)
    )
    
    # Estadísticas
    st.caption(f"📊 Mostrando {len(df_resultado)} de {len(df_filtrado):,} filas | {len(columnas_validas)} columnas")



def selector_grafica_interactivo(df: pd.DataFrame, titulo: str = "Gráfica"):
    """Selector de tipo de gráfica tipo Power BI"""
    
    if df.empty:
        st.warning("No hay datos para graficar")
        return
    
    st.markdown(f"### 📊 {titulo}")
    
    # Selector de tipo de gráfica
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        tipo_grafica = st.selectbox(
            "Tipo de gráfica:",
            ["Barras", "Líneas", "Área", "Scatter", "Pie", "Barras Apiladas", "Barras Horizontales"],
            key=f"tipo_graf_{titulo}"
        )
    
    # Obtener columnas
    columnas_numericas = df.select_dtypes(include=[np.number]).columns.tolist()
    columnas_todas = df.columns.tolist()
    
    with col2:
        eje_x = st.selectbox(
            "Eje X:",
            columnas_todas,
            key=f"eje_x_{titulo}"
        )
    
    with col3:
        eje_y = st.selectbox(
            "Eje Y:",
            columnas_numericas,
            key=f"eje_y_{titulo}"
        )
    
    # Opciones adicionales
    col_opt1, col_opt2 = st.columns(2)
    
    with col_opt1:
        mostrar_valores = st.checkbox("Mostrar valores", value=False, key=f"vals_{titulo}")
        mostrar_leyenda = st.checkbox("Mostrar leyenda", value=True, key=f"leg_{titulo}")
    
    with col_opt2:
        color_personalizado = st.color_picker("Color principal:", "#2563EB", key=f"color_{titulo}")
    
    # Crear gráfica según tipo
    fig = go.Figure()
    
    if tipo_grafica == "Barras":
        fig.add_trace(go.Bar(
            x=df[eje_x],
            y=df[eje_y],
            marker=dict(color=color_personalizado),
            text=df[eje_y] if mostrar_valores else None,
            texttemplate='%{text:,.0f}' if mostrar_valores else None,
            textposition='outside' if mostrar_valores else None
        ))
    
    elif tipo_grafica == "Líneas":
        fig.add_trace(go.Scatter(
            x=df[eje_x],
            y=df[eje_y],
            mode='lines+markers',
            line=dict(color=color_personalizado, width=3),
            marker=dict(size=8)
        ))
    
    elif tipo_grafica == "Área":
        fig.add_trace(go.Scatter(
            x=df[eje_x],
            y=df[eje_y],
            fill='tozeroy',
            line=dict(color=color_personalizado)
        ))
    
    elif tipo_grafica == "Scatter":
        fig.add_trace(go.Scatter(
            x=df[eje_x],
            y=df[eje_y],
            mode='markers',
            marker=dict(
                size=10,
                color=color_personalizado,
                line=dict(width=2, color='white')
            )
        ))
    
    elif tipo_grafica == "Pie":
        fig = go.Figure(go.Pie(
            labels=df[eje_x],
            values=df[eje_y],
            marker=dict(colors=[color_personalizado])
        ))
    
    elif tipo_grafica == "Barras Apiladas":
        # Para apiladas necesitamos más de una serie
        fig.add_trace(go.Bar(
            x=df[eje_x],
            y=df[eje_y],
            marker=dict(color=color_personalizado)
        ))
    
    elif tipo_grafica == "Barras Horizontales":
        fig.add_trace(go.Bar(
            y=df[eje_x],
            x=df[eje_y],
            orientation='h',
            marker=dict(color=color_personalizado),
            text=df[eje_y] if mostrar_valores else None,
            texttemplate='%{text:,.0f}' if mostrar_valores else None
        ))
    
    # Configurar layout
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        showlegend=mostrar_leyenda,
        height=450,
        margin=dict(l=60, r=60, t=60, b=60),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title=eje_x
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title=eje_y
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)


def drill_down_explorer(df: pd.DataFrame, jerarquia: list):
    """Explorador drill-down tipo Power BI"""
    
    st.markdown("### 🔍 Explorador Drill-Down")
    
    if not jerarquia or df.empty:
        st.warning("Define una jerarquía para explorar")
        return
    
    # Estado de navegación
    if 'drill_level' not in st.session_state:
        st.session_state.drill_level = 0
        st.session_state.drill_filters = {}
    
    # Breadcrumb
    breadcrumb = " > ".join([jerarquia[i] for i in range(st.session_state.drill_level + 1)])
    st.markdown(f"**📍 Nivel:** {breadcrumb}")
    
    # Aplicar filtros acumulados
    df_filtrado = df.copy()
    for col, val in st.session_state.drill_filters.items():
        df_filtrado = df_filtrado[df_filtrado[col] == val]
    
    # Nivel actual
    nivel_actual = jerarquia[st.session_state.drill_level]
    
    # Agregar por nivel actual
    if nivel_actual in df_filtrado.columns:
        resumen = df_filtrado.groupby(nivel_actual).agg({
            'Total_alloc': 'sum',
            'Utilidad': 'sum',
            'DOC_KEY': 'nunique'
        }).reset_index()
        
        resumen.columns = [nivel_actual, 'Ventas', 'Utilidad', 'Transacciones']
        resumen = resumen.sort_values('Ventas', ascending=False)
        
        # Mostrar tabla con botón de drill
        for idx, row in resumen.head(10).iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"**{row[nivel_actual]}**")
            with col2:
                st.markdown(f"💰 {money_fmt(row['Ventas'])}")
            with col3:
                st.markdown(f"📈 {money_fmt(row['Utilidad'])}")
            with col4:
                if st.session_state.drill_level < len(jerarquia) - 1:
                    if st.button("🔽", key=f"drill_{idx}"):
                        st.session_state.drill_level += 1
                        st.session_state.drill_filters[nivel_actual] = row[nivel_actual]
                        st.rerun()
    
    # Botón de subir nivel
    col_back, col_reset = st.columns([1, 4])
    with col_back:
        if st.session_state.drill_level > 0:
            if st.button("⬆️ Subir nivel"):
                st.session_state.drill_level -= 1
                # Quitar último filtro
                if jerarquia[st.session_state.drill_level] in st.session_state.drill_filters:
                    del st.session_state.drill_filters[jerarquia[st.session_state.drill_level]]
                st.rerun()
    
    with col_reset:
        if st.button("🔄 Reiniciar exploración"):
            st.session_state.drill_level = 0
            st.session_state.drill_filters = {}
            st.rerun()


def comparador_periodos(df_all: pd.DataFrame, year: int):
    """Comparador de períodos tipo Power BI"""
    
    st.markdown("### 📅 Comparador de Períodos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Período 1")
        year1 = st.selectbox("Año 1:", [year-2, year-1, year], index=2, key="year1_comp")
        mes_inicio1 = st.selectbox("Mes inicio 1:", list(range(1, 13)), index=0, key="mes1_ini")
        mes_fin1 = st.selectbox("Mes fin 1:", list(range(1, 13)), index=11, key="mes1_fin")
    
    with col2:
        st.markdown("#### Período 2")
        year2 = st.selectbox("Año 2:", [year-2, year-1, year], index=1, key="year2_comp")
        mes_inicio2 = st.selectbox("Mes inicio 2:", list(range(1, 13)), index=0, key="mes2_ini")
        mes_fin2 = st.selectbox("Mes fin 2:", list(range(1, 13)), index=11, key="mes2_fin")
    
    # Filtrar datos
    df1 = df_all[(df_all['Año'] == year1) & (df_all['Mes'].between(mes_inicio1, mes_fin1))]
    df2 = df_all[(df_all['Año'] == year2) & (df_all['Mes'].between(mes_inicio2, mes_fin2))]
    
    # Calcular KPIs
    kpis_comp = st.columns(4)
    
    ventas1 = df1['Total_alloc'].sum()
    ventas2 = df2['Total_alloc'].sum()
    delta_ventas = ((ventas1 - ventas2) / ventas2 * 100) if ventas2 > 0 else 0
    
    with kpis_comp[0]:
        st.metric("Ventas P1", money_fmt(ventas1))
        st.metric("Ventas P2", money_fmt(ventas2), f"{delta_ventas:+.1f}%")
    
    util1 = df1['Utilidad'].sum()
    util2 = df2['Utilidad'].sum()
    delta_util = ((util1 - util2) / util2 * 100) if util2 > 0 else 0
    
    with kpis_comp[1]:
        st.metric("Utilidad P1", money_fmt(util1))
        st.metric("Utilidad P2", money_fmt(util2), f"{delta_util:+.1f}%")
    
    txns1 = df1['DOC_KEY'].nunique()
    txns2 = df2['DOC_KEY'].nunique()
    delta_txns = ((txns1 - txns2) / txns2 * 100) if txns2 > 0 else 0
    
    with kpis_comp[2]:
        st.metric("Transacciones P1", f"{txns1:,}")
        st.metric("Transacciones P2", f"{txns2:,}", f"{delta_txns:+.1f}%")
    
    ticket1 = ventas1 / txns1 if txns1 > 0 else 0
    ticket2 = ventas2 / txns2 if txns2 > 0 else 0
    delta_ticket = ((ticket1 - ticket2) / ticket2 * 100) if ticket2 > 0 else 0
    
    with kpis_comp[3]:
        st.metric("Ticket P1", money_fmt(ticket1))
        st.metric("Ticket P2", money_fmt(ticket2), f"{delta_ticket:+.1f}%")
    
    # Gráfica comparativa
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name=f'{year1} ({mes_inicio1}-{mes_fin1})',
        x=['Ventas', 'Utilidad', 'Transacciones'],
        y=[ventas1, util1, txns1],
        marker=dict(color='#2563EB')
    ))
    
    fig.add_trace(go.Bar(
        name=f'{year2} ({mes_inicio2}-{mes_fin2})',
        x=['Ventas', 'Utilidad', 'Transacciones'],
        y=[ventas2, util2, txns2],
        marker=dict(color='#10B981')
    ))
    
    fig.update_layout(
        barmode='group',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# COMPARADOR AVANZADO MENSUAL Y ACUMULADO YoY
# ============================================================


# ============================================================
# COMPARADOR UNIFICADO (MENSUAL + ACUMULADO)
# ============================================================

def crear_comparador_unificado_yoy(df_all: pd.DataFrame, year_actual: int, ventas_con_iva: bool):
    """
    Comparador unificado: Mensual (izq) + Acumulado (der) con filtros
    """
    
    st.markdown("### 📊 Comparador Completo YoY (Mensual + Acumulado)")
    
    # ========================================
    # FILTROS SUPERIORES
    # ========================================
    st.markdown("#### 🎛️ Configuración")
    
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
    
    años_disponibles = sorted(df_all['Año'].unique())
    sucursales_disponibles = ['TODAS'] + sorted(df_all['Almacen_CANON'].unique().tolist())
    familias_disponibles = ['TODAS'] + sorted(df_all['Familia_Nombre'].dropna().unique().tolist())
    marcas_disponibles = ['TODAS'] + sorted(df_all['Marca_Nombre'].dropna().unique().tolist())
    
    with col_f1:
        año_base = st.selectbox(
            "Año Base:",
            años_disponibles,
            index=len(años_disponibles)-2 if len(años_disponibles) > 1 else 0,
            key="año_base_unif"
        )
    
    with col_f2:
        año_comp = st.selectbox(
            "Año Comparar:",
            años_disponibles,
            index=len(años_disponibles)-1,
            key="año_comp_unif"
        )
    
    with col_f3:
        sucursal_filtro = st.selectbox(
            "🏪 Sucursal:",
            sucursales_disponibles,
            key="sucursal_unif"
        )
    
    with col_f4:
        familia_filtro = st.selectbox(
            "📦 Familia:",
            familias_disponibles,
            key="familia_unif"
        )
    
    with col_f5:
        marca_filtro = st.selectbox(
            "🏷️ Marca:",
            marcas_disponibles,
            key="marca_unif"
        )
    
    if año_base == año_comp:
        st.warning("⚠️ Selecciona años diferentes para comparar")
        return
    
    # Aplicar filtros
    df_filtrado = df_all.copy()
    
    if sucursal_filtro != 'TODAS':
        df_filtrado = df_filtrado[df_filtrado['Almacen_CANON'] == sucursal_filtro]
    
    if familia_filtro != 'TODAS':
        df_filtrado = df_filtrado[df_filtrado['Familia_Nombre'] == familia_filtro]
    
    if marca_filtro != 'TODAS':
        df_filtrado = df_filtrado[df_filtrado['Marca_Nombre'] == marca_filtro]
    
    # Separar por año
    df_base = df_filtrado[df_filtrado['Año'] == año_base]
    df_comp = df_filtrado[df_filtrado['Año'] == año_comp]
    
    ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
    
    # Resumen mensual
    resumen_base = df_base.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique',
        'Sub Total': 'sum'
    }).reset_index().sort_values('Mes')
    
    resumen_comp = df_comp.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique',
        'Sub Total': 'sum'
    }).reset_index().sort_values('Mes')
    
    # Calcular acumulados
    resumen_base['Ventas_Acum'] = resumen_base[ventas_col].cumsum()
    resumen_base['Utilidad_Acum'] = resumen_base['Utilidad'].cumsum()
    resumen_base['Mes_Nombre'] = resumen_base['Mes'].map(MONTHS_FULL)
    
    resumen_comp['Ventas_Acum'] = resumen_comp[ventas_col].cumsum()
    resumen_comp['Utilidad_Acum'] = resumen_comp['Utilidad'].cumsum()
    resumen_comp['Mes_Nombre'] = resumen_comp['Mes'].map(MONTHS_FULL)
    
    st.markdown("---")
    
    # ========================================
    # LAYOUT: IZQUIERDA (MENSUAL) | DERECHA (ACUMULADO)
    # ========================================
    
    col_izq, col_der = st.columns(2)
    
    # ========================================
    # IZQUIERDA: COMPARACIÓN MENSUAL
    # ========================================
    with col_izq:
        st.markdown("### 📅 Mensual")
        
        # Gráfica de barras agrupadas
        fig_mensual = go.Figure()
        
        fig_mensual.add_trace(go.Bar(
            name=f'{año_base}',
            x=resumen_base['Mes_Nombre'],
            y=resumen_base[ventas_col],
            marker=dict(color='#64748B'),
            text=resumen_base[ventas_col].apply(money_fmt),
            textposition='outside',
            textfont=dict(size=9)
        ))
        
        fig_mensual.add_trace(go.Bar(
            name=f'{año_comp}',
            x=resumen_comp['Mes_Nombre'],
            y=resumen_comp[ventas_col],
            marker=dict(color='#2563EB'),
            text=resumen_comp[ventas_col].apply(money_fmt),
            textposition='outside',
            textfont=dict(size=9)
        ))
        
        fig_mensual.update_layout(
            title='<b>Ventas por Mes</b>',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#F8FAFC', size=10),
            barmode='group',
            height=350,
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=dict(title=''),
            yaxis=dict(title='Ventas', tickformat='$,.0f'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0.5, xanchor='center'),
            showlegend=True
        )
        
        st.plotly_chart(fig_mensual, use_container_width=True)
        
        # Variación
        comparacion = resumen_base[['Mes', 'Mes_Nombre', ventas_col]].merge(
            resumen_comp[['Mes', ventas_col]],
            on='Mes',
            how='outer',
            suffixes=(f'_{año_base}', f'_{año_comp}')
        )
        
        comparacion['Var_Pct'] = ((comparacion[f'{ventas_col}_{año_comp}'] - 
                                    comparacion[f'{ventas_col}_{año_base}']) / 
                                   comparacion[f'{ventas_col}_{año_base}']) * 100
        
        colors_var = ['#10B981' if x >= 0 else '#EF4444' for x in comparacion['Var_Pct']]
        
        fig_var = go.Figure()
        
        fig_var.add_trace(go.Bar(
            x=comparacion['Mes_Nombre'],
            y=comparacion['Var_Pct'],
            marker=dict(color=colors_var),
            text=comparacion['Var_Pct'].apply(lambda x: f'{x:+.0f}%'),
            textposition='outside',
            textfont=dict(size=9)
        ))
        
        fig_var.update_layout(
            title='<b>% Variación</b>',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#F8FAFC', size=10),
            height=250,
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=dict(title=''),
            yaxis=dict(title='%', zeroline=True),
            showlegend=False
        )
        
        st.plotly_chart(fig_var, use_container_width=True)
    
    # ========================================
    # DERECHA: COMPARACIÓN ACUMULADA
    # ========================================
    with col_der:
        st.markdown("### 📈 Acumulado")
        
        # Gráfica de líneas acumuladas
        fig_acum = go.Figure()
        
        fig_acum.add_trace(go.Scatter(
            name=f'{año_base}',
            x=resumen_base['Mes_Nombre'],
            y=resumen_base['Ventas_Acum'],
            mode='lines+markers',
            line=dict(color='#64748B', width=3),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>%{y:$,.0f}<extra></extra>'
        ))
        
        fig_acum.add_trace(go.Scatter(
            name=f'{año_comp}',
            x=resumen_comp['Mes_Nombre'],
            y=resumen_comp['Ventas_Acum'],
            mode='lines+markers',
            line=dict(color='#2563EB', width=3),
            marker=dict(size=6),
            hovertemplate='<b>%{x}</b><br>%{y:$,.0f}<extra></extra>'
        ))
        
        fig_acum.update_layout(
            title='<b>Ventas Acumuladas</b>',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#F8FAFC', size=10),
            height=350,
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=dict(title=''),
            yaxis=dict(title='Acumulado', tickformat='$,.0f'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0.5, xanchor='center'),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_acum, use_container_width=True)
        
        # Utilidad acumulada
        fig_util_acum = go.Figure()
        
        fig_util_acum.add_trace(go.Scatter(
            name=f'{año_base}',
            x=resumen_base['Mes_Nombre'],
            y=resumen_base['Utilidad_Acum'],
            mode='lines+markers',
            line=dict(color='#F59E0B', width=3, dash='dash'),
            marker=dict(size=6)
        ))
        
        fig_util_acum.add_trace(go.Scatter(
            name=f'{año_comp}',
            x=resumen_comp['Mes_Nombre'],
            y=resumen_comp['Utilidad_Acum'],
            mode='lines+markers',
            line=dict(color='#10B981', width=3),
            marker=dict(size=6)
        ))
        
        fig_util_acum.update_layout(
            title='<b>Utilidad Acumulada</b>',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#F8FAFC', size=10),
            height=250,
            margin=dict(l=40, r=20, t=40, b=40),
            xaxis=dict(title=''),
            yaxis=dict(title='Utilidad', tickformat='$,.0f'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0.5, xanchor='center'),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_util_acum, use_container_width=True)
    
    # ========================================
    # ── TABLAS DE CALOR — FAMILIAS Y MARCAS ─────────────────
    st.markdown("---")

    MONTHS_ABBR = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                   7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    TOP_N = 5
    vcol_tm = _ventas_col(ventas_con_iva)

    def _heatmap_mensual_acumulado(df_b, df_c, dim_col, año_b, año_c, titulo):
        """
        Genera 2 heatmaps lado a lado:
        - Izquierda: variación % mensual
        - Derecha: variación % acumulada mes a mes
        """
        # Top N por ventas año comparado
        top_dims = (df_c.groupby(dim_col, observed=True)[vcol_tm]
                        .sum().sort_values(ascending=False).index.tolist())

        # Pivot mensual
        def _pivot(df, dims):
            g = (df[df[dim_col].isin(dims)]
                 .groupby([dim_col, "Mes"], observed=True)
                 .agg(V=(vcol_tm,"sum")).reset_index())
            p = g.pivot(index=dim_col, columns="Mes", values="V").fillna(0)
            p.columns = [MONTHS_ABBR.get(c, c) for c in p.columns]
            return p

        piv_b = _pivot(df_b, top_dims)
        piv_c = _pivot(df_c, top_dims)

        # Alinear columnas (solo meses presentes en ambos)
        meses_comunes = [m for m in MONTHS_ABBR.values()
                         if m in piv_b.columns and m in piv_c.columns]

        piv_b = piv_b.reindex(columns=meses_comunes, fill_value=0)
        piv_c = piv_c.reindex(columns=meses_comunes, fill_value=0)

        # Reindexar por top_dims
        piv_b = piv_b.reindex(top_dims).fillna(0)
        piv_c = piv_c.reindex(top_dims).fillna(0)

        # Variación % mensual
        with np.errstate(divide="ignore", invalid="ignore"):
            var_mens = np.where(piv_b > 0,
                                (piv_c.values - piv_b.values) / piv_b.values * 100,
                                np.nan)
        df_var_mens = pd.DataFrame(var_mens, index=top_dims, columns=meses_comunes)

        # Variación % acumulada
        acum_b = piv_b.cumsum(axis=1)
        acum_c = piv_c.cumsum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            var_acum = np.where(acum_b > 0,
                                (acum_c.values - acum_b.values) / acum_b.values * 100,
                                np.nan)
        df_var_acum = pd.DataFrame(var_acum, index=top_dims, columns=meses_comunes)

        def _make_heatmap(df_var, subtitulo):
            # Texto de cada celda
            text = df_var.applymap(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
            ).values

            # Colores: rojo=-50%, blanco=0%, verde=+50%
            colorscale = [
                [0.0,  "#7F1D1D"],
                [0.25, "#EF4444"],
                [0.45, "#FCA5A5"],
                [0.5,  "#1E293B"],
                [0.55, "#86EFAC"],
                [0.75, "#16A34A"],
                [1.0,  "#14532D"],
            ]

            fig = go.Figure(go.Heatmap(
                z=df_var.values,
                x=df_var.columns.tolist(),
                y=df_var.index.tolist(),
                text=text,
                texttemplate="%{text}",
                textfont=dict(size=11, color="white"),
                colorscale=colorscale,
                zmid=0,
                zmin=-50,
                zmax=50,
                colorbar=dict(
                    title="%",
                    thickness=10,
                    len=0.8,
                    ticksuffix="%"
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "%{x}: <b>%{text}</b><br>"
                    "<extra></extra>"
                )
            ))

            fig.update_layout(
                title=dict(text=f"<b>{subtitulo}</b>",
                           font=dict(size=12, color="#F8FAFC")),
                height=180 + len(top_dims) * 32,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#F8FAFC", size=10),
                margin=dict(l=10, r=10, t=45, b=10),
                xaxis=dict(side="top", tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
            )
            return fig

        col_izq, col_der = st.columns(2, gap="large")
        with col_izq:
            st.plotly_chart(
                _make_heatmap(df_var_mens, f"{titulo} — Variación % Mensual vs {año_b}", use_container_width=True),
                use_container_width=True
            )
        with col_der:
            st.plotly_chart(
                _make_heatmap(df_var_acum, f"{titulo} — Variación % Acumulada vs {año_b}", use_container_width=True),
                use_container_width=True
            )

        # Leyenda
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("🟢 **Verde** — Crecimiento vs año anterior")
        with c2: st.markdown("⬛ **Oscuro** — Sin cambio")
        with c3: st.markdown("🔴 **Rojo** — Caída vs año anterior")

    # ── FAMILIAS ─────────────────────────────────────────────
    st.markdown("### 📦 Familias — Tabla de Calor")
    st.caption(f"Variación % de {año_comp} vs {año_base} · Solo meses con datos en ambos años")
    _heatmap_mensual_acumulado(df_base, df_comp, "Familia_Nombre", año_base, año_comp, "Familias")

    st.markdown("---")

    # ── MARCAS ───────────────────────────────────────────────
    st.markdown("### 🏷️ Marcas — Tabla de Calor")
    st.caption(f"Variación % de {año_comp} vs {año_base} · Solo meses con datos en ambos años")
    _heatmap_mensual_acumulado(df_base, df_comp, "Marca_Nombre", año_base, año_comp, "Marcas")

        # ========================================
    # TABLA RESUMEN ABAJO
    # ========================================
    st.markdown("---")
    st.markdown("### 📋 Tabla Comparativa")
    
    # Merge completo
    tabla_comp = comparacion[['Mes_Nombre', f'{ventas_col}_{año_base}', 
                               f'{ventas_col}_{año_comp}', 'Var_Pct']].merge(
        resumen_base[['Mes', 'Ventas_Acum', 'Utilidad_Acum']],
        left_on='Mes_Nombre',
        right_on=resumen_base['Mes'].map(MONTHS_FULL),
        how='left'
    ).merge(
        resumen_comp[['Mes', 'Ventas_Acum', 'Utilidad_Acum']],
        left_on='Mes_Nombre',
        right_on=resumen_comp['Mes'].map(MONTHS_FULL),
        how='left',
        suffixes=(f'_{año_base}', f'_{año_comp}')
    )
    
    tabla_comp = tabla_comp[['Mes_Nombre', 
                              f'{ventas_col}_{año_base}', 
                              f'{ventas_col}_{año_comp}',
                              'Var_Pct',
                              f'Ventas_Acum_{año_base}',
                              f'Ventas_Acum_{año_comp}']]
    
    tabla_comp.columns = ['Mes', 
                          f'Ventas {año_base}', 
                          f'Ventas {año_comp}',
                          'Var %',
                          f'Acum {año_base}',
                          f'Acum {año_comp}']
    
    # Formatear
    for col in [f'Ventas {año_base}', f'Ventas {año_comp}', 
                f'Acum {año_base}', f'Acum {año_comp}']:
        tabla_comp[col] = tabla_comp[col].apply(money_fmt)
    
    tabla_comp['Var %'] = tabla_comp['Var %'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '—')
    
    st.dataframe(tabla_comp, use_container_width=True, height=400)
    
    # Resumen final
    st.markdown("---")
    cols_res = st.columns(4)
    
    total_base = resumen_base['Ventas_Acum'].iloc[-1] if len(resumen_base) > 0 else 0
    total_comp = resumen_comp['Ventas_Acum'].iloc[-1] if len(resumen_comp) > 0 else 0
    var_total = ((total_comp - total_base) / total_base * 100) if total_base > 0 else 0
    
    with cols_res[0]:
        st.metric(f"Total {año_base}", money_fmt(total_base))
    
    with cols_res[1]:
        st.metric(f"Total {año_comp}", money_fmt(total_comp), f"{var_total:+.1f}%")
    
    util_base = resumen_base['Utilidad_Acum'].iloc[-1] if len(resumen_base) > 0 else 0
    util_comp = resumen_comp['Utilidad_Acum'].iloc[-1] if len(resumen_comp) > 0 else 0
    var_util = ((util_comp - util_base) / util_base * 100) if util_base > 0 else 0
    
    with cols_res[2]:
        st.metric(f"Utilidad {año_base}", money_fmt(util_base))
    
    with cols_res[3]:
        st.metric(f"Utilidad {año_comp}", money_fmt(util_comp), f"{var_util:+.1f}%")



def crear_comparador_mensual_yoy(df_all: pd.DataFrame, year_actual: int, ventas_con_iva: bool):
    """
    Comparador mensual detallado año vs año
    """
    
    st.markdown("### 📅 Comparación Mensual (Año vs Año)")
    
    # Selector de años
    col1, col2, col3 = st.columns([2, 2, 2])
    
    años_disponibles = sorted(df_all['Año'].unique())
    
    with col1:
        año_base = st.selectbox(
            "Año Base (comparar contra):",
            años_disponibles,
            index=len(años_disponibles)-2 if len(años_disponibles) > 1 else 0,
            key="año_base_mensual"
        )
    
    with col2:
        año_comparar = st.selectbox(
            "Año a Comparar:",
            años_disponibles,
            index=len(años_disponibles)-1,
            key="año_comparar_mensual"
        )
    
    with col3:
        metrica_comparar = st.selectbox(
            "Métrica:",
            ["Ventas", "Utilidad", "Transacciones", "Ticket Promedio", "Margen %"],
            key="metrica_mensual"
        )
    
    if año_base == año_comparar:
        st.warning("⚠️ Selecciona años diferentes para comparar")
        return
    
    # Obtener datos
    ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
    
    # Resumen mensual para ambos años
    df_base = df_all[df_all['Año'] == año_base]
    df_comp = df_all[df_all['Año'] == año_comparar]
    
    # Agrupar por mes
    resumen_base = df_base.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique',
        'Sub Total': 'sum'
    }).reset_index()
    
    resumen_comp = df_comp.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique',
        'Sub Total': 'sum'
    }).reset_index()
    
    # Calcular métricas
    resumen_base['Ticket'] = resumen_base[ventas_col] / resumen_base['DOC_KEY']
    resumen_base['Margen'] = resumen_base['Utilidad'] / resumen_base['Sub Total']
    
    resumen_comp['Ticket'] = resumen_comp[ventas_col] / resumen_comp['DOC_KEY']
    resumen_comp['Margen'] = resumen_comp['Utilidad'] / resumen_comp['Sub Total']
    
    # Mapear métrica seleccionada
    metrica_map = {
        "Ventas": ventas_col,
        "Utilidad": "Utilidad",
        "Transacciones": "DOC_KEY",
        "Ticket Promedio": "Ticket",
        "Margen %": "Margen"
    }
    
    col_metrica = metrica_map[metrica_comparar]
    
    # Merge para comparación
    comparacion = resumen_base[['Mes', col_metrica]].merge(
        resumen_comp[['Mes', col_metrica]],
        on='Mes',
        how='outer',
        suffixes=(f'_{año_base}', f'_{año_comparar}')
    )
    
    comparacion['Mes'] = comparacion['Mes'].astype(int)
    comparacion = comparacion.sort_values('Mes')
    comparacion['Mes_Nombre'] = comparacion['Mes'].map(MONTHS_FULL)
    
    # Calcular variación
    col_base = f'{col_metrica}_{año_base}'
    col_comp = f'{col_metrica}_{año_comparar}'
    
    comparacion['Variacion_Abs'] = comparacion[col_comp] - comparacion[col_base]
    comparacion['Variacion_Pct'] = ((comparacion[col_comp] - comparacion[col_base]) / comparacion[col_base]) * 100
    
    # GRÁFICA DE BARRAS AGRUPADAS
    fig_barras = go.Figure()
    
    fig_barras.add_trace(go.Bar(
        name=f'{año_base}',
        x=comparacion['Mes_Nombre'],
        y=comparacion[col_base],
        marker=dict(color='#64748B'),
        text=comparacion[col_base].apply(lambda x: money_fmt(x) if metrica_comparar in ["Ventas", "Utilidad", "Ticket Promedio"] else f'{x:,.0f}'),
        textposition='outside',
        textfont=dict(size=10)
    ))
    
    fig_barras.add_trace(go.Bar(
        name=f'{año_comparar}',
        x=comparacion['Mes_Nombre'],
        y=comparacion[col_comp],
        marker=dict(color='#2563EB'),
        text=comparacion[col_comp].apply(lambda x: money_fmt(x) if metrica_comparar in ["Ventas", "Utilidad", "Ticket Promedio"] else f'{x:,.0f}'),
        textposition='outside',
        textfont=dict(size=10)
    ))
    
    fig_barras.update_layout(
        title=f'<b>{metrica_comparar} - Comparación Mensual</b>',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        barmode='group',
        height=400,
        xaxis=dict(title='Mes'),
        yaxis=dict(title=metrica_comparar),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    st.plotly_chart(fig_barras, use_container_width=True)
    
    # GRÁFICA DE VARIACIÓN
    fig_variacion = go.Figure()
    
    colors = ['#10B981' if x >= 0 else '#EF4444' for x in comparacion['Variacion_Pct']]
    
    fig_variacion.add_trace(go.Bar(
        x=comparacion['Mes_Nombre'],
        y=comparacion['Variacion_Pct'],
        marker=dict(color=colors),
        text=comparacion['Variacion_Pct'].apply(lambda x: f'{x:+.1f}%'),
        textposition='outside',
        textfont=dict(size=10),
        hovertemplate='<b>%{x}</b><br>Variación: %{y:.1f}%<extra></extra>'
    ))
    
    fig_variacion.update_layout(
        title=f'<b>% Variación {año_comparar} vs {año_base}</b>',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        height=300,
        xaxis=dict(title='Mes'),
        yaxis=dict(title='% Variación', zeroline=True, zerolinecolor='rgba(255,255,255,0.3)'),
        showlegend=False
    )
    
    st.plotly_chart(fig_variacion, use_container_width=True)
    
    # TABLA DETALLADA
    st.markdown("#### 📋 Detalle Mensual")
    
    # Formatear tabla
    tabla_display = comparacion[['Mes_Nombre', col_base, col_comp, 'Variacion_Abs', 'Variacion_Pct']].copy()
    tabla_display.columns = ['Mes', f'{año_base}', f'{año_comparar}', 'Var. Abs', 'Var. %']
    
    # Aplicar formato
    if metrica_comparar in ["Ventas", "Utilidad", "Ticket Promedio"]:
        tabla_display[f'{año_base}'] = tabla_display[f'{año_base}'].apply(money_fmt)
        tabla_display[f'{año_comparar}'] = tabla_display[f'{año_comparar}'].apply(money_fmt)
        tabla_display['Var. Abs'] = tabla_display['Var. Abs'].apply(money_fmt)
    elif metrica_comparar == "Margen %":
        tabla_display[f'{año_base}'] = tabla_display[f'{año_base}'].apply(lambda x: pct_fmt(x) if pd.notna(x) else '—')
        tabla_display[f'{año_comparar}'] = tabla_display[f'{año_comparar}'].apply(lambda x: pct_fmt(x) if pd.notna(x) else '—')
        tabla_display['Var. Abs'] = tabla_display['Var. Abs'].apply(lambda x: f'{x:+.1f} pp' if pd.notna(x) else '—')
    else:
        tabla_display[f'{año_base}'] = tabla_display[f'{año_base}'].apply(lambda x: f'{x:,.0f}')
        tabla_display[f'{año_comparar}'] = tabla_display[f'{año_comparar}'].apply(lambda x: f'{x:,.0f}')
        tabla_display['Var. Abs'] = tabla_display['Var. Abs'].apply(lambda x: f'{x:+,.0f}')
    
    tabla_display['Var. %'] = tabla_display['Var. %'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '—')
    
    st.dataframe(tabla_display, use_container_width=True, height=400)


def crear_comparador_acumulado_yoy(df_all: pd.DataFrame, year_actual: int, ventas_con_iva: bool):
    """
    Comparador acumulado año vs año
    """
    
    st.markdown("### 📈 Comparación Acumulada (Año vs Año)")
    st.markdown("*Acumulado mes a mes para identificar tendencias*")
    
    # Selector de años
    col1, col2 = st.columns(2)
    
    años_disponibles = sorted(df_all['Año'].unique())
    
    with col1:
        año_base_acum = st.selectbox(
            "Año Base:",
            años_disponibles,
            index=len(años_disponibles)-2 if len(años_disponibles) > 1 else 0,
            key="año_base_acum"
        )
    
    with col2:
        año_comparar_acum = st.selectbox(
            "Año a Comparar:",
            años_disponibles,
            index=len(años_disponibles)-1,
            key="año_comparar_acum"
        )
    
    if año_base_acum == año_comparar_acum:
        st.warning("⚠️ Selecciona años diferentes para comparar")
        return
    
    # Obtener datos
    ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
    
    df_base = df_all[df_all['Año'] == año_base_acum]
    df_comp = df_all[df_all['Año'] == año_comparar_acum]
    
    # Resumen mensual
    resumen_base = df_base.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique'
    }).reset_index().sort_values('Mes')
    
    resumen_comp = df_comp.groupby('Mes').agg({
        ventas_col: 'sum',
        'Utilidad': 'sum',
        'DOC_KEY': 'nunique'
    }).reset_index().sort_values('Mes')
    
    # CALCULAR ACUMULADOS
    resumen_base['Ventas_Acum'] = resumen_base[ventas_col].cumsum()
    resumen_base['Utilidad_Acum'] = resumen_base['Utilidad'].cumsum()
    resumen_base['Txns_Acum'] = resumen_base['DOC_KEY'].cumsum()
    
    resumen_comp['Ventas_Acum'] = resumen_comp[ventas_col].cumsum()
    resumen_comp['Utilidad_Acum'] = resumen_comp['Utilidad'].cumsum()
    resumen_comp['Txns_Acum'] = resumen_comp['DOC_KEY'].cumsum()
    
    resumen_base['Mes_Nombre'] = resumen_base['Mes'].map(MONTHS_FULL)
    resumen_comp['Mes_Nombre'] = resumen_comp['Mes'].map(MONTHS_FULL)
    
    # GRÁFICA DE VENTAS ACUMULADAS
    fig_acum = go.Figure()
    
    fig_acum.add_trace(go.Scatter(
        name=f'Ventas {año_base_acum}',
        x=resumen_base['Mes_Nombre'],
        y=resumen_base['Ventas_Acum'],
        mode='lines+markers',
        line=dict(color='#64748B', width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>Acumulado: %{y:$,.0f}<extra></extra>'
    ))
    
    fig_acum.add_trace(go.Scatter(
        name=f'Ventas {año_comparar_acum}',
        x=resumen_comp['Mes_Nombre'],
        y=resumen_comp['Ventas_Acum'],
        mode='lines+markers',
        line=dict(color='#2563EB', width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>Acumulado: %{y:$,.0f}<extra></extra>'
    ))
    
    fig_acum.update_layout(
        title='<b>Ventas Acumuladas - Comparación YoY</b>',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        height=400,
        xaxis=dict(title='Mes'),
        yaxis=dict(title='Ventas Acumuladas', tickformat='$,.0f'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_acum, use_container_width=True)
    
    # GRÁFICA DE UTILIDAD ACUMULADA
    fig_util_acum = go.Figure()
    
    fig_util_acum.add_trace(go.Scatter(
        name=f'Utilidad {año_base_acum}',
        x=resumen_base['Mes_Nombre'],
        y=resumen_base['Utilidad_Acum'],
        mode='lines+markers',
        line=dict(color='#F59E0B', width=3, dash='dash'),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>Acumulado: %{y:$,.0f}<extra></extra>'
    ))
    
    fig_util_acum.add_trace(go.Scatter(
        name=f'Utilidad {año_comparar_acum}',
        x=resumen_comp['Mes_Nombre'],
        y=resumen_comp['Utilidad_Acum'],
        mode='lines+markers',
        line=dict(color='#10B981', width=3),
        marker=dict(size=8),
        hovertemplate='<b>%{x}</b><br>Acumulado: %{y:$,.0f}<extra></extra>'
    ))
    
    fig_util_acum.update_layout(
        title='<b>Utilidad Acumulada - Comparación YoY</b>',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='#F8FAFC'),
        height=400,
        xaxis=dict(title='Mes'),
        yaxis=dict(title='Utilidad Acumulada', tickformat='$,.0f'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_util_acum, use_container_width=True)
    
    # TABLA COMPARATIVA ACUMULADA
    st.markdown("#### 📋 Tabla Acumulada")
    
    # Merge para comparación
    comparacion_acum = resumen_base[['Mes', 'Mes_Nombre', 'Ventas_Acum', 'Utilidad_Acum', 'Txns_Acum']].merge(
        resumen_comp[['Mes', 'Ventas_Acum', 'Utilidad_Acum', 'Txns_Acum']],
        on='Mes',
        how='outer',
        suffixes=(f'_{año_base_acum}', f'_{año_comparar_acum}')
    ).sort_values('Mes')
    
    # Calcular variaciones
    comparacion_acum[f'Var_Ventas'] = ((comparacion_acum[f'Ventas_Acum_{año_comparar_acum}'] - 
                                         comparacion_acum[f'Ventas_Acum_{año_base_acum}']) / 
                                        comparacion_acum[f'Ventas_Acum_{año_base_acum}']) * 100
    
    comparacion_acum[f'Var_Utilidad'] = ((comparacion_acum[f'Utilidad_Acum_{año_comparar_acum}'] - 
                                          comparacion_acum[f'Utilidad_Acum_{año_base_acum}']) / 
                                         comparacion_acum[f'Utilidad_Acum_{año_base_acum}']) * 100
    
    # Formatear tabla
    tabla_acum = comparacion_acum[['Mes_Nombre', 
                                    f'Ventas_Acum_{año_base_acum}', 
                                    f'Ventas_Acum_{año_comparar_acum}',
                                    'Var_Ventas',
                                    f'Utilidad_Acum_{año_base_acum}',
                                    f'Utilidad_Acum_{año_comparar_acum}',
                                    'Var_Utilidad']].copy()
    
    tabla_acum.columns = ['Mes', 
                          f'Ventas {año_base_acum}', 
                          f'Ventas {año_comparar_acum}',
                          'Var %',
                          f'Utilidad {año_base_acum}',
                          f'Utilidad {año_comparar_acum}',
                          'Var %']
    
    # Aplicar formato
    for col in [f'Ventas {año_base_acum}', f'Ventas {año_comparar_acum}', 
                f'Utilidad {año_base_acum}', f'Utilidad {año_comparar_acum}']:
        tabla_acum[col] = tabla_acum[col].apply(money_fmt)
    
    # Formatear variaciones
    var_cols = [c for c in tabla_acum.columns if 'Var %' in c]
    for col in var_cols:
        tabla_acum[col] = tabla_acum[col].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '—')
    
    st.dataframe(tabla_acum, use_container_width=True, height=400)
    
    # RESUMEN EJECUTIVO
    st.markdown("---")
    st.markdown("#### 📊 Resumen Ejecutivo")
    
    cols_resumen = st.columns(4)
    
    # Totales del año
    total_ventas_base = resumen_base['Ventas_Acum'].iloc[-1] if len(resumen_base) > 0 else 0
    total_ventas_comp = resumen_comp['Ventas_Acum'].iloc[-1] if len(resumen_comp) > 0 else 0
    var_ventas_total = ((total_ventas_comp - total_ventas_base) / total_ventas_base * 100) if total_ventas_base > 0 else 0
    
    total_util_base = resumen_base['Utilidad_Acum'].iloc[-1] if len(resumen_base) > 0 else 0
    total_util_comp = resumen_comp['Utilidad_Acum'].iloc[-1] if len(resumen_comp) > 0 else 0
    var_util_total = ((total_util_comp - total_util_base) / total_util_base * 100) if total_util_base > 0 else 0
    
    with cols_resumen[0]:
        st.metric(
            f"Ventas {año_base_acum}",
            money_fmt(total_ventas_base)
        )
    
    with cols_resumen[1]:
        st.metric(
            f"Ventas {año_comparar_acum}",
            money_fmt(total_ventas_comp),
            f"{var_ventas_total:+.1f}%"
        )
    
    with cols_resumen[2]:
        st.metric(
            f"Utilidad {año_base_acum}",
            money_fmt(total_util_base)
        )
    
    with cols_resumen[3]:
        st.metric(
            f"Utilidad {año_comparar_acum}",
            money_fmt(total_util_comp),
            f"{var_util_total:+.1f}%"
        )



# ============================================================
# 🎨 NUEVA SECCIÓN HERO - DASHBOARD MEJORADO
# ============================================================

st.markdown("""
<div class="hero-section">
    <div class="hero-title">📊 FERRETERÍA EL CEDRO - Dashboard Ejecutivo</div>
    <div class="hero-subtitle">
        Período: Últimos 13 meses | 
        Actualizado: {}
    </div>
</div>
""".format(datetime.now().strftime("%d/%m/%Y %H:%M")), unsafe_allow_html=True)

# ============================================================
# FILTROS AVANZADOS EN EXPANDER
# ============================================================
with st.expander("🔍 Filtros Avanzados y Opciones", expanded=False):
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        st.markdown("#### 📅 Período de Análisis")
        periodo_tipo = st.radio(
            "Tipo de período:",
            ["Últimos 13 meses", "Último trimestre", "Año completo", "Personalizado"],
            index=0,
            key="periodo_tipo_hero"
        )
        
    with col_f2:
        st.markdown("#### 💰 Rango de Ventas")
        if not df_kpi.empty:
            max_venta = float(df_kpi[_ventas_col(ventas_con_iva)].sum() * 1.2)
            rango_ventas = st.slider(
                "Filtrar por rango:",
                0.0, max_venta,
                (0.0, max_venta),
                key="rango_ventas_hero"
            )
        
    with col_f3:
        st.markdown("#### 📊 Vista Rápida")
        vista_rapida = st.multiselect(
            "Mostrar secciones:",
            ["KPIs", "Gráficas", "Tablas", "Heatmap", "Waterfall"],
            default=["KPIs", "Gráficas"],
            key="vista_rapida_hero"
        )

# ============================================================
# SECCIÓN DE KPIs MEJORADOS CON SPARKLINES
# ============================================================

st.markdown("### 📊 Indicadores Clave con Tendencia")

# Obtener datos históricos para sparklines (últimos 6 meses)
if not ms_cur.empty:
    ultimos_meses = ms_cur.tail(6)
    sparkline_ventas = ultimos_meses['Ventas_Total'].tolist()
    sparkline_utilidad = ultimos_meses['Utilidad'].tolist()
    sparkline_txns = ultimos_meses['TXNS'].tolist()
    sparkline_margen = ultimos_meses['Margen'].tolist()
else:
    sparkline_ventas = sparkline_utilidad = sparkline_txns = sparkline_margen = []

# Calcular color de tendencia
y_sales = (k_cur["ventas"] - k_prev["ventas"]) / k_prev["ventas"] if k_prev["ventas"] > 0 else 0
trend_color_ventas = "#10B981" if y_sales >= 0 else "#EF4444"

y_profit = (k_cur["utilidad"] - k_prev["utilidad"]) / k_prev["utilidad"] if k_prev["utilidad"] > 0 else 0
trend_color_utilidad = "#10B981" if y_profit >= 0 else "#EF4444"

# KPIs con sparklines en 4 columnas
kpi_cols = st.columns(4)

with kpi_cols[0]:
    cls, txt = _pill_pct(y_sales)
    kpi_card_with_sparkline(
        "💰 VENTAS TOTALES" + (" (CON IVA)" if ventas_con_iva else " (SIN IVA)"),
        money_fmt(k_cur["ventas"]),
        txt, cls,
        sparkline_ventas,
        trend_color_ventas
    )

with kpi_cols[1]:
    cls, txt = _pill_pct(y_profit)
    kpi_card_with_sparkline(
        "📈 UTILIDAD TOTAL",
        money_fmt(k_cur["utilidad"]),
        txt, cls,
        sparkline_utilidad,
        trend_color_utilidad
    )

with kpi_cols[2]:
    d_margin_pp = (k_cur["margen"] - k_prev["margen"]) if pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"]) else 0
    cls, txt = _pill_pp(d_margin_pp)
    kpi_card_with_sparkline(
        "🎯 MARGEN",
        pct_fmt(k_cur["margen"]) if pd.notna(k_cur["margen"]) else "—",
        txt, cls,
        sparkline_margen,
        "#10B981"
    )

with kpi_cols[3]:
    y_txns = (k_cur["txns"] - k_prev["txns"]) / k_prev["txns"] if k_prev["txns"] > 0 else 0
    cls, txt = _pill_pct(y_txns)
    kpi_card_with_sparkline(
        "🔄 TRANSACCIONES",
        num_fmt(k_cur["txns"]),
        txt, cls,
        sparkline_txns,
        "#10B981" if y_txns >= 0 else "#EF4444"
    )

# ============================================================
# HEATMAP DE RENDIMIENTO MENSUAL
# ============================================================

if "Heatmap" in vista_rapida or not 'vista_rapida' in locals():
    st.markdown("---")
    if not ms_cur.empty:
        fig_heatmap = create_heatmap_performance(ms_cur)
        st.plotly_chart(fig_heatmap, use_container_width=True)

# ============================================================
# GRÁFICAS COMPARATIVAS LADO A LADO
# ============================================================

if "Gráficas" in vista_rapida or not 'vista_rapida' in locals():
    st.markdown("---")
    st.markdown("### 📊 Análisis Comparativo")
    
    comp_cols = st.columns(2)
    
    # GAUGES DE MARGEN Y UTILIDAD
    with comp_cols[0]:
        if pd.notna(k_cur["margen"]):
            fig_gauge_margen = create_gauge_chart(
                k_cur["margen"],
                0.5,  # Max 50%
                "Margen de Utilidad",
                0.25  # Threshold 25%
            )
            st.plotly_chart(fig_gauge_margen, use_container_width=True)
    
    # WATERFALL DE UTILIDAD
    with comp_cols[1]:
        fig_waterfall = create_waterfall_chart(k_cur, k_prev)
        st.plotly_chart(fig_waterfall, use_container_width=True)

# ============================================================
# BULLET CHARTS DE OBJETIVOS
# ============================================================

st.markdown("---")
st.markdown("### 🎯 Progreso vs Objetivos")

# Calcular objetivos (10% más que año anterior)
objetivo_ventas = k_prev["ventas"] * 1.10
objetivo_utilidad = k_prev["utilidad"] * 1.10
objetivo_txns = k_prev["txns"] * 1.05

bullet_cols = st.columns(3)

with bullet_cols[0]:
    st.markdown(
        create_bullet_chart(k_cur["ventas"], objetivo_ventas, "Ventas vs Objetivo (+10% YoY)"),
        unsafe_allow_html=True
    )

with bullet_cols[1]:
    st.markdown(
        create_bullet_chart(k_cur["utilidad"], objetivo_utilidad, "Utilidad vs Objetivo (+10% YoY)"),
        unsafe_allow_html=True
    )

with bullet_cols[2]:
    st.markdown(
        create_bullet_chart(k_cur["txns"], objetivo_txns, "Transacciones vs Objetivo (+5% YoY)"),
        unsafe_allow_html=True
    )

# ============================================================
# SEPARADOR ANTES DEL CONTENIDO ORIGINAL
# ============================================================

st.markdown("---")
st.markdown("## 📋 Dashboard Detallado")
st.markdown("*Vista completa con todas las métricas y análisis*")

# ============================================================
# FUNCIONES DE ANÁLISIS INTELIGENTE Y RESUMEN EJECUTIVO
# ============================================================

def analizar_cambios_yoy(k_cur: dict, k_prev: dict, ms_cur: pd.DataFrame, ms_prev: pd.DataFrame) -> dict:
    """
    Analiza cambios YoY y determina posibles causas
    """
    analisis = {
        'cambio_ventas': 0,
        'cambio_utilidad': 0,
        'cambio_margen': 0,
        'causas_identificadas': [],
        'alertas': [],
        'recomendaciones': []
    }
    
    # Calcular cambios
    if k_prev["ventas"] > 0:
        analisis['cambio_ventas'] = ((k_cur["ventas"] - k_prev["ventas"]) / k_prev["ventas"]) * 100
    
    if k_prev["utilidad"] > 0:
        analisis['cambio_utilidad'] = ((k_cur["utilidad"] - k_prev["utilidad"]) / k_prev["utilidad"]) * 100
    
    if pd.notna(k_prev["margen"]) and pd.notna(k_cur["margen"]):
        analisis['cambio_margen'] = (k_cur["margen"] - k_prev["margen"]) * 100
    
    # ANÁLISIS DE CAUSAS
    
    # 1. Ventas bajaron pero utilidad subió = Mejora de margen
    if analisis['cambio_ventas'] < 0 and analisis['cambio_utilidad'] > 0:
        analisis['causas_identificadas'].append({
            'tipo': 'positivo',
            'titulo': '💰 Mejora de Rentabilidad',
            'descripcion': f"Aunque las ventas bajaron {abs(analisis['cambio_ventas']):.1f}%, la utilidad subió {analisis['cambio_utilidad']:.1f}%. Esto indica mejor margen de ganancia."
        })
        analisis['recomendaciones'].append("✅ Mantener la estrategia actual de productos más rentables")
    
    # 2. Ventas subieron pero utilidad bajó = Problema de margen
    elif analisis['cambio_ventas'] > 0 and analisis['cambio_utilidad'] < 0:
        analisis['causas_identificadas'].append({
            'tipo': 'alerta',
            'titulo': '⚠️ Crecimiento No Rentable',
            'descripcion': f"Las ventas subieron {analisis['cambio_ventas']:.1f}% pero la utilidad bajó {abs(analisis['cambio_utilidad']):.1f}%. Posible exceso de descuentos o cambio a productos menos rentables."
        })
        analisis['alertas'].append("⚠️ Revisar política de descuentos")
        analisis['recomendaciones'].append("🔍 Analizar mix de productos vendidos vs año anterior")
    
    # 3. Ambos bajaron = Problema general
    elif analisis['cambio_ventas'] < 0 and analisis['cambio_utilidad'] < 0:
        if abs(analisis['cambio_utilidad']) > abs(analisis['cambio_ventas']) * 1.5:
            analisis['causas_identificadas'].append({
                'tipo': 'critico',
                'titulo': '🚨 Caída Acelerada de Utilidad',
                'descripcion': f"Ventas bajaron {abs(analisis['cambio_ventas']):.1f}% pero utilidad cayó {abs(analisis['cambio_utilidad']):.1f}%. El margen está empeorando."
            })
            analisis['alertas'].append("🚨 Urgente: Revisar estructura de costos")
        else:
            analisis['causas_identificadas'].append({
                'tipo': 'neutral',
                'titulo': '📉 Disminución Proporcional',
                'descripcion': f"Ventas y utilidad bajaron proporcionalmente ({abs(analisis['cambio_ventas']):.1f}% y {abs(analisis['cambio_utilidad']):.1f}%). El margen se mantiene."
            })
    
    # 4. Ambos subieron = Éxito
    elif analisis['cambio_ventas'] > 0 and analisis['cambio_utilidad'] > 0:
        if analisis['cambio_utilidad'] > analisis['cambio_ventas'] * 1.2:
            analisis['causas_identificadas'].append({
                'tipo': 'excelente',
                'titulo': '🎉 Crecimiento Acelerado',
                'descripcion': f"Ventas subieron {analisis['cambio_ventas']:.1f}% y utilidad {analisis['cambio_utilidad']:.1f}%. El margen está mejorando."
            })
            analisis['recomendaciones'].append("✅ Identificar qué productos están impulsando este crecimiento")
        else:
            analisis['causas_identificadas'].append({
                'tipo': 'positivo',
                'titulo': '📈 Crecimiento Saludable',
                'descripcion': f"Ventas y utilidad crecieron en línea ({analisis['cambio_ventas']:.1f}% y {analisis['cambio_utilidad']:.1f}%)."
            })
    
    # Análisis de transacciones vs ticket
    if k_prev["txns"] > 0:
        cambio_txns = ((k_cur["txns"] - k_prev["txns"]) / k_prev["txns"]) * 100
        cambio_ticket = ((k_cur["ticket"] - k_prev["ticket"]) / k_prev["ticket"]) * 100 if k_prev["ticket"] > 0 else 0
        
        if cambio_txns < -10:
            analisis['alertas'].append(f"⚠️ Transacciones cayeron {abs(cambio_txns):.1f}% - Menos clientes")
            analisis['recomendaciones'].append("📢 Considerar campaña de atracción de clientes")
        
        if cambio_ticket > 15:
            analisis['causas_identificadas'].append({
                'tipo': 'positivo',
                'titulo': '💳 Ticket Promedio Alto',
                'descripcion': f"El ticket promedio subió {cambio_ticket:.1f}%. Los clientes están comprando más por visita."
            })
    
    return analisis


def crear_resumen_ejecutivo(df_kpi: pd.DataFrame, k_cur: dict, k_prev: dict, 
                            ms_cur: pd.DataFrame, ms_prev: pd.DataFrame,
                            ventas_con_iva: bool, sucursal: str):
    """
    Crea el tab de resumen ejecutivo con análisis inteligente
    """
    
    st.markdown("## 📊 Resumen Ejecutivo del Período")
    
    # Análisis automático de cambios
    analisis = analizar_cambios_yoy(k_cur, k_prev, ms_cur, ms_prev)
    
    # ========================================
    # SECCIÓN 1: ANÁLISIS INTELIGENTE
    # ========================================
    st.markdown("### 🧠 Análisis Inteligente")
    
    # Mostrar causas identificadas
    if analisis['causas_identificadas']:
        for causa in analisis['causas_identificadas']:
            if causa['tipo'] == 'excelente':
                st.success(f"**{causa['titulo']}**\n\n{causa['descripcion']}")
            elif causa['tipo'] == 'positivo':
                st.info(f"**{causa['titulo']}**\n\n{causa['descripcion']}")
            elif causa['tipo'] == 'alerta':
                st.warning(f"**{causa['titulo']}**\n\n{causa['descripcion']}")
            elif causa['tipo'] == 'critico':
                st.error(f"**{causa['titulo']}**\n\n{causa['descripcion']}")
            else:
                st.info(f"**{causa['titulo']}**\n\n{causa['descripcion']}")
    
    # Alertas
    if analisis['alertas']:
        with st.expander("⚠️ Alertas Importantes", expanded=True):
            for alerta in analisis['alertas']:
                st.markdown(f"- {alerta}")
    
    # Recomendaciones
    if analisis['recomendaciones']:
        with st.expander("💡 Recomendaciones", expanded=False):
            for rec in analisis['recomendaciones']:
                st.markdown(f"- {rec}")
    
    st.markdown("---")
    
    # ========================================
    # SECCIÓN 2: TOP & BOTTOM PERFORMERS
    # ========================================
    st.markdown("### 🏆 Top & Bottom Performers")
    
    if not df_kpi.empty and "Vendedor_Nombre" in df_kpi.columns:
        
        # Agrupar por vendedor
        ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
        
        vendedores = df_kpi.groupby("Vendedor_Nombre", observed=True).agg({
            ventas_col: 'sum',
            'Utilidad': 'sum',
            'DOC_KEY': 'nunique'
        }).reset_index()
        
        vendedores.columns = ['Vendedor', 'Ventas', 'Utilidad', 'Transacciones']
        vendedores = vendedores[vendedores['Vendedor'].notna()]
        vendedores = vendedores[vendedores['Vendedor'].str.strip() != '']
        vendedores = vendedores[vendedores['Vendedor'] != 'TODOS']
        
        if len(vendedores) > 0:
            # Calcular ticket promedio
            vendedores['Ticket_Prom'] = vendedores['Ventas'] / vendedores['Transacciones']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🥇 Top Performers")
                
                # Top en ventas
                top_ventas = vendedores.nlargest(1, 'Ventas').iloc[0]
                st.metric(
                    "💰 Mayor Vendedor",
                    top_ventas['Vendedor'],
                    f"{money_fmt(top_ventas['Ventas'])}"
                )
                
                # Top en utilidad
                top_utilidad = vendedores.nlargest(1, 'Utilidad').iloc[0]
                st.metric(
                    "📈 Mayor Utilidad",
                    top_utilidad['Vendedor'],
                    f"{money_fmt(top_utilidad['Utilidad'])}"
                )
                
                # Top en transacciones
                top_txns = vendedores.nlargest(1, 'Transacciones').iloc[0]
                st.metric(
                    "🔄 Más Transacciones",
                    top_txns['Vendedor'],
                    f"{int(top_txns['Transacciones']):,} txns"
                )
            
            with col2:
                st.markdown("#### 📊 Bottom Performers")
                
                # Bottom en ventas
                bottom_ventas = vendedores.nsmallest(1, 'Ventas').iloc[0]
                st.metric(
                    "💰 Menor Vendedor",
                    bottom_ventas['Vendedor'],
                    f"{money_fmt(bottom_ventas['Ventas'])}"
                )
                
                # Bottom en utilidad
                bottom_utilidad = vendedores.nsmallest(1, 'Utilidad').iloc[0]
                st.metric(
                    "📈 Menor Utilidad",
                    bottom_utilidad['Vendedor'],
                    f"{money_fmt(bottom_utilidad['Utilidad'])}"
                )
                
                # Bottom en ticket promedio
                bottom_ticket = vendedores.nsmallest(1, 'Ticket_Prom').iloc[0]
                st.metric(
                    "💳 Menor Ticket Promedio",
                    bottom_ticket['Vendedor'],
                    f"{money_fmt(bottom_ticket['Ticket_Prom'])}"
                )
    
    st.markdown("---")
    
    # ========================================
    # SECCIÓN 3: TOP 10 PRODUCTOS
    # ========================================
    st.markdown("### 📦 Top 10 - Productos, Marcas y Familias")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 Por Ventas",
        "📈 Por Utilidad",
        "🏷️ Marcas",
        "📂 Familias"
    ])
    
    with tab1:
        st.markdown("#### Top 10 Artículos por Ventas")
        
        if not df_kpi.empty and "Articulo" in df_kpi.columns:
            ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
            
            top_articulos_ventas = df_kpi.groupby("Articulo", observed=True).agg({
                ventas_col: 'sum',
                'Utilidad': 'sum',
                'DOC_KEY': 'nunique'
            }).reset_index()
            
            top_articulos_ventas.columns = ['Artículo', 'Ventas', 'Utilidad', 'Transacciones']
            top_articulos_ventas = top_articulos_ventas.nlargest(10, 'Ventas')
            
            # Formatear
            top_articulos_ventas['Ventas'] = top_articulos_ventas['Ventas'].apply(money_fmt)
            top_articulos_ventas['Utilidad'] = top_articulos_ventas['Utilidad'].apply(money_fmt)
            top_articulos_ventas['Transacciones'] = top_articulos_ventas['Transacciones'].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(top_articulos_ventas, use_container_width=True, height=400)
    
    with tab2:
        st.markdown("#### Top 10 Artículos por Utilidad")
        
        if not df_kpi.empty and "Articulo" in df_kpi.columns:
            ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
            
            top_articulos_utilidad = df_kpi.groupby("Articulo", observed=True).agg({
                ventas_col: 'sum',
                'Utilidad': 'sum',
                'DOC_KEY': 'nunique'
            }).reset_index()
            
            top_articulos_utilidad.columns = ['Artículo', 'Ventas', 'Utilidad', 'Transacciones']
            top_articulos_utilidad['Margen'] = (top_articulos_utilidad['Utilidad'] / top_articulos_utilidad['Ventas'] * 100).fillna(0)
            top_articulos_utilidad = top_articulos_utilidad.nlargest(10, 'Utilidad')
            
            # Formatear
            top_articulos_utilidad['Ventas'] = top_articulos_utilidad['Ventas'].apply(money_fmt)
            top_articulos_utilidad['Utilidad'] = top_articulos_utilidad['Utilidad'].apply(money_fmt)
            top_articulos_utilidad['Margen'] = top_articulos_utilidad['Margen'].apply(lambda x: f"{x:.1f}%")
            
            st.dataframe(top_articulos_utilidad, use_container_width=True, height=400)
    
    with tab3:
        st.markdown("#### Top 10 Marcas")
        
        if not df_kpi.empty and "Marca_Nombre" in df_kpi.columns:
            ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
            
            top_marcas = df_kpi.groupby("Marca_Nombre", observed=True).agg({
                ventas_col: 'sum',
                'Utilidad': 'sum',
                'DOC_KEY': 'nunique'
            }).reset_index()
            
            top_marcas.columns = ['Marca', 'Ventas', 'Utilidad', 'Transacciones']
            top_marcas = top_marcas.nlargest(10, 'Ventas')
            
            # Formatear
            top_marcas['Ventas'] = top_marcas['Ventas'].apply(money_fmt)
            top_marcas['Utilidad'] = top_marcas['Utilidad'].apply(money_fmt)
            top_marcas['Transacciones'] = top_marcas['Transacciones'].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(top_marcas, use_container_width=True, height=400)
    
    with tab4:
        st.markdown("#### Top 10 Familias")
        
        if not df_kpi.empty and "Familia_Nombre" in df_kpi.columns:
            ventas_col = "Total_alloc" if ventas_con_iva else "Sub Total"
            
            top_familias = df_kpi.groupby("Familia_Nombre", observed=True).agg({
                ventas_col: 'sum',
                'Utilidad': 'sum',
                'DOC_KEY': 'nunique'
            }).reset_index()
            
            top_familias.columns = ['Familia', 'Ventas', 'Utilidad', 'Transacciones']
            top_familias = top_familias.nlargest(10, 'Ventas')
            
            # Formatear
            top_familias['Ventas'] = top_familias['Ventas'].apply(money_fmt)
            top_familias['Utilidad'] = top_familias['Utilidad'].apply(money_fmt)
            top_familias['Transacciones'] = top_familias['Transacciones'].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(top_familias, use_container_width=True, height=400)


# ------------------------------------------------------------
# NUEVA ESTRUCTURA EJECUTIVA — 4 TABS
# Diseño C-Suite: máximo 2 niveles de navegación
# ------------------------------------------------------------
tab_comando, tab_negocio, tab_comparativos, tab_avanzado = st.tabs([
        "🎯 Comando Central",
        "📊 Análisis de Negocio",
        "📈 Comparativos",
        "🔬 Análisis Avanzado"
    ])


# ╔══════════════════════════════════════════════════════════════╗
# ║   NUEVA ARQUITECTURA EJECUTIVA — 4 TABS C-SUITE             ║
# ╚══════════════════════════════════════════════════════════════╝

# ──────────────────────────────────────────────────────────────
# FUNCIÓN AUXILIAR: Narrativa automática del período
# ──────────────────────────────────────────────────────────────
def narrativa_ejecutiva(k_cur, k_prev, sucursal, m_start, m_end, año_sel):
    """Narrativa directa estilo conversacional para el CCO"""
    MONTHS = {
        1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
        7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"
    }
    # Período en texto
    if m_start == m_end:
        periodo_txt = f"En {MONTHS.get(m_start, str(m_start))} de {año_sel}"
    else:
        periodo_txt = f"De {MONTHS.get(m_start, str(m_start))} a {MONTHS.get(m_end, str(m_end))} de {año_sel}"

    suc_txt = "en todas las sucursales" if sucursal == "CONSOLIDADO" else f"en {sucursal}"

    # Deltas
    cv = ((k_cur["ventas"]   - k_prev["ventas"])   / k_prev["ventas"]  * 100) if k_prev["ventas"]   > 0 else 0
    cu = ((k_cur["utilidad"] - k_prev["utilidad"]) / k_prev["utilidad"] * 100) if k_prev["utilidad"] > 0 else 0
    cm = (k_cur["margen"]    - k_prev["margen"]) * 100 if (pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"])) else 0

    # Texto ventas
    if cv > 0:
        txt_v = f'<span style="color:#10B981;font-weight:700;">▲ {cv:.1f}% más que el año pasado</span>'
    else:
        txt_v = f'<span style="color:#EF4444;font-weight:700;">▼ {abs(cv):.1f}% menos que el año pasado</span>'

    # Texto utilidad
    if cu > 0:
        txt_u = f'<span style="color:#10B981;font-weight:700;">▲ {cu:.1f}% más</span>'
    else:
        txt_u = f'<span style="color:#EF4444;font-weight:700;">▼ {abs(cu):.1f}% menos</span>'

    # Texto margen
    if cm > 0.2:
        txt_m = f'<span style="color:#10B981;font-weight:600;">subió {cm:.1f} puntos</span>'
    elif cm < -0.2:
        txt_m = f'<span style="color:#EF4444;font-weight:600;">bajó {abs(cm):.1f} puntos</span>'
    else:
        txt_m = f'<span style="color:#F59E0B;font-weight:600;">se mantuvo estable</span>'

    margen_actual = pct_fmt(k_cur["margen"]) if pd.notna(k_cur["margen"]) else "—"

    html = f"""
    <div style='background:linear-gradient(135deg,#1e3a5f 0%,#0f2540 100%);
                border-left:4px solid #2563EB;border-radius:8px;
                padding:16px 22px;margin-bottom:16px;'>
        <p style='color:#64748B;font-size:11px;margin:0 0 6px 0;
                  text-transform:uppercase;letter-spacing:1px;'>
            {periodo_txt} · {suc_txt}
        </p>
        <p style='color:#F1F5F9;font-size:16px;margin:0;line-height:1.8;'>
            Vendimos <strong>{money_fmt(k_cur["ventas"])}</strong>, {txt_v}.
            Ganamos <strong>{money_fmt(k_cur["utilidad"])}</strong> de utilidad ({txt_u}).
            El margen quedó en <strong>{margen_actual}</strong> — {txt_m}.
        </p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def semaforo_salud(k_cur, k_prev):
    """Semáforo ejecutivo de salud del negocio"""
    cv = ((k_cur["ventas"]   - k_prev["ventas"])   / k_prev["ventas"]  * 100) if k_prev["ventas"]   > 0 else 0
    cu = ((k_cur["utilidad"] - k_prev["utilidad"]) / k_prev["utilidad"] * 100) if k_prev["utilidad"] > 0 else 0
    cm = (k_cur["margen"]    - k_prev["margen"]) * 100 if (pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"])) else 0

    score = 0
    if cv > 5:  score += 2
    elif cv > 0: score += 1
    if cu > 5:  score += 2
    elif cu > 0: score += 1
    if cm > 0:  score += 1

    if score >= 4:
        estado, color, icono = "NEGOCIO SALUDABLE", "#10B981", "🟢"
    elif score >= 2:
        estado, color, icono = "ATENCIÓN REQUERIDA", "#F59E0B", "🟡"
    else:
        estado, color, icono = "ACCIÓN INMEDIATA", "#EF4444", "🔴"

    st.markdown(f"""
    <div style='display:inline-block;background:{color}22;border:1px solid {color};
                border-radius:20px;padding:4px 16px;margin-bottom:12px;'>
        <span style='color:{color};font-weight:700;font-size:13px;'>{icono} {estado}</span>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 1 — COMANDO CENTRAL
# Responde: ¿Estamos creciendo? ¿Hay alguna crisis?
# ══════════════════════════════════════════════════════════════
with tab_comando:

    # Semáforo y narrativa
    semaforo_salud(k_cur, k_prev)
    narrativa_ejecutiva(k_cur, k_prev, sucursal, m_start, m_end, int(year))

    # ── KPIs principales (5) ─────────────────────────────────
    y_sales    = yoy(k_cur["ventas"],    k_prev["ventas"])
    y_profit   = yoy(k_cur["utilidad"],  k_prev["utilidad"])
    d_margin   = (k_cur["margen"] - k_prev["margen"]) * 100 if (pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"])) else np.nan
    y_txns     = yoy(k_cur["txns"],      k_prev["txns"])
    y_ticket   = yoy(k_cur["ticket"],    k_prev["ticket"])

    # 4 KPIs ejecutivos principales — vista C-Suite
    cols = st.columns(4)
    with cols[0]:
        cls, txt = _pill_pct(y_sales);  kpi_card("Ventas Totales" + (" CON IVA" if ventas_con_iva else " SIN IVA"), money_fmt(k_cur["ventas"]), txt, cls)
    with cols[1]:
        cls, txt = _pill_pct(y_profit); kpi_card("Utilidad Bruta", money_fmt(k_cur["utilidad"]), txt, cls)
    with cols[2]:
        cls, txt = _pill_pp(d_margin);  kpi_card("Margen de Utilidad", pct_fmt(k_cur["margen"]) if pd.notna(k_cur["margen"]) else "—", txt, cls)
    with cols[3]:
        cls, txt = _pill_pct(y_ticket); kpi_card("Ticket Promedio", money_fmt(k_cur["ticket"]), txt, cls)

    # ── Gráfico mensual 13 meses ─────────────────────────────
    st.markdown("#### 📈 Evolución Mensual — Últimos 13 Meses")
    if GRAFICOS_MEJORADOS:
        st.plotly_chart(fig_grafica_mensual_mejorada(ms_cur, ventas_con_iva, max(1, m_start), m_end), use_container_width=True)
    else:
        st.plotly_chart(fig_hist_static(ms_cur, ventas_con_iva, m_start, m_end), use_container_width=True)

    # ── Análisis inteligente + Alertas priorizadas ───────────
    st.markdown("#### 🧠 Análisis Automático del Período")
    analisis = analizar_cambios_yoy(k_cur, k_prev, ms_cur, ms_prev)

    for causa in analisis["causas_identificadas"]:
        if causa["tipo"] == "excelente": st.success(f"**{causa['titulo']}** — {causa['descripcion']}")
        elif causa["tipo"] == "positivo": st.info(f"**{causa['titulo']}** — {causa['descripcion']}")
        elif causa["tipo"] == "alerta": st.warning(f"**{causa['titulo']}** — {causa['descripcion']}")
        elif causa["tipo"] == "critico": st.error(f"**{causa['titulo']}** — {causa['descripcion']}")
        else: st.info(f"**{causa['titulo']}** — {causa['descripcion']}")

    if analisis["alertas"]:
        with st.expander("⚠️ Alertas del período", expanded=True):
            for a in analisis["alertas"]: st.markdown(f"- {a}")
    if analisis["recomendaciones"]:
        with st.expander("💡 Recomendaciones", expanded=False):
            for r in analisis["recomendaciones"]: st.markdown(f"- {r}")

    # ── Top & Bottom vendedores (resumen rápido) ──────────────
    st.markdown("#### 🏆 Performers del Período")
    if not df_kpi.empty and "Vendedor_Nombre" in df_kpi.columns:
        ventas_col_v = "Total_alloc" if ventas_con_iva else "Sub Total"
        _vdf = df_kpi.groupby("Vendedor_Nombre", observed=True).agg(
            Ventas=(ventas_col_v,"sum"), Utilidad=("Utilidad","sum"),
            Txns=("DOC_KEY","nunique")).reset_index()
        _vdf = _vdf[_vdf["Vendedor_Nombre"].fillna("").str.strip().ne("")]
        _vdf = _vdf[~_vdf["Vendedor_Nombre"].str.upper().isin(["TODOS","SUPERVISOR"])]
        if len(_vdf) > 0:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("**🥇 Mayores del período**")
                tv  = _vdf.nlargest(1,"Ventas").iloc[0]
                tu  = _vdf.nlargest(1,"Utilidad").iloc[0]
                ttx = _vdf.nlargest(1,"Txns").iloc[0]
                st.metric("💰 Mayor en ventas",    tv["Vendedor_Nombre"],  money_fmt(tv["Ventas"]))
                st.metric("📈 Mayor en utilidad",  tu["Vendedor_Nombre"],  money_fmt(tu["Utilidad"]))
                st.metric("🔄 Más transacciones",  ttx["Vendedor_Nombre"], f"{int(ttx['Txns']):,} txns")
            with colB:
                st.markdown("**📊 Menores del período**")
                bv  = _vdf.nsmallest(1,"Ventas").iloc[0]
                bu  = _vdf.nsmallest(1,"Utilidad").iloc[0]
                _vdf["Ticket"] = _vdf["Ventas"] / _vdf["Txns"].replace(0, np.nan)
                btk = _vdf.nsmallest(1,"Ticket").iloc[0]
                st.metric("💰 Menor en ventas",    bv["Vendedor_Nombre"],  money_fmt(bv["Ventas"]))
                st.metric("📈 Menor en utilidad",  bu["Vendedor_Nombre"],  money_fmt(bu["Utilidad"]))
                st.metric("💳 Menor ticket prom",  btk["Vendedor_Nombre"], money_fmt(btk["Ticket"]))


# ══════════════════════════════════════════════════════════════
# TAB 2 — ANÁLISIS DE NEGOCIO
# Sub-tabs: Ventas & Margen | Mix | Equipo
# ══════════════════════════════════════════════════════════════
with tab_negocio:
    sub_ventas, sub_mix, sub_equipo = st.tabs([
        "💰 Ventas & Margen",
        "🏪 Mix de Productos",
        "👥 Equipo de Ventas"
    ])

    # ── SUB-TAB: VENTAS & MARGEN ──────────────────────────────
    with sub_ventas:
        y_sales   = yoy(k_cur["ventas"],   k_prev["ventas"])
        y_profit  = yoy(k_cur["utilidad"], k_prev["utilidad"])
        d_margin  = (k_cur["margen"] - k_prev["margen"]) * 100 if (pd.notna(k_cur["margen"]) and pd.notna(k_prev["margen"])) else np.nan
        y_txns    = yoy(k_cur["txns"],     k_prev["txns"])
        y_ticket  = yoy(k_cur["ticket"],   k_prev["ticket"])
        d_desc_pp = (k_cur["descpct"] - k_prev["descpct"]) * 100 if (pd.notna(k_cur["descpct"]) and pd.notna(k_prev["descpct"])) else np.nan

        cols = st.columns(6)
        with cols[0]:
            cls, txt = _pill_pct(y_sales);   kpi_card("Ventas Totales" + (" CON IVA" if ventas_con_iva else " SIN IVA"), money_fmt(k_cur["ventas"]), txt, cls)
        with cols[1]:
            cls, txt = _pill_pct(y_profit);  kpi_card("Utilidad (SIN IVA)", money_fmt(k_cur["utilidad"]), txt, cls)
        with cols[2]:
            cls, txt = _pill_pp(d_margin);   kpi_card("Margen", pct_fmt(k_cur["margen"]) if pd.notna(k_cur["margen"]) else "—", txt, cls)
        with cols[3]:
            cls, txt = _pill_pct(y_txns);    kpi_card("Transacciones", num_fmt(k_cur["txns"]), txt, cls)
        with cols[4]:
            cls, txt = _pill_pct(y_ticket);  kpi_card("Ticket Promedio", money_fmt(k_cur["ticket"]), txt, cls)
        with cols[5]:
            cls, txt = _pill_pp(d_desc_pp);  kpi_card("% Descuento", pct_fmt(k_cur["descpct"]) if pd.notna(k_cur["descpct"]) else "—", txt, cls)

        # Tabla mensual compacta (solo columnas clave)
        st.markdown("### 📅 Evolución Mensual")
        tbl = ms[[
            "Mes","Ventas_Cont","Ventas_Cred","Ventas_Total",
            "Utilidad","Margen","TXNS","Ticket",
            "YoY_Ventas_Total","YoY_Utilidad","YoY_Margen_pp"
        ]].copy().rename(columns={
            "Ventas_Cont":"Contado","Ventas_Cred":"Crédito",
            "Ventas_Total":"Ventas Total","TXNS":"Txns",
            "Ticket":"Ticket Prom","YoY_Ventas_Total":"YoY Ventas",
            "YoY_Utilidad":"YoY Utilidad","YoY_Margen_pp":"YoY Margen"
        })
        render_table(tbl,
            money_cols=["Contado","Crédito","Ventas Total","Utilidad","Ticket Prom"],
            pct_cols=["Margen"], int_cols=["Txns"],
            yoy_pct_cols=["YoY Ventas","YoY Utilidad"],
            yoy_pp_cols=["YoY Margen"], height=340)

    # ── SUB-TAB: MIX DE PRODUCTOS ─────────────────────────────
    with sub_mix:
        # KPIs de mix (contado/crédito + m²)
        y_m2_sales  = yoy(k_cur["ventas_m2"],   k_prev["ventas_m2"])
        y_m2_profit = yoy(k_cur["utilidad_m2"], k_prev["utilidad_m2"])
        y_sales_cont = yoy(k_cur["ventas_cont"], k_prev["ventas_cont"])
        y_sales_cred = yoy(k_cur["ventas_cred"], k_prev["ventas_cred"])
        cred_share      = safe_div(k_cur["ventas_cred"], k_cur["ventas"])
        cred_share_prev = safe_div(k_prev["ventas_cred"], k_prev["ventas"])
        d_cred_pp = (cred_share - cred_share_prev) * 100 if (pd.notna(cred_share) and pd.notna(cred_share_prev)) else np.nan

        cols = st.columns(5)
        with cols[0]: cls,txt=_pill_pct(y_m2_sales);  kpi_card("Ventas/m²",   money_fmt(k_cur["ventas_m2"]),   txt,cls)
        with cols[1]: cls,txt=_pill_pct(y_m2_profit); kpi_card("Utilidad/m²", money_fmt(k_cur["utilidad_m2"]), txt,cls)
        with cols[2]: cls,txt=_pill_pct(y_sales_cont);kpi_card("Ventas Contado", money_fmt(k_cur["ventas_cont"]),txt,cls)
        with cols[3]: cls,txt=_pill_pct(y_sales_cred);kpi_card("Ventas Crédito", money_fmt(k_cur["ventas_cred"]),txt,cls)
        with cols[4]: cls,txt=_pill_pp(d_cred_pp);    kpi_card("% Crédito",    pct_fmt(cred_share) if pd.notna(cred_share) else "—",txt,cls)

        include_otros_mix = st.toggle("Incluir familia OTROS", value=False, key="mix_otros_neg")
        df_mix     = df_kpi.copy()
        df_mix_prev = df_prev.copy()
        if not include_otros_mix:
            _m = df_mix["Familia_Nombre"].fillna("").str.strip().str.upper().eq("OTROS")
            df_mix = df_mix.loc[~_m].copy()
            _m2 = df_mix_prev["Familia_Nombre"].fillna("").str.strip().str.upper().eq("OTROS")
            df_mix_prev = df_mix_prev.loc[~_m2].copy()

        st.markdown("### Top 20 — Familias vs Marcas")
        colA, colB = st.columns(2, gap="large")

        with colA:
            fam_rank = breakdown_dim(df_mix, df_mix_prev, "Familia_Nombre", ventas_con_iva, top_n=20)
            if fam_rank.empty: st.warning("Sin datos de familias.")
            else:
                st.plotly_chart(fig_bars_line_rank(fam_rank.rename(columns={"Familia_Nombre":"Familia"}),
                    "Familia", ventas_con_iva, "Top 20 Familias"), use_container_width=True)

        with colB:
            marca_rank = breakdown_dim(df_mix, df_mix_prev, "Marca_Nombre", ventas_con_iva, top_n=20)
            if marca_rank.empty: st.warning("Sin datos de marcas.")
            else:
                st.plotly_chart(fig_bars_line_rank(marca_rank.rename(columns={"Marca_Nombre":"Marca"}),
                    "Marca", ventas_con_iva, "Top 20 Marcas"), use_container_width=True)

        # Tablas compactas
        colTA, colTB = st.columns(2, gap="large")
        with colTA:
            if "fam_rank" in dir() and not fam_rank.empty:
                ft = fam_rank.rename(columns={"Familia_Nombre":"Familia","TXNS":"Txns",
                    "YoY_Ventas":"YoY V","YoY_Utilidad":"YoY U","YoY_Margen_pp":"YoY M"})
                render_table(ft[["Familia","Ventas","Utilidad","Margen","YoY V","YoY U","YoY M"]],
                    money_cols=["Ventas","Utilidad"], pct_cols=["Margen"],
                    yoy_pct_cols=["YoY V","YoY U"], yoy_pp_cols=["YoY M"], height=480)
        with colTB:
            if "marca_rank" in dir() and not marca_rank.empty:
                mt = marca_rank.rename(columns={"Marca_Nombre":"Marca","TXNS":"Txns",
                    "YoY_Ventas":"YoY V","YoY_Utilidad":"YoY U","YoY_Margen_pp":"YoY M"})
                render_table(mt[["Marca","Ventas","Utilidad","Margen","YoY V","YoY U","YoY M"]],
                    money_cols=["Ventas","Utilidad"], pct_cols=["Margen"],
                    yoy_pct_cols=["YoY V","YoY U"], yoy_pp_cols=["YoY M"], height=480)

        # ── TREEMAP CON VARIACIÓN YoY ────────────────────────────
        st.markdown("### Treemap — Participación Familia → Marca")

        modo_treemap = st.radio(
            "Colorear por:",
            ["📊 Ventas (participación)", "📈 Variación vs año anterior (%)"],
            horizontal=True,
            key="treemap_modo"
        )

        if not df_mix.empty:
            ventas_col_tm = _ventas_col(ventas_con_iva)

            # Calcular ventas actuales
            tm = (df_mix.groupby(["Familia_Nombre","Marca_Nombre"], observed=True)
                        .agg(Ventas=(ventas_col_tm,"sum"),
                             Utilidad=("Utilidad","sum"))
                        .reset_index())

            # Calcular ventas año anterior para variación
            tm_prev = (df_mix_prev.groupby(["Familia_Nombre","Marca_Nombre"], observed=True)
                                  .agg(Ventas_LY=(ventas_col_tm,"sum"))
                                  .reset_index())

            tm = tm.merge(tm_prev, on=["Familia_Nombre","Marca_Nombre"], how="left")
            tm["Ventas_LY"] = tm["Ventas_LY"].fillna(0)
            tm["YoY_Pct"] = ((tm["Ventas"] - tm["Ventas_LY"]) / tm["Ventas_LY"].replace(0, float("nan"))) * 100
            tm["Margen"] = (tm["Utilidad"] / tm["Ventas"].replace(0, float("nan")) * 100).round(1)
            tm = tm[tm["Ventas"] > 0]

            if not tm.empty:
                # Texto hover personalizado
                # YoY por concepto
                tm["YoY_Ventas"] = ((tm["Ventas"] - tm["Ventas_LY"]) / tm["Ventas_LY"].replace(0, float("nan"))) * 100

                tm_util_prev = (df_mix_prev.groupby(["Familia_Nombre","Marca_Nombre"], observed=True)
                                           .agg(Utilidad_LY=("Utilidad","sum")).reset_index())
                tm = tm.merge(tm_util_prev, on=["Familia_Nombre","Marca_Nombre"], how="left")
                tm["Utilidad_LY"] = tm["Utilidad_LY"].fillna(0)
                tm["YoY_Utilidad"] = ((tm["Utilidad"] - tm["Utilidad_LY"]) / tm["Utilidad_LY"].replace(0, float("nan"))) * 100

                tm_marc_prev = (df_mix_prev.groupby(["Familia_Nombre","Marca_Nombre"], observed=True)
                                           .agg(Sub_LY=("Sub Total","sum")).reset_index())
                tm = tm.merge(tm_marc_prev, on=["Familia_Nombre","Marca_Nombre"], how="left")
                tm["Margen_LY"] = (tm["Utilidad_LY"] / tm["Sub_LY"].replace(0, float("nan")) * 100)
                tm["YoY_Margen_pp"] = tm["Margen"] - tm["Margen_LY"]

                def _fmt_yoy(val, tipo="pct"):
                    if pd.isna(val): return "<span style='color:#9CA3AF'>— sin dato</span>"
                    if tipo == "pct":
                        color = "#4ADE80" if val >= 0 else "#F87171"
                        flecha = "▲" if val >= 0 else "▼"
                        return f"<span style='color:{color};font-weight:600'>{flecha} {val:+.1f}%</span>"
                    else:  # pp
                        color = "#4ADE80" if val >= 0 else "#F87171"
                        flecha = "▲" if val >= 0 else "▼"
                        return f"<span style='color:{color};font-weight:600'>{flecha} {val:+.1f} pp</span>"

                tm["hover"] = tm.apply(lambda r: (
                    f"<b style='font-size:13px'>{r['Marca_Nombre']}</b><br>"
                    f"<span style='color:#94A3B8'>Familia: {r['Familia_Nombre']}</span><br>"
                    f"─────────────────────<br>"
                    f"💰 Ventas: <b>${r['Ventas']:,.0f}</b>  {_fmt_yoy(r['YoY_Ventas'])}<br>"
                    f"📈 Utilidad: <b>${r['Utilidad']:,.0f}</b>  {_fmt_yoy(r['YoY_Utilidad'])}<br>"
                    f"📊 Margen: <b>{r['Margen']:.1f}%</b>  {_fmt_yoy(r['YoY_Margen_pp'], 'pp')}"
                ), axis=1)

                if "participación" in modo_treemap:
                    # Escala multicolor por familia para distinguir rangos
                    fig_tm = px.treemap(
                        tm,
                        path=["Familia_Nombre", "Marca_Nombre"],
                        values="Ventas",
                        color="Ventas",
                        color_continuous_scale=[
                            [0.0,  "#374151"],
                            [0.2,  "#93C5FD"],
                            [0.4,  "#3B82F6"],
                            [0.6,  "#1D4ED8"],
                            [0.8,  "#15803D"],
                            [1.0,  "#14532D"]
                        ],
                        custom_data=["hover"]
                    )
                    fig_tm.update_traces(
                        hovertemplate="%{customdata[0]}<extra></extra>",
                        textfont=dict(size=12, color="white"),
                        marker=dict(line=dict(width=2, color="rgba(0,0,0,0.4)"))
                    )
                    fig_tm.update_coloraxes(
                        colorbar=dict(
                            title="Ventas",
                            tickformat="$,.0f",
                            thickness=14,
                            len=0.8
                        )
                    )
                    titulo_tm = "Participación por Ventas — Gris (bajo) → Verde oscuro (alto)"

                else:
                    # Colorear por variación YoY: rojo=caída, gris=sin dato, verde=subida
                    tm["YoY_clip"] = tm["YoY_Pct"].clip(-50, 50)

                    fig_tm = px.treemap(
                        tm,
                        path=["Familia_Nombre", "Marca_Nombre"],
                        values="Ventas",
                        color="YoY_clip",
                        color_continuous_scale=[
                            [0.0,  "#7F1D1D"],
                            [0.2,  "#EF4444"],
                            [0.4,  "#F87171"],
                            [0.5,  "#6B7280"],
                            [0.6,  "#4ADE80"],
                            [0.8,  "#16A34A"],
                            [1.0,  "#14532D"]
                        ],
                        range_color=[-50, 50],
                        custom_data=["hover"]
                    )
                    fig_tm.update_traces(
                        hovertemplate="%{customdata[0]}<extra></extra>",
                        textfont=dict(size=12, color="white"),
                        marker=dict(line=dict(width=2, color="rgba(0,0,0,0.4)"))
                    )
                    fig_tm.update_coloraxes(
                        colorbar=dict(
                            title="% vs LY",
                            ticksuffix="%",
                            thickness=14,
                            len=0.8
                        )
                    )
                    titulo_tm = "Variación vs Año Anterior — Rojo (caída) → Verde (crecimiento)"

                fig_tm.update_layout(
                    title=dict(text=f"<b>Treemap: Familia → Marca</b><br><sup>{titulo_tm}</sup>",
                               font=dict(size=14, color="#F8FAFC")),
                    height=660,
                    margin=dict(l=10, r=10, t=60, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#F8FAFC")
                )
                st.plotly_chart(fig_tm, use_container_width=True)

                # Leyenda rápida debajo
                if "Variación" in modo_treemap:
                    col_l1, col_l2, col_l3 = st.columns(3)
                    with col_l1:
                        st.markdown("🔴 **Rojo** — Caída vs año anterior")
                    with col_l2:
                        st.markdown("⬛ **Gris** — Sin cambio o sin dato")
                    with col_l3:
                        st.markdown("🟢 **Verde** — Crecimiento vs año anterior")

    # ── SUB-TAB: EQUIPO DE VENTAS ─────────────────────────────
    with sub_equipo:
        omit_supervisor = st.toggle("Omitir Supervisor", value=True, key="omit_sup_neg")
        df_p = df_kpi.copy()
        df_p_prev = df_prev.copy()
        if omit_supervisor:
            _m = _clean_text_series(df_p["Vendedor_Nombre"]).str.contains("SUPERVISOR", na=False)
            df_p = df_p[~_m]
            _m2 = _clean_text_series(df_p_prev["Vendedor_Nombre"]).str.contains("SUPERVISOR", na=False)
            df_p_prev = df_p_prev[~_m2]

        vend_count      = count_vendedores_activos(df_p)
        vend_count_prev = count_vendedores_activos(df_p_prev)
        k_p      = kpis_from_df(df_p,      ventas_con_iva, m2)
        k_p_prev = kpis_from_df(df_p_prev, ventas_con_iva, m2)

        ventas_x_emp      = safe_div(k_p["ventas"],      vend_count)      if vend_count      else np.nan
        ventas_x_emp_prev = safe_div(k_p_prev["ventas"], vend_count_prev) if vend_count_prev else np.nan
        ops_x_emp      = safe_div(k_p["txns"],      vend_count)      if vend_count      else np.nan
        ops_x_emp_prev = safe_div(k_p_prev["txns"], vend_count_prev) if vend_count_prev else np.nan
        util_x_emp      = safe_div(k_p["utilidad"],      vend_count)      if vend_count      else np.nan
        util_x_emp_prev = safe_div(k_p_prev["utilidad"], vend_count_prev) if vend_count_prev else np.nan
        ticket_x_emp      = safe_div(ventas_x_emp,      ops_x_emp)      if (pd.notna(ventas_x_emp)      and pd.notna(ops_x_emp))      else np.nan
        ticket_x_emp_prev = safe_div(ventas_x_emp_prev, ops_x_emp_prev) if (pd.notna(ventas_x_emp_prev) and pd.notna(ops_x_emp_prev)) else np.nan
        margen_emp      = safe_div(util_x_emp,      safe_div(k_p["subtotal"],      vend_count)      if vend_count      else np.nan)
        margen_emp_prev = safe_div(util_x_emp_prev, safe_div(k_p_prev["subtotal"], vend_count_prev) if vend_count_prev else np.nan)
        d_marg_emp_pp   = (margen_emp - margen_emp_prev) * 100 if (pd.notna(margen_emp) and pd.notna(margen_emp_prev)) else np.nan

        cols = st.columns(5)
        with cols[0]: cls,txt=_pill_pct(yoy(ventas_x_emp,ventas_x_emp_prev)); kpi_card("Ventas/Empleado", money_fmt(ventas_x_emp) if pd.notna(ventas_x_emp) else "—",txt,cls)
        with cols[1]: cls,txt=_pill_pct(yoy(ops_x_emp,ops_x_emp_prev));       kpi_card("Ops/Empleado",    num_fmt(ops_x_emp)    if pd.notna(ops_x_emp)    else "—",txt,cls)
        with cols[2]: cls,txt=_pill_pct(yoy(ticket_x_emp,ticket_x_emp_prev)); kpi_card("Ticket/Empleado", money_fmt(ticket_x_emp) if pd.notna(ticket_x_emp) else "—",txt,cls)
        with cols[3]: cls,txt=_pill_pct(yoy(util_x_emp,util_x_emp_prev));     kpi_card("Utilidad/Empleado",money_fmt(util_x_emp) if pd.notna(util_x_emp)   else "—",txt,cls)
        with cols[4]: cls,txt=_pill_pp(d_marg_emp_pp);                        kpi_card("Margen/Empleado", pct_fmt(margen_emp)   if pd.notna(margen_emp)    else "—",txt,cls)

        vdf = vendor_metrics(df_p, df_p_prev, ventas_con_iva, top_n=30)
        if vdf.empty:
            st.warning("Sin datos de vendedores.")
        else:
            # Gráfico top vendedores
            st.markdown("### Top Vendedores — Ventas y Utilidad")
            if GRAFICOS_MEJORADOS:
                st.plotly_chart(fig_top_vendedores_mejorada(vdf, top_n=20), use_container_width=True)
            else:
                st.plotly_chart(fig_top_vendedores(vdf, ventas_con_iva), use_container_width=True)

            # Matriz 2x2
            st.markdown("### Matriz Estratégica — Ticket vs Transacciones")
            q = vdf[["Vendedor","Ventas","Utilidad","TXNS","Ticket"]].copy()
            med_x = float(np.nanmedian(q["TXNS"]))   if len(q) else 0.0
            med_y = float(np.nanmedian(q["Ticket"])) if len(q) else 0.0
            q["Cuadrante"] = q.apply(lambda r:
                "⭐ Estrellas"   if (r["TXNS"]>=med_x and r["Ticket"]>=med_y) else
                "Volumen"        if (r["TXNS"]>=med_x and r["Ticket"]<med_y)  else
                "Oportunidad"    if (r["TXNS"]<med_x  and r["Ticket"]>=med_y) else
                "Bajo desempeño", axis=1)
            if GRAFICOS_MEJORADOS:
                st.plotly_chart(fig_quadrants_mejorada(q), use_container_width=True)
            else:
                st.plotly_chart(fig_quadrants(q), use_container_width=True)

            # Tabla vendedores (columnas clave)
            st.markdown("### Tabla de Vendedores")
            vtbl = vdf.copy().rename(columns={
                "TXNS":"Txns","Ticket":"Ticket Prom",
                "YoY_Ventas":"YoY V","YoY_Utilidad":"YoY U",
                "YoY_TXNS":"YoY Txns","YoY_Ticket":"YoY Ticket","YoY_Margen_pp":"YoY M"})
            vtbl = vtbl.merge(q[["Vendedor","Cuadrante"]], on="Vendedor", how="left")
            render_table(
                vtbl[["Vendedor","Ventas","Utilidad","Margen","Txns","Ticket Prom","Cuadrante","YoY V","YoY U","YoY M"]],
                money_cols=["Ventas","Utilidad","Ticket Prom"],
                pct_cols=["Margen"], int_cols=["Txns"],
                yoy_pct_cols=["YoY V","YoY U","YoY Txns" if "YoY Txns" in vtbl.columns else "YoY V"],
                yoy_pp_cols=["YoY M"], height=520)


# ══════════════════════════════════════════════════════════════
# TAB 3 — COMPARATIVOS
# YoY mensual, acumulado y top movers
# ══════════════════════════════════════════════════════════════
with tab_comparativos:
    sub_yoy, sub_movers = st.tabs(["📅 YoY Completo", "📊 Top Movers"])

    with sub_yoy:
        # Reutiliza la función de comparador YoY completo
        crear_comparador_unificado_yoy(df_all, int(year), ventas_con_iva)

    with sub_movers:
        st.markdown("### 📊 Ganadores y Perdedores vs Año Anterior")
        _dm  = df_kpi.copy()
        _dmp = df_prev.copy()
        include_otros_ins = st.toggle("Incluir OTROS", value=False, key="movers_otros")
        if not include_otros_ins:
            _dm  = _dm[~_dm["Familia_Nombre"].fillna("").str.strip().str.upper().eq("OTROS")]
            _dmp = _dmp[~_dmp["Familia_Nombre"].fillna("").str.strip().str.upper().eq("OTROS")]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Familias — Δ vs LY**")
            fam_m = breakdown_dim(_dm, _dmp, "Familia_Nombre", ventas_con_iva, top_n=50)
            if not fam_m.empty:
                fam_m["Δ Ventas"] = fam_m["Ventas"] - fam_m["Ventas_LY"].fillna(0)
                up = fam_m.sort_values("Δ Ventas", ascending=False).head(8)[["Familia_Nombre","Δ Ventas","YoY_Ventas"]].rename(columns={"Familia_Nombre":"Familia"})
                render_table(up, money_cols=["Δ Ventas"], yoy_pct_cols=["YoY_Ventas"], height=320)
        with c2:
            st.markdown("**Marcas — Δ vs LY**")
            mk_m = breakdown_dim(_dm, _dmp, "Marca_Nombre", ventas_con_iva, top_n=50)
            if not mk_m.empty:
                mk_m["Δ Ventas"] = mk_m["Ventas"] - mk_m["Ventas_LY"].fillna(0)
                up2 = mk_m.sort_values("Δ Ventas", ascending=False).head(8)[["Marca_Nombre","Δ Ventas","YoY_Ventas"]].rename(columns={"Marca_Nombre":"Marca"})
                render_table(up2, money_cols=["Δ Ventas"], yoy_pct_cols=["YoY_Ventas"], height=320)


# ══════════════════════════════════════════════════════════════
# TAB 4 — ANÁLISIS AVANZADO (Analistas)
# ══════════════════════════════════════════════════════════════
with tab_avanzado:
    st.markdown("""
    <div style='background:#1e293b;border:1px solid #334155;border-radius:8px;
                padding:12px 20px;margin-bottom:20px;'>
        <p style='color:#94A3B8;font-size:12px;margin:0;'>
            🔬 <strong style='color:#F1F5F9;'>Módulo de Análisis Avanzado</strong> — 
            Herramientas de uso técnico destinadas al equipo de analítica y BI. 
            Para consultas ejecutivas utilice las secciones anteriores.
        </p>
    </div>
    """, unsafe_allow_html=True)

    subtabA, subtabB, subtabC, subtabD = st.tabs([
        "📊 Constructor",
        "📈 Gráficas",
        "🔍 Drill-Down",
        "📅 Comparadores"
    ])

    with subtabA:
        st.markdown("### 📊 Constructor de Tablas Personalizado")
        dataset_opcion = st.radio("Dataset:", ["Período actual", "Año completo", "Resumen mensual"], horizontal=True)
        if dataset_opcion == "Período actual":
            tabla_drag_drop_builder(df_kpi, "Datos del Período")
        elif dataset_opcion == "Año completo":
            tabla_drag_drop_builder(df_year, "Datos del Año")
        else:
            tabla_drag_drop_builder(ms_cur, "Resumen Mensual")

    with subtabB:
        st.markdown("### 📈 Gráficas Interactivas")
        dataset_graf = st.radio("Dataset:", ["Resumen mensual", "Top familias", "Top marcas"], horizontal=True, key="avz_graf")
        if dataset_graf == "Resumen mensual":
            if not ms_cur.empty: selector_grafica_interactivo(ms_cur, "Tendencia Mensual")
        elif dataset_graf == "Top familias":
            if not df_kpi.empty and "Familia_Nombre" in df_kpi.columns:
                top_fam = (df_kpi.groupby("Familia_Nombre", observed=True)
                    .agg({_ventas_col(ventas_con_iva):"sum","Utilidad":"sum"}).reset_index()
                    .nlargest(20, _ventas_col(ventas_con_iva)))
                top_fam.columns = ["Familia","Ventas","Utilidad"]
                selector_grafica_interactivo(top_fam, "Top 20 Familias")
        else:
            if not df_kpi.empty and "Marca_Nombre" in df_kpi.columns:
                top_mar = (df_kpi.groupby("Marca_Nombre", observed=True)
                    .agg({_ventas_col(ventas_con_iva):"sum","Utilidad":"sum"}).reset_index()
                    .nlargest(20, _ventas_col(ventas_con_iva)))
                top_mar.columns = ["Marca","Ventas","Utilidad"]
                selector_grafica_interactivo(top_mar, "Top 20 Marcas")

    with subtabC:
        st.markdown("### 🔍 Explorador Drill-Down")
        jerarquia_opciones = {
            "Sucursal → Familia → Marca": ["Almacen_CANON","Familia_Nombre","Marca_Nombre"],
            "Familia → Marca → SKU":      ["Familia_Nombre","Marca_Nombre","Articulo"],
            "Vendedor → Familia → Marca": ["Vendedor_Nombre","Familia_Nombre","Marca_Nombre"],
        }
        jer_sel = st.selectbox("Jerarquía:", list(jerarquia_opciones.keys()))
        drill_down_explorer(df_all, jerarquia_opciones[jer_sel])

    with subtabD:
        sub_comp1, sub_comp2 = st.tabs(["📅 Comparador Períodos", "📊 Comparador YoY Completo"])
        with sub_comp1:
            comparador_periodos(df_all, int(year))
        with sub_comp2:
            crear_comparador_mensual_yoy(df_all, int(year), ventas_con_iva)

    with st.expander("💡 Consejos de Uso"):
        st.markdown("""
        **Constructor:** Selecciona columnas, aplica agregaciones, exporta a CSV.
        **Gráficas:** Prueba distintos tipos para el mismo dato.
        **Drill-Down:** Click 🔽 para bajar un nivel, ⬆️ para subir.
        **Comparador:** Ideal para comparar trimestres o meses similares.
        """)
