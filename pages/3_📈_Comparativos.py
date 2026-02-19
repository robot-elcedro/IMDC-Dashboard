import streamlit as st
from utils import *

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Debes iniciar sesión primero")
    st.stop()

st.title("📈 Comparativos")

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