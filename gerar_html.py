"""
gerar_html.py — Exporta um dashboard ESTÁTICO (dashboard_frota.html) que roda em
qualquer navegador, SEM depender de Python/Streamlit em tempo de execução.

O HTML é autocontido: embute o plotly.js, os dados processados (JSON) e um
mini-renderizador JS (seletor de mês + botão claro/escuro). Inclui também o
consumo de CO2 da frota (estimado a partir do km real, Diesel + Gasolina).

CLI:  python gerar_html.py [caminho_do_arquivo.xlsx]
Também é importável:  build_html(df) -> str
"""
from __future__ import annotations

import functools
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from frota_utils import (MESES_ORDEM, co2_por_veiculo, consolidado_consumo,
                         enriquecer_consumo, processar_planilha, resumo_mensal)

ARQ_PADRAO = "PA - CONTROLE DE KM (version 1).xlsx"
FONTE_JS = "Inter, 'Segoe UI', Arial, sans-serif"

PALETA = ["#2563eb", "#f59e0b", "#0ea5e9", "#10b981", "#8b5cf6",
          "#ec4899", "#f97316", "#14b8a6", "#84cc16", "#64748b"]
STATUS_CORES_JS = {
    "Operacional": "#10b981", "Manuten\u00e7\u00e3o": "#ef4444",
    "Mobiliza\u00e7\u00e3o": "#f97316", "Pendente": "#94a3b8",
    "Lavador": "#0ea5e9", "Erro Dados": "#a855f7",
}


