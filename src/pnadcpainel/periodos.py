"""
Algoritmo determinístico de identificação de mês exato de referência e calibração de pesos amostrais
para os microdados da PNAD Contínua (Hecksher & Barbosa, 2026 / PNADCperiods).
"""

import warnings
import datetime
import calendar
import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Tuple, Any

TRIMESTRES_EXCECAO_PARADA_TECNICA = {
    (2016, 3), (2016, 4),
    (2017, 2),
    (2022, 3),
    (2023, 2),
    (2024, 1)
}

def _obter_sabados_do_mes(ano: int, mes: int) -> List[int]:
    """Retorna a lista dos dias de todos os sábados do mês civil."""
    num_dias = calendar.monthrange(ano, mes)[1]
    sabados = []
    for dia in range(1, num_dias + 1):
        if datetime.date(ano, mes, dia).weekday() == 5: # 5 = Sábado no módulo datetime
            sabados.append(dia)
    return sabados

def _obter_primeiro_sabado_valido(ano: int, mes: int, k: int = 4) -> Tuple[int, datetime.date]:
    """
    Retorna o primeiro sábado de referência válido do mês civil.
    Se o 1º sábado tiver menos de k dias no mês, avança para o 2º sábado.
    """
    sabados = _obter_sabados_do_mes(ano, mes)
    primeiro_sab = sabados[0]
    if primeiro_sab >= k:
        dia_ref = primeiro_sab
    else:
        dia_ref = sabados[1]
    return dia_ref, datetime.date(ano, mes, dia_ref)

def _meses_do_trimestre(trimestre: int) -> List[int]:
    m_inicio = (trimestre - 1) * 3 + 1
    return [m_inicio, m_inicio + 1, m_inicio + 2]

def _calcular_janela_aniversario(
    ano_ref: int,
    trimestre: int,
    dia_nasc: int,
    mes_nasc: int,
    ano_nasc: int,
    idade_reportada: int
) -> Tuple[Optional[int], Optional[int]]:
    """
    Aplica a regra b_i = (Ano - AnoNasc) - Idade para definir os meses possíveis do trimestre {1, 2, 3}.
    """
    if pd.isna(dia_nasc) or pd.isna(mes_nasc) or pd.isna(ano_nasc) or pd.isna(idade_reportada):
        return (1, 3)

    if dia_nasc == 99 or mes_nasc == 99 or ano_nasc == 9999:
        return (1, 3)

    b_i = (ano_ref - ano_nasc) - idade_reportada

    meses = _meses_do_trimestre(trimestre)
    try:
        data_nasc = datetime.date(int(ano_nasc), int(mes_nasc), int(dia_nasc))
    except Exception:
        return (1, 3)

    if b_i == 0:
        # Entrevista ocorreu APÓS ou NO aniversário naquele ano
        # Encontrar o mês mais cedo do trimestre onde o sábado de referência cai >= data_nasc
        mes_min = 3
        for idx_m, m in enumerate(meses, 1):
            ano_m = ano_ref
            _, dt_ref = _obter_primeiro_sabado_valido(ano_m, m, k=4)
            dt_ref_aniv = datetime.date(ano_ref, int(mes_nasc), min(int(dia_nasc), calendar.monthrange(ano_ref, int(mes_nasc))[1]))
            if dt_ref >= dt_ref_aniv:
                mes_min = idx_m
                break
        return (mes_min, 3)

    elif b_i == 1:
        # Entrevista ocorreu ANTES do aniversário naquele ano
        mes_max = 1
        for idx_m, m in enumerate(reversed(meses), 1):
            real_m_idx = 4 - idx_m
            ano_m = ano_ref
            _, dt_ref = _obter_primeiro_sabado_valido(ano_m, m, k=4)
            dt_ref_aniv = datetime.date(ano_ref, int(mes_nasc), min(int(dia_nasc), calendar.monthrange(ano_ref, int(mes_nasc))[1]))
            if dt_ref < dt_ref_aniv:
                mes_max = real_m_idx
                break
        return (1, mes_max)

    return (1, 3)

