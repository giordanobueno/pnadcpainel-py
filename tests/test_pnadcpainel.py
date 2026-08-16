"""
Suíte de testes automatizados consolidada para o pacote pnadcpainel em Python.
"""

import os
import json
import hashlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from pnadcpainel import (
    gerar_painel_pnadc,
    criar_ids_datazoom,
    consolidar_base_habitacao,
    diagnosticar_painel,
    mensagem_diagnostico,
    downcast_pnadc,
    vars_tri_default,
    vars_visita_default,
    chaves_obrig_tri,
    chaves_obrig_visita,
    set_mock_provider,
    get_mock_provider,
)
from pnadcpainel.core import _resolve_ibge_filename, get_pnadc_internal


# ------------------------------------------------------------------------------
# 1. TESTES DE OTIMIZAÇÃO DE MEMÓRIA (DOWNCASTING)
# ------------------------------------------------------------------------------

def test_downcast_pnadc_converte_colunas_especificadas_para_int32():
    df = pd.DataFrame({
        "V2007": [1.0, 2.0, np.nan],
        "V2008": [15.0, 20.0, 99.0],
        "VD4020": [2500.5, 3000.0, np.nan], # Rendimento (double, não sofre downcast)
        "UPA": ["110000016", "110000016", "110000016"] # Chave (string)
    })
    res = downcast_pnadc(df)

    assert str(res["V2007"].dtype) == "Int32"
    assert str(res["V2008"].dtype) == "Int32"
    assert str(res["VD4020"].dtype) in ("float64", "Float64")
    assert str(res["UPA"].dtype) == "object"
    assert res["V2007"].iloc[0] == 1
    assert pd.isna(res["V2007"].iloc[2])


# ------------------------------------------------------------------------------
# 2. TESTES DE IDENTIFICAÇÃO DATA ZOOM
# ------------------------------------------------------------------------------

def test_nan_em_data_de_nascimento_e_excluido():
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "V2008": [15, np.nan],
        "V20081": [5, 8],
        "V20082": [1990, 1992],
        "V2007": [1, 2],
        "UF": ["11", "11"]
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 1
    assert res["id_dom"].iloc[0] == "1100000160110"

def test_99_e_9999_sao_excluidos():
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016", "110000016"],
        "V1008": ["01", "01", "01"],
        "V1014": ["10", "10", "10"],
        "V2008": [99, 15, 15],
        "V20081": [5, 99, 5],
        "V20082": [1990, 1990, 9999],
        "V2007": [1, 2, 1],
        "UF": ["11", "11", "11"]
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 0

def test_zero_a_esquerda_de_v1008_e_v2008_e_preservado():
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": [1, "01"],
        "V1014": [10, 10],
        "V2008": [5, 12],
        "V20081": [8, 11],
        "V20082": [1995, 1988],
        "V2007": [1, 2],
        "UF": [11, 11]
    })
    res = criar_ids_datazoom(df)
    assert res["id_dom"].iloc[0] == "1100000160110"
    assert res["id_dom"].iloc[1] == "1100000160110"
    assert res["id_ind"].iloc[0] == "110000016011005081995111"
    assert res["id_ind"].iloc[1] == "110000016011012111988211"

def test_strings_numericas_com_sufixo_float_sao_normalizadas():
    df = pd.DataFrame({
        "UPA": ["110000016.0"],
        "V1008": ["01"],
        "V1014": ["10.0"],
        "V2008": [15],
        "V20081": [5],
        "V20082": [1990],
        "V2007": ["1.0"],
        "UF": ["11.0"]
    })
    res = criar_ids_datazoom(df)
    assert res["id_dom"].iloc[0] == "1100000160110"
    assert res["id_ind"].iloc[0] == "110000016011015051990111"


# ------------------------------------------------------------------------------
# 3. TESTES DE DIAGNÓSTICO E MENSAGENS BRASILEIRAS
# ------------------------------------------------------------------------------

def test_diagnosticar_painel_calcula_metricas_corretamente():
    df_test = pd.DataFrame({
        "id_dom": ["D1", "D2", "D3", "D4"],
        "VD5002": [1000.0, 2000.0, np.nan, np.nan],
        "S01013": [1.0, np.nan, 1.0, np.nan]
    })
    diag = diagnosticar_painel(df_test, colunas=["VD5002", "S01013"])
    assert len(diag) == 2
    row_vd5002 = diag[diag["variavel"] == "VD5002"].iloc[0]
    assert row_vd5002["com_dado"] == 2
    assert row_vd5002["sem_dado"] == 2
    assert row_vd5002["pct_disponivel"] == 50.0

