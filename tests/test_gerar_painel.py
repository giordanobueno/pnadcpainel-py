"""
Testes de validação de argumentos e comportamento de gerar_painel_pnadc (Port 1:1 de test-gerar_painel_pnadc.R).
"""

import pytest
import pandas as pd
import numpy as np
from pnadcpainel.core import gerar_painel_pnadc
from pnadcpainel.defaults import chaves_obrig_tri, chaves_obrig_visita


def test_gerar_painel_pnadc_valida_o_ano_de_entrada_rigorosamente():
    with pytest.raises(TypeError):
        gerar_painel_pnadc()
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=None)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=np.nan)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=np.inf)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=-np.inf)
    with pytest.raises(ValueError, match="Ano invalido"):
        gerar_painel_pnadc(ano=2000)
    with pytest.raises(ValueError, match="Ano invalido"):
        gerar_painel_pnadc(ano=2030)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano="invalido")
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano=[2022, 2023])
    with pytest.raises(ValueError, match="deve ser um numero inteiro valido"):
        gerar_painel_pnadc(ano=2023.5)


def test_consolidar_base_habitacao_na_aggregation_first_non_na():
    from pnadcpainel.habitacao import consolidar_base_habitacao
    from pnadcpainel._ibge_source import set_mock_provider

    mock_data = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "Ano": [2023, 2023],
        "UF": ["11", "11"],
        "S01013": [np.nan, 1.0],      # First row NA, second row 1.0
        "VD5002": [100.0, np.nan],    # First row 100.0, second row NA
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



def test_gerar_painel_pnadc_valida_argumentos_logicos():
    with pytest.raises(ValueError, match="balancear"):
        gerar_painel_pnadc(ano=2023, balancear="sim")
    with pytest.raises(ValueError, match="balancear"):
        gerar_painel_pnadc(ano=2023, balancear=None)
    with pytest.raises(ValueError, match="low_memory"):
        gerar_painel_pnadc(ano=2023, low_memory=1)
    with pytest.raises(ValueError, match="verbose"):
        gerar_painel_pnadc(ano=2023, verbose="FALSE")


def test_gerar_painel_pnadc_valida_vars_tri_e_vars_visita():
    with pytest.raises(ValueError, match="vars_tri"):
        gerar_painel_pnadc(ano=2023, vars_tri=123)
    with pytest.raises(ValueError, match="nao pode ser um vetor vazio"):
        gerar_painel_pnadc(ano=2023, vars_tri=[])
    with pytest.raises(ValueError, match="vars_visita"):
        gerar_painel_pnadc(ano=2023, vars_visita=456)
    with pytest.raises(ValueError, match="nao pode ser um vetor vazio"):
        gerar_painel_pnadc(ano=2023, vars_visita=[])


def test_gerar_painel_pnadc_inclui_chaves_de_id_obrigatorias_mesmo_em_selecoes_customizadas():
    custom_tri = ["V2009", "VD4020"]
    res_tri = list(dict.fromkeys(chaves_obrig_tri + custom_tri))

    assert all(k in res_tri for k in chaves_obrig_tri)
    assert all(k in res_tri for k in custom_tri)


def test_consolidar_base_habitacao_preserva_colunas_quando_vars_visita_e_null():
    dados_casa_mock = pd.DataFrame({
        "UPA": ["110000016"],
        "V1008": ["01"],
        "V1014": ["10"],
        "Ano": [2023],
        "UF": ["11"],
        "VD5002": [1500.0],
        "V5002A": [1],
        "S01006": [2],
        "coluna_extra_visita": ["A"]
    })

    chaves = ["UPA", "V1008", "V1014", "Ano", "UF"]
    vars_hab_especificas = [c for c in dados_casa_mock.columns if c not in chaves]
    assert vars_hab_especificas == ["VD5002", "V5002A", "S01006", "coluna_extra_visita"]
    assert len(vars_hab_especificas) > 0


def test_gerar_painel_pnadc_exclui_colunas_trimestrais_de_vars_hab_especificas_quando_vars_visita_e_null():
    painel_cruzado_mock = pd.DataFrame({
        "id_dom": ["1100000160110"],
        "id_ind": ["110000016011022081992111"],
        "UPA": ["110000016"],
        "V1008": ["01"],
        "V1014": ["10"],
        "Ano": [2023],
        "Trimestre": [1],
        "UF": ["11"],
        "V2009": [30],       # Coluna trimestral de pessoa
        "VD4020": [2500.0],  # Coluna trimestral de pessoa
        "VD5002": [1200.0],  # Coluna de Visita 1 (habitação)
        "S01013": [1]        # Coluna de Visita 1 (habitação)
    })

    chaves_obrig_visita_local = ["UPA", "V1008", "V1014", "Ano", "UF"]
    vars_tri_proc = ["UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF", "Ano", "Trimestre", "V2009", "VD4020"]

    cols_excluir = set(["id_dom", "id_ind"] + chaves_obrig_visita_local + vars_tri_proc)
    vars_hab_especificas = [c for c in painel_cruzado_mock.columns if c not in cols_excluir]

    assert vars_hab_especificas == ["VD5002", "S01013"]
    assert "V2009" not in vars_hab_especificas
    assert "VD4020" not in vars_hab_especificas


def test_balancear_true_preserva_linhas_com_vd4020_na_mas_remove_linhas_com_vd5002_na():
    painel_mock = pd.DataFrame({
        "id_dom": ["D1", "D2", "D3"],
        "id_ind": ["I1", "I2", "I3"],
        "V2009": [5, 35, 40],          # I1 é criança (5 anos)
        "VD4020": [np.nan, 3000.0, 2000.0], # I1 tem VD4020 = NA
        "VD5002": [1000.0, 1000.0, np.nan], # D3 não casou na Visita 1 (VD5002 = NA)
        "S01013": [1, 1, np.nan]
    })

    vars_hab = ["VD5002", "S01013"]
    painel_bal = painel_mock[painel_mock[vars_hab].notna().all(axis=1)].copy()

    assert len(painel_bal) == 2
    assert list(painel_bal["id_ind"]) == ["I1", "I2"]
    assert "I3" not in list(painel_bal["id_ind"])
