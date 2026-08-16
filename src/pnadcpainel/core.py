"""
Core engine do pacote pnadcpainel em Python.
Contém a lógica de download, processamento, identificação Data Zoom, diagnósticos e balanceamento do painel.
"""

import os
import re
import io
import time
import zipfile
import tempfile
import warnings
import datetime
import requests
import pandas as pd
import numpy as np
from typing import List, Optional, Union, Callable, Dict, Tuple, Any

# ==============================================================================
# 1. VALORES PADRÃO E LISTAS MESTRAS DE VARIÁVEIS
# ==============================================================================

vars_tri_default: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "Trimestre", "UF",
    "V2007", "V2008", "V20081", "V20082",
    "V2001", "V2005", "V2009",
    "VD3004", "V3001",
    "VD4001", "VD4002", "VD4009", "VD4020", "VD4010"
]

vars_visita_default: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "UF",
    "V5001A",
    "VD5002", "V5002A",
    "S01013", "S01006", "S01010"
]

chaves_obrig_tri: List[str] = [
    "UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF", "Ano", "Trimestre"
]

chaves_obrig_visita: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "UF"
]

COLUNAS_REQUERIDAS_ID: List[str] = [
    "UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF"
]

COLUNAS_INT: List[str] = [
    "V2007", "V2008", "V20081", "V20082",
    "V2001", "V2005", "V2009",
    "VD3004", "V3001",
    "VD4001", "VD4002", "VD4009", "VD4010",
    "V5001A", "V5002A",
    "S01013", "S01006", "S01010",
    "Ano", "Trimestre", "UF"
]

# ==============================================================================
# 2. OTIMIZAÇÃO DE MEMÓRIA (DOWNCASTING)
# ==============================================================================

