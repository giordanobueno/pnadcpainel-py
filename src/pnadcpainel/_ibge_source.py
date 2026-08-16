"""
Camada de acesso a dados da PNAD Contínua (IBGE FTP / Mocks) com suporte a
descoberta dinâmica de arquivos e leitura de dicionários de largura fixa (FWF).
"""

import os
import re
import io
import zipfile
import tempfile
import warnings
import requests
import pandas as pd
from typing import List, Optional, Callable, Dict, Tuple, Any

from ._retry import executar_com_retry
from .defaults import (
    vars_tri_default,
    vars_visita_default,
    chaves_obrig_tri,
    chaves_obrig_visita,
)

# Provider mock global para testes offline
_mock_provider: Optional[Callable[..., pd.DataFrame]] = None

# Caches em memória para nomes de arquivos e especificações de leiaute SAS
_filename_cache: Dict[Tuple[str, str], str] = {}
_dict_cache: Dict[Tuple[bool, int, int], Tuple[List[Tuple[int, int]], List[str]]] = {}


def set_mock_provider(provider: Optional[Callable[..., pd.DataFrame]]) -> None:
    """Define ou remove o provider de mock para testes unitários/integração."""
    global _mock_provider
    _mock_provider = provider


def get_mock_provider() -> Optional[Callable[..., pd.DataFrame]]:
    """Retorna o provider de mock ativo, se houver."""
    return _mock_provider


def get_pnadc_internal(
    year: int,
    quarter: Optional[int] = None,
    interview: Optional[int] = None,
    vars: Optional[List[str]] = None,
    design: bool = False,
    labels: bool = False,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Wrapper interno de download de dados da PNADc com suporte a retry e mocks.
    """
    mock = get_mock_provider()
    if mock is not None and callable(mock):
        return mock(
            year=year,
            quarter=quarter,
            interview=interview,
            vars=vars,
            design=design,
            labels=labels
        )

    rotulo = (
        f"Download Trimestre {quarter}/{year}" if quarter is not None
        else (f"Download Visita {interview}/{year}" if interview is not None else f"Download PNADc {year}")
    )

    def _do_download() -> pd.DataFrame:
        return _download_ibge_ftp(year=year, quarter=quarter, interview=interview, vars=vars)

    return executar_com_retry(
        func=_do_download,
        max_tentativas=3,
        delay_inicial=1.0,
        verbose=verbose,
        rotulo=rotulo
    )


def _resolve_ibge_filename(url_dir: str, pattern_str: str) -> str:
    """
    Busca no índice do diretório HTTP do IBGE o nome do arquivo .zip que corresponde
    ao padrão regex informado (ex: PNADC_012023_YYYYMMDD.zip ou PNADC_2023_visita1_YYYYMMDD.zip).
    Aceita links relativos e absolutos em tags href HTML.
    """
    cache_key = (url_dir, pattern_str)
    if cache_key in _filename_cache:
        return _filename_cache[cache_key]

    resp = requests.get(url_dir, timeout=30)
    resp.raise_for_status()

    # Extrair todos os links href HTML
    href_links = re.findall(r'href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)

    regex = re.compile(pattern_str, re.IGNORECASE)
    matches: List[str] = []

    for link in href_links:
        # Extrair nome do arquivo basename descartando caminhos relativos/absolutos
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
    """
    Faz o parsing de um arquivo de input SAS do IBGE (ex: input_PNADC_trimestral.txt),
    extraindo as colunas, posições iniciais e larguras de cada variável.
    """
    colspecs: List[Tuple[int, int]] = []
    names: List[str] = []

    # Padrão SAS: @00001 UPA $9. ou @00010 V1008 $2. ou @00014 V1022 1.
    pattern = re.compile(r"@(\d+)\s+([A-Za-z0-9_]+)\s+\$?(\d+)\.")

    for line in content_text.splitlines():
        match = pattern.search(line)
        if match:
            start_pos = int(match.group(1)) - 1  # 1-indexed para 0-indexed
            var_name = match.group(2)
            length = int(match.group(3))
            end_pos = start_pos + length

            colspecs.append((start_pos, end_pos))
            names.append(var_name)

    return colspecs, names


def _get_sas_input_spec(is_visita: bool, interview: int = 1, year: int = 2023) -> Tuple[List[Tuple[int, int]], List[str]]:
    """
    Obtém a especificação de largura fixa (colspecs e names) do dicionário IBGE na pasta Documentacao.
    """
    cache_key = (is_visita, interview, year)
    if cache_key in _dict_cache:
        return _dict_cache[cache_key]

    base_doc_url = "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua"
    if is_visita:
        doc_dir = f"{base_doc_url}/Anual/Microdados/Visita/Visita_{interview}/Documentacao"
    else:
        doc_dir = f"{base_doc_url}/Trimestral/Microdados/Documentacao"

    resp = requests.get(doc_dir, timeout=30)
    resp.raise_for_status()

    href_links = re.findall(r'href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)

    # Buscar arquivo de dicionário/input: aceitar input_PNADC_2023_visita1_*.txt, input_*.txt, Dicionario_*.zip ou *.txt
    match_file = None

    # Tentar match estrito de input de visita se is_visita
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
    """
    Baixa os microdados do servidor FTP HTTP do IBGE e lê o dicionário/layout de largura fixa.
    """
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

    # Fazer download para pasta temporária
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

        # Verificar se o arquivo TXT usa delimitador ';' (fallback para CSV sintético) ou largura fixa (FWF)
        with open(txt_file, "r", encoding="latin1", errors="ignore") as f_check:
            first_line = f_check.readline()

        if ";" in first_line:
            df = pd.read_csv(txt_file, sep=";", dtype=str, low_memory=False)
        else:
            colspecs, names = _get_sas_input_spec(is_visita=is_visita, interview=interview or 1, year=year)
            df = pd.read_fwf(txt_file, colspecs=colspecs, names=names, dtype=str)

        # Validação de chaves obrigatórias
        chaves_obrig = chaves_obrig_visita if is_visita else chaves_obrig_tri
        chaves_faltantes = [k for k in chaves_obrig if k not in df.columns]
        if chaves_faltantes:
            raise RuntimeError(f"Colunas obrigatorias ausentes no arquivo baixado: {', '.join(chaves_faltantes)}")

        if vars is not None:
            cols_existentes = [c for c in vars if c in df.columns]
            cols_faltantes = [c for c in vars if c not in df.columns]
            if cols_faltantes:
                warnings.warn(
                    f"Variaveis solicitadas nao encontradas no arquivo: {', '.join(cols_faltantes)}",
                    UserWarning
                )
            if cols_existentes:
                df = df[cols_existentes]

        return df
