import io
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from frota_utils import (MESES_ORDEM, co2_por_veiculo, consolidado_consumo,
                         corrigir_workbook, enriquecer_consumo, processar_planilha,
                         resumo_mensal, timestamp_humano)
from gerar_html import build_html

st.set_page_config(
    page_title="Dashboard Frota Carajás",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# TEMAS (claro / escuro)
# ============================================================================
FONTE = "Inter, 'Segoe UI', Arial, sans-serif"

LIGHT = {
    "nome": "claro",
    "bg": "#f4f7fb", "card": "#ffffff", "borda": "#e3e9f2",
    "texto": "#22303f", "muted": "#5f7286",
    "primaria": "#2563eb", "accent": "#f59e0b",
    "texto_em_barra": "#ffffff", "texto_no_accent": "#1f2937",
    "linha_veic": "#14b8a6", "grid": "#e8eef6", "hover_bg": "#22303f",
    "bar_semana": "rgba(37,99,235,.15)",
    "sombra": "0 4px 16px rgba(30,41,59,.07)",
    "serie": ["#2563eb", "#f59e0b", "#0ea5e9", "#10b981", "#8b5cf6",
              "#ec4899", "#f97316", "#14b8a6", "#84cc16", "#64748b"],
    "kpi_c3": "#0ea5e9", "kpi_c4": "#e11d48", "kpi_c5": "#10b981",
    "pos": "#047857", "neg": "#b91c1c", "alerta": "#b45309",
    "neutro": "#5f7286", "info": "#0369a1", "roxo": "#7e22ce",
}

DARK = {
    "nome": "escuro",
    "bg": "#0b1220", "card": "#111c30", "borda": "#23364f",
    "texto": "#e7eef7", "muted": "#94a7c1",
    "primaria": "#60a5fa", "accent": "#fbbf24",
    "texto_em_barra": "#0b1220", "texto_no_accent": "#1f2937",
    "linha_veic": "#2dd4bf", "grid": "rgba(148,163,184,.15)", "hover_bg": "#23364f",
    "bar_semana": "rgba(96,165,250,.22)",
    "sombra": "0 6px 20px rgba(0,0,0,.35)",
    "serie": ["#60a5fa", "#fbbf24", "#38bdf8", "#34d399", "#a78bfa",
              "#f472b6", "#fb923c", "#2dd4bf", "#a3e635", "#94a3b8"],
    "kpi_c3": "#38bdf8", "kpi_c4": "#f43f5e", "kpi_c5": "#34d399",
    "pos": "#10b981", "neg": "#f87171", "alerta": "#fbbf24",
    "neutro": "#94a7c1", "info": "#38bdf8", "roxo": "#c084fc",
}

STATUS_CORES = {
    "Operacional": "#10b981",
    "Manutenção": "#ef4444",
    "Mobilização": "#f97316",
    "Pendente": "#94a3b8",
    "Lavador": "#0ea5e9",
    "Erro Dados": "#a855f7",
}

CFG_GRAF = {
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png", "filename": "dashboard_frota_carajas", "scale": 2,
    },
}

# Registro dos gráficos/tabelas para o export de prints (PNG/ZIP).
PRINTS: list = []  # (nome, go.Figure, largura_px, altura_px)


def reg_print(nome, fig, largura=1200, altura=520):
    """Guarda a figura para o export de prints e devolve a própria figura."""
    PRINTS.append((nome, fig, largura, altura))
    return fig


def figura_tabela(titulo, colunas, linhas, tema):
    """Transforma uma tabela (colunas + colunas-de-valores) em figura PNG."""
    n_linhas = max((len(l) for l in linhas), default=0)
    fig = go.Figure(data=[go.Table(
        columnwidth=[1.4] + [1.0] * (len(colunas) - 1),
        header=dict(
            values=list(colunas), align="left",
            fill_color=tema["primaria"],
            font=dict(color="#ffffff", size=13, family=FONTE),
            line_color=tema["borda"], height=30,
        ),
        cells=dict(
            values=linhas, align="left",
            fill_color=[tema["card"], tema["bg"]],
            font=dict(color=tema["texto"], size=12, family=FONTE),
            line_color=tema["borda"], height=27,
        ),
    )])
    fig.update_layout(
        title=dict(text=titulo, x=0.01, xanchor="left",
                   font=dict(size=16, color=tema["primaria"], family=FONTE)),
        paper_bgcolor=tema["bg"], font=dict(color=tema["texto"], family=FONTE),
        margin=dict(l=16, r=16, t=56 if titulo else 16, b=16),
        height=110 + 27 * n_linhas,
    )
    return fig