def downcast_pnadc(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas numéricas/categóricas para Int32 para economizar RAM."""
    df = df.copy()
    cols_presentes = [c for c in COLUNAS_INT if c in df.columns]
    for col in cols_presentes:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int32")
    return df

# ==============================================================================
# 3. ALGORITMO DE IDENTIFICAÇÃO DATA ZOOM
# ==============================================================================

def _normalize_str_code(series: pd.Series) -> pd.Series:
    s_str = series.astype(str)
    return s_str.str.replace(r"\.0$", "", regex=True)

def _pad2(series: pd.Series) -> pd.Series:
    s_str = _normalize_str_code(series)
    return s_str.str.zfill(2)

def _format_key_str(series: pd.Series) -> pd.Series:
    return _normalize_str_code(series)

def criar_ids_datazoom(dados: pd.DataFrame) -> pd.DataFrame:
    """Cria identificadores longitudinais id_dom e id_ind com a metodologia Data Zoom (PUC-Rio)."""
    faltantes = [c for c in COLUNAS_REQUERIDAS_ID if c not in dados.columns]
    if faltantes:
        raise ValueError(f"Colunas obrigatorias ausentes para criar IDs Data Zoom: {', '.join(faltantes)}")

    df = dados.copy()

    v2008 = pd.to_numeric(df["V2008"], errors="coerce")
    v20081 = pd.to_numeric(df["V20081"], errors="coerce")
    v20082 = pd.to_numeric(df["V20082"], errors="coerce")
    v2007 = pd.to_numeric(df["V2007"], errors="coerce")

    mascara_valida = (
        v2008.notna() & v20081.notna() & v20082.notna() & v2007.notna()
        & v2008.ne(99) & v20081.ne(99) & v20082.ne(9999)
    )

    df = df[mascara_valida].copy()

    if df.empty:
        df["id_dom"] = pd.Series(dtype="object")
        df["id_ind"] = pd.Series(dtype="object")
        df = df.drop(columns=["V2008", "V20081", "V20082"], errors="ignore")
        return df

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

# ==============================================================================
# 4. DIAGNÓSTICO E PERDA DE DADOS
# ==============================================================================

def diagnosticar_painel(painel: pd.DataFrame, colunas: Optional[List[str]] = None) -> pd.DataFrame:
    """Gera tabela de disponibilidade/completude por coluna no painel."""
    if colunas is None:
        cols = list(painel.columns)
    else:
        cols = [c for c in colunas if c in painel.columns]

    if not cols:
        raise ValueError("Nenhuma coluna valida fornecida para diagnostico.")

    n_total = len(painel)
    if n_total == 0:
        res = [{"variavel": c, "total_linhas": 0, "com_dado": 0, "sem_dado": 0, "pct_disponivel": 0.0} for c in cols]
        return pd.DataFrame(res).sort_values(by=["pct_disponivel", "variavel"], ascending=[True, True], kind="mergesort").reset_index(drop=True)

    registros = []
    for col in cols:
        s = painel[col]
        com_dado = int(s.notna().sum())
        sem_dado = int(s.isna().sum())
        pct = round((com_dado / n_total) * 100.0, 2) if n_total > 0 else 0.0
        registros.append({
            "variavel": col,
            "total_linhas": n_total,
            "com_dado": com_dado,
            "sem_dado": sem_dado,
            "pct_disponivel": pct
        })

    return pd.DataFrame(registros).sort_values(
        by=["pct_disponivel", "variavel"], ascending=[True, True], kind="mergesort"
    ).reset_index(drop=True)

def _format_br(num: Union[int, float]) -> str:
    if isinstance(num, float):
        formatted = f"{num:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        return f"{num:,}".replace(",", ".")

def mensagem_diagnostico(
    diagnostico: Optional[pd.DataFrame],
    painel_antes: Optional[pd.DataFrame],
    painel_depois: Optional[pd.DataFrame],
    ano: int
) -> str:
    """Emite no console a mensagem estruturada de perda de dados."""
    n_antes = len(painel_antes) if painel_antes is not None else 0
    n_depois = len(painel_depois) if painel_depois is not None else 0
    perda_abs = n_antes - n_depois
    perda_pct = round((perda_abs / n_antes) * 100.0, 2) if n_antes > 0 else 0.0

    if diagnostico is not None and not diagnostico.empty:
        var_critica_row = diagnostico.iloc[0]
        var_critica = str(var_critica_row["variavel"])
        pct_ausente_critica = round(100.0 - float(var_critica_row["pct_disponivel"]), 2)
    else:
        var_critica = "Nenhuma"
        pct_ausente_critica = 0.0

    perda_pct_str = _format_br(perda_pct)
    pct_ausente_str = _format_br(pct_ausente_critica)

    msg = (
        f"\n>>> Diagnóstico do painel PNADc - ano {ano}\n"
        f"Linhas antes do cruzamento (base trimestral): {_format_br(n_antes)}\n"
        f"Linhas após cruzamento + balanceamento:       {_format_br(n_depois)}\n"
        f"Perda total: {_format_br(perda_abs)} linhas ({perda_pct_str}%)\n"
        f"Variável com maior perda antes do balanceamento: {var_critica} - {pct_ausente_str}% de dados ausentes\n"
        f"Motivo: descompasso temporal entre a base trimestral (Ano/Trimestre corrente) "
        f"e a base de Visita 1 (entrevista específica, ano corrente + ano anterior).\n"
    )

    print(msg)
    return msg

# ==============================================================================
# 5. RETRY, MOCKS E DOWNLOAD DA PNADc (IBGE)
# ==============================================================================

_mock_provider: Optional[Callable[..., pd.DataFrame]] = None
_filename_cache: Dict[Tuple[str, str], str] = {}
_dict_cache: Dict[Tuple[bool, int, int], Tuple[List[Tuple[int, int]], List[str]]] = {}

def set_mock_provider(provider: Optional[Callable[..., pd.DataFrame]]) -> None:
    global _mock_provider
    _mock_provider = provider

def get_mock_provider() -> Optional[Callable[..., pd.DataFrame]]:
    return _mock_provider

def executar_com_retry(
    func: Callable[[], Any],
    max_tentativas: int = 3,
    delay_inicial: float = 1.0,
    verbose: bool = True,
    rotulo: str = "Requisição"
) -> Any:
    tentativa = 1
    delay = delay_inicial

    while tentativa <= max_tentativas:
        inicio = time.time()
        try:
            val = func()
            if verbose and tentativa > 1:
                duracao = round(time.time() - inicio, 2)
                print(f">>> {rotulo} bem-sucedida na tentativa {tentativa}/{max_tentativas} ({duracao:.2f}s)")
            return val
        except Exception as e:
            duracao = round(time.time() - inicio, 2)
            if tentativa < max_tentativas:
                if verbose:
                    print(
                        f">>> {rotulo} falhou na tentativa {tentativa}/{max_tentativas} ({duracao:.2f}s). "
                        f"Erro: {e}. Tentando em {delay:.1f}s..."
                    )
                time.sleep(delay)
                delay *= 2
            else:
                raise RuntimeError(f"{rotulo} falhou após {max_tentativas} tentativas. Erro final: {e}") from e
        tentativa += 1

def _resolve_ibge_filename(url_dir: str, pattern_str: str) -> str:
    cache_key = (url_dir, pattern_str)
    if cache_key in _filename_cache:
        return _filename_cache[cache_key]

    resp = requests.get(url_dir, timeout=30)
    resp.raise_for_status()

    href_links = re.findall(r'href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
    regex = re.compile(pattern_str, re.IGNORECASE)
    matches: List[str] = []

    for link in href_links:
        clean_name = os.path.basename(link.split("?")[0])
        if regex.search(clean_name):
            matches.append(clean_name)

    matches = sorted(list(set(matches)), reverse=True)
    if not matches:
        raise RuntimeError(f"Nenhum arquivo correspondente ao padrão '{pattern_str}' foi encontrado em {url_dir}")

    selected_filename = matches[0]
    _filename_cache[cache_key] = selected_filename
    return selected_filename

def _parse_sas_input_file(content_text: str) -> Tuple[List[Tuple[int, int]], List[str]]:
    colspecs: List[Tuple[int, int]] = []
    names: List[str] = []
    pattern = re.compile(r"@(\d+)\s+([A-Za-z0-9_]+)\s+\$?(\d+)\.")

    for line in content_text.splitlines():
        match = pattern.search(line)
        if match:
            start_pos = int(match.group(1)) - 1
            var_name = match.group(2)
            length = int(match.group(3))
            end_pos = start_pos + length
            colspecs.append((start_pos, end_pos))
            names.append(var_name)

    return colspecs, names

def _get_sas_input_spec(is_visita: bool, interview: int = 1, year: int = 2023) -> Tuple[List[Tuple[int, int]], List[str]]:
    cache_key = (is_visita, interview, year)
    if cache_key in _dict_cache:
        return _dict_cache[cache_key]

    base_doc_url = "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua"
    doc_dir = f"{base_doc_url}/Anual/Microdados/Visita/Visita_{interview}/Documentacao" if is_visita else f"{base_doc_url}/Trimestral/Microdados/Documentacao"

    resp = requests.get(doc_dir, timeout=30)
    resp.raise_for_status()

    href_links = re.findall(r'href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
    match_file = None

    if is_visita:
        for link in href_links:
            clean_name = os.path.basename(link.split("?")[0])
            if re.search(rf"input_PNADC_{year}_visita{interview}.*\.txt$", clean_name, re.IGNORECASE):
                match_file = clean_name
                break

    if not match_file:
        for link in href_links:
            clean_name = os.path.basename(link.split("?")[0])
            if "input" in clean_name.lower() and clean_name.lower().endswith(".txt"):
                match_file = clean_name
                break

    if not match_file:
        for link in href_links:
            clean_name = os.path.basename(link.split("?")[0])
            if "dicionario" in clean_name.lower() and clean_name.lower().endswith(".zip"):
                match_file = clean_name
                break

    if not match_file:
        for link in href_links:
            clean_name = os.path.basename(link.split("?")[0])
            if clean_name.lower().endswith(".zip"):
                match_file = clean_name
                break

    if not match_file:
        raise RuntimeError(f"Arquivo de dicionário/input não encontrado em {doc_dir}")

    doc_url = f"{doc_dir}/{match_file}"
    doc_resp = requests.get(doc_url, timeout=60)
    doc_resp.raise_for_status()

    input_text = ""
    if match_file.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(doc_resp.content)) as zf:
            input_files = [f for f in zf.namelist() if "input" in f.lower() and f.lower().endswith(".txt")]
            if not input_files:
                input_files = [f for f in zf.namelist() if f.lower().endswith(".txt")]
            if not input_files:
                raise RuntimeError("Nenhum arquivo TXT de input encontrado dentro do zip de documentação.")
            input_text = zf.read(input_files[0]).decode("latin1", errors="ignore")
    else:
        input_text = doc_resp.content.decode("latin1", errors="ignore")

    colspecs, names = _parse_sas_input_file(input_text)
    if not colspecs or not names:
        raise RuntimeError("Falha ao extrair especificações de colunas do arquivo de input SAS do IBGE.")

    _dict_cache[cache_key] = (colspecs, names)
    return colspecs, names

def _download_ibge_ftp(
    year: int,
    quarter: Optional[int] = None,
    interview: Optional[int] = None,
    vars: Optional[List[str]] = None
) -> pd.DataFrame:
    base_url = "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua"

    if quarter is not None:
        url_dir = f"{base_url}/Trimestral/Microdados/{year}"
        pattern_str = rf"PNADC_0{quarter}{year}(?:_\d{{8}})?\.zip"
        is_visita = False
    elif interview is not None:
        url_dir = f"{base_url}/Anual/Microdados/Visita/Visita_{interview}/Dados"
        pattern_str = rf"PNADC_{year}_visita{interview}(?:_\d{{8}})?\.zip"
        is_visita = True
    else:
        raise ValueError("É necessário especificar 'quarter' ou 'interview'.")

    filename = _resolve_ibge_filename(url_dir, pattern_str)
    full_url = f"{url_dir}/{filename}"

    response = requests.get(full_url, stream=True, timeout=60)
    response.raise_for_status()

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, filename)
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
            extracted_files = zip_ref.namelist()

        txt_file = None
        for fn in extracted_files:
            if fn.lower().endswith(".txt"):
                txt_file = os.path.join(tmpdir, fn)
                break

        if txt_file is None:
            raise RuntimeError(f"Nenhum arquivo TXT encontrado dentro de {filename}")

        with open(txt_file, "r", encoding="latin1", errors="ignore") as f_check:
            first_line = f_check.readline()

        if ";" in first_line:
            df = pd.read_csv(txt_file, sep=";", dtype=str, low_memory=False)
        else:
            colspecs, names = _get_sas_input_spec(is_visita=is_visita, interview=interview or 1, year=year)
            df = pd.read_fwf(txt_file, colspecs=colspecs, names=names, dtype=str)

        chaves_obrig = chaves_obrig_visita if is_visita else chaves_obrig_tri
        chaves_faltantes = [k for k in chaves_obrig if k not in df.columns]
        if chaves_faltantes:
            raise RuntimeError(f"Colunas obrigatorias ausentes no arquivo baixado: {', '.join(chaves_faltantes)}")

        if vars is not None:
            cols_existentes = [c for c in vars if c in df.columns]
            cols_faltantes = [c for c in vars if c not in df.columns]
            if cols_faltantes:
                warnings.warn(f"Variaveis solicitadas nao encontradas no arquivo: {', '.join(cols_faltantes)}", UserWarning)
            if cols_existentes:
                df = df[cols_existentes]

        return df

def get_pnadc_internal(
    year: int,
    quarter: Optional[int] = None,
    interview: Optional[int] = None,
    vars: Optional[List[str]] = None,
    design: bool = False,
    labels: bool = False,
    verbose: bool = True
) -> pd.DataFrame:
    mock = get_mock_provider()
    if mock is not None and callable(mock):
        return mock(year=year, quarter=quarter, interview=interview, vars=vars, design=design, labels=labels)

    rotulo = (
        f"Download Trimestre {quarter}/{year}" if quarter is not None
        else (f"Download Visita {interview}/{year}" if interview is not None else f"Download PNADc {year}")
    )

    def _do_download() -> pd.DataFrame:
        return _download_ibge_ftp(year=year, quarter=quarter, interview=interview, vars=vars)

    return executar_com_retry(func=_do_download, max_tentativas=3, delay_inicial=1.0, verbose=verbose, rotulo=rotulo)

# ==============================================================================
# 6. CONSOLIDAÇÃO DE HABITAÇÃO E GERAÇÃO DE PAINEL
# ==============================================================================

def consolidar_base_habitacao(
    ano: int,
    vars_visita: Optional[Union[List[str], str]] = vars_visita_default,
    verbose: bool = True
) -> pd.DataFrame:
    dados_casa_lista = []

    if verbose:
        print(f">>> Baixando Habitacao {ano} (Visita 1)...")

    try:
        df_corrente = get_pnadc_internal(
            year=ano, interview=1, vars=vars_visita if isinstance(vars_visita, list) else None,
            design=False, labels=False, verbose=verbose
        )
        if df_corrente is None or df_corrente.empty:
            raise RuntimeError(f"Download de Visita 1 para o ano {ano} retornou vazio.")
        casa_corrente = downcast_pnadc(df_corrente)
        dados_casa_lista.append(casa_corrente)
    except Exception as e:
        raise RuntimeError(f"Falha ao baixar dados de Visita 1 para o ano {ano}: {e}") from e

    ano_anterior = ano - 1
    try:
        if verbose:
            print(f">>> Baixando Habitacao {ano_anterior} (Visita 1)...")
        df_anterior = get_pnadc_internal(
            year=ano_anterior, interview=1, vars=vars_visita if isinstance(vars_visita, list) else None,
            design=False, labels=False, verbose=verbose
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

    upa = _normalize_str_code(dados_casa_total["UPA"])
    v1008 = _pad2(dados_casa_total["V1008"])
    v1014 = _normalize_str_code(dados_casa_total["V1014"])
    dados_casa_total["id_dom"] = upa + v1008 + v1014

    cols_manter = ["id_dom"] + [c for c in vars_hab_especificas if c in dados_casa_total.columns]
    sub = dados_casa_total[cols_manter]

    def _first_non_na(s: pd.Series):
        non_na = s.dropna()
        return non_na.iloc[0] if not non_na.empty else (s.iloc[0] if not s.empty else None)

    agg_dict = {c: _first_non_na for c in vars_hab_especificas if c in sub.columns}

    if agg_dict:
        base_habitacao = sub.groupby("id_dom", as_index=False).agg(agg_dict)
    else:
        base_habitacao = pd.DataFrame({"id_dom": sub["id_dom"].unique()})

    return base_habitacao

def baixar_trimestres_pnadc(
    ano: int,
    vars_tri: Optional[List[str]] = None,
    low_memory: bool = False,
    verbose: bool = True
) -> pd.DataFrame:
    lista_painel = []
    temp_files = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for tri in range(1, 5):
            if verbose:
                print(f">>> Processando Trimestre {tri} de {ano}...")

            dados_brutos = get_pnadc_internal(
                year=ano, quarter=tri, vars=vars_tri, design=False, labels=False, verbose=verbose
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
    """
    ano_atual = datetime.datetime.now().year

    if ano is None or isinstance(ano, bool) or isinstance(ano, (list, tuple, np.ndarray, pd.Series)):
        raise ValueError("O argumento 'ano' deve ser um unico numero inteiro valido.")

    try:
        if isinstance(ano, str):
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
        raise ValueError(f"Ano invalido: {ano_int}. A PNAD Continua esta disponivel entre 2012 e {ano_atual}.")

    if not isinstance(balancear, bool):
        raise ValueError("O argumento 'balancear' deve ser um unico valor logico (TRUE ou FALSE).")
    if not isinstance(low_memory, bool):
        raise ValueError("O argumento 'low_memory' deve ser um unico valor logico (TRUE ou FALSE).")
    if not isinstance(verbose, bool):
        raise ValueError("O argumento 'verbose' deve ser um unico valor logico (TRUE ou FALSE).")

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
        raise ValueError("O argumento 'vars_tri' deve ser NULL, 'todas' ou um vetor de caracteres com nomes de variaveis.")

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
        raise ValueError("O argumento 'vars_visita' deve ser NULL, 'todas' ou um vetor de caracteres com nomes de variaveis.")

    painel_pessoas = baixar_trimestres_pnadc(
        ano=ano_int, vars_tri=vars_tri_proc, low_memory=low_memory, verbose=verbose
    )

    base_habitacao = consolidar_base_habitacao(
        ano=ano_int, vars_visita=vars_visita_proc, verbose=verbose
    )

    if verbose:
        print(">>> Realizando o cruzamento final (left_join por id_dom)...")

    painel_cruzado = pd.merge(painel_pessoas, base_habitacao, on="id_dom", how="left")

    if vars_visita_proc is None:
        cols_excluir = set(["id_dom", "id_ind"] + chaves_obrig_visita + (vars_tri_proc if vars_tri_proc else []))
        vars_hab_especificas = [c for c in painel_cruzado.columns if c not in cols_excluir]
    else:
        vars_hab_especificas = [c for c in vars_visita_proc if c not in chaves_obrig_visita]

    vars_hab_especificas = [c for c in vars_hab_especificas if c in painel_cruzado.columns]
    diag_tb = diagnosticar_painel(painel_cruzado, colunas=vars_hab_especificas)

    if balancear and len(vars_hab_especificas) > 0:
        mascara_completa = painel_cruzado[vars_hab_especificas].notna().all(axis=1)
        painel_final = painel_cruzado[mascara_completa].copy()
    else:
        painel_final = painel_cruzado.copy()

    if verbose and len(diag_tb) > 0:
        mensagem_diagnostico(
            diagnostico=diag_tb, painel_antes=painel_cruzado, painel_depois=painel_final, ano=ano_int
        )

    painel_final.attrs["diagnostico"] = diag_tb
    return painel_final
