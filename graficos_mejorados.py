# graficos_mejorados.py
# Funciones de visualización mejoradas para el dashboard IMDC

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ============================================================
# PALETA DE COLORES PROFESIONAL
# ============================================================
COLORS = {
    'primary': '#2563EB',
    'primary_light': '#3B82F6',
    'success': '#10B981',
    'success_dark': '#059669',
    'danger': '#EF4444',
    'danger_dark': '#DC2626',
    'warning': '#F59E0B',
    'neutral_700': '#374151',
    'bg_dark': '#0F172A',
    'text': '#F8FAFC',
}

GRADIENT_BLUE = ['#1E40AF', '#2563EB', '#3B82F6', '#60A5FA', '#93C5FD']
GRADIENT_GREEN = ['#065F46', '#059669', '#10B981', '#34D399', '#6EE7B7']

# ============================================================
# GRÁFICA MENSUAL MEJORADA (12 meses con highlight)
# ============================================================
def fig_grafica_mensual_mejorada(
    ms: pd.DataFrame,
    ventas_con_iva: bool,
    m_start: int,
    m_end: int
) -> go.Figure:
    """Gráfica mensual con barras apiladas y línea de utilidad"""
    
    MONTHS_ABBR = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }
    
    df = ms.copy()
    df = df.sort_values("MesNum")
    df["MesLabel"] = df["MesNum"].map(MONTHS_ABBR)
    
    # Colores para highlight
    colors_cred = []
    colors_cont = []
    for m in df["MesNum"]:
        if m_start <= m <= m_end:
            colors_cred.append(COLORS['primary'])
            colors_cont.append(COLORS['success'])
        else:
            colors_cred.append('rgba(59, 130, 246, 0.3)')
            colors_cont.append('rgba(16, 185, 129, 0.3)')
    
    fig = go.Figure()
    
    # Barras apiladas
    fig.add_trace(go.Bar(
        x=df["MesLabel"],
        y=df["Ventas_Cont"],
        name='Contado',
        marker=dict(color=colors_cont, line=dict(width=0)),
        hovertemplate='<b>Contado</b><br>%{y:$,.0f}<extra></extra>',
    ))
    
    fig.add_trace(go.Bar(
        x=df["MesLabel"],
        y=df["Ventas_Cred"],
        name='Crédito',
        marker=dict(color=colors_cred, line=dict(width=0)),
        hovertemplate='<b>Crédito</b><br>%{y:$,.0f}<extra></extra>',
    ))
    
    # Línea de utilidad
    fig.add_trace(go.Scatter(
        x=df["MesLabel"],
        y=df["Utilidad"],
        name='Utilidad',
        mode='lines+markers',
        line=dict(color=COLORS['warning'], width=3, shape='spline'),
        marker=dict(size=8, color=COLORS['warning'], line=dict(color='white', width=2)),
        yaxis='y2',
        hovertemplate='<b>Utilidad</b><br>%{y:$,.0f}<extra></extra>',
    ))
    
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(family='Inter, sans-serif', color=COLORS['text'], size=12),
        title=dict(
            text='<b>Histórico mensual — Ventas (Crédito + Contado) y Utilidad</b>',
            font=dict(size=18),
            x=0.02
        ),
        barmode='stack',
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='',
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Ventas (CON IVA)</b>' if ventas_con_iva else '<b>Ventas (SIN IVA)</b>',
            tickformat='$,.0f',
        ),
        yaxis2=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Utilidad (SIN IVA)</b>',
            overlaying='y',
            side='right',
            tickformat='$,.0f',
        ),
        legend=dict(
            orientation='h',
            y=1.02,
            x=1,
            xanchor='right',
            bgcolor='rgba(17, 24, 39, 0.8)',
            bordercolor=COLORS['primary'],
            borderwidth=1,
        ),
        height=450,
        margin=dict(l=60, r=60, t=80, b=60),
    )
    
    return fig