def css_tema(t: dict) -> str:
    return f"""
<style>
  :root {{
    --bg: {t["bg"]}; --card: {t["card"]}; --borda: {t["borda"]};
    --texto: {t["texto"]}; --muted: {t["muted"]};
    --primaria: {t["primaria"]}; --accent: {t["accent"]};
    --sombra: {t["sombra"]};
    color-scheme: {t["nome"]};
  }}

  /* Força o tema do Streamlit inteiro vetorizando as variáveis de tema.
     É isso que faz o fundo, textos e widgets (selects, menus) mudarem
     de verdade no modo escuro. */
  html, body, [data-testid="stAppViewContainer"] {{
    --background-color: {t["bg"]} !important;
    --secondary-background-color: {t["card"]} !important;
    --text-color: {t["texto"]} !important;
    --secondary-text-color: {t["muted"]} !important;
    --primary-color: {t["primaria"]} !important;
    background-color: {t["bg"]} !important;
    color: {t["texto"]};
  }}
  .stApp {{ background-color: {t["bg"]} !important; }}

  .block-container {{
    padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1500px;
    color: var(--texto);
  }}
  #MainMenu, footer {{ visibility: hidden; }}

  .topo {{
    background: linear-gradient(115deg, #0d2b45 0%, #14507a 55%, #1d6b9c 100%);
    border-radius: 18px;
    padding: 22px 28px;
    margin-bottom: 6px;
    color: #fff;
    box-shadow: 0 8px 22px rgba(13,43,69,.25);
    position: relative;
    overflow: hidden;
  }}
  .topo h1 {{ margin: 0; font-size: 1.65rem; font-weight: 800; letter-spacing: .2px; }}
  .topo p  {{ margin: 6px 0 0; font-size: .9rem; opacity: .85; }}
  .topo-meta {{ display: flex; align-items: center; justify-content: space-between;
               gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }}
  .selo {{ font-size: .64rem; font-weight: 800; letter-spacing: 1.4px; text-transform: uppercase;
          background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
          padding: 4px 12px; border-radius: 999px; }}
  .selo-data {{ font-size: .74rem; opacity: .92; }}

  .kpi {{
    background: var(--card);
    border: 1px solid var(--borda);
    border-left: 5px solid var(--kcor, var(--primaria));
    border-radius: 14px;
    padding: 14px 18px;
    min-height: 108px;
    box-shadow: var(--sombra);
  }}
  .kpi .lbl {{ font-size: .72rem; letter-spacing: .6px; text-transform: uppercase;
               font-weight: 700; color: var(--muted); }}
  .kpi .val {{ font-size: 1.7rem; font-weight: 800; color: var(--primaria); line-height: 1.2;
             font-variant-numeric: tabular-nums; }}
  .kpi .sub {{ font-size: .76rem; color: var(--muted); margin-top: 2px; }}
  .exec {{ background: var(--card); border: 1px solid var(--borda);
           border-left: 5px solid var(--accent); border-radius: 12px;
           padding: 10px 14px; margin: 4px 0 8px; font-size: .9rem;
           color: var(--texto); box-shadow: var(--sombra); }}

  h3.carta {{ margin: .9rem 0 .4rem; font-size: 1rem; font-weight: 800;
              color: var(--primaria); letter-spacing: .3px; }}

  div[data-testid="stSidebar"] {{ background: var(--card) !important; }}
  div[data-testid="stSidebar"] .stMarkdown,
  div[data-testid="stSidebar"] .stMarkdown p,
  div[data-testid="stSidebar"] label {{ color: var(--texto) !important; }}
  div[data-testid="stSidebar"] .stMarkdown h2 {{ color: var(--primaria) !important; }}

  [data-baseweb="select"] div {{
    background: var(--card) !important; color: var(--texto) !important;
  }}
  [data-baseweb="select"] span, [data-baseweb="select"] input {{
    color: var(--texto) !important;
  }}
  [data-baseweb="popover"] [data-baseweb="menu"],
  [data-baseweb="menu"] li, [data-baseweb="option"] {{
    background: var(--card) !important; color: var(--texto) !important;
  }}
  [data-baseweb="option"]:hover {{ background: rgba(96,165,250,.18) !important; }}
  [data-baseweb="option"][aria-selected="true"] {{
    background: rgba(96,165,250,.32) !important;
  }}
  [data-testid="stToggle"] label {{ color: var(--texto) !important; }}
  [data-testid="stDataFrame"] {{ color: var(--texto) !important; }}
  .stDownloadButton button {{
    background: {t["primaria"]}; color: #fff; font-weight: 600;
  }}
  hr {{ border-color: var(--borda); }}
</style>
"""


