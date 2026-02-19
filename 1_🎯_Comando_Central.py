import streamlit as st
from utils import *

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Debes iniciar sesión primero")
    st.stop()

st.title("🎯 Comando Central")


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