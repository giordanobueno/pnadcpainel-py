"""
Função principal para geração do painel consolidado PNAD Contínua (Pessoa + Domicílio).
"""

import os
import tempfile
import datetime
import pandas as pd
import numpy as np
from typing import List, Optional, Union, Any

from .defaults import (
    vars_tri_default,
    vars_visita_default,
    chaves_obrig_tri,
    chaves_obrig_visita,
)
from .memoria import downcast_pnadc
from .identificacao import criar_ids_datazoom
from .habitacao import consolidar_base_habitacao
from .diagnostico import diagnosticar_painel, mensagem_diagnostico
from ._ibge_source import get_pnadc_internal


def gerar_painel_pnadc(
    ano: int,
    vars_tri: Optional[Union[List[str], str]] = None,
    vars_visita: Optional[Union[List[str], str]] = None,
    balancear: bool = True,
    low_memory: bool = False,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Baixa e cruza a base trimestral de pessoas com a base de Visita 1 de domicílios
    da PNAD Contínua para um determinado ano, identificando domicílios e indivíduos
    com a metodologia Data Zoom (PUC-Rio).

    Parameters
    ----------
    ano : int
        Ano de referência (inteiro entre 2012 e o ano atual).
    vars_tri : list of str or str, optional
        Vetor de variáveis trimestrais a baixar. Se None, utiliza vars_tri_default.
        Se 'todas', 'all' ou 'tudo', baixa todas as colunas da PNADc trimestral.
    vars_visita : list of str or str, optional
        Vetor de variáveis de Visita 1 a baixar. Se None, utiliza vars_visita_default.
        Se 'todas', 'all' ou 'tudo', baixa todas as colunas de Visita 1.
    balancear : bool, default True
        Se True, remove linhas do painel onde qualquer variável oriunda de Visita 1
        selecionada esteja com NA, garantindo painel retangular.
    low_memory : bool, default False
        Se True, grava intermediários trimestrais em disco temporário.
    verbose : bool, default True
        Se True, exibe mensagens informativas e de diagnóstico.

    Returns
    -------
    pd.DataFrame
        DataFrame consolidado contendo as informações de pessoas e domicílios.
        O objeto possui o atributo .attrs["diagnostico"] contendo a tabela de diagnóstico.
    """
    # 1. Validação estrita de argumentos
    ano_atual = datetime.datetime.now().year

    if ano is None:
        raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")

    if isinstance(ano, bool):
        raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")

    if isinstance(ano, (list, tuple, np.ndarray, pd.Series)):
        raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")

    try:
        if isinstance(ano, str):
            # Tentar converter string para float/int
            float_val = float(ano)
            if not float_val.is_integer():
                raise ValueError("O argumento 'ano' deve ser um numero inteiro valido.")
            ano_int = int(float_val)
        elif isinstance(ano, (int, float, np.integer, np.floating)):
            if np.isnan(ano) or np.isinf(ano):
                raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")
            if float(ano) != int(ano):
                raise ValueError("O argumento 'ano' deve ser um numero inteiro valido.")
            ano_int = int(ano)
        else:
            raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")
    except (ValueError, TypeError) as e:
        if "numero inteiro valido" in str(e) or "Ano invalido" in str(e):
            raise
        raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.") from e

    if ano_int < 2012 or ano_int > ano_atual:
        raise ValueError(
            f"Ano invalido: {ano_int}. A PNAD Continua esta disponivel entre 2012 e {ano_atual}."
        )

    if not isinstance(balancear, bool):
        raise ValueError("O argumento 'balancear' deve ser um unico valor logico (TRUE ou FALSE).")
    if not isinstance(low_memory, bool):
        raise ValueError("O argumento 'low_memory' deve ser um unico valor logico (TRUE ou FALSE).")
    if not isinstance(verbose, bool):
        raise ValueError("O argumento 'verbose' deve ser um unico valor logico (TRUE ou FALSE).")

    # Validar e processar vars_tri
    if vars_tri is None:
        vars_tri_proc: Optional[List[str]] = list(vars_tri_default)
    elif isinstance(vars_tri, str):
        if vars_tri.lower() in ("all", "todas", "tudo"):
            vars_tri_proc = None
        else:
            vars_tri_proc = list(dict.fromkeys(chaves_obrig_tri + [vars_tri]))
    elif isinstance(vars_tri, (list, tuple)):
        if len(vars_tri) == 0:
            raise ValueError("O argumento 'vars_tri' nao pode ser um vetor vazio.")
        if len(vars_tri) == 1 and str(vars_tri[0]).lower() in ("all", "todas", "tudo"):
            vars_tri_proc = None
        else:
            vars_tri_proc = list(dict.fromkeys(chaves_obrig_tri + list(vars_tri)))
    else:
        raise ValueError(
            "O argumento 'vars_tri' deve ser NULL, 'todas' ou um vetor de caracteres com nomes de variaveis."
        )

    # Validar e processar vars_visita
    if vars_visita is None:
        vars_visita_proc: Optional[List[str]] = list(vars_visita_default)
    elif isinstance(vars_visita, str):
        if vars_visita.lower() in ("all", "todas", "tudo"):
            vars_visita_proc = None
        else:
            vars_visita_proc = list(dict.fromkeys(chaves_obrig_visita + [vars_visita]))
    elif isinstance(vars_visita, (list, tuple)):
        if len(vars_visita) == 0:
            raise ValueError("O argumento 'vars_visita' nao pode ser um vetor vazio.")
        if len(vars_visita) == 1 and str(vars_visita[0]).lower() in ("all", "todas", "tudo"):
            vars_visita_proc = None
        else:
            vars_visita_proc = list(dict.fromkeys(chaves_obrig_visita + list(vars_visita)))
    else:
        raise ValueError(
            "O argumento 'vars_visita' deve ser NULL, 'todas' ou um vetor de caracteres com nomes de variaveis."
        )

    # 2. Processar base trimestral
    painel_pessoas = baixar_trimestres_pnadc(
        ano=ano_int,
        vars_tri=vars_tri_proc,
        low_memory=low_memory,
        verbose=verbose
    )

    # 3. Processar base de habitação (Visita 1)
    base_habitacao = consolidar_base_habitacao(
        ano=ano_int,
        vars_visita=vars_visita_proc,
        verbose=verbose
    )

    # 4. Cruzamento (left_join por id_dom)
    if verbose:
        print(">>> Realizando o cruzamento final (left_join por id_dom)...")

    painel_cruzado = pd.merge(painel_pessoas, base_habitacao, on="id_dom", how="left")

    # 5. Diagnóstico de preenchimento
    if vars_visita_proc is None:
        cols_excluir = set(["id_dom", "id_ind"] + chaves_obrig_visita + (vars_tri_proc if vars_tri_proc else []))
        vars_hab_especificas = [c for c in painel_cruzado.columns if c not in cols_excluir]
    else:
        vars_hab_especificas = [c for c in vars_visita_proc if c not in chaves_obrig_visita]

    vars_hab_especificas = [c for c in vars_hab_especificas if c in painel_cruzado.columns]

    diag_tb = diagnosticar_painel(painel_cruzado, colunas=vars_hab_especificas)

    # 6. Balanceamento do painel
    if balancear and len(vars_hab_especificas) > 0:
        mascara_completa = painel_cruzado[vars_hab_especificas].notna().all(axis=1)
        painel_final = painel_cruzado[mascara_completa].copy()
    else:
        painel_final = painel_cruzado.copy()

    # Emissão de mensagem de diagnóstico
    if verbose and len(diag_tb) > 0:
        mensagem_diagnostico(
            diagnostico=diag_tb,
            painel_antes=painel_cruzado,
            painel_depois=painel_final,
            ano=ano_int
        )

    # Anexar atributo de diagnóstico
    painel_final.attrs["diagnostico"] = diag_tb

    return painel_final


def baixar_trimestres_pnadc(
    ano: int,
    vars_tri: Optional[List[str]] = None,
    low_memory: bool = False,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Baixa e consolida os 4 trimestres de um determinado ano.
    """
    lista_painel = []
    temp_files = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for tri in range(1, 5):
            if verbose:
                print(f">>> Processando Trimestre {tri} de {ano}...")

            dados_brutos = get_pnadc_internal(
                year=ano,
                quarter=tri,
                vars=vars_tri,
                design=False,
                labels=False,
                verbose=verbose
            )

            if dados_brutos is None or dados_brutos.empty:
                raise RuntimeError(f"Download vazio ou nulo para o Trimestre {tri} de {ano}.")

            dados_brutos = downcast_pnadc(dados_brutos)
            dados_proc = criar_ids_datazoom(dados_brutos)

            if low_memory:
                tpath = os.path.join(tmpdir, f"pnadc_tri_{ano}_{tri}.pkl")
                dados_proc.to_pickle(tpath)
                temp_files.append(tpath)
            else:
                lista_painel.append(dados_proc)

        if low_memory:
            res_list = [pd.read_pickle(f) for f in temp_files]
            painel_pessoas = pd.concat(res_list, ignore_index=True)
        else:
            painel_pessoas = pd.concat(lista_painel, ignore_index=True)

    return painel_pessoas