def kpi_card(icone, label, valor, sub, cor):
    st.markdown(
        f"""
        <div class="kpi" style="--kcor:{cor}">
          <div class="lbl">{icone} {label}</div>
          <div class="val">{valor}</div>
          <div class="sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def base_layout(fig, t, titulo=None):
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONTE, color=t["texto"], size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=42 if titulo else 20, b=10),
        title=dict(
            text=titulo or "",
            x=0.01, xanchor="left",
            font=dict(size=15, color=t["primaria"], family=FONTE),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5,
                    xanchor="center", font=dict(color=t["texto"])),
        hoverlabel=dict(
            bgcolor=t["hover_bg"],
            bordercolor=t["borda"],
            font=dict(family=FONTE, color="#ffffff", size=13),
        ),
    )
    return fig


def fmt_km(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.0f} km".replace(",", ".")


def fmt_num(v):
    return f"{v:,.0f}".replace(",", ".")


def fmt_co2(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.1f}".replace(",", ".")


def render_consumo(df: pd.DataFrame, mes_sel, tema):
    """Consumo mensal de CO2 da frota (2025→): estima litros do km real (km/L por
    modelo) e aplica o fator MCTI. Leve (TN 01) = Gasolina; Caminhonetes = Diesel.
    Segue o mês selecionado no filtro principal (mes_sel)."""
    c = enriquecer_consumo(df)
    cons = consolidado_consumo(c)
    por_v = co2_por_veiculo(c)
    if cons.empty:
        st.info("Sem dados de quilometragem para calcular o consumo de CO2.")
        return

    meses = [m for m in MESES_ORDEM if m in cons["MES_REF"].values]
    mes_c = mes_sel if mes_sel in meses else meses[-1]
    linha = cons[cons["MES_REF"] == mes_c].iloc[0]
    ordem_c = int(linha["MES_ORDEM"])
    mes_ant = None
    prev = cons[cons["MES_ORDEM"] == ordem_c - 1]
    if not prev.empty:
        mes_ant = prev.iloc[0]["MES_REF"]

    delta_pct = linha["DELTA_PCT"]
    cor_fonte = {"Diesel": tema["accent"], "Gasolina": tema["kpi_c4"]}

    st.markdown("---")
    st.markdown(f"#### ⛽ Consumo de CO₂ da frota — veículo a veículo ({mes_c})")
    st.caption("Período real da planilha de KM: OUTUBRO 2025 → AGOSTO 2026. "
               "Estimativa: litros = km real ÷ consumo médio do modelo (Nivus 11, "
               "Pulse 11,5, Tracker 11, Hilux/Ranger/S10 9,5, Frontier 9, Strada 10 "
               "km/L) e CO₂ = litros × fator MCTI (Diesel 2,68 / Gasolina 2,16 kgCO₂e/L). "
               "O veículo leve (TN 01) roda a Gasolina; as caminhonetes rodam a Diesel.")

    # ---- KPIs ----------------------------------------------------------
    litros_t = linha["LITROS_DIESEL"] + linha["LITROS_GASOLINA"]
    pct_d = linha["CO2_DIESEL"] / linha["CO2_TOTAL"] * 100 if linha["CO2_TOTAL"] else 0
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("⛽", "CO2 do mês", f"{fmt_co2(linha['CO2_TOTAL'])} kg",
                 ("▲ " if (delta_pct is not None and delta_pct >= 0) else "▼ ") +
                 f"{abs(delta_pct or 0):.1f}% vs mês anterior" if delta_pct is not None else "—",
                 tema["primaria"])
    with c2:
        kpi_card("🛢️", "CO2 Diesel", fmt_co2(linha["CO2_DIESEL"]),
                 f"{pct_d:.0f}% das emissões • {fmt_co2(linha['LITROS_DIESEL'])} L",
                 tema["accent"])
    with c3:
        pct_g = 100 - pct_d
        kpi_card("⛽", "CO2 Gasolina", fmt_co2(linha["CO2_GASOLINA"]),
                 f"{pct_g:.0f}% das emissões • {fmt_co2(linha['LITROS_GASOLINA'])} L",
                 tema["kpi_c4"])
    with c4:
        kpi_card("🧯", "Litros totais", f"{fmt_co2(litros_t)} L",
                 "combustível no mês", tema["kpi_c3"])
    with c5:
        kpi_card("🚚", "Veículos no mês", f"{int(linha['VEICULOS'])}",
                 f"{fmt_km(linha['KM_TOTAL'])} rodados", tema["kpi_c5"])

    # ---- tendência mensal consolidada + top veículos --------------------
    col_a, col_b = st.columns([1.5, 1])
    with col_a:
        st.markdown('<h3 class="carta">📈 CO₂ consolidado por mês (kg)</h3>',
                    unsafe_allow_html=True)
        meses_all = cons["MES_REF"].tolist()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=meses_all, y=cons["CO2_DIESEL"], name="Diesel",
            marker_color=cor_fonte["Diesel"],
            hovertemplate="%{x}<br>Diesel: <b>%{y:,.1f} kg</b><extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=meses_all, y=cons["CO2_GASOLINA"], name="Gasolina",
            marker_color=cor_fonte["Gasolina"],
            hovertemplate="%{x}<br>Gasolina: <b>%{y:,.1f} kg</b><extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=meses_all, y=cons["CO2_TOTAL"], name="Total",
            mode="lines+markers",
            line=dict(color=tema["texto"], width=2.5), marker=dict(size=7),
            hovertemplate="%{x}<br>Total: <b>%{y:,.1f} kg</b>"
                          " (%{customdata[0]:+.1f}%)<extra></extra>",
            customdata=cons["DELTA_PCT"].fillna(0).values,
        ))
        fig.update_layout(
            barmode="stack", bargap=0.3, height=340,
            yaxis=dict(title="kgCO₂e", gridcolor=tema["grid"],
                       range=[0, cons["CO2_TOTAL"].max() * 1.18]),
        )
        base_layout(fig, tema)
        st.plotly_chart(reg_print("06_co2_por_mes", fig), width="stretch", config=CFG_GRAF)

    with col_b:
        st.markdown('<h3 class="carta">🏆 Top veículos — CO₂ no mês</h3>',
                    unsafe_allow_html=True)
        sel = por_v[por_v["MES_REF"] == mes_c].sort_values("CO2E")
        top = sel.tail(5)
        top_max = float(top["CO2E"].max())
        fig2 = go.Figure(go.Bar(
            x=top["CO2E"], y=[f"{t} · {m}" for t, m in zip(top["TAG"], top["MODELO"])],
            orientation="h",
            marker_color=[cor_fonte.get(c, "#94a3b8") for c in top["COMBUSTIVEL"]],
            text=[fmt_co2(v) for v in top["CO2E"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(size=11.5, family=FONTE, color=tema["texto"]),
            hovertemplate="%{y}<br><b>%{x:,.1f} kg CO₂e</b><extra></extra>",
        ))
    fig2.update_layout(
        height=340, showlegend=False,
        xaxis=dict(visible=False, range=[0, top_max * 1.18]),
        yaxis=dict(automargin=True, tickcolor="rgba(0,0,0,0)"),
        margin=dict(l=110, r=26, t=20, b=10),
    )
    base_layout(fig2, tema)
    st.plotly_chart(reg_print("07_top_co2_veiculos", fig2), width="stretch", config=CFG_GRAF)

    # ---- comparação veículo a veículo ----------------------------------
    st.markdown(f'<h3 class="carta">🔎 Comparação por veículo — {mes_c}'
                f'{" (vs " + str(mes_ant) + ")" if mes_ant else ""}</h3>',
                unsafe_allow_html=True)
    delta_map = {}
    if mes_ant is not None:
        ant = por_v[por_v["MES_REF"] == mes_ant]
        delta_map = dict(zip(ant["TAG"], ant["CO2E"]))

    tabela = sel[["TAG", "MODELO", "COMBUSTIVEL", "KM_MES", "LITROS", "CO2E"]].copy()
    tabela["ANT"] = tabela["TAG"].map(delta_map)
    tabela["DELTA"] = tabela["CO2E"] - tabela["ANT"]
    tabela["DELTA_PCT"] = tabela["DELTA"] / tabela["ANT"] * 100
    tabela = tabela.sort_values("CO2E", ascending=False).reset_index(drop=True)
    tabela.columns = ["Veículo", "Modelo", "Combustível", "Km no mês", "Litros",
                      "CO2 (kg)", "CO2 mês ant. (kg)", "Δ CO2 (kg)", "Δ (%)"]

    def cor_emissao(val):
        if pd.isna(val):
            return ""
        return f"color:{tema['neg']};font-weight:700;" if val > 0 else \
            (f"color:{tema['pos']};font-weight:700;" if val < 0 else "")

    def fmt_delta_co2(val):
        if pd.isna(val):
            return "—"
        return f"{val:+,.1f}"

    def fmt_delta_pct(val):
        if pd.isna(val):
            return "novo no mês" if "novo" in str(val) else "—"
        return f"{val:+,.1f}%"

    styled = (tabela.style
              .map(cor_emissao, subset=["Δ CO2 (kg)", "Δ (%)"])
              .format({"Km no mês": "{:,.0f}", "Litros": "{:.1f}",
                       "CO2 (kg)": "{:.1f}", "CO2 mês ant. (kg)": "{:.1f}",
                       "Δ CO2 (kg)": fmt_delta_co2, "Δ (%)": fmt_delta_pct})
              .hide(axis="index"))
    st.dataframe(styled, width="stretch", height=360)

    # print: tabela veículo a veículo vira figura PNG
    print_cols = tabela[["Veículo", "Modelo", "Combustível", "Km no mês", "Litros",
                         "CO2 (kg)", "CO2 mês ant. (kg)", "Δ (%)"]].copy()
    print_cols["Km no mês"] = print_cols["Km no mês"].fillna(0).map("{:,.0f}".format)
    print_cols["Litros"] = print_cols["Litros"].fillna(0).map("{:.1f}".format)
    print_cols["CO2 (kg)"] = print_cols["CO2 (kg)"].fillna(0).map("{:.1f}".format)
    print_cols["CO2 mês ant. (kg)"] = print_cols["CO2 mês ant. (kg)"].fillna(0).map("{:.1f}".format)
    print_cols["Δ (%)"] = print_cols["Δ (%)"].map(
        lambda v: "—" if (isinstance(v, str) or pd.isna(v)) else f"{v:+.1f}%")
    PRINTS.append(("10_consumo_co2_por_veiculo",
                   figura_tabela(f"Consumo de CO₂ por veículo — {mes_c}", print_cols.columns,
                                 [print_cols[c].tolist() for c in print_cols.columns], tema),
                   1200, 110 + 27 * len(print_cols)))

    with st.expander("📋 Consolidado mensal (km, litros e CO₂ por mês)"):
        con = cons.copy()
        con["Veículos"] = con["VEICULOS"]
        con["Var. vs mês anterior"] = con["DELTA_PCT"]
        con["KM total"] = con["KM_TOTAL"]
        con["CO2 total (kg)"] = con["CO2_TOTAL"]
        con["Litros diesel"] = con["LITROS_DIESEL"]
        con["Litros gasolina"] = con["LITROS_GASOLINA"]
        con["CO2 diesel (kg)"] = con["CO2_DIESEL"]
        con["CO2 gasolina (kg)"] = con["CO2_GASOLINA"]
        con = con[["MES_REF", "Veículos", "KM total", "Litros diesel",
                   "Litros gasolina", "CO2 diesel (kg)", "CO2 gasolina (kg)",
                   "CO2 total (kg)", "Var. vs mês anterior"]]
        con.columns = ["Mês", "Veículos", "KM total", "Litros diesel",
                       "Litros gasolina", "CO2 diesel (kg)", "CO2 gasolina (kg)",
                       "CO2 total (kg)", "Var. vs mês anterior"]
        st.dataframe(
            con.style.format({"KM total": "{:,.0f}", "Litros diesel": "{:.1f}",
                              "Litros gasolina": "{:.1f}",
                              "CO2 diesel (kg)": "{:.1f}",
                              "CO2 gasolina (kg)": "{:.1f}",
                              "CO2 total (kg)": "{:.1f}",
                              "Var. vs mês anterior": fmt_delta_pct})
            .map(cor_status, subset=["Mês"])
            .map(cor_emissao, subset=["Var. vs mês anterior"])
            .hide(axis="index"),
            width="stretch", height=340,
        )
        st.caption("Fatores de emissão (MCTI — Setor Energia): Diesel 2,68 e "
                   "Gasolina 2,16 kgCO₂e/L. Consumo médio (km/L) por modelo: "
                   "Nivus 11,0 · Pulse 11,5 · Tracker 11,0 · Hilux/Ranger/S10 9,5 · "
                   "Frontier 9,0 · Strada 10,0.")


# ============================================================================
# BARRA LATERAL — tema + dados
# ============================================================================
with st.sidebar:
    escuro = st.toggle("🌙 Modo escuro", value=st.session_state.get("tema_escuro", False),
                       key="tema_escuro")
    st.markdown("---")

    st.markdown("## 📂 Dados")
    subiu = st.file_uploader("Upload da planilha de KM", type=["xlsx", "xls"])
    if subiu is not None:
        st.session_state["arquivo_carregado"] = subiu.getvalue()
        st.cache_data.clear()

    ARQUIVO_EXEMPLO = Path(__file__).parent / "PA - CONTROLE DE KM (version 1).xlsx"
    if "arquivo_carregado" not in st.session_state:
        st.session_state["arquivo_carregado"] = None

    if st.session_state["arquivo_carregado"] is None and ARQUIVO_EXEMPLO.exists():
        if st.button("📄 Usar planilha de exemplo (PA - CONTROLE DE KM)"):
            st.session_state["arquivo_carregado"] = ARQUIVO_EXEMPLO.read_bytes()
            st.cache_data.clear()

    dados_prontos = st.session_state["arquivo_carregado"] is not None

    if dados_prontos:
        @st.cache_data(show_spinner="Processando planilha...")
        def processar(bytes_arquivo):
            return processar_planilha(io.BytesIO(bytes_arquivo))

        @st.cache_data(show_spinner="Gerando planilha corrigida...")
        def gerar_corrigida(bytes_arquivo):
            return corrigir_workbook(bytes_arquivo)

        @st.cache_data(show_spinner="Gerando versão estática (HTML)...")
        def gerar_html_estatico(df):
            return build_html(df)

        df = processar(st.session_state["arquivo_carregado"])
        if df.empty:
            st.error("Nenhuma aba mensal válida foi encontrada na planilha.")
            st.stop()

        st.divider()
        st.markdown("## 🎛️ Filtros")

        ordem_meses = MESES_ORDEM + sorted(
            m for m in df["MES_REF"].unique() if m not in MESES_ORDEM
        )
        meses = [m for m in ordem_meses if m in df["MES_REF"].unique()]

        mes_padrao = "AGOSTO" if "AGOSTO" in meses else meses[-1]
        mes_sel = st.selectbox("Mês de referência", meses, index=meses.index(mes_padrao))

        tags = sorted(df["TAG"].unique())
        tag_sel = st.multiselect("🚚 Veículos (TAG)", tags, default=tags)

        tipos = sorted(df["TIPO"].dropna().unique())
        tipo_sel = st.multiselect("🚗 Tipo de veículo", tipos, default=tipos)

        status_ok = sorted(df["STATUS"].dropna().unique())
        status_sel = st.multiselect("🚦 Status", status_ok, default=status_ok)

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                "📥 Dados (CSV)",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name="frota_processada.csv",
                mime="text/csv",
                width="stretch",
            )
        with col_b:
            corrigido, abas = gerar_corrigida(st.session_state["arquivo_carregado"])
            st.download_button(
                "🗜️ Planilha corrigida",
                data=corrigido,
                file_name="PA - CONTROLE DE KM (CORRIGIDO).xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        with st.expander("🌐 Exportar dashboard (HTML)"):
            st.download_button(
                "🧾 Baixar dashboard_frota.html",
                data=gerar_html_estatico(df).encode("utf-8"),
                file_name="dashboard_frota.html",
                mime="text/html",
                width="stretch",
            )
        with st.expander("ℹ️ Abas corrigidas"):
            st.write("Coluna ACUM. e semanas S1–S5 recalculadas em: " +
                     ", ".join(abas) if abas else "nenhuma aba mensal detectada.")

# ============================================================================
# TEMA ATIVO + CSS
# ============================================================================
tema = DARK if escuro else LIGHT
st.markdown(css_tema(tema), unsafe_allow_html=True)

# ============================================================================
# CABEÇALHO
# ============================================================================
st.markdown(
    f"""
    <div class="topo">
      <div class="topo-meta">
        <span class="selo">Gestão de Frota · KM &amp; Emissões (ESG)</span>
        <span class="selo-data">Atualizado em {datetime.now().strftime("%d/%m/%Y")}</span>
      </div>
      <h1>🚛 Dashboard de Controle de Frota — Carajás</h1>
      <p>Monitoramento de quilometragem mensal, status operacional e evolução semanal da frota.
      Dados corrigidos: o acumulado do mês é calculado pelas leituras do hodômetro
      (bloco de cadastro).</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- estado vazio -------------------------------------------------------------
if not dados_prontos:
    st.info("👆 Faça o upload da planilha de KM (ou use a planilha de exemplo) para gerar o dashboard.")
    st.markdown(
        "**O que o dashboard faz:**\n\n"
        "- Calcula o **KM total acumulado do mês** pela leitura do hodômetro (de forma robusta);\n"
        "- Corrige a coluna **ACUM.** da planilha (o mês de AGOSTO, por exemplo, mostrava zero por causa de fórmulas quebradas: `#REF!`, referência errada e somas com marcadores negativos);\n"
        "- Mostra tendência mensal, ranking de veículos, status e evolução semanal."
    )
    st.stop()

# ============================================================================
# FILTROS APLICADOS
# ============================================================================
mascara = (
    (df["MES_REF"] == mes_sel)
    & (df["TAG"].isin(tag_sel))
    & (df["TIPO"].isin(tipo_sel))
    & (df["STATUS"].isin(status_sel))
)
filtrado = df[mascara].copy()

if filtrado.empty:
    st.warning("Sem dados para os filtros selecionados — ajuste os filtros na barra lateral.")
    st.stop()

filtrado["KM_MES"] = pd.to_numeric(filtrado["KM_MES"], errors="coerce")

# Base com TODOS os meses, já com os mesmos filtros (TAG/TIPO/STATUS).
# Usada para comparar o mês selecionado com o anterior de forma consistente.
base = df[
    df["TAG"].isin(tag_sel)
    & df["TIPO"].isin(tipo_sel)
    & df["STATUS"].isin(status_sel)
].copy()
base["KM_MES"] = pd.to_numeric(base["KM_MES"], errors="coerce")

# ============================================================================
# KPIs
# ============================================================================
km_total = filtrado["KM_MES"].fillna(0).sum()
km_acum_historico = df["KM_MES"].fillna(0).sum()
media_veic = filtrado["KM_MES"].fillna(0).mean()
veiculos = int(filtrado["TAG"].nunique())
em_manut = int((filtrado["STATUS"] == "Manutenção").sum())

resumo = resumo_mensal(df)
ordem_sel = int(filtrado["MES_ORDEM"].iloc[0])
linha_ant_resumo = resumo[resumo["MES_ORDEM"] == ordem_sel - 1]
mes_ant_label = str(linha_ant_resumo["MES_REF"].iloc[0]) if not linha_ant_resumo.empty else None
km_ant = float(base.loc[base["MES_ORDEM"] == ordem_sel - 1, "KM_MES"].fillna(0).sum())
delta_pct = ((km_total - km_ant) / km_ant * 100) if km_ant else None

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("🎯", "KM total no mês", fmt_km(km_total),
             f"{'▲' if delta_pct and delta_pct >= 0 else '▼'} {abs(delta_pct or 0):.1f}% vs mês anterior"
             if delta_pct is not None else "—", tema["primaria"])
with c2:
    kpi_card("📈", "Acumulado histórico", fmt_km(km_acum_historico),
             f"{df['MES_REF'].nunique()} meses analisados", tema["accent"])
with c3:
    kpi_card("🚚", "Média por veículo", fmt_km(media_veic),
             f"{veiculos} veículos no mês", tema["kpi_c3"])
with c4:
    kpi_card("🛠️", "Em manutenção", f"{em_manut}",
             f"de {len(filtrado)} linhas no mês", tema["kpi_c4"])
with c5:
    ativos = int((filtrado["STATUS"] == "Operacional").sum())
    pct = (ativos / len(filtrado) * 100) if len(filtrado) else 0
    kpi_card("✅", "Frota operacional", f"{ativos}",
             f"{pct:.0f}% do mês selecionado", tema["kpi_c5"])

# ---- resumo executivo (leitura rápida para apresentação) -------------------
delta_txt = (
    f"{'▲ +' if delta_pct is not None and delta_pct >= 0 else '▼ '}"
    f"{abs(delta_pct or 0):.1f}% vs {mes_ant_label}"
    if delta_pct is not None else "primeiro mês da série"
)
op_txt = (
    "Toda a frota ativa" if ativos == len(filtrado)
    else f"{pct:.0f}% da frota ativa"
)
if em_manut == 1:
    mant_txt = "1 veículo em manutenção"
elif em_manut > 1:
    mant_txt = f"{em_manut} veículos em manutenção"
else:
    mant_txt = "sem veículos em manutenção"
st.markdown(
    f'<div class="exec"><b>{mes_sel}</b>: {fmt_km(km_total)} em '
    f"{veiculos} veículos ({delta_txt}). {op_txt} · "
    f"média {fmt_km(media_veic)} por veículo · {mant_txt}.</div>",
    unsafe_allow_html=True,
)

# ============================================================================
# COMPARATIVO — MÊS ATUAL × MÊS ANTERIOR (KM total + consumo de CO2)
# ============================================================================
st.markdown("---")
comp = None
if mes_ant_label is None:
    st.info(f"Sem registro do mês anterior a {mes_sel} — o comparativo não é exibido.")
else:
    cons_comp = consolidado_consumo(enriquecer_consumo(base))
    l_at = cons_comp[cons_comp["MES_REF"] == mes_sel]
    l_ant = cons_comp[cons_comp["MES_REF"] == mes_ant_label]
    if l_at.empty or l_ant.empty:
        st.info(f"Sem dados de consumo para comparar {mes_ant_label} × {mes_sel} "
                "(não há CO2 estimado para o mês anterior no recorte selecionado).")
    else:
        a = l_ant.iloc[0]
        b = l_at.iloc[0]
        co2_atual, co2_ant = float(b["CO2_TOTAL"]), float(a["CO2_TOTAL"])
        lit_at = float(b["LITROS_DIESEL"] + b["LITROS_GASOLINA"])
        lit_ant = float(a["LITROS_DIESEL"] + a["LITROS_GASOLINA"])
        veic_ant = int(a["VEICULOS"])

        st.markdown(f"#### 🔁 Comparativo — {mes_ant_label} → {mes_sel} "
                    f"(KM total + consumo de CO₂)")

        def delta_abs(valor, ant):
            return "—" if not ant else f"{valor - ant:+,.1f}".replace(",", ".")

        def delta_pct_txt(valor, ant):
            return "—" if not ant else f"{(valor - ant) / ant * 100:+.1f}%"

        comp = pd.DataFrame({
            "Métrica": ["KM total (km)", "Veículos no mês", "CO2 total (kg)",
                        "Litros totais (L)"],
            mes_ant_label: [fmt_num(km_ant), f"{veic_ant}", fmt_co2(co2_ant),
                            f"{lit_ant:,.1f}".replace(",", ".")],
            mes_sel: [fmt_num(km_total), f"{veiculos}", fmt_co2(co2_atual),
                      f"{lit_at:,.1f}".replace(",", ".")],
            "Δ (absoluto)": [
                "—" if not km_ant else f"{km_total - km_ant:+,.0f}".replace(",", "."),
                "—" if not veic_ant else f"{veiculos - veic_ant:+,d}",
                delta_abs(co2_atual, co2_ant), delta_abs(lit_at, lit_ant),
            ],
            "Δ (%)": [
                "—" if not km_ant else f"{delta_pct:+.1f}%",
                "—" if not veic_ant else f"{(veiculos - veic_ant) / veic_ant * 100:+.1f}%",
                delta_pct_txt(co2_atual, co2_ant),
                delta_pct_txt(lit_at, lit_ant),
            ],
        })
        comp.columns = ["Métrica", mes_ant_label, mes_sel, "Δ (absoluto)", "Δ (%)"]

        def cor_delta_comp(v):
            if v in ("—", "Métrica") or (isinstance(v, str) and (not v or v == "—")):
                return ""
            try:
                x = float(v.rstrip("%").replace(",", "."))
            except ValueError:
                return ""
            if x > 0:
                return f"color:{tema['neg']};font-weight:700;"
            if x < 0:
                return f"color:{tema['pos']};font-weight:700;"
            return "color:var(--muted);"

        st.dataframe(
            comp.style
            .map(cor_delta_comp, subset=["Δ (absoluto)", "Δ (%)"])
            .hide(axis="index"),
            width="stretch", height=250,
        )
        st.caption("Compara o mês selecionado com o anterior usando os MESMOS filtros "
                   "(veículos, tipo e status). ▲ / valores positivos = aumento; "
                   "▼ / negativos = redução. → O primeiro mês da planilha (OUTUBRO 2025) "
                   "não tem mês anterior para comparar.")
        PRINTS.append(("08_comparativo_mes",
                       figura_tabela(f"Comparativo {mes_ant_label} → {mes_sel}",
                                     comp.columns,
                                     [comp[c].tolist() for c in comp.columns], tema),
                       1200, 110 + 27 * len(comp)))

st.markdown("---")
st.markdown("#### 🧭 Visão geral da frota")

col_tend, col_top = st.columns([1.5, 1])

# ---------------- tendência mensal -------------------------------------------
with col_tend:
    st.markdown('<h3 class="carta">📈 KM total por mês (toda a frota)</h3>',
                unsafe_allow_html=True)
    cores_t = [tema["accent"] if m == mes_sel else tema["primaria"]
               for m in resumo["MES_REF"]]
    cores_rot = [tema["texto_no_accent"] if c == tema["accent"] else tema["texto_em_barra"]
                 for c in cores_t]
    max_km = resumo["KM_TOTAL"].max()

    fig_t = go.Figure()
    fig_t.add_trace(go.Bar(
        x=resumo["MES_REF"], y=resumo["KM_TOTAL"], name="KM total",
        marker_color=cores_t,
        text=[fmt_num(v) for v in resumo["KM_TOTAL"]],
        textposition="inside", insidetextanchor="middle",
        textfont=dict(size=11.5, family=FONTE, color=cores_rot),
        cliponaxis=False,
        customdata=resumo["VEICULOS"].values,
        hovertemplate="%{x}<br>KM total: <b>%{y:,.0f} km</b><br>%{customdata[0]} veículos<extra></extra>",
    ))
    fig_t.add_trace(go.Scatter(
        x=resumo["MES_REF"], y=resumo["VEICULOS"], name="Veículos",
        yaxis="y2", mode="lines+markers",
        line=dict(color=tema["linha_veic"], width=2.5),
        marker=dict(size=7),
        hovertemplate="%{x}<br>%{y} veículos<extra></extra>",
    ))
    fig_t.update_layout(
        xaxis=dict(title=None),
        yaxis=dict(title="km", gridcolor=tema["grid"],
                   range=[0, max_km * 1.12]),
        yaxis2=dict(title="veículos", overlaying="y", side="right",
                    showgrid=False, range=[0, resumo["VEICULOS"].max() + 2]),
        bargap=0.35, height=330, showlegend=True,
    )
    base_layout(fig_t, tema)
    st.plotly_chart(reg_print("01_km_total_por_mes", fig_t), width="stretch", config=CFG_GRAF)

# ------------------ top veículos do mês --------------------------------------
with col_top:
    st.markdown('<h3 class="carta">🏆 Top 5 veículos do mês</h3>', unsafe_allow_html=True)
    top = (filtrado.nlargest(5, "KM_MES")
           .sort_values("KM_MES")[["TAG", "KM_MES"]])
    top_max = float(top["KM_MES"].fillna(0).max())
    fig_top = go.Figure(go.Bar(
        x=top["KM_MES"].fillna(0),
        y=top["TAG"], orientation="h",
        marker_color=[tema["serie"][(i + 4) % len(tema["serie"])]
                      for i in range(len(top))],
        text=[fmt_num(v) for v in top["KM_MES"].fillna(0)],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=11.5, family=FONTE, color=tema["texto"]),
        hovertemplate="%{y}: <b>%{x:,.0f} km</b><extra></extra>",
    ))
    fig_top.update_layout(
        height=330, showlegend=False,
        # folga no eixo p/ o rótulo de km não ser cortado quando a barra é longa
        xaxis=dict(visible=False, range=[0, top_max * 1.18]),
        # automargin garante que os rótulos (TAG) do eixo Y nunca fiquem cortados
        yaxis=dict(automargin=True, tickcolor="rgba(0,0,0,0)"),
        margin=dict(l=70, r=26, t=20, b=10),
    )
    base_layout(fig_top, tema)
    st.plotly_chart(reg_print("02_top5_veiculos", fig_top), width="stretch", config=CFG_GRAF)

