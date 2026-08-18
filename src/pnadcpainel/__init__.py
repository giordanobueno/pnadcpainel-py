"""
pnadcpainel: Painel Consolidado da PNAD Contínua (IBGE) em Python.
"""

from .core import (
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
from .periodos import construir_crosswalk_pnadc, calibrar_pesos_mensais
from .mensal import gerar_painel_pnadc_mensal

__version__ = "0.1.0"

__all__ = [
    "gerar_painel_pnadc",
    "gerar_painel_pnadc_mensal",
    "construir_crosswalk_pnadc",
    "calibrar_pesos_mensais",
    "criar_ids_datazoom",
    "consolidar_base_habitacao",
    "diagnosticar_painel",
    "mensagem_diagnostico",
    "downcast_pnadc",
    "vars_tri_default",
    "vars_visita_default",
    "chaves_obrig_tri",
    "chaves_obrig_visita",
    "set_mock_provider",
    "get_mock_provider",
]
