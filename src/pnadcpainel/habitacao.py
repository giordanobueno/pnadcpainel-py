"""
Baixar e consolidar dados de Visita 1 (Habitação) para domicílios.
"""

import warnings
import pandas as pd
from typing import List, Optional, Union

from ._ibge_source import get_pnadc_internal
from .defaults import vars_visita_default, chaves_obrig_visita
from .memoria import downcast_pnadc
from .identificacao import _normalize_str_code, _pad2


def consolidar_base_habitacao(
    ano: int,
    vars_visita: Optional[Union[List[str], str]] = vars_visita_default,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Baixa os microdados de entrevista 1 (Visita 1) para o ano corrente e
    o ano anterior (se disponível), consolidando as informações no nível do domicílio (`id_dom`).

    Parameters
    ----------
    ano : int
        Ano corrente de referência.
    vars_visita : list of str, str or None, default vars_visita_default
        Vetor de variáveis de habitação a serem baixadas.
    verbose : bool, default True
        Se True, exibe mensagens informativas.

    Returns
    -------
    pd.DataFrame
        DataFrame contendo uma linha por domicílio (`id_dom`) com as primeiras
        respostas não-NA de cada variável de habitação.
    """
    dados_casa_lista = []

    # 1. Ano corrente
    if verbose:
        print(f">>> Baixando Habitacao {ano} (Visita 1)...")

    try:
        df_corrente = get_pnadc_internal(
            year=ano,
            interview=1,
            vars=vars_visita if isinstance(vars_visita, list) else None,
            design=False,
            labels=False,
            verbose=verbose
        )
        if df_corrente is None or df_corrente.empty:
            raise RuntimeError(f"Download de Visita 1 para o ano {ano} retornou vazio.")
        casa_corrente = downcast_pnadc(df_corrente)
        dados_casa_lista.append(casa_corrente)
    except Exception as e:
        raise RuntimeError(f"Falha ao baixar dados de Visita 1 para o ano {ano}: {e}") from e

    # 2. Ano anterior
    ano_anterior = ano - 1
    try:
        if verbose:
            print(f">>> Baixando Habitacao {ano_anterior} (Visita 1)...")
        df_anterior = get_pnadc_internal(
            year=ano_anterior,
            interview=1,
            vars=vars_visita if isinstance(vars_visita, list) else None,
            design=False,
            labels=False,
            verbose=verbose
        )
        if df_anterior is not None and not df_anterior.empty:
            casa_anterior = downcast_pnadc(df_anterior)
            dados_casa_lista.append(casa_anterior)
    except Exception as e:
        warnings.warn(
            f"Nao foi possivel baixar dados de Visita 1 para o ano anterior ({ano_anterior}). "
            f"A consolidacao sera realizada apenas com os dados de {ano}. Erro: {e}",
            UserWarning
        )

    dados_casa_total = pd.concat(dados_casa_lista, ignore_index=True)

    if verbose:
        print(">>> Consolidando Base de Habitacao...")

    chaves = ["UPA", "V1008", "V1014", "Ano", "UF"]
    if vars_visita is None or (isinstance(vars_visita, str) and vars_visita.lower() in ("todas", "all", "tudo")):
        vars_hab_especificas = [c for c in dados_casa_total.columns if c not in chaves]
    else:
        vars_hab_especificas = [c for c in vars_visita if c not in chaves]

    # Construir id_dom
    upa = _normalize_str_code(dados_casa_total["UPA"])
    v1008 = _pad2(dados_casa_total["V1008"])
    v1014 = _normalize_str_code(dados_casa_total["V1014"])
    dados_casa_total["id_dom"] = upa + v1008 + v1014

    cols_manter = ["id_dom"] + [c for c in vars_hab_especificas if c in dados_casa_total.columns]
    sub = dados_casa_total[cols_manter]

    # Agrupar por id_dom e pegar primeira resposta não-NA por coluna (replicando lógica do R)
    def _first_non_na(s: pd.Series):
        non_na = s.dropna()
        return non_na.iloc[0] if not non_na.empty else (s.iloc[0] if not s.empty else None)

    agg_dict = {c: _first_non_na for c in vars_hab_especificas if c in sub.columns}

    if agg_dict:
        base_habitacao = sub.groupby("id_dom", as_index=False).agg(agg_dict)
    else:
        base_habitacao = pd.DataFrame({"id_dom": sub["id_dom"].unique()})

    return base_habitacao