st.markdown("#### 🚦 Distribuição")

col_tipo, col_status, col_sem = st.columns([1, 1, 1.35])

# ---------------- distribuição por tipo --------------------------------------
with col_tipo:
    st.markdown('<h3 class="carta">🚐 KM por tipo de veículo</h3>', unsafe_allow_html=True)
    km_tipo = filtrado.groupby("TIPO")["KM_MES"].sum().reset_index()
    fig_tipo = px.pie(
        km_tipo, values="KM_MES", names="TIPO", hole=0.55,
        color_discrete_sequence=[tema["primaria"], tema["accent"],
                                 "#0ea5e9", "#10b981"],
    )
    fig_tipo.update_traces(
        textinfo="label+percent", textfont=dict(color="#fff", size=11),
        hovertemplate="%{label}<br><b>%{value:,.0f} km</b> (%{percent})<extra></extra>",
    )
    fig_tipo.update_layout(height=310, annotations=[dict(
        text=f"{fmt_km(km_total)}", x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=tema["texto"], family=FONTE))])
    base_layout(fig_tipo, tema)
    st.plotly_chart(reg_print("03_km_por_tipo", fig_tipo), width="stretch", config=CFG_GRAF)

# ---------------- distribuição por status ------------------------------------
with col_status:
    st.markdown('<h3 class="carta">🚦 Status operacional</h3>', unsafe_allow_html=True)
    km_status = filtrado.groupby("STATUS")["KM_MES"].sum().reset_index()
    km_status = km_status.sort_values("KM_MES", ascending=False)
    st_max = float(km_status["KM_MES"].fillna(0).max())
    fig_st = go.Figure(go.Bar(
        x=km_status["KM_MES"], y=km_status["STATUS"], orientation="h",
        marker_color=[STATUS_CORES.get(s, "#94a3b8") for s in km_status["STATUS"]],
        text=[fmt_num(v) for v in km_status["KM_MES"]],
        textposition="outside",
        cliponaxis=False,
        textfont=dict(size=11.5, family=FONTE, color=tema["texto"]),
        hovertemplate="%{y}<br><b>%{x:,.0f} km</b><extra></extra>",
    ))
    fig_st.update_layout(
        height=310, showlegend=False,
        xaxis=dict(visible=False, range=[0, st_max * 1.18]),
        # automargin evita que as barras cubram/cortem os nomes (Y à esquerda)
        yaxis=dict(automargin=True, tickcolor="rgba(0,0,0,0)",
                   tickfont=dict(family=FONTE, size=11.5)),
        margin=dict(l=120, r=26, t=20, b=10),
    )
    base_layout(fig_st, tema)
    st.plotly_chart(reg_print("04_status_operacional", fig_st), width="stretch", config=CFG_GRAF)

