"""
Suíte completa de testes de regressão e paridade cross-language para pnadcpainel (Python).
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


def _compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------
# 1. TESTES DE OTIMIZAÇÃO DE MEMÓRIA (DOWNCASTING E ERROS CONTROLADOS)
# ------------------------------------------------------------------------------

def test_downcast_pnadc_converte_colunas_especificadas_para_int32():
    df = pd.DataFrame({
        "V2007": [1.0, 2.0, np.nan],
        "V2008": [15.0, 20.0, 99.0],
        "VD4020": [2500.5, 3000.0, np.nan],
        "UPA": ["110000016", "110000016", "110000016"]
    })
    res = downcast_pnadc(df)

    assert str(res["V2007"].dtype) == "Int32"
    assert str(res["V2008"].dtype) == "Int32"
    assert str(res["VD4020"].dtype) in ("float64", "Float64")
    assert str(res["UPA"].dtype) == "object"
    assert res["V2007"].iloc[0] == 1
    assert pd.isna(res["V2007"].iloc[2])

def test_downcast_pnadc_rejeita_fracoes_com_erro_controlado():
    df = pd.DataFrame({
        "V2008": [1.5, 2.0]
    })
    with pytest.raises(ValueError, match="Valores fracionarios nao sao permitidos"):
        downcast_pnadc(df)

def test_downcast_pnadc_rejeita_overflow_com_erro_controlado():
    df = pd.DataFrame({
        "V2008": [2147483648, 10]
    })
    with pytest.raises(ValueError, match="fora do intervalo inteiro de 32-bits"):
        downcast_pnadc(df)

def test_downcast_pnadc_string_invalida_gera_warning():
    df = pd.DataFrame({
        "V2008": ["texto", "10"]
    })
    with pytest.warns(UserWarning, match="Strings nao numericas"):
        res = downcast_pnadc(df)
    assert pd.isna(res["V2008"].iloc[0])
    assert res["V2008"].iloc[1] == 10


# ------------------------------------------------------------------------------
# 2. TESTES DE IDENTIFICAÇÃO DATA ZOOM E CONTRATO DE CHAVES
# ------------------------------------------------------------------------------

def test_nan_em_data_de_nascimento_ou_uf_ou_sexo_e_excluido():
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016", "110000016"],
        "V1008": ["01", "01", "01"],
        "V1014": ["10", "10", "10"],
        "V2008": [15, np.nan, 10],
        "V20081": [5, 8, 5],
        "V20082": [1990, 1992, 1985],
        "V2007": [1, 2, np.nan],       # NA em V2007
        "UF": ["11", "11", np.nan]     # NA em UF
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 1
    assert res["id_dom"].iloc[0] == "1100000160110"

def test_sexo_textual_e_aceito_sem_descarte_de_linha():
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1008": ["01", "01"],
        "V1014": ["10", "10"],
        "V2008": [15, 20],
        "V20081": [5, 8],
        "V20082": [1990, 1992],
        "V2007": ["M", "F"],           # Códigos de sexo textuais
        "UF": ["11", "11"]
    })
    res = criar_ids_datazoom(df)
    assert len(res) == 2
    assert "M" in res["id_ind"].iloc[0]
    assert "F" in res["id_ind"].iloc[1]

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


# ------------------------------------------------------------------------------
# 3. TESTES DE DIAGNÓSTICO E ORDENAÇÃO DETERMINÍSTICA
# ------------------------------------------------------------------------------

def test_diagnosticar_painel_em_dataframe_vazio_ordena_por_pct_e_variavel():
    df_empty = pd.DataFrame(columns=["b", "a", "c"])
    diag = diagnosticar_painel(df_empty, colunas=["b", "a", "c"])

    assert len(diag) == 3
    assert list(diag["variavel"]) == ["a", "b", "c"]
    assert list(diag["pct_disponivel"]) == [0.0, 0.0, 0.0]

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
# 4. TESTES DE VALIDAÇÃO ESTRICTA DE ARGUMENTOS
# ------------------------------------------------------------------------------

def test_gerar_painel_pnadc_valida_o_ano_de_entrada_rigorosamente():
    with pytest.raises(ValueError, match="Informe 'ano' ou 'anos'"):
        gerar_painel_pnadc()
    with pytest.raises(ValueError, match="Informe 'ano' ou 'anos'"):
        gerar_painel_pnadc(ano=None)
    with pytest.raises(ValueError, match="deve ser um unico numero inteiro valido"):
        gerar_painel_pnadc(ano="2023") # Rejeita string numérica no Python para paridade com R
    with pytest.raises(ValueError, match="numero inteiro valido"):
        gerar_painel_pnadc(ano=2023.5)
    with pytest.raises(ValueError, match="Ano invalido"):
        gerar_painel_pnadc(ano=2000)

def test_gerar_painel_pnadc_valida_flags_booleanas_estritamente():
    with pytest.raises(ValueError, match="balancear"):
        gerar_painel_pnadc(ano=2023, balancear=1) # Rejeita inteiro 1 como flag
    with pytest.raises(ValueError, match="balancear"):
        gerar_painel_pnadc(ano=2023, balancear="sim")
    with pytest.raises(ValueError, match="low_memory"):
        gerar_painel_pnadc(ano=2023, low_memory=0)
    with pytest.raises(ValueError, match="verbose"):
        gerar_painel_pnadc(ano=2023, verbose="FALSE")


# ------------------------------------------------------------------------------
# 5. TESTES DE AGREGACAO DE HABITACAO E INVARIÂNCIA LOW_MEMORY
# ------------------------------------------------------------------------------

def test_consolidar_base_habitacao_primeira_resposta_nao_na():
    mock_data = pd.DataFrame({
        "UPA": ["110000016", "110000016", "110000016"],
        "V1008": ["01", "01", "01"],
        "V1014": ["10", "10", "10"],
        "Ano": [2023, 2023, 2023],
        "UF": ["11", "11", "11"],
        "S01013": [np.nan, 10.0, 20.0], # Deve resultar em 10.0
        "VD5002": [np.nan, np.nan, 20.0] # Deve resultar em 20.0
    })

    def mock_provider(**kwargs):
        return mock_data.copy()

    set_mock_provider(mock_provider)
    try:
        res = consolidar_base_habitacao(ano=2023, vars_visita=["S01013", "VD5002"], verbose=False)
        assert len(res) == 1
        assert res["S01013"].iloc[0] == 10.0
        assert res["VD5002"].iloc[0] == 20.0
    finally:
        set_mock_provider(None)

def mock_full_provider(year, quarter=None, interview=None, vars=None, **kwargs):
    if quarter is not None:
        df = pd.DataFrame({
            "UPA": ["110000016", "110000016"],
            "V1008": ["01", "01"],
            "V1014": ["10", "10"],
            "Ano": [year, year],
            "Trimestre": [quarter, quarter],
            "UF": ["11", "11"],
            "V2007": [1, 2],
            "V2008": [15, 20],
            "V20081": [5, 8],
            "V20082": [1990, 1992],
            "V2001": [2, 2],
            "V2005": [1, 2],
            "V2009": [33, 31],
            "VD3004": [7, 6],
            "V3001": [1, 1],
            "VD4001": [1, 1],
            "VD4002": [1, 1],
            "VD4009": [1, 3],
            "VD4020": [3500.0, 2800.0],
            "VD4010": [1, 2]
        })
    else:
        df = pd.DataFrame({
            "UPA": ["110000016"],
            "V1008": ["01"],
            "V1014": ["10"],
            "Ano": [year],
            "UF": ["11"],
            "V5001A": [2],
            "VD5002": [1500.0],
            "V5002A": [2],
            "S01013": [1],
            "S01006": [2],
            "S01010": [1]
        })
    if vars is not None:
        chaves = ["UPA", "V1008", "V1014", "Ano", "UF"] if interview is not None else ["UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF", "Ano", "Trimestre"]
        cols = list(dict.fromkeys(chaves + [c for c in vars if c in df.columns]))
        return df[cols].copy()
    return df


def test_invariancia_low_memory_false_vs_true():
    set_mock_provider(mock_full_provider)
    try:
        res_mem_false = gerar_painel_pnadc(ano=2023, low_memory=False, verbose=False)
        res_mem_true  = gerar_painel_pnadc(ano=2023, low_memory=True, verbose=False)

        assert res_mem_false.shape == res_mem_true.shape
        assert list(res_mem_false.columns) == list(res_mem_true.columns)
        assert res_mem_false["id_dom"].equals(res_mem_true["id_dom"])
        assert res_mem_false["id_ind"].equals(res_mem_true["id_ind"])
    finally:
        set_mock_provider(None)


# ------------------------------------------------------------------------------
# 6. GERAÇÃO DE ARTEFATOS CROSS-LANGUAGE COMPARTILHADOS
# ------------------------------------------------------------------------------

def test_geracao_de_artefatos_cross_language_normatizados():
    set_mock_provider(mock_full_provider)
    try:
        painel = gerar_painel_pnadc(ano=2023, verbose=False)
        diag = diagnosticar_painel(painel)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path   = os.path.join(tmpdir, "panel.csv")
            diag_path  = os.path.join(tmpdir, "diagnostico.csv")
            ids_path   = os.path.join(tmpdir, "ids.csv")
            schema_path= os.path.join(tmpdir, "schema.json")
            meta_path  = os.path.join(tmpdir, "metadata.json")

            painel_clean = painel.copy()
            painel_clean.attrs = {}
            painel_clean.to_csv(csv_path, index=False)

            diag.to_csv(diag_path, index=False)

            ids_df = painel[["id_dom", "id_ind"]]
            ids_df.to_csv(ids_path, index=False)

            schema_info = {col: str(dtype) for col, dtype in painel.dtypes.items()}
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(schema_info, f, indent=2)

            metadata = {
                "ano": 2023,
                "shape": list(painel.shape),
                "hashes": {
                    "panel_csv": _compute_sha256(csv_path),
                    "diagnostico_csv": _compute_sha256(diag_path),
                    "ids_csv": _compute_sha256(ids_path),
                    "schema_json": _compute_sha256(schema_path),
                }
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            assert os.path.exists(csv_path)
            assert os.path.exists(diag_path)
            assert os.path.exists(ids_path)
            assert os.path.exists(schema_path)
            assert os.path.exists(meta_path)
    finally:
        set_mock_provider(None)


# ------------------------------------------------------------------------------
# 7. TESTES DE PAINEL LONGITUDINAL MULTI-ANO (CASOS DE USO 1 A 10)
# ------------------------------------------------------------------------------

def mock_multiyear_provider(year, quarter=None, interview=None, vars=None, **kwargs):
    if quarter is not None:
        records = []
        # Person A (Ind 1): present in 2023 Q1..Q4 and 2024 Q1 (T4->T1 continuity!)
        if (year == 2023) or (year == 2024 and quarter == 1):
            records.append({
                "UPA": "110000016", "V1008": "01", "V1014": "10", "Ano": year, "Trimestre": quarter, "UF": "11",
                "V2007": 1, "V2008": 15, "V20081": 5, "V20082": 1990,
                "V2001": 2, "V2005": 1, "V2009": 33, "VD3004": 7, "V3001": 1,
                "VD4001": 1, "VD4002": 1, "VD4009": 1, "VD4020": 3500.0, "VD4010": 1
            })
        # Person B (Ind 2): present ONLY in 2023 Q4 (observed only once)
        if year == 2023 and quarter == 4:
            records.append({
                "UPA": "110000016", "V1008": "01", "V1014": "10", "Ano": year, "Trimestre": quarter, "UF": "11",
                "V2007": 2, "V2008": 20, "V20081": 8, "V20082": 1992,
                "V2001": 2, "V2005": 2, "V2009": 31, "VD3004": 6, "V3001": 1,
                "VD4001": 1, "VD4002": 1, "VD4009": 3, "VD4020": 2800.0, "VD4010": 2
            })
        # Person C (Ind 3): present in 2023 Q1 and 2023 Q2 (observed twice)
        if year == 2023 and quarter in (1, 2):
            records.append({
                "UPA": "110000016", "V1008": "02", "V1014": "10", "Ano": year, "Trimestre": quarter, "UF": "11",
                "V2007": 1, "V2008": 5, "V20081": 1, "V20082": 1985,
                "V2001": 2, "V2005": 1, "V2009": 38, "VD3004": 5, "V3001": 1,
                "VD4001": 1, "VD4002": 1, "VD4009": 1, "VD4020": 5000.0, "VD4010": 1
            })
        # Person D (Ind 4): present in all quarters of 2023 and 2024
        records.append({
            "UPA": "110000016", "V1008": "02", "V1014": "10", "Ano": year, "Trimestre": quarter, "UF": "11",
            "V2007": 2, "V2008": 12, "V20081": 11, "V20082": 1988,
            "V2001": 2, "V2005": 2, "V2009": 35, "VD3004": 7, "V3001": 1,
            "VD4001": 1, "VD4002": 1, "VD4009": 1, "VD4020": 4000.0, "VD4010": 1
        })
        df = pd.DataFrame(records)
    else:
        df = pd.DataFrame({
            "UPA": ["110000016", "110000016"],
            "V1008": ["01", "02"],
            "V1014": ["10", "10"],
            "Ano": [year, year],
            "UF": ["11", "11"],
            "V5001A": [2, 2],
            "VD5002": [1500.0, 2500.0],
            "V5002A": [2, 2],
            "S01013": [1, 1],
            "S01006": [2, 3],
            "S01010": [1, 1]
        })
    if vars is not None:
        chaves = ["UPA", "V1008", "V1014", "Ano", "UF"] if interview is not None else ["UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF", "Ano", "Trimestre"]
        cols = list(dict.fromkeys(chaves + [c for c in vars if c in df.columns]))
        return df[cols].copy()
    return df

def test_caso_1_um_unico_ano():
    set_mock_provider(mock_full_provider)
    try:
        painel = gerar_painel_pnadc(ano=2023, verbose=False)
        assert len(painel) > 0
        assert set(painel["Ano"].unique()) == {2023}
        assert set(painel["Trimestre"].unique()) == {1, 2, 3, 4}
    finally:
        set_mock_provider(None)

def test_caso_2_dois_anos_consecutivos_range_e_lista():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel_range = gerar_painel_pnadc(anos=range(2023, 2025), verbose=False)
        painel_list  = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)

        assert set(painel_range["Ano"].unique()) == {2023, 2024}
        assert painel_range.shape == painel_list.shape
        assert "periodo" in painel_range.columns
    finally:
        set_mock_provider(None)

def test_caso_3_continuidade_t4_para_t1():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)
        # Person A ID
        id_person_a = "110000016011015051990111"
        obs_person_a = painel[painel["id_ind"] == id_person_a]
        periodos_a = list(obs_person_a["periodo"])

        # Deve conter 2023_4 e 2024_1 com o mesmo id_ind
        assert "2023_4" in periodos_a
        assert "2024_1" in periodos_a
        idx_2023_4 = periodos_a.index("2023_4")
        idx_2024_1 = periodos_a.index("2024_1")
        assert idx_2024_1 == idx_2023_4 + 1
    finally:
        set_mock_provider(None)

def test_caso_4_individuo_observado_apenas_uma_vez():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)
        # Person B ID (present only in 2023 T4)
        id_person_b = "110000016011020081992211"
        obs_person_b = painel[painel["id_ind"] == id_person_b]
        assert len(obs_person_b) == 1
        assert obs_person_b["periodo"].iloc[0] == "2023_4"
    finally:
        set_mock_provider(None)

def test_caso_5_individuo_observado_em_dois_trimestres():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)
        # Person C ID (present in 2023 T1 and 2023 T2)
        id_person_c = "110000016021005011985111"
        obs_person_c = painel[painel["id_ind"] == id_person_c]
        assert len(obs_person_c) == 2
        assert list(obs_person_c["periodo"]) == ["2023_1", "2023_2"]
    finally:
        set_mock_provider(None)

def test_caso_6_individuo_observado_em_todos_os_trimestres():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)
        # Person D ID (present in all 8 quarters)
        id_person_d = "110000016021012111988211"
        obs_person_d = painel[painel["id_ind"] == id_person_d]
        assert len(obs_person_d) == 8
    finally:
        set_mock_provider(None)

def test_caso_7_nao_duplicacao_no_chave_natural():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2023, 2024], verbose=False)
        dups = painel.duplicated(["id_ind", "Ano", "Trimestre"])
        assert dups.sum() == 0
    finally:
        set_mock_provider(None)

def test_caso_8_backward_compatibility():
    set_mock_provider(mock_full_provider)
    try:
        painel_ano = gerar_painel_pnadc(ano=2023, verbose=False)
        assert len(painel_ano) > 0
        assert "periodo" in painel_ano.columns
        assert painel_ano["periodo"].iloc[0].startswith("2023_")
    finally:
        set_mock_provider(None)

def test_caso_9_balancear_nao_elimina_presencas_longitudinais_parciais():
    set_mock_provider(mock_multiyear_provider)
    try:
        painel_bal = gerar_painel_pnadc(anos=[2023, 2024], balancear=True, verbose=False)
        # Person B (1 observação) e Person C (2 observações) devem ser mantidos no balanceamento de habitação
        ids_presentes = set(painel_bal["id_ind"])
        assert "110000016011020081992211" in ids_presentes
        assert "110000016021005011985111" in ids_presentes
    finally:
        set_mock_provider(None)

def test_caso_10_anos_nao_consecutivos():
    set_mock_provider(mock_full_provider)
    try:
        painel = gerar_painel_pnadc(anos=[2020, 2022], verbose=False)
        anos_presentes = set(painel["Ano"].unique())
        assert anos_presentes == {2020, 2022}
        assert 2021 not in anos_presentes
    finally:
        set_mock_provider(None)

def test_validacao_conflito_ano_e_anos():
    with pytest.raises(ValueError, match="Informe apenas 'ano' ou 'anos', não ambos"):
        gerar_painel_pnadc(ano=2023, anos=[2023, 2024])

def test_validacao_nenhum_ano_fornecido():
    with pytest.raises(ValueError, match="Informe 'ano' ou 'anos'"):
        gerar_painel_pnadc()


# ------------------------------------------------------------------------------
# 8. TESTES DE MENSALIZAÇÃO DA PNADC (HECKSHER & BARBOSA, 2026)
# ------------------------------------------------------------------------------

def test_gerar_painel_pnadc_mensal_offline_com_mock():
    from pnadcpainel import gerar_painel_pnadc_mensal

    set_mock_provider(mock_full_provider)
    try:
        painel_m = gerar_painel_pnadc_mensal(ano=2023, filtrar_indeterminados=True, verbose=False)
        assert isinstance(painel_m, pd.DataFrame)
        assert len(painel_m) > 0
        assert "mes_exato_aaaamm" in painel_m.columns
        assert "peso_mensal" in painel_m.columns
        assert painel_m["mes_exato_aaaamm"].notna().all()
        assert type(painel_m) is pd.DataFrame
    finally:
        set_mock_provider(None)

def test_construir_crosswalk_pnadc_python():
    from pnadcpainel import construir_crosswalk_pnadc

    df_sample = pd.DataFrame({
        "UPA": ["110000016", "110000016"],
        "V1014": ["10", "10"],
        "Ano": [2023, 2023],
        "Trimestre": [1, 2],
        "V2008": [15, 15],
        "V20081": [5, 5],
        "V20082": [1990, 1990],
        "V2009": [33, 33]
    })

    cw = construir_crosswalk_pnadc(df_sample)
    assert isinstance(cw, pd.DataFrame)
    assert "ref_month_yyyymm" in cw.columns
    assert "mes_exato_aaaamm" in cw.columns


# ------------------------------------------------------------------------------
# 9. TESTES DE DATAFRAME PURO E OPERAÇÕES PANDAS CONVENCIONAIS
# ------------------------------------------------------------------------------

def test_painel_retorna_dataframe_puro_e_permite_operacoes_padrao():
    from pnadcpainel import gerar_painel_pnadc_mensal

    set_mock_provider(mock_full_provider)
    try:
        painel_m = gerar_painel_pnadc_mensal(ano=2023, verbose=False)
        
        # Garante que e um pd.DataFrame comum sem atributos problematicos
        assert type(painel_m) is pd.DataFrame
        assert len(painel_m.attrs) == 0

        # Testa head(10), tail(), to_string() exatamente como um CSV lido por pd.read_csv()
        repr_output = repr(painel_m.head(10))
        assert isinstance(repr_output, str)

        str_output = painel_m.to_string()
        assert isinstance(str_output, str)

        # Concatenação e fatiamento funcionam sem interferência
        painel_concat = pd.concat([painel_m.iloc[:1], painel_m.iloc[1:]])
        assert len(painel_concat) == len(painel_m)
    finally:
        set_mock_provider(None)



