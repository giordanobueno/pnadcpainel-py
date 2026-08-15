"""
Criação de identificadores longitudinais baseados na metodologia Data Zoom (PUC-Rio).
"""

import pandas as pd
from typing import List

COLUNAS_REQUERIDAS_ID: List[str] = [
    "UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF"
]


def criar_ids_datazoom(dados: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica a metodologia desenvolvida pelo Data Zoom (PUC-Rio) para construção
    dos identificadores longitudinais de domicílio (id_dom) e indivíduo (id_ind)
    a partir das colunas primárias da PNAD Contínua.

    Parameters
    ----------
    dados : pd.DataFrame
        DataFrame contendo microdados da PNADc. Deve conter as colunas:
        UPA, V1008, V1014, V2008, V20081, V20082, V2007 e UF.

    Returns
    -------
    pd.DataFrame
        DataFrame com id_dom e id_ind adicionados, e colunas auxiliares de data
        (V2008, V20081, V20082) removidas.

    Raises
    ------
    ValueError
        Se alguma das colunas obrigatórias estiver ausente no DataFrame.
    """
    faltantes = [c for c in COLUNAS_REQUERIDAS_ID if c not in dados.columns]
    if faltantes:
        raise ValueError(
            f"Colunas obrigatorias ausentes para criar IDs Data Zoom: {', '.join(faltantes)}"
        )

    df = dados.copy()

    # Converter temporariamente para tipos numéricos para validação de valores especiais (99, 9999, NA)
    v2008 = pd.to_numeric(df["V2008"], errors="coerce")
    v20081 = pd.to_numeric(df["V20081"], errors="coerce")
    v20082 = pd.to_numeric(df["V20082"], errors="coerce")
    v2007 = df["V2007"]

    mascara_valida = (
        (v2008 != 99) &
        (v20081 != 99) &
        (v20082 != 9999) &
        v2007.notna()
    )

    df = df[mascara_valida].copy()

    if df.empty:
        # Se ficou vazio, adiciona as colunas esperadas e remove as temporárias
        df["id_dom"] = pd.Series(dtype="object")
        df["id_ind"] = pd.Series(dtype="object")
        df = df.drop(columns=["V2008", "V20081", "V20082"], errors="ignore")
        return df

    # Formatação com zeros à esquerda
    v2008_clean = pd.to_numeric(df["V2008"], errors="coerce").fillna(0).astype(int)
    v20081_clean = pd.to_numeric(df["V20081"], errors="coerce").fillna(0).astype(int)
    v20082_clean = pd.to_numeric(df["V20082"], errors="coerce").fillna(0).astype(int)

    dia = v2008_clean.astype(str).str.zfill(2)
    mes = v20081_clean.astype(str).str.zfill(2)
    ano = v20082_clean.astype(str)
    sexo = df["V2007"].astype(str).str.split(".").str[0]
    uf = df["UF"].astype(str).str.split(".").str[0]

    upa = df["UPA"].astype(str)
    v1008 = df["V1008"].astype(str)
    v1014 = df["V1014"].astype(str)

    id_dom = upa + v1008 + v1014
    id_ind = id_dom + dia + mes + ano + sexo + uf

    df["id_dom"] = id_dom
    df["id_ind"] = id_ind

    df = df.drop(columns=["V2008", "V20081", "V20082"], errors="ignore")
    return df
