"""
Fixtures sintéticas para testes offline da PNADc (Port 1:1 de synthetic_pnadc.R).
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Callable


def criar_fixture_trimestre(year: int, quarter: int, vars: Optional[List[str]] = None) -> pd.DataFrame:
    """Cria fixture sintética de 4 linhas (2 domicílios x 2 pessoas) para um trimestre."""
    df = pd.DataFrame({
        "UPA": ["110000016", "110000016", "110000017", "110000017"],
        "V1008": ["01", "01", "02", "02"],
        "V1014": ["10", "10", "10", "10"],
        "Ano": [int(year)] * 4,
        "Trimestre": [int(quarter)] * 4,
        "UF": ["11"] * 4,
        "V2007": [1, 2, 1, 2],
        "V2008": [15, 20, 10, 5],
        "V20081": [5, 8, 12, 1],
        "V20082": [1990, 1992, 1985, 2015],
        "V2001": [2, 2, 2, 2],
        "V2005": [1, 2, 1, 2],
        "V2009": [33, 31, 38, 8],
        "VD3004": [5, 6, 4, 1],
        "V3001": [1, 1, 1, 2],
        "VD4001": [1, 1, 1, 2],
        "VD4002": [1, 2, 1, np.nan],
        "VD4009": [1, np.nan, 2, np.nan],
        "VD4020": [3500.0, np.nan, 2200.0, np.nan],
        "VD4010": [2, np.nan, 5, np.nan],
    })

    if vars is not None:
        chaves_tri = ["UPA", "V1008", "V1014", "Ano", "Trimestre", "UF", "V2007", "V2008", "V20081", "V20082"]
        cols_manter = [c for c in dict.fromkeys(chaves_tri + list(vars)) if c in df.columns]
        df = df[cols_manter].copy()

    return df


def criar_fixture_habitacao(year: int, vars: Optional[List[str]] = None) -> pd.DataFrame:
    """Cria fixture sintética de habitação (Visita 1) para 2 domicílios."""
    df = pd.DataFrame({
        "UPA": ["110000016", "110000017"],
        "V1008": ["01", "02"],
        "V1014": ["10", "10"],
        "Ano": [int(year)] * 2,
        "UF": ["11"] * 2,
        "V5001A": [2, 2],
        "VD5002": [1750.0, 1100.0],
        "V5002A": [2, 1],
        "S01013": [1, 1],
        "S01006": [2, 3],
        "S01010": [1, 1],
    })

    if vars is not None:
        chaves_hab = ["UPA", "V1008", "V1014", "Ano", "UF"]
        cols_manter = [c for c in dict.fromkeys(chaves_hab + list(vars)) if c in df.columns]
        df = df[cols_manter].copy()

    return df


def criar_mock_provider() -> Callable[..., pd.DataFrame]:
    """Retorna a função de mock provider sintético."""
    def _mock_provider(year: int, quarter: Optional[int] = None, interview: Optional[int] = None, vars: Optional[List[str]] = None, **kwargs):
        if quarter is not None:
            return criar_fixture_trimestre(year, quarter, vars)
        elif interview is not None and interview == 1:
            return criar_fixture_habitacao(year, vars)
        else:
            raise ValueError("Parâmetros inválidos de mock.")

    return _mock_provider
