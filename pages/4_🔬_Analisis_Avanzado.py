import streamlit as st
from utils import *

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Debes iniciar sesión primero")
    st.stop()

st.title("🔬 Análisis Avanzado")

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
