"""
Testes de casos de borda para geração de IDs Data Zoom.
"""

import pytest
import pandas as pd
import numpy as np
from pnadcpainel.identificacao import criar_ids_datazoom


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


def test_zero_a_esquerda_de_v1008_e_preservado():
    df = pd.DataFrame({
        "UPA": ["110000016"],
        "V1008": ["01"],
        "V1014": ["10"],
        "V2008": [15],
        "V20081": [5],
        "V20082": [1990],
        "V2007": [1],
        "UF": ["11"]
    })
    res = criar_ids_datazoom(df)
    assert res["id_dom"].iloc[0] == "1100000160110"
    assert "01" in res["id_dom"].iloc[0]


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


def test_na_em_sexo_e_excluido():
    df = pd.DataFrame({
        "UPA": ["110000016"],
        "V1008": ["01"],
        "V1014": ["10"],
        "V2008": [15],
        "V20081": [5],
        "V20082": [1990],
        "V2007": [np.nan],
        "UF": ["11"]
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 0


def test_saida_vazia_mantem_schema_de_ids():
    df = pd.DataFrame({
        "UPA": ["110000016"],
        "V1008": ["01"],
        "V1014": ["10"],
        "V2008": [99],
        "V20081": [5],
        "V20082": [1990],
        "V2007": [1],
        "UF": ["11"]
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 0
    assert "id_dom" in res.columns
    assert "id_ind" in res.columns
    assert "V2008" not in res.columns