def test_mensagem_diagnostico_formatacao_brasileira_completa():
    df_antes = pd.DataFrame({"VD5002": [1.0] * 1000000})
    df_depois = pd.DataFrame({"VD5002": [1.0] * 750000})
    diag = diagnosticar_painel(df_antes, colunas=["VD5002"])

    msg = mensagem_diagnostico(diag, df_antes, df_depois, ano=2023)
    assert "1.000.000" in msg
    assert "750.000" in msg
    assert "250.000" in msg
    assert "25,00%" in msg


# ------------------------------------------------------------------------------
# 4. TESTES DE VALIDAÇÃO DE ARGUMENTOS E REGRAS DE NEGÓCIO
# ------------------------------------------------------------------------------

def test_gerar_painel_pnadc_valida_o_ano_de_entrada_rigorosamente():
    with pytest.raises(TypeError):
        gerar_painel_pnadc()
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=None)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=np.nan)
    with pytest.raises(ValueError, match="Ano invalido"):
        gerar_painel_pnadc(ano=2000)
    with pytest.raises(ValueError, match="Ano invalido"):
        gerar_painel_pnadc(ano=2030)

def test_consolidar_base_habitacao_na_aggregation_first_non_na():
    mock_data = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "Ano": [2023, 2023],
        "UF": ["11", "11"],
        "S01013": [np.nan, 1.0],
        "VD5002": [100.0, np.nan],
    })

    def mock_provider(**kwargs):
        return mock_data.copy()

    set_mock_provider(mock_provider)
    try:
        res = consolidar_base_habitacao(ano=2023, vars_visita=["S01013", "VD5002"], verbose=False)
        assert len(res) == 1
        assert res["S01013"].iloc[0] == 1.0
        assert res["VD5002"].iloc[0] == 100.0
    finally:
        set_mock_provider(None)


# ------------------------------------------------------------------------------
# 5. TESTES DE ROTA HTTP/FTP DO IBGE E VARS = TODAS
# ------------------------------------------------------------------------------

def test_rota_trimestral_2023():
    html_mock = '<html><a href="PNADC_012023_20250815.zip">PNADC_012023_20250815.zip</a></html>'
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html_mock
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = _resolve_ibge_filename("https://ftp.ibge.gov.br/test", r"PNADC_012023(?:_\d{8})?\.zip")
        assert res == "PNADC_012023_20250815.zip"

def test_download_vars_none_ou_todas_retorna_todas_as_colunas():
    todas_colunas = list(vars_tri_default) + ["EXTRA_VAR1", "EXTRA_VAR2"]
    df_todas = pd.DataFrame({col: ["1"] for col in todas_colunas})

    def mock_provider(**kwargs):
        req_vars = kwargs.get("vars")
        if req_vars is None:
            return df_todas.copy()
        cols = [c for c in req_vars if c in df_todas.columns]
        return df_todas[cols].copy()

    set_mock_provider(mock_provider)
    try:
        res_none = get_pnadc_internal(year=2023, quarter=1, vars=None, verbose=False)
        assert len(res_none.columns) > len(vars_tri_default)
        assert "EXTRA_VAR1" in res_none.columns
    finally:
        set_mock_provider(None)


# ------------------------------------------------------------------------------
# 6. TESTE CROSS-LANGUAGE PARITY E SERIALIZAÇÃO E2E
# ------------------------------------------------------------------------------

def test_cross_language_e2e_parity_ids_e_diagnostico():
    df_input = pd.DataFrame({
        "UPA": ["110000016", "110000016", "110000016"],
        "V1008": [1, "01", "10"],
        "V1014": [10, 10, 10],
        "V2008": [5, 12, 25],
        "V20081": [8, 11, 1],
        "V20082": [1995, 1988, 2000],
        "V2007": [1, 2, 1],
        "UF": [11, 11, 11]
    })

    res_ids = criar_ids_datazoom(df_input)
    assert res_ids["id_dom"].iloc[0] == "1100000160110"
    assert res_ids["id_ind"].iloc[0] == "110000016011005081995111"
    assert res_ids["id_ind"].iloc[1] == "110000016011012111988211"
