"""
Testes de integração com mock provider offline (Port 1:1 de test-mocked_integration.R).
"""

import pytest
import warnings
import pandas as pd
from pnadcpainel._ibge_source import set_mock_provider
from pnadcpainel.core import gerar_painel_pnadc
from tests.fixtures.synthetic_pnadc import criar_mock_provider


def test_gerar_painel_pnadc_executa_pipeline_completo_offline_com_mock_provider():
    set_mock_provider(criar_mock_provider())

    painel = gerar_painel_pnadc(ano=2023, verbose=False)

    assert isinstance(painel, pd.DataFrame)
    assert len(painel) > 0
    assert "id_dom" in painel.columns
    assert "id_ind" in painel.columns
    assert "diagnostico" in painel.attrs

    diag = painel.attrs["diagnostico"]
    assert isinstance(diag, pd.DataFrame)
    assert all(c in diag.columns for c in ["variavel", "total_linhas", "com_dado", "sem_dado", "pct_disponivel"])


def test_gerar_painel_pnadc_aceita_vars_tri_e_vars_visita_como_todas_e_all():
    set_mock_provider(criar_mock_provider())

    painel_todas = gerar_painel_pnadc(ano=2023, vars_tri="todas", vars_visita="todas", verbose=False)
    assert isinstance(painel_todas, pd.DataFrame)
    assert len(painel_todas) > 0

    painel_all = gerar_painel_pnadc(ano=2023, vars_tri="all", vars_visita="all", verbose=False)
    assert isinstance(painel_all, pd.DataFrame)
    assert len(painel_all) > 0


def test_low_memory_true_e_false_geram_resultados_semanticamente_equivalentes():
    set_mock_provider(criar_mock_provider())

    p_mem = gerar_painel_pnadc(ano=2023, low_memory=False, verbose=False)
    p_low = gerar_painel_pnadc(ano=2023, low_memory=True, verbose=False)

    assert len(p_mem) == len(p_low)
    assert list(p_mem.columns) == list(p_low.columns)
    assert list(p_mem["id_ind"]) == list(p_low["id_ind"])


def test_falha_do_ano_anterior_gera_warning_nao_fatal_e_falha_do_corrente_gera_erro():
    base_mock = criar_mock_provider()

    def mock_falha_anterior(year, quarter=None, interview=None, vars=None, **kwargs):
        if interview is not None and year == 2022:
            raise RuntimeError("Servidor IBGE indisponivel para 2022.")
        return base_mock(year, quarter, interview, vars, **kwargs)

    set_mock_provider(mock_falha_anterior)
    with pytest.warns(UserWarning, match="Nao foi possivel baixar dados de Visita 1 para o ano anterior"):
        p = gerar_painel_pnadc(ano=2023, verbose=False)
        assert isinstance(p, pd.DataFrame)

    def mock_falha_corrente(year, quarter=None, interview=None, vars=None, **kwargs):
        if interview is not None and year == 2023:
            raise RuntimeError("Erro de conexao com IBGE.")
        return base_mock(year, quarter, interview, vars, **kwargs)

    set_mock_provider(mock_falha_corrente)
    with pytest.raises(RuntimeError, match="Falha ao baixar dados de Visita 1"):
        gerar_painel_pnadc(ano=2023, verbose=False)


def test_executar_com_retry_com_parametro_func_e_retry_sucesso():
    from pnadcpainel._retry import executar_com_retry

    tentativas = 0

    def _operacao_instavel():
        nonlocal tentativas
        tentativas += 1
        if tentativas < 2:
            raise ValueError("Erro temporário de conexão")
        return "sucesso"

    res = executar_com_retry(func=_operacao_instavel, max_tentativas=3, delay_inicial=0.01, verbose=False)
    assert res == "sucesso"
    assert tentativas == 2


def test_ano_2012_tenta_baixar_ano_anterior_2011_e_emite_warning():
    base_mock = criar_mock_provider()

    def mock_falha_2011(year, quarter=None, interview=None, vars=None, **kwargs):
        if interview is not None and year == 2011:
            raise RuntimeError("Visita 1 para 2011 não existe no IBGE.")
        return base_mock(year, quarter, interview, vars, **kwargs)

    set_mock_provider(mock_falha_2011)
    with pytest.warns(UserWarning, match="Nao foi possivel baixar dados de Visita 1 para o ano anterior \\(2011\\)"):
        p = gerar_painel_pnadc(ano=2012, verbose=False)
        assert isinstance(p, pd.DataFrame)


def test_parse_sas_input_file_e_resolve_filename():
    from pnadcpainel._ibge_source import _parse_sas_input_file, _resolve_ibge_filename

    sas_text = """
    @00001 UPA $9.
    @00010 V1008 $2.
    @00012 V1014 $2.
    """
    colspecs, names = _parse_sas_input_file(sas_text)
    assert names == ["UPA", "V1008", "V1014"]
    assert colspecs == [(0, 9), (9, 11), (11, 13)]