def _num(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(v):
        return None
    return int(v) if v == int(v) else round(v, 2)


def preparar(df: pd.DataFrame) -> dict:
    """Converte o DataFrame processado num dicionário JSON-serializável."""
    dfn = df.copy()
    dfn["KM_MES"] = pd.to_numeric(dfn["KM_MES"], errors="coerce").fillna(0)
    for c in ["W1", "W2", "W3", "W4", "W5"]:
        dfn[c] = pd.to_numeric(dfn[c], errors="coerce")

    meses_ordem = MESES_ORDEM + sorted(
        m for m in dfn["MES_REF"].unique() if m not in MESES_ORDEM
    )
    meses = [m for m in meses_ordem if m in dfn["MES_REF"].unique()]

    resumo = resumo_mensal(dfn)
    tendencia = [{"mes": r["MES_REF"], "km": _num(r["KM_TOTAL"]),
                  "veic": int(r["VEICULOS"])} for _, r in resumo.iterrows()]

    piv = dfn.pivot_table(index="TAG", columns="MES_ORDEM",
                          values="KM_MES", aggfunc="sum")
    wcols = ["W1", "W2", "W3", "W4", "W5"]

    por_mes = {}
    for m in meses:
        sub = dfn[dfn["MES_REF"] == m].copy()
        km_total = float(sub["KM_MES"].sum())
        ordn = int(sub["MES_ORDEM"].iloc[0])

        prev = resumo[resumo["MES_ORDEM"] == ordn - 1]
        delta_pct = None
        if not prev.empty and prev["KM_TOTAL"].iloc[0] > 0:
            delta_pct = (km_total - float(prev["KM_TOTAL"].iloc[0])) \
                / float(prev["KM_TOTAL"].iloc[0]) * 100

        veiculos = int(sub["TAG"].nunique())
        media = float(sub["KM_MES"].mean()) if len(sub) else 0.0
        em_manut = int((sub["STATUS"] == "Manutenção").sum())
        ativos = int((sub["STATUS"] == "Operacional").sum())
        pct_op = round(ativos / len(sub) * 100, 1) if len(sub) else 0.0

        top5 = sub.nlargest(5, "KM_MES")[["TAG", "KM_MES"]].values.tolist()
        top5 = [[str(t), _num(k)] for t, k in top5]
        tipo = [[str(n), _num(k)] for n, k in sub.groupby("TIPO")["KM_MES"].sum().items()]
        status = [[str(n), _num(k)] for n, k in sub.groupby("STATUS")["KM_MES"].sum().items()]

        semanal_tot = sub[wcols].sum()
        totais = {f"S{i}": _num(semanal_tot[f"W{i}"]) for i in range(1, 6)}
        top6 = sub.nlargest(6, "KM_MES")
        tags = top6["TAG"].tolist()
        series = {
            str(t): {f"S{i}": _num(row[f"W{i}"]) for i in range(1, 6)}
            for t, row in zip(tags, top6.to_dict("records"))
        }

        delta_por_tag = None
        if ordn - 1 in piv.columns:
            delta_por_tag = (piv[ordn].fillna(0) - piv[ordn - 1].fillna(0))

        detalhe = []
        for _, r in sub.sort_values("KM_MES", ascending=False).iterrows():
            delta = None
            if delta_por_tag is not None and r["TAG"] in delta_por_tag.index:
                delta = _num(delta_por_tag[r["TAG"]])
            detalhe.append([
                m, str(r["TAG"]), str(r["TIPO"]), str(r["MODELO"]),
                str(r["PLACA"]), _num(r["KM_INICIAL"]), _num(r["KM_FINAL"]),
                _num(r["KM_MES"]), delta, str(r["STATUS"]),
            ])

        sem_tabela = []
        for _, r in sub.sort_values("KM_MES", ascending=False).iterrows():
            sem_tabela.append([
                str(r["TAG"]), *[_num(r[c]) for c in wcols], _num(r["KM_MES"]),
            ])

        por_mes[m] = {
            "kmTotal": _num(km_total), "deltaPct": _num(delta_pct),
            "veiculos": veiculos, "media": _num(media),
            "emManut": em_manut, "ativos": ativos, "pctOp": pct_op,
            "linhas": len(sub),
            "top5": top5, "tipo": tipo, "status": status,
            "semanal": {"totais": totais, "tags": tags, "series": series},
            "detalhe": detalhe, "semTabela": sem_tabela,
        }

    # ---- consumo de CO2 da frota (2025→) ----------------------------------
    dcons = enriquecer_consumo(dfn)
    cons = consolidado_consumo(dcons)
    consumoTend = [{
        "mes": r["MES_REF"], "diesel": _num(r["CO2_DIESEL"]),
        "gasolina": _num(r["CO2_GASOLINA"]), "total": _num(r["CO2_TOTAL"]),
        "delta": _num(r["DELTA_PCT"]),
        "litrosD": _num(r["LITROS_DIESEL"]), "litrosG": _num(r["LITROS_GASOLINA"]),
        "km": _num(r["KM_TOTAL"]), "veic": int(r["VEICULOS"]),
    } for _, r in cons.iterrows()]

    por_veic = co2_por_veiculo(dcons)
    consumo_mes = {}
    for m in meses:
        sub = por_veic[por_veic["MES_REF"] == m].sort_values("CO2E", ascending=False)
        consumo_mes[m] = [[str(r["TAG"]), str(r["MODELO"]), str(r["COMBUSTIVEL"]),
                           _num(r["KM_MES"]), _num(r["LITROS"]), _num(r["CO2E"])]
                          for _, r in sub.iterrows()]

    return {
        "titulo": "Dashboard de Controle de Frota — Carajás",
        "meses": meses,
        "tendencia": tendencia,
        "historico": _num(dfn["KM_MES"].sum()),
        "por_mes": por_mes,
        "consumoTend": consumoTend,
        "consumo": consumo_mes,
    }


@functools.lru_cache()
def _plotly_js() -> str:
    """Extrai o bundle completo do plotly.js (sem o `<div>` e sem o render do
    gráfico "dummy" usado só para obter o script)."""
    parte = pio.to_html(go.Figure(), include_plotlyjs=True, full_html=False)
    blocos = re.findall(r"<script[^>]*>.*?</script>", parte, re.S)
    if not blocos:
        return ""
    return "".join(blocos[:-1])


DIR_TPL = Path(__file__).resolve().parent


def _ler_tpl(nome: str) -> str:
    """Le um arquivo de template (HTML/CSS/JS) do disco. O HTML final embute o
    conteudo desses arquivos para continuar autocontido (arquivo unico que abre
    sem Python/Streamlit). Mantenha template.html, template.css e template.js
    ao lado do gerar_html.py."""
    caminho = DIR_TPL / nome
    if not caminho.exists():
        raise FileNotFoundError(
            "Template '%s' nao encontrado — mantenha template.html, "
            "template.css e template.js ao lado do gerar_html.py." % nome
        )
    return caminho.read_text(encoding="utf-8")


def build_html(df: pd.DataFrame) -> str:
    dados = preparar(df)
    dados_json = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    paleta_json = json.dumps(PALETA, ensure_ascii=False)
    status_json = json.dumps(STATUS_CORES_JS, ensure_ascii=False)
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html = _ler_tpl("template.html")
    if "{{CSS}}" not in html or "{{JS}}" not in html:
        raise RuntimeError(
            "template.html perdeu os marcadores {{CSS}}/{{JS}}: algum "
            "autoformatador (ex. Prettier) pode ter reformatado o arquivo. "
            "Restaurar template.html (ou exclui-lo da formatacao automatica); "
            "os arquivos template.css e template.js continuam validos."
        )
    html = html.replace("{{CSS}}", _ler_tpl("template.css"))
    html = html.replace("{{JS}}", _ler_tpl("template.js"))

    trocas = {
        "{{TITULO}}": dados["titulo"],
        "{{PLOTLY_JS}}": _plotly_js(),
        "{{JSON}}": dados_json,
        "{{PALETA}}": paleta_json,
        "{{STATUS_COR}}": status_json,
        "{{GERADO}}": agora,
    }
    for chave, valor in trocas.items():
        html = html.replace(chave, valor)
    return html


def main() -> int:
    args = sys.argv[1:]
    caminho = Path(args[0]) if args else Path(__file__).parent / ARQ_PADRAO
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}")
        return 1
    df = processar_planilha(caminho)
    if df.empty:
        print("Nenhuma aba mensal válida encontrada na planilha.")
        return 1

    html = build_html(df)
    saida = caminho.parent / "dashboard_frota.html"
    saida.write_text(html, encoding="utf-8")
    print(f"Gerado: {saida} ({saida.stat().st_size/1024:.0f} KB)")
    print("Abra com dois cliques no navegador — não precisa de Python/Streamlit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())