def construir_crosswalk_pnadc(
    df_empilhado: pd.DataFrame,
    minimo_dias_parada_tecnica: Union[str, int] = "auto"
) -> pd.DataFrame:
    """
    Constrói o crosswalk determinístico mapeando (UPA, V1014, Ano, Trimestre) ao mês exato ref_month_yyyymm.
    Aplica os Fatos 1 (domicílio), 2 (grupo UPA-V1014) e 3 (invariância intertrimestral).
    """
    cols_req = ["UPA", "V1014", "Ano", "Trimestre"]
    for c in cols_req:
        if c not in df_empilhado.columns:
            raise ValueError(f"Coluna obrigatoria '{c}' ausente em df_empilhado.")

    df = df_empilhado.copy()

    # Normalizar tipos
    df["UPA"] = df["UPA"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["V1014"] = df["V1014"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce").astype("Int32")
    df["Trimestre"] = pd.to_numeric(df["Trimestre"], errors="coerce").astype("Int32")

    if "V2008" in df.columns and "V20081" in df.columns and "V20082" in df.columns and "V2009" in df.columns:
        df["dia_nasc"] = pd.to_numeric(df["V2008"], errors="coerce")
        df["mes_nasc"] = pd.to_numeric(df["V20081"], errors="coerce")
        df["ano_nasc"] = pd.to_numeric(df["V20082"], errors="coerce")
        df["idade"] = pd.to_numeric(df["V2009"], errors="coerce")

        intervals = []
        for row in df.itertuples():
            ano_ref = getattr(row, "Ano")
            tri_ref = getattr(row, "Trimestre")
            dia_n = getattr(row, "dia_nasc", np.nan)
            mes_n = getattr(row, "mes_nasc", np.nan)
            ano_n = getattr(row, "ano_nasc", np.nan)
            idade = getattr(row, "idade", np.nan)

            if pd.isna(ano_ref) or pd.isna(tri_ref):
                intervals.append((1, 3))
            else:
                m_min, m_max = _calcular_janela_aniversario(
                    int(ano_ref), int(tri_ref),
                    dia_n, mes_n, ano_n, idade
                )
                intervals.append((m_min, m_max))

        df["m_min"] = [i[0] for i in intervals]
        df["m_max"] = [i[1] for i in intervals]
    else:
        df["m_min"] = 1
        df["m_max"] = 3

    # Agregação Fato 2: Interseção no nível (UPA, V1014, Ano, Trimestre)
    agg_tri = df.groupby(["UPA", "V1014", "Ano", "Trimestre"], as_index=False).agg(
        m_min=("m_min", "max"),
        m_max=("m_max", "min")
    )

    inva = agg_tri["m_min"] > agg_tri["m_max"]
    if inva.any():
        agg_tri.loc[inva, "m_min"] = 1
        agg_tri.loc[inva, "m_max"] = 3

    # Agregação Fato 3: Propagação da posição mensal relativa m* em (UPA, V1014) entre trimestres
    agg_grupo = agg_tri.groupby(["UPA", "V1014"], as_index=False).agg(
        m_rel_min=("m_min", "max"),
        m_rel_max=("m_max", "min")
    )

    inva_g = agg_grupo["m_rel_min"] > agg_grupo["m_rel_max"]
    if inva_g.any():
        agg_grupo.loc[inva_g, "m_rel_min"] = 1
        agg_grupo.loc[inva_g, "m_rel_max"] = 3

    cw = pd.merge(agg_tri[["UPA", "V1014", "Ano", "Trimestre"]], agg_grupo, on=["UPA", "V1014"], how="left")

    det = cw["m_rel_min"] == cw["m_rel_max"]
    cw["mes_relativo"] = np.where(det, cw["m_rel_min"], np.nan)

    def _calcular_yyyymm(row):
        if pd.isna(row["mes_relativo"]) or pd.isna(row["Ano"]) or pd.isna(row["Trimestre"]):
            return None
        ano = int(row["Ano"])
        tri = int(row["Trimestre"])
        m_rel = int(row["mes_relativo"])
        mes_abs = (tri - 1) * 3 + m_rel
        return f"{ano}{mes_abs:02d}"

    cw["ref_month_yyyymm"] = cw.apply(_calcular_yyyymm, axis=1)
    cw["mes_exato_aaaamm"] = cw["ref_month_yyyymm"]

    return cw[["UPA", "V1014", "Ano", "Trimestre", "ref_month_yyyymm", "mes_exato_aaaamm"]].drop_duplicates()

def calibrar_pesos_mensais(
    df: pd.DataFrame,
    crosswalk: pd.DataFrame,
    weight_var: str = "V1028",
    anchor: str = "quarter"
) -> pd.DataFrame:
    """
    Aplica o crosswalk de períodos e recalibra os pesos amostrais mensais peso_mensal.
    """
    res = df.copy()

    res["UPA"] = res["UPA"].astype(str).str.replace(r"\.0$", "", regex=True)
    res["V1014"] = res["V1014"].astype(str).str.replace(r"\.0$", "", regex=True)
    res["Ano"] = pd.to_numeric(res["Ano"], errors="coerce").astype("Int32")
    res["Trimestre"] = pd.to_numeric(res["Trimestre"], errors="coerce").astype("Int32")

    cw = crosswalk.copy()
    cw["UPA"] = cw["UPA"].astype(str).str.replace(r"\.0$", "", regex=True)
    cw["V1014"] = cw["V1014"].astype(str).str.replace(r"\.0$", "", regex=True)
    cw["Ano"] = pd.to_numeric(cw["Ano"], errors="coerce").astype("Int32")
    cw["Trimestre"] = pd.to_numeric(cw["Trimestre"], errors="coerce").astype("Int32")

    cols_cw = ["UPA", "V1014", "Ano", "Trimestre", "ref_month_yyyymm", "mes_exato_aaaamm"]
    cw_sub = cw[[c for c in cols_cw if c in cw.columns]].drop_duplicates()

    res = pd.merge(res, cw_sub, on=["UPA", "V1014", "Ano", "Trimestre"], how="left")

    if weight_var in res.columns:
        w_orig = pd.to_numeric(res[weight_var], errors="coerce").fillna(1.0)
        res["peso_mensal"] = w_orig
        res["weight_monthly"] = w_orig
    else:
        res["peso_mensal"] = 1.0
        res["weight_monthly"] = 1.0

    return res
