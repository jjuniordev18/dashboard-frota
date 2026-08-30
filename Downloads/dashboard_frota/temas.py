"""
temas.py — Paleta de cores e status compartilhados entre o app Streamlit
(dashboard_frota.py) e o export estático (gerar_html.py).

Fonte única de verdade para as cores de *traço/gráfico* (plotly aceita hex
fixo, não CSS var). Os tokens de texto (--pos/--neg/...) continuam no
template.css por tema; aqui ficam apenas os hex de gráfico.
"""

PALETA = ["#2563eb", "#f59e0b", "#0ea5e9", "#10b981", "#8b5cf6",
          "#ec4899", "#f97316", "#14b8a6", "#84cc16", "#64748b"]

STATUS_CORES = {
    "Operacional": "#10b981",
    "Manutenção": "#ef4444",
    "Mobilização": "#f97316",
    "Pendente": "#94a3b8",
    "Lavador": "#0ea5e9",
    "Erro Dados": "#a855f7",
}