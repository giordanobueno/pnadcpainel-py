"""
Testes unitários para geração dos identificadores longitudinais Data Zoom (Port 1:1 de test-datazoom_ids.R).
"""

import pytest
import pandas as pd
import numpy as np
from pnadcpainel.identificacao import criar_ids_datazoom


def test_criar_ids_datazoom_gera_id_dom_e_id_ind_corretamente():
    df_dummy = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "V2008": [22, 4],
        "V20081": [8, 4],
        "V20082": [1992, 1993],
        "V2007": [1, 2],
        "UF": ["11", "11"]
    })

    res = criar_ids_datazoom(df_dummy)

    assert "id_dom" in res.columns
    assert "id_ind" in res.columns
    assert res["id_dom"].iloc[0] == "1100000160110"
    assert res["id_ind"].iloc[0] == "110000016011022081992111"
    assert "V2008" not in res.columns


def test_criar_ids_datazoom_valida_colunas_ausentes():
    df_invalido = pd.DataFrame({"UPA": ["110000016"]})
    with pytest.raises(ValueError, match="Colunas obrigatorias ausentes"):
        criar_ids_datazoom(df_invalido)


def test_criar_ids_datazoom_filtra_dados_invalidos_de_nascimento_e_sexo_na():
    df_invalido = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "V2008": [99, 4],
        "V20081": [8, 99],
        "V20082": [1992, 1993],
        "V2007": [1, np.nan],
        "UF": ["11", "11"]
    })

    res = criar_ids_datazoom(df_invalido)
    assert len(res) == 0
