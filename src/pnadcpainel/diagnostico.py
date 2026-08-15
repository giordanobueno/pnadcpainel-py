"""
Diagnóstico de preenchimento de variáveis e perda de dados por balanceamento.
"""

import pandas as pd
import numpy as np
from typing import List, Optional


def diagnosticar_painel(
    painel: pd.DataFrame,
    colunas: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Calcula métricas de disponibilidade (linhas preenchidas vs. ausentes) para cada
    coluna do painel gerado.

    Parameters
    ----------
    painel : pd.DataFrame
        DataFrame do painel.
    colunas : List[str], optional
        Vetor de nomes de colunas a diagnosticar. Se None, diagnostica todas as colunas.

    Returns
    -------
    pd.DataFrame
        DataFrame contendo as colunas:
        'variavel', 'total_linhas', 'com_dado', 'sem_dado', 'pct_disponivel'.
    """
    if colunas is None:
        cols = list(painel.columns)
    else:
        cols = [c for c in colunas if c in painel.columns]

    if not cols:
        return pd.DataFrame({
            "variavel": pd.Series(dtype="str"),
            "total_linhas": pd.Series(dtype="int64"),
            "com_dado": pd.Series(dtype="int64"),
            "sem_dado": pd.Series(dtype="int64"),
            "pct_disponivel": pd.Series(dtype="float64")
        })

    n_total = len(painel)
    if n_total == 0:
        res = []
        for col in cols:
            res.append({
                "variavel": col,
                "total_linhas": 0,
                "com_dado": 0,
                "sem_dado": 0,
                "pct_disponivel": 0.0
            })
        return pd.DataFrame(res)

    registros = []
    for col in cols:
        s = painel[col]
        com_dado = int(s.notna().sum())
        sem_dado = int(s.isna().sum())
        pct = round((com_dado / n_total) * 100.0, 2) if n_total > 0 else 0.0
        registros.append({
            "variavel": col,
            "total_linhas": n_total,
            "com_dado": com_dado,
            "sem_dado": sem_dado,
            "pct_disponivel": pct
        })

    diag_df = pd.DataFrame(registros)
    diag_df = diag_df.sort_values(by="pct_disponivel", ascending=True).reset_index(drop=True)
    return diag_df


def mensagem_diagnostico(
    diagnostico: pd.DataFrame,
    painel_antes: Optional[pd.DataFrame],
    painel_depois: Optional[pd.DataFrame],
    ano: int
) -> str:
    """
    Emite uma mensagem estruturada no console descrevendo a perda de dados resultante
    do cruzamento e balanceamento temporal entre a base trimestral e a Visita 1.

    Parameters
    ----------
    diagnostico : pd.DataFrame
        DataFrame gerado por diagnosticar_painel.
    painel_antes : pd.DataFrame, optional
        DataFrame do painel antes do balanceamento.
    painel_depois : pd.DataFrame, optional
        DataFrame do painel após o balanceamento.
    ano : int
        Ano de referência.

    Returns
    -------
    str
        A string formatada da mensagem.
    """
    n_antes = len(painel_antes) if painel_antes is not None else 0
    n_depois = len(painel_depois) if painel_depois is not None else 0
    perda_abs = n_antes - n_depois
    perda_pct = round((perda_abs / n_antes) * 100.0, 2) if n_antes > 0 else 0.0

    if diagnostico is not None and not diagnostico.empty:
        var_critica_row = diagnostico.iloc[0]
        var_critica = str(var_critica_row["variavel"])
        pct_ausente_critica = round(100.0 - float(var_critica_row["pct_disponivel"]), 2)
    else:
        var_critica = "Nenhuma"
        pct_ausente_critica = 0.0

    msg = (
        f"\n>>> Diagnóstico do painel PNADc - ano {ano}\n"
        f"Linhas antes do cruzamento (base trimestral): {n_antes:,}\n"
        f"Linhas após cruzamento + balanceamento:       {n_depois:,}\n"
        f"Perda total: {perda_abs:,} linhas ({perda_pct:.2f}%)\n"
        f"Variável com maior perda antes do balanceamento: {var_critica} - {pct_ausente_critica:.2f}% de dados ausentes\n"
        f"Motivo: descompasso temporal entre a base trimestral (Ano/Trimestre corrente) "
        f"e a base de Visita 1 (entrevista específica, ano corrente + ano anterior).\n"
    )

    print(msg)
    return msg
