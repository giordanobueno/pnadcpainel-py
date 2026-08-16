"""
Testes de equivalência de balanceamento e gestão de memória.
"""

import pytest
import pandas as pd
from pnadcpainel._ibge_source import set_mock_provider
from pnadcpainel.core import gerar_painel_pnadc
from tests.fixtures.synthetic_pnadc import criar_mock_provider


def test_balancear_true_retorna_subset_de_balancear_false():
    set_mock_provider(criar_mock_provider())

    p_false = gerar_painel_pnadc(ano=2023, balancear=False, verbose=False)
    p_true = gerar_painel_pnadc(ano=2023, balancear=True, verbose=False)

    set_false = set(p_false["id_ind"])
    set_true = set(p_true["id_ind"])

    assert set_true.issubset(set_false)
    assert len(p_true) <= len(p_false)


def test_low_memory_true_e_false_retornam_mesmo_schema_ordem_e_valores():
    set_mock_provider(criar_mock_provider())

    p_mem = gerar_painel_pnadc(ano=2023, low_memory=False, verbose=False)
    p_low = gerar_painel_pnadc(ano=2023, low_memory=True, verbose=False)

    assert list(p_mem.columns) == list(p_low.columns)
    assert len(p_mem) == len(p_low)
    assert p_mem["id_dom"].equals(p_low["id_dom"])
    assert p_mem["id_ind"].equals(p_low["id_ind"])