# ============================================================
# TOP 20 BARRAS HORIZONTALES MEJORADAS
# ============================================================
def fig_top20_barras_mejoradas(
    df: pd.DataFrame,
    title: str,
    value_col: str = "Ventas",
    label_col: str = "Nombre",
    top_n: int = 20,
    color_scale: str = 'blue'
) -> go.Figure:
    """Gráfica de barras horizontales con gradiente"""
    
    df_sorted = df.nlargest(top_n, value_col)
    df_sorted = df_sorted.sort_values(value_col, ascending=True)
    
    # Seleccionar gradiente
    colors = GRADIENT_BLUE[::-1] if color_scale == 'blue' else GRADIENT_GREEN[::-1]
    
    # Crear gradiente basado en valores
    values_norm = (df_sorted[value_col] - df_sorted[value_col].min()) / (df_sorted[value_col].max() - df_sorted[value_col].min())
    bar_colors = [colors[int(v * (len(colors)-1))] for v in values_norm]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df_sorted[label_col],
        x=df_sorted[value_col],
        orientation='h',
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=df_sorted[value_col].apply(lambda x: f'${x:,.0f}'),
        textposition='outside',
        textfont=dict(size=11),
        hovertemplate='<b>%{y}</b><br>%{x:$,.0f}<extra></extra>',
    ))
    
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(family='Inter, sans-serif', color=COLORS['text']),
        title=dict(text=f'<b>{title}</b>', font=dict(size=16), x=0.02),
        xaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.06)', tickformat='$,.0f'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.06)', tickfont=dict(size=10)),
        height=max(500, top_n * 25),
        showlegend=False,
        margin=dict(l=150, r=100, t=60, b=40),
    )
    
    return fig


# ============================================================
# TREEMAP MEJORADO
# ============================================================
def fig_treemap_mejorado(
    df: pd.DataFrame,
    ventas_col: str = "Ventas"
) -> go.Figure:
    """Treemap con colores profesionales"""
    
    if df.empty:
        return go.Figure()
    
    fig = px.treemap(
        df,
        path=['Familia_Nombre', 'Marca_Nombre'],
        values=ventas_col,
        color=ventas_col,
        color_continuous_scale=[
            [0.0, '#1E3A8A'],
            [0.25, '#2563EB'],
            [0.5, '#3B82F6'],
            [0.75, '#60A5FA'],
            [1.0, '#93C5FD']
        ],
    )
    
    fig.update_traces(
        textfont=dict(size=13, color='white'),
        marker=dict(line=dict(width=2, color='rgba(0, 0, 0, 0.3)')),
        hovertemplate='<b>%{label}</b><br>Ventas: %{value:$,.0f}<extra></extra>',
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color=COLORS['text']),
        title=dict(text='<b>Treemap: Familia → Marca</b>', font=dict(size=16), x=0.02),
        height=600,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    
    return fig