# ---------------- evolução semanal -------------------------------------------
with col_sem:
    st.markdown('<h3 class="carta">📊 KM semanal no mês selecionado</h3>',
                unsafe_allow_html=True)
    semana_cols = ["W1", "W2", "W3", "W4", "W5"]
    top_n = 6
    top_tags = filtrado.nlargest(top_n, "KM_MES")["TAG"].tolist()
    df_plot = filtrado[filtrado["TAG"].isin(top_tags)].copy()
    df_melt = df_plot.melt(
        id_vars=["TAG"], value_vars=semana_cols,
        var_name="Semana", value_name="KM",
    )
    df_melt["Semana"] = df_melt["Semana"].str.replace("W", "S")
    df_melt["KM"] = pd.to_numeric(df_melt["KM"], errors="coerce").fillna(0)

    total_sem = df_melt.groupby("Semana")["KM"].sum().reset_index()
    fig_sem = go.Figure()
    fig_sem.add_trace(go.Bar(
        x=total_sem["Semana"], y=total_sem["KM"], name="Total da frota",
        marker_color=tema["bar_semana"],
        hovertemplate="%{x}<br>total: <b>%{y:,.0f} km</b><extra></extra>",
    ))
    for i, tag in enumerate(top_tags):
        sub = df_melt[df_melt["TAG"] == tag]
        fig_sem.add_trace(go.Scatter(
            x=sub["Semana"], y=sub["KM"], mode="lines+markers", name=tag,
            line=dict(width=2.6, color=tema["serie"][i % len(tema["serie"])]),
            hovertemplate=f"{tag}<br>%{{x}}: %{{y:,.0f}} km<extra></extra>",
        ))
    fig_sem.update_layout(height=310,
                          yaxis=dict(title="km", gridcolor=tema["grid"], automargin=True),
                          xaxis=dict(automargin=True),
                          barmode="overlay", showlegend=True)
    base_layout(fig_sem, tema)
    fig_sem.update_layout(margin=dict(l=16, r=16, t=40, b=40))
    st.plotly_chart(reg_print("05_evolucao_semanal", fig_sem), width="stretch", config=CFG_GRAF)

