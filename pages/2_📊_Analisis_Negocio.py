import streamlit as st
from utils import *

if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Debes iniciar sesión primero")
    st.stop()

st.title("📊 Análisis de Negocio")

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