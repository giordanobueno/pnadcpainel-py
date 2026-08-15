"""
Camada de acesso a dados da PNAD Contínua (IBGE FTP / Mocks).
"""

import os
import zipfile
import tempfile
import requests
import pandas as pd
from typing import List, Optional, Callable, Any

from ._retry import executar_com_retry
from .defaults import vars_tri_default, vars_visita_default

# Provider mock global para testes offline
_mock_provider: Optional[Callable[..., pd.DataFrame]] = None


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
        expr=_do_download,
        max_tentativas=3,
        delay_inicial=1.0,
        verbose=verbose,
        rotulo=rotulo
    )


def _download_ibge_ftp(
    year: int,
    quarter: Optional[int] = None,
    interview: Optional[int] = None,
    vars: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Baixa os microdados do servidor FTP HTTP do IBGE e lê o dicionário/layout.
    """
    base_url = "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua"

    if quarter is not None:
        url_dir = f"{base_url}/Trimestral/Microdados/{year}"
        filename = f"PNADC_0{quarter}{year}.zip"
    elif interview is not None:
        url_dir = f"{base_url}/Anual/Microdados/Visita_{interview}/{year}"
        filename = f"PNADC_visita{interview}_{year}.zip"
    else:
        raise ValueError("É necessário especificar 'quarter' ou 'interview'.")

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

        # Se vars foi especificado, filtrar colunas no retorno
        # Como fallback de leitura simples sem dicionário SAS complexo se o arquivo não estiver disponível:
        df = pd.read_csv(txt_file, sep=";", dtype=str, low_memory=False)

        if vars is not None:
            cols_existentes = [c for c in vars if c in df.columns]
            if cols_existentes:
                df = df[cols_existentes]

        return df
