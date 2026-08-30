"""
corrigir_planilha.py — Corrige a planilha 'PA - CONTROLE DE KM (version 1).xlsx'.

O que faz:
  - Conserta a coluna ACUM. e as semanas S1..S5 do bloco ACOMPANHAMENTO de TODAS
    as abas mensais (OUTUBRO 2025 ... AGOSTO).
  - Remove as fórmulas quebradas (#REF!, referência errada =K10-J9, somas com
    marcadores negativos do hodômetro) e grava valores numéricos corretos,
    calculados a partir das leituras do hodômetro do bloco de cadastro.
  - Salva uma cópia com o sufixo "(CORRIGIDO)" (o arquivo original é preservado).

Uso:
    python corrigir_planilha.py [caminho_do_arquivo.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

from frota_utils import corrigir_workbook, timestamp_humano

DEFAULT_ARQ = "PA - CONTROLE DE KM (version 1).xlsx"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    caminho = Path(args[0]) if args else Path(__file__).parent / DEFAULT_ARQ
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}")
        sys.exit(1)

    original = caminho.read_bytes()
    corrigido, abas = corrigir_workbook(original)

    saida = caminho.with_name(caminho.stem + " (CORRIGIDO)" + caminho.suffix)
    saida.write_bytes(corrigido)

    print(f"Abas corrigidas ({len(abas)}): {', '.join(abas)}")
    print(f"Planilha corrigida salva em: {saida.name}")
    print(f"Gerado por frota_utils em {timestamp_humano()}.")


if __name__ == "__main__":
    main()