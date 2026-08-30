# Dashboard de Frota — Carajás

Painel mensal de quilometragem, status operacional e consumo de CO2 (ESG) da
frota, gerado a partir do workbook `PA - CONTROLE DE KM (version 1).xlsx`.

O produto principal é o **HTML estático autocontido** (`dashboard_frota.html`),
que abre em qualquer navegador sem Python/Streamlit: gráficos plotly, seletor
de mês e tema claro/escuro embutidos. Também existe o app **Streamlit**
(`dashboard_frota.py`) e o **workbook corrigido** (`... (CORRIGIDO).xlsx`) com
os erros da planilha reparados pelo ETL.

## O que cada arquivo faz

| Arquivo | Papel |
|---|---|
| `frota_utils.py` | ETL: lê a planilha, corrige os erros (ACKUP./AGOSTO, `TN78`→`TN 78`, `HILLUX`, etc.), calcula `KM_MES` (última leitura válida do hodômetro − KM INICIAL), estima CO2 (km → litros → kgCO2e, fatores MCTI) |
| `dashboard_frota.py` | App Streamlit (KPIs, gráficos, consumo de CO2, comparativo mensal, prints PNG/ZIP) |
| `gerar_html.py` | Gera o `dashboard_frota.html` estático a partir dos templates (plotly.js + dados embutidos) |
| `corrigir_planilha.py` | CLI que gera `PA - CONTROLE DE KM (version 1) (CORRIGIDO).xlsx` a partir da original |
| `test_frota_utils.py` | Regressão do ETL (roda sem pytest) |
| `Dashboard_consumo_co2.xlsx` | Workbook de exemplo usado nos testes (fatores de emissão MCTI) — não é exibido no app |
| `servir.py` | Serve o `dashboard_frota.html` em servidor HTTP local |
| `gerar_apresentacao.py` | Gera `Apresentacao_Julho_Agosto.xlsx` (planilha de apresentação JULHO×AGOSTO com gráficos e textos prontos) |
| `template.html` / `template.css` / `template.js` | Fonte do HTML estático, dividida em 3 templates (não formatar!) |
| `CONTEXT.md` | Linguagem do domínio e decisões do projeto (TAG, hodômetro, KM_MES, CO2...) |

## Comandos

```bash
python test_frota_utils.py                 # regressão do ETL (roda sozinho)
python gerar_html.py [arquivo.xlsx]         # gera dashboard_frota.html
python corrigir_planilha.py [arquivo.xlsx]  # gera ... (CORRIGIDO).xlsx
python gerar_apresentacao.py                # gera Apresentacao_Julho_Agosto.xlsx
python servir.py [arquivo.xlsx] [porta]     # serve o dashboard_frota.html em http://localhost:8723
streamlit run dashboard_frota.py            # app interativo (opcional)
```

## Deploy

O `dashboard_frota.html` é autocontido e deploia em qualquer hospedagem
estática (GitHub Pages, Netlify, Vercel, etc.) — publicando apenas esse
arquivo, sem necessidade de servidor Python.

## Repositório

Este repo contém o código-fonte e o HTML já gerado. As planilhas com dados
reais da frota (`PA - CONTROLE DE KM (version 1).xlsx`, `(CORRIGIDO).xlsx` e
`Dashboard_consumo_co2.xlsx`) **não** são versionadas por serem dados sensíveis;
mantenha-as na pasta local para rodar os scripts.

## Skills de agente

O projeto trabalha melhor com o opencode e o pack de skills local
(`agent-skills/` na pasta do projeto, fora do repo), registrado via
`opencode.json` (`skills.paths`). Reinicie o opencode após mudar o
`opencode.json` para as skills serem carregadas. As skills mais usadas aqui:

- `frontend-ui-engineering` — UI/HTML (acessibilidade, responsivo, hierarquia)
- `browser-testing-with-devtools` — verificação real no navegador (DOM, console, Lighthouse)
- `performance-optimization` — o `dashboard_frota.html` tem ~4,3 MB (plotly.js embutido)
- `test-driven-development` / `code-review-and-quality` — mudanças no ETL/HTML

## Notas de qualidade (auditoria recente)

A pedido do projeto, o `dashboard_frota.html` foi auditado com Chrome DevTools
MCP + Lighthouse: **best practices 100**, **acessibilidade 100** (antes 93) e
**SEO 80** (antes 60, faltava `meta description`). As correções aplicadas:

- `meta name="description"` no `<head>`
- landmark `<main>` no lugar do `<div class="wrap">`
- hierarquia de títulos corrigida (H1 → H2 "Quilometragem da frota" → H3...)
- tabelas largas em `<div class="tab-scroll">` (scroll horizontal no mobile —
  antes a página estourava 795px em telas de 320px)

Fazendo edições no HTML: mexa nos templates em `template.html`/`template.css`/
`template.js` e rode `python gerar_html.py` para regenerar o
`dashboard_frota.html`. Estes arquivos nunca devem ser reformatados por
autoformatadores (veja `.prettierignore`).