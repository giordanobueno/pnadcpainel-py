"""
Otimização de memória RAM e downcast de tipos de dados para microdados PNADc.

Nota sobre equivalência R/Python:
- Em R, inteiros com NA são representados pelo C integer NA (`NA_integer_`).
- Em pandas, o tipo `Int32` (nullable integer) utiliza um vetor interno de inteiros 32-bit
  combinado com uma máscara booleana de NAs. Embora a representação física na memória divirja,
  ambos são 100% equivalentes semanticamente para todas as operações de valor e teste de ausência.
- Chaves textuais como `UPA`, `V1008` e `V1014` NUNCA sofrem downcast para manter zeros à esquerda.
"""

import pandas as pd
from typing import List

# Colunas numéricas/categóricas a serem convertidas para inteiros de 32 bits com suporte a NA
COLUNAS_INT: List[str] = [
    "V2007", "V2008", "V20081", "V20082",
    "V2001", "V2005", "V2009",
    "VD3004", "V3001",
    "VD4001", "VD4002", "VD4009", "VD4010",
    "V5001A", "V5002A",
    "S01013", "S01006", "S01010",
    "Ano", "Trimestre", "UF"
]


def downcast_pnadc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte colunas numéricas e categóricas dos microdados da PNADc para inteiros
    de 32 bits com suporte a NA (tipo 'Int32' do pandas) para otimizar uso de memória RAM.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame contendo microdados da PNADc.

    Returns
    -------
    pd.DataFrame
        DataFrame com colunas especificadas convertidas para 'Int32'.
    """
    df = df.copy()
    cols_presentes = [c for c in COLUNAS_INT if c in df.columns]
    for col in cols_presentes:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int32")
    return df
