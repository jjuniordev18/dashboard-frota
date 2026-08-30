from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from frota_utils import (chave_frota, co2_por_veiculo, consolidado_consumo,
                         corrigir_workbook, enriquecer_consumo, processar_co2,
                         processar_planilha, resumo_mensal, safe_num)
from gerar_html import build_html, preparar

ARQUIVO = Path(__file__).parent / "PA - CONTROLE DE KM (version 1).xlsx"
ARQUIVO_CO2 = Path(__file__).parent / "Dashboard_consumo_co2.xlsx"

fails = []


def ok(nome, cond, detalhe=""):
    if cond:
        print(f"  OK   {nome}")
    else:
        fails.append(nome)
        print(f"  FAIL {nome} {detalhe}")


def main() -> int:
    if not ARQUIVO.exists():
        print(f"FALTANDO planilha: {ARQUIVO}")
        return 1

    print("[1] ETL - todas as abas mensais")
    df = processar_planilha(ARQUIVO)
    ok("planilha lida e tabela gerada", not df.empty)

    rep = df[["TAG", "MES_REF"]].duplicated().sum()
    ok("sem duplicados (TAG x mes)", rep == 0, f"-> {rep} duplicados")

    ok("colunas esperadas presentes",
       {"MES_REF", "TAG", "TIPO", "KM_INICIAL", "KM_FINAL", "KM_MES",
        "STATUS", "W1", "W2", "W3", "W4", "W5"} <= set(df.columns))

    ok("KM_MES sem negativos", (df["KM_MES"].fillna(0) >= 0).all())

    ag = df[df["MES_REF"] == "AGOSTO"]
    ok("AGOSTO com registros", not ag.empty, "-> bug original: AGOSTO zerado")
    total_agosto = ag["KM_MES"].fillna(0).sum()
    ok("AGOSTO total > 0 (12.727 esperado)", total_agosto > 0, f"-> {total_agosto:,.0f} km")

    resumo = resumo_mensal(df)
    ok("resumo_mensal tem 10 meses", len(resumo) == 10, f"-> {len(resumo)}")

    print("[2] Gerar planilha corrigida a partir da original")
    corrigido_bytes, abas = corrigir_workbook(ARQUIVO.read_bytes())
    ok("workbook corrigido gerado", len(corrigido_bytes) > 0)
    ok("abas corrigidas reportadas", len(abas) >= 10, f"-> {len(abas)}")

    print("[3] Reprocessar a planilha corrigida (dados preservados)")
    df2 = processar_planilha(__import__("io").BytesIO(corrigido_bytes))
    total_agosto2 = df2[df2["MES_REF"] == "AGOSTO"]["KM_MES"].fillna(0).sum()
    ok("AGOSTO preservado apos correcao",
       abs(total_agosto2 - total_agosto) < 1,
       f"-> antes {total_agosto:,.0f} / depois {total_agosto2:,.0f}")

    print("[4] CO2 / ESG - Dashboard_consumo_co2.xlsx")
    if not ARQUIVO_CO2.exists():
        ok("planilha de CO2 presente", False, "-> arquivo nao encontrado")
    else:
        co2 = processar_co2(ARQUIVO_CO2, so_frota=False)
        ok("registros lidos", not co2.empty, f"-> {len(co2)} linhas")
        ok("colunas CO2 esperadas",
           {"MES_REF", "FONTE", "ATIVIDADE", "QUANTIDADE", "UNIDADE", "FATOR",
            "CO2E", "USO", "MES_CHAVE"} <= set(co2.columns))
        tot = co2["CO2E"].sum()
        ok("emissoes recalculadas pelos fatores (1847 esperado)",
           abs(tot - 1847) < 1, f"-> {tot:,.1f} kgCO2e")
        diesel = co2[co2["FONTE_CURTA"] == "Diesel"]["CO2E"].iloc[0]
        ok("Diesel 500L x 2.68 = 1340", abs(diesel - 1340) < 1, f"-> {diesel}")
        gas = co2[co2["FONTE_CURTA"] == "Gasolina"]["CO2E"].iloc[0]
        ok("Gasolina 200L x 2.16 = 432", abs(gas - 432) < 1, f"-> {gas}")
        energia = co2[co2["FONTE_CURTA"] == "Energia"]["CO2E"].iloc[0]
        ok("Energia 1500kWh x 0.05 = 75", abs(energia - 75) < 1, f"-> {energia}")
        fatores = co2[["FONTE", "FATOR"]].drop_duplicates().sort_values("FATOR")
        ok("fatores 2.68/2.16/0.05 presente",
           {2.68, 2.16, 0.05} <= set(fatores["FATOR"].round(2)))

        frota = processar_co2(ARQUIVO_CO2)  # padrao: so veiculos (USO == Frota)
        ok("apenas veiculos (sem geradores)", len(frota) == 1,
           f"-> {len(frota)} registros")
        ok("fonte do veiculo = Gasolina",
           set(frota["FONTE_CURTA"]) == {"Gasolina"},
           f"-> {sorted(frota['FONTE_CURTA'].tolist())}")
        ok("CO2 dos veiculos = 432", abs(frota["CO2E"].sum() - 432) < 1,
           f"-> {frota['CO2E'].sum():.0f}")
        ok("todos os registros sao de frota",
           (frota["USO"] == "Frota").all())

        ok("chave de mes com ano (OUTUBRO 2023)",
           set(frota["MES_CHAVE"]) == {"OUTUBRO 2023"})
        ok("chave_frota alinhada (AGOSTO -> AGOSTO 2026)",
           chave_frota("AGOSTO", 2026) == "AGOSTO 2026")
        ok("chave_frota mantem mes com ano",
           chave_frota("OUTUBRO 2023") == "OUTUBRO 2023")
        ok("chave_frota usa ano corrente por padrao",
           chave_frota("AGOSTO") == f"AGOSTO {datetime.now().year}")

    print("[5] Consumo de CO2 da frota (km real -> litros -> kgCO2e)")
    cdf = enriquecer_consumo(df)
    ok("colunas de consumo presentes",
       {"COMBUSTIVEL", "KM_POR_L", "LITROS", "FATOR_CO2", "CO2E"}
       <= set(cdf.columns))
    comb = cdf.groupby("COMBUSTIVEL")["CO2E"].sum()
    ok("Leve (TN 01) roda a Gasolina",
       set(cdf.loc[cdf["TIPO"] == "Leve", "COMBUSTIVEL"]) == {"Gasolina"},
       f"-> {sorted(cdf.loc[cdf['TIPO']=='Leve','COMBUSTIVEL'].unique().tolist())}")
    ok("Caminhonetes rodam a Diesel",
       set(cdf.loc[cdf["TIPO"] == "Caminhonete", "COMBUSTIVEL"]) == {"Diesel"})
    N = len(df)
    ok(f"todas as linhas classificadas ({N})",
       cdf["COMBUSTIVEL"].notna().sum() == N)

    cons = consolidado_consumo(cdf)
    ok("consolidado tem 10 meses", len(cons) == 10, f"-> {len(cons)}")
    ok("total mensal bate com a soma por linha",
       abs(cons["CO2_TOTAL"].sum() - cdf["CO2E"].sum()) < 1)
    ag = cons[cons["MES_REF"] == "AGOSTO"].iloc[0]
    ok("AGOSTO com Diesel e Gasolina", ag["CO2_DIESEL"] > 0
       and ag["CO2_GASOLINA"] > 0,
       f"-> diesel {ag['CO2_DIESEL']:.0f} / gasolina {ag['CO2_GASOLINA']:.0f}")
    ok("AGOSTO CO2 total ~3389 kg", abs(ag["CO2_TOTAL"] - 3389) < 10,
       f"-> {ag['CO2_TOTAL']:.1f}")
    ok("primeiro mes sem variacao (OUTUBRO 2025)",
       pd.isna(cons.iloc[0]["DELTA_PCT"]))
    j = cons[cons["MES_REF"] == "JULHO"].iloc[0]
    ok("JULHO subiu vs mes anterior (~+113%)",
       j["DELTA_PCT"] and j["DELTA_PCT"] > 90,
       f"-> {j['DELTA_PCT']:.1f}%")

    por = co2_por_veiculo(cdf)
    ok("por veiculo/mes agrupado", len(por) >= 90, f"-> {len(por)}")
    ag_veic = por[(por["MES_REF"] == "AGOSTO") & (por["TAG"] == "TN 01")]
    ok("TN 01 (Pulse) agostino ~367 kg",
       abs(ag_veic["CO2E"].iloc[0] - 367) < 5,
       f"-> {ag_veic['CO2E'].iloc[0]:.1f}")

    print("[6] safe_num (decimal/milhar pt-BR e ingles)")
    ok("inteiro simples", safe_num("1234") == 1234)
    ok("pt-BR milhar ponto (12.727)", safe_num("12.727") == 12727)
    ok("pt-BR decimal virgula (1,5)", abs(safe_num("1,5") - 1.5) < 1e-9)
    ok("pt-BR milhar+decimal (12.727,50)",
       abs(safe_num("12.727,50") - 12727.5) < 1e-9)
    ok("ingles decimal (1.5)", abs(safe_num("1.5") - 1.5) < 1e-9)
    ok("ingles decimal 2 casas (3.14)", abs(safe_num("3.14") - 3.14) < 1e-9)
    ok("milhar multiplo (1.234.567)", safe_num("1.234.567") == 1234567)
    ok("texto invalido vira NaN", pd.isna(safe_num("Manutenção")))
    ok("vazio vira NaN", pd.isna(safe_num("")))
    ok("None vira NaN", pd.isna(safe_num(None)))

    print("[7] Export estatico (preparar/build_html)")
    dados = preparar(df)
    ok("JSON tem meses e tendencia",
       {"meses", "tendencia", "por_mes", "consumoTend", "consumo"} <=
       set(dados.keys()))
    ok("por_mes cobre JULHO/AGOSTO",
       {"JULHO", "AGOSTO"} <= set(dados["por_mes"].keys()))
    ok("consumoTend deriva diesel+gasolina", all(
       abs(c["total"] - (c["diesel"] + c["gasolina"])) < 0.01
       for c in dados["consumoTend"]))
    ok("por_mes AGOSTO nao zera km",
       (dados["por_mes"]["AGOSTO"]["kmTotal"] or 0) > 0)
    html = build_html(df)
    ok("HTML gerado", len(html) > 10000, f"-> {len(html)/1024:.0f} KB")
    ok("tokens do template substituidos",
       "{{TITULO}}" not in html and "{{JSON}}" not in html
       and "{{PLOTLY_JS}}" not in html)
    ok("plotly.js embutido no body",
       html.count("<script") >= 2 and "PLOTLYENV" in html
       and html.count("plotly-logomark") == 1)

    print()
    if fails:
        print(f"FALHAS: {len(fails)}")
        for f in fails:
            print(" -", f)
        return 1
    print("TUDO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())