# ============================================================================
# EVOLUÇÃO SEMANAL POR VEÍCULO (tabela)
# ============================================================================
with st.expander(f"📅 Evolução semanal por veículo — {mes_sel}"):
    df_sem = filtrado[["TAG"] + semana_cols + ["KM_MES"]].copy()
    df_sem = df_sem.sort_values("KM_MES", ascending=False).reset_index(drop=True)
    df_sem.columns = ["Veículo", "S1", "S2", "S3", "S4", "S5", "Total no mês"]
    st.dataframe(
        df_sem.style
        .format({c: "{:,.0f}" for c in ["S1", "S2", "S3", "S4", "S5", "Total no mês"]},
                na_rep="—")
        .hide(axis="index"),
        width="stretch", height=300,
    )

# ============================================================================
# TABELA DETALHADA
# ============================================================================
st.markdown("---")
st.markdown("#### 🗓️ Detalhamento do mês selecionado")

tabela = filtrado[["TAG", "TIPO", "MODELO", "PLACA", "KM_INICIAL", "KM_FINAL",
                   "KM_MES", "STATUS"]].copy()

piv_km = df.pivot_table(index="TAG", columns="MES_ORDEM",
                        values="KM_MES", aggfunc="sum")
if ordem_sel - 1 in piv_km.columns:
    delta_veic = piv_km[ordem_sel].fillna(0) - piv_km[ordem_sel - 1].fillna(0)
    tabela["DELTA"] = tabela["TAG"].map(delta_veic)
else:
    tabela["DELTA"] = np.nan

tabela["Mês"] = mes_sel
tabela = tabela[["Mês", "TAG", "TIPO", "MODELO", "PLACA", "KM_INICIAL",
                 "KM_FINAL", "KM_MES", "DELTA", "STATUS"]]
tabela.columns = ["Mês", "Veículo", "Tipo", "Modelo", "Placa", "Km inicial",
                  "Km final", "Km no mês", "Δ vs mês anterior", "Status"]
tabela = tabela.sort_values("Km no mês", ascending=False).reset_index(drop=True)


def cor_status(val):
    sem = {"Operacional": "pos", "Manuten\u00e7\u00e3o": "neg",
           "Mobiliza\u00e7\u00e3o": "alerta", "Pendente": "neutro",
           "Lavador": "info", "Erro Dados": "roxo"}
    cor = tema.get(sem.get(str(val), "neutro"), tema["neutro"])
    return f"color: {cor}; font-weight:700;"


def cor_delta(val):
    if pd.isna(val):
        return ""
    return (f"color:{tema['pos']};font-weight:700;" if val >= 0
            else f"color:{tema['neg']};font-weight:700;")


def fmt_delta(val):
    if pd.isna(val):
        return "—"
    return f"{val:+,.0f} km"