# ============================================================
# GRÁFICA TOP VENDEDORES - VERSIÓN CORREGIDA
# ============================================================
def fig_top_vendedores_mejorada(
    vdf: pd.DataFrame,
    top_n: int = 20
) -> go.Figure:
    """Barras apiladas + línea de utilidad - SIN ERROR DE MARGIN"""
    
    df = vdf.nlargest(top_n, 'Ventas').copy()
    df = df.sort_values('Ventas', ascending=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df['Vendedor'],
        x=df['Ventas_Cont'],
        name='Contado',
        orientation='h',
        marker=dict(color=COLORS['success'], line=dict(width=0)),
        hovertemplate='<b>Contado</b><br>%{x:$,.0f}<extra></extra>',
    ))
    
    fig.add_trace(go.Bar(
        y=df['Vendedor'],
        x=df['Ventas_Cred'],
        name='Crédito',
        orientation='h',
        marker=dict(color=COLORS['primary'], line=dict(width=0)),
        hovertemplate='<b>Crédito</b><br>%{x:$,.0f}<extra></extra>',
    ))
    
    fig.add_trace(go.Scatter(
        y=df['Vendedor'],
        x=df['Utilidad'],
        name='Utilidad',
        mode='lines+markers',
        line=dict(color=COLORS['warning'], width=3),
        marker=dict(size=8, color=COLORS['warning'], line=dict(color='white', width=2)),
        xaxis='x2',
        hovertemplate='<b>Utilidad</b><br>%{x:$,.0f}<extra></extra>',
    ))
    
    # IMPORTANTE: Todos los parámetros en update_layout EXPLÍCITOS
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(family='Inter, sans-serif', color=COLORS['text'], size=12),
        title=dict(
            text='<b>Top Vendedores — Ventas y Utilidad</b>',
            font=dict(size=16),
            x=0.02
        ),
        barmode='stack',
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Ventas</b>',
            tickformat='$,.0f',
        ),
        xaxis2=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Utilidad</b>',
            overlaying='x',
            side='top',
            tickformat='$,.0f',
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(255, 255, 255, 0.06)',
            tickfont=dict(size=10),
        ),
        legend=dict(
            orientation='h',
            y=1.02,
            x=1,
            xanchor='right',
            bgcolor='rgba(17, 24, 39, 0.8)',
            bordercolor=COLORS['primary'],
            borderwidth=1,
        ),
        height=max(500, top_n * 30),
        margin=dict(l=150, r=100, t=80, b=40),
    )
    
    return fig


# ============================================================
# MATRIZ 2x2 CUADRANTES MEJORADA - VERSIÓN CORREGIDA
# ============================================================
def fig_quadrants_mejorada(df: pd.DataFrame) -> go.Figure:
    """Scatter plot con cuadrantes - SIN ERROR DE MARGIN"""
    
    if df.empty:
        return go.Figure()
    
    med_x = df["TXNS"].median()
    med_y = df["Ticket"].median()
    
    color_map = {
        "⭐ Estrellas": COLORS['success'],
        "Volumen": COLORS['primary'],
        "Oportunidad": COLORS['warning'],
        "Bajo desempeño": COLORS['danger']
    }
    
    fig = go.Figure()
    
    for cuadrante in df["Cuadrante"].unique():
        df_cuad = df[df["Cuadrante"] == cuadrante]
        
        fig.add_trace(go.Scatter(
            x=df_cuad["TXNS"],
            y=df_cuad["Ticket"],
            mode='markers+text',
            name=cuadrante,
            marker=dict(
                size=df_cuad["Ventas"] / df_cuad["Ventas"].max() * 50 + 10,
                color=color_map.get(cuadrante, COLORS['neutral_700']),
                opacity=0.7,
                line=dict(width=2, color='white')
            ),
            text=df_cuad["Vendedor"].str[:15],
            textposition='top center',
            textfont=dict(size=9, color='white'),
            hovertemplate='<b>%{text}</b><br>Transacciones: %{x:,.0f}<br>Ticket: %{y:$,.0f}<extra></extra>',
        ))
    
    fig.add_hline(y=med_y, line_dash="dash", line_color="rgba(255,255,255,0.3)", line_width=1)
    fig.add_vline(x=med_x, line_dash="dash", line_color="rgba(255,255,255,0.3)", line_width=1)
    
    # IMPORTANTE: Todos los parámetros en update_layout EXPLÍCITOS
    fig.update_layout(
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(family='Inter, sans-serif', color=COLORS['text'], size=12),
        title=dict(
            text='<b>Matriz 2×2 — Ticket vs Transacciones</b>',
            font=dict(size=16),
            x=0.02
        ),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Transacciones</b>',
            tickformat=',.0f',
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(255, 255, 255, 0.06)',
            title='<b>Ticket Promedio</b>',
            tickformat='$,.0f',
        ),
        legend=dict(
            orientation='v',
            y=0.98,
            x=0.98,
            yanchor='top',
            xanchor='right',
            bgcolor='rgba(17, 24, 39, 0.9)',
            bordercolor=COLORS['primary'],
            borderwidth=1,
        ),
        height=550,
        margin=dict(l=60, r=40, t=60, b=60),
    )
    
    return fig
