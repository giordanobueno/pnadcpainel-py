"""
Testes de paridade de diagnóstico de preenchimento.
"""

import pytest
import pandas as pd
import numpy as np
from pnadcpainel.diagnostico import diagnosticar_painel, mensagem_diagnostico


def test_colunas_heterogeneas_nao_quebram_diagnostico():
    df = pd.DataFrame({
        "col_int": pd.Series([1, 2, np.nan], dtype="Int32"),
        "col_str": ["A", None, "C"],
        "col_float": [1.5, 2.5, np.nan],
        "col_bool": [True, False, None]
    })
    diag = diagnosticar_painel(df)
    assert len(diag) == 4
    assert set(diag["variavel"]) == {"col_int", "col_str", "col_float", "col_bool"}
    assert all(diag["total_linhas"] == 3)


def test_nenhuma_coluna_valida_lanca_mesmo_erro_do_r():
    df = pd.DataFrame({"A": [1, 2]})
    with pytest.raises(ValueError, match="Nenhuma coluna valida fornecida para diagnostico"):
        diagnosticar_painel(df, colunas=["INEXISTENTE"])


def test_empates_sao_ordenados_por_variavel():
    df = pd.DataFrame({
        "ZZ_var": [1, np.nan],
        "AA_var": [1, np.nan],
        "MM_var": [1, np.nan]
    })
    diag = diagnosticar_painel(df)
    assert diag["pct_disponivel"].tolist() == [50.0, 50.0, 50.0]
    # Com o desempate determinístico por variavel asc: AA_var, MM_var, ZZ_var
    assert diag["variavel"].tolist() == ["AA_var", "MM_var", "ZZ_var"]


def test_percentual_usa_arredondamento_de_duas_casas():
    df = pd.DataFrame({
        "col1": [1, 1, np.nan]
    })
    diag = diagnosticar_painel(df)
    assert diag["pct_disponivel"].iloc[0] == 66.67
