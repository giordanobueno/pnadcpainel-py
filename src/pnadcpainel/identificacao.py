"""
Criação de identificadores longitudinais baseados na metodologia Data Zoom (PUC-Rio).
"""

import pandas as pd
from typing import List

COLUNAS_REQUERIDAS_ID: List[str] = [
    "UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF"
]


def _normalize_str_code(series: pd.Series) -> pd.Series:
    """
    Normaliza valores para string removendo o sufixo '.0' introduzido por conversão numérica float,
    mas preservando os valores textuais com zeros à esquerda (ex: '01' continua '01', '1.0' vira '1').
    """
    s_str = series.astype(str)
    return s_str.str.replace(r"\.0$", "", regex=True)


def _pad2(series: pd.Series) -> pd.Series:
    """
    Normaliza valores para string removendo '.0' e aplica zero-padding até 2 dígitos (zfill(2)).
    Ex: 1 -> '01', '1' -> '01', '01' -> '01', 5 -> '05', 12 -> '12', 1.0 -> '01'.
    """
    s_str = _normalize_str_code(series)
    return s_str.str.zfill(2)


def _format_key_str(series: pd.Series) -> pd.Series:
    """
    Preserva o valor textual exato fornecido para chaves de identificação (ex: '01', '10').
    Se o valor contiver sufixo float '.0', remove o '.0', mas nunca converte '01' para '1'.
    """
    return _normalize_str_code(series)


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

    # Conversão explícita para validação estrita sem fillna(0)
    v2008 = pd.to_numeric(df["V2008"], errors="coerce")
    v20081 = pd.to_numeric(df["V20081"], errors="coerce")
    v20082 = pd.to_numeric(df["V20082"], errors="coerce")
    v2007 = pd.to_numeric(df["V2007"], errors="coerce")

    mascara_valida = (
        v2008.notna()
        & v20081.notna()
        & v20082.notna()
        & v2007.notna()
        & v2008.ne(99)
        & v20081.ne(99)
        & v20082.ne(9999)
    )

    df = df[mascara_valida].copy()

    if df.empty:
        df["id_dom"] = pd.Series(dtype="object")
        df["id_ind"] = pd.Series(dtype="object")
        df = df.drop(columns=["V2008", "V20081", "V20082"], errors="ignore")
        return df

    # Para as linhas válidas, extrair componentes de data
    dia = _pad2(df["V2008"])
    mes = _pad2(df["V20081"])
    ano = _normalize_str_code(df["V20082"])

    sexo = _normalize_str_code(df["V2007"])
    uf = _normalize_str_code(df["UF"])
    upa = _normalize_str_code(df["UPA"])
    v1008 = _pad2(df["V1008"])
    v1014 = _normalize_str_code(df["V1014"])

    id_dom = upa + v1008 + v1014
    id_ind = id_dom + dia + mes + ano + sexo + uf

    df["id_dom"] = id_dom
    df["id_ind"] = id_ind

    df = df.drop(columns=["V2008", "V20081", "V20082"], errors="ignore")
    return df

