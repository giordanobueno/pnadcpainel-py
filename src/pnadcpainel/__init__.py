"""
pnadcpainel-py: Painel Consolidado Pessoa e Domicílio da PNAD Contínua em Python.
"""

from .core import gerar_painel_pnadc
from .identificacao import criar_ids_datazoom
from .habitacao import consolidar_base_habitacao
from .diagnostico import diagnosticar_painel, mensagem_diagnostico
from .memoria import downcast_pnadc
from .defaults import vars_tri_default, vars_visita_default
from ._ibge_source import set_mock_provider, get_mock_provider

__version__ = "0.1.1"

__all__ = [
    "gerar_painel_pnadc",
    "criar_ids_datazoom",
    "consolidar_base_habitacao",
    "diagnosticar_painel",
    "mensagem_diagnostico",
    "downcast_pnadc",
    "vars_tri_default",
    "vars_visita_default",
    "set_mock_provider",
    "get_mock_provider",
]