styled = (
    tabela.style
    .map(cor_status, subset=["Status"])
    .map(cor_delta, subset=["Δ vs mês anterior"])
    .format({"Km inicial": "{:,.0f}", "Km final": "{:,.0f}", "Km no mês": "{:,.0f}",
             "Δ vs mês anterior": fmt_delta})
    .hide(axis="index")
)

st.dataframe(styled, width="stretch", height=390)

# print: detalhamento do mês vira figura PNG
print_tab = tabela.copy()
for c in ["Km inicial", "Km final", "Km no mês"]:
    print_tab[c] = print_tab[c].fillna(0).map("{:,.0f}".format)
print_tab["Δ vs mês anterior"] = print_tab["Δ vs mês anterior"].map(
    lambda v: "—" if (pd.isna(v) if not isinstance(v, str) else v == "—") else f"{v:+,.0f} km")
PRINTS.append(("09_detalhamento_mes",
               figura_tabela(f"Detalhamento do mês — {mes_sel}", print_tab.columns,
                             [print_tab[c].tolist() for c in print_tab.columns], tema),
               1200, 110 + 27 * len(print_tab)))

if (filtrado["TAG"] + filtrado["MES_REF"]).duplicated().any():
    st.caption("⚠️ Alguns veículos possuem mais de um registro no mês (dados repetidos na planilha).")

# ============================================================================
# CONSUMO DE CO2 DA FROTA (2025→) — segue o mês e os filtros principais
# ============================================================================
if not base.empty:
    render_consumo(base, mes_sel, tema)
else:
    st.info("Sem dados de quilometragem para os filtros selecionados — o consumo de CO2 não é exibido.")

# ============================================================================
# PRINTS (PNG) — uma imagem por informação essencial
# ============================================================================
st.markdown("---")
st.markdown("#### 🖼️ Prints — uma imagem por informação essencial")
st.caption("Cada gráfico e tabela viram um arquivo .png (resolução 2x) e tudo é "
           "baixado em um único .zip. Renderiza na hora usando kaleido — pode "
           "levar alguns segundos.")
nome_prints = {
    "01_km_total_por_mes": "KM total por mês",
    "02_top5_veiculos": "Top 5 veículos do mês",
    "03_km_por_tipo": "KM por tipo de veículo",
    "04_status_operacional": "Status operacional",
    "05_evolucao_semanal": "Evolução semanal",
    "06_co2_por_mes": "CO2 consolidado por mês",
    "07_top_co2_veiculos": "Top veículos CO2 do mês",
    "08_comparativo_mes": "Comparativo mês atual × anterior",
    "09_detalhamento_mes": "Detalhamento do mês",
    "10_consumo_co2_por_veiculo": "Consumo de CO2 por veículo",
}
if st.button("🖨️ Gerar prints (ZIP)", width="stretch"):
    if not PRINTS:
        st.error("Nenhum gráfico/tabela registrado para exportar.")
    else:
        with st.spinner(f"Renderizando {len(PRINTS)} imagens (leve alguns segundos)..."):
            _buf = io.BytesIO()
            try:
                with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for nome, fig, largura, altura in PRINTS:
                        try:
                            png = pio.to_image(fig, format="png", scale=2,
                                               width=largura, height=altura)
                        except Exception:
                            png = pio.to_image(fig, format="png", scale=1,
                                               width=largura, height=altura)
                        z.writestr(f"{nome}.png", png)
                st.session_state["zip_print_bytes"] = _buf.getvalue()
            except Exception as ex:
                st.error(f"Falha ao gerar os prints: {ex}")
if st.session_state.get("zip_print_bytes") is not None:
    st.download_button("⬇️ Baixar prints_frota.zip",
                       data=st.session_state["zip_print_bytes"],
                       file_name="prints_frota.zip",
                       mime="application/zip",
                       width="stretch")
    with st.expander(f"📦 Arquivos no ZIP ({len(PRINTS)})"):
        for nome, _f, _w, _h in PRINTS:
            st.write(f"`{nome}.png` — {nome_prints.get(nome, nome)}")

# rodapé
st.caption(f"Gerado em {timestamp_humano()} • Fonte: PA - CONTROLE DE KM (version 1)")