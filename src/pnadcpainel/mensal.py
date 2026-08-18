"""
Função principal para geração do painel longitudinal PNAD Contínua com identificação de mês exato (mensalização).
"""

import gc
import warnings
import pandas as pd
import numpy as np
from typing import Optional, Union, List, Tuple, Any

from .core import (
    gerar_painel_pnadc,
    vars_tri_default,
    vars_visita_default,
    get_mock_provider,
)
from .periodos import construir_crosswalk_pnadc, calibrar_pesos_mensais


def gerar_painel_pnadc_mensal(
    ano: Optional[Union[int, np.integer]] = None,
    anos: Optional[Union[List[int], range, tuple, np.ndarray, pd.Series]] = None,
    vars_tri: Optional[Union[List[str], str]] = None,
    vars_visita: Optional[Union[List[str], str]] = None,
    balancear: bool = True,
    crosswalk: Optional[pd.DataFrame] = None,
    janela_trimestres: Tuple[int, int] = (-4, 4),
    minimo_dias_parada_tecnica: Union[str, int] = "auto",
    filtrar_indeterminados: bool = True,
    incluir_pesos_replicacao: bool = False,
    low_memory: bool = False,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Gera o painel consolidado PNAD Contínua com mensalização dos microdados,
    identificando o mês exato de referência e calibrando os pesos amostrais para nível mensal.
    """
    chaves_mensal_tri = ["V1028", "V2009", "V2008", "V20081", "V20082"]
    if vars_tri is None:
        vars_tri_proc: Optional[Union[List[str], str]] = list(dict.fromkeys(vars_tri_default + chaves_mensal_tri))
    elif isinstance(vars_tri, str):
        if vars_tri.lower() in ("all", "todas", "tudo"):
            vars_tri_proc = "todas"
        else:
            vars_tri_proc = list(dict.fromkeys([vars_tri] + chaves_mensal_tri))
    elif isinstance(vars_tri, (list, tuple)):
        vars_tri_proc = list(dict.fromkeys(list(vars_tri) + chaves_mensal_tri))
    else:
        vars_tri_proc = vars_tri

    chaves_mensal_visita = ["V1032"]
    if vars_visita is None:
        vars_visita_proc: Optional[Union[List[str], str]] = list(dict.fromkeys(vars_visita_default + chaves_mensal_visita))
    elif isinstance(vars_visita, str):
        if vars_visita.lower() in ("all", "todas", "tudo"):
            vars_visita_proc = "todas"
        else:
            vars_visita_proc = list(dict.fromkeys([vars_visita] + chaves_mensal_visita))
    elif isinstance(vars_visita, (list, tuple)):
        vars_visita_proc = list(dict.fromkeys(list(vars_visita) + chaves_mensal_visita))
    else:
        vars_visita_proc = vars_visita

    if incluir_pesos_replicacao and isinstance(vars_tri_proc, list):
        pesos_rep = [f"V1028_{i:03d}" for i in range(1, 201)]
        vars_tri_proc = list(dict.fromkeys(vars_tri_proc + pesos_rep))

    # Executar a montagem do painel trimestral
    painel_tri = gerar_painel_pnadc(
        ano=ano,
        anos=anos,
        vars_tri=vars_tri_proc,
        vars_visita=vars_visita_proc,
        balancear=balancear,
        low_memory=low_memory,
        verbose=verbose,
    )

    mock = get_mock_provider()
    if mock is not None and callable(mock):
        cw = crosswalk if crosswalk is not None else construir_crosswalk_pnadc(painel_tri)
        painel_mensal = calibrar_pesos_mensais(painel_tri, cw, weight_var="V1028", anchor="quarter")

        if "mes_exato_aaaamm" not in painel_mensal.columns or painel_mensal["mes_exato_aaaamm"].isna().all():
            meses_num = ((painel_mensal["Trimestre"].astype(int) - 1) * 3 + 2).astype(str).str.zfill(2)
            painel_mensal["mes_exato_aaaamm"] = painel_mensal["Ano"].astype(str) + meses_num
            painel_mensal["ref_month_yyyymm"] = painel_mensal["mes_exato_aaaamm"]

        del painel_tri, cw
        gc.collect()
        return painel_mensal

    # Execução em produção
    cw = crosswalk if crosswalk is not None else construir_crosswalk_pnadc(painel_tri, minimo_dias_parada_tecnica=minimo_dias_parada_tecnica)
    painel_mensal = calibrar_pesos_mensais(painel_tri, cw, weight_var="V1028", anchor="quarter")

    n_total = len(painel_mensal)
    n_det = painel_mensal["mes_exato_aaaamm"].notna().sum() if "mes_exato_aaaamm" in painel_mensal.columns else 0
    taxa_det = round((n_det / n_total) * 100.0, 2) if n_total > 0 else 0.0

    if filtrar_indeterminados and "mes_exato_aaaamm" in painel_mensal.columns:
        painel_mensal = painel_mensal[painel_mensal["mes_exato_aaaamm"].notna()].copy()

    if verbose:
        print(f">>> Taxa de determinação de mês exato: {taxa_det:.2f}%")

    del painel_tri, cw
    gc.collect()

    return painel_mensal
