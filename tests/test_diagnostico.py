"""
Testes unitários para diagnosticar_painel e mensagem_diagnostico (Port 1:1 de test-diagnostico.R).
"""

import pytest
import pandas as pd
import numpy as np
from pnadcpainel.diagnostico import diagnosticar_painel, mensagem_diagnostico


def test_diagnosticar_painel_calcula_metricas_corretamente():
    df_test = pd.DataFrame({
        "id_dom": ["D1", "D2", "D3", "D4"],
        "VD5002": [1000.0, 2000.0, np.nan, np.nan],
        "S01013": [1.0, np.nan, 1.0, np.nan]
    })

    diag = diagnosticar_painel(df_test, colunas=["VD5002", "S01013"])

    assert isinstance(diag, pd.DataFrame)
    assert list(diag.columns) == ["variavel", "total_linhas", "com_dado", "sem_dado", "pct_disponivel"]
    assert len(diag) == 2

    row_vd5002 = diag[diag["variavel"] == "VD5002"].iloc[0]
    assert row_vd5002["com_dado"] == 2
    assert row_vd5002["sem_dado"] == 2
    assert row_vd5002["pct_disponivel"] == 50.0


def test_mensagem_diagnostico_produz_formato_correto():
    df_test = pd.DataFrame({
        "VD5002": [1000.0, 2000.0, np.nan, np.nan],
        "S01013": [1.0, np.nan, 1.0, np.nan]
    })
    diag = diagnosticar_painel(df_test, colunas=["VD5002", "S01013"])
    df_depois = df_test[df_test["VD5002"].notna() & df_test["S01013"].notna()]

    msg = mensagem_diagnostico(diag, df_test, df_depois, ano=2023)
    assert "Diagnóstico do painel PNADc - ano 2023" in msg
    assert "Linhas antes do cruzamento" in msg
    assert "descompasso temporal" in msg


def test_mensagem_diagnostico_usa_ponto_separador_milhar_brasileiro():
    # DataFrame com mais de 1000 linhas para validar o separador de milhar brasileiro (ponto)
    df_antes = pd.DataFrame({"VD5002": [1000.0] * 1234})
    df_depois = pd.DataFrame({"VD5002": [1000.0] * 1000})
    diag = diagnosticar_painel(df_antes, colunas=["VD5002"])

    msg = mensagem_diagnostico(diag, df_antes, df_depois, ano=2023)
    assert "1.234" in msg
    assert "1,234" not in msg

