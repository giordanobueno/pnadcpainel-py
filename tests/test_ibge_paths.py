"""
Testes de resolução de rotas HTTP/FTP oficiais do IBGE.
"""

import pytest
from unittest.mock import MagicMock, patch
from pnadcpainel._ibge_source import _resolve_ibge_filename


def test_rota_trimestral_2023():
    html_mock = """
    <html>
      <a href="PNADC_012023_20250815.zip">PNADC_012023_20250815.zip</a>
    </html>
    """
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html_mock
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = _resolve_ibge_filename(
            "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/2023",
            r"PNADC_012023(?:_\d{8})?\.zip"
        )
        assert res == "PNADC_012023_20250815.zip"


def test_rota_visita1_oficial_2023():
    html_mock = """
    <html>
      <a href="/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Anual/Microdados/Visita/Visita_1/Dados/PNADC_2023_visita1_20250822.zip">PNADC_2023_visita1_20250822.zip</a>
    </html>
    """
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html_mock
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = _resolve_ibge_filename(
            "https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Anual/Microdados/Visita/Visita_1/Dados",
            r"PNADC_2023_visita1(?:_\d{8})?\.zip"
        )
        assert res == "PNADC_2023_visita1_20250822.zip"


def test_nome_pnadc_2023_visita1_com_data():
    html_mock = """
    <html>
      <a href="PNADC_2023_visita1_20240101.zip">PNADC_2023_visita1_20240101.zip</a>
      <a href="PNADC_2023_visita1_20250822.zip">PNADC_2023_visita1_20250822.zip</a>
    </html>
    """
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html_mock
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        res = _resolve_ibge_filename(
            "https://ftp.ibge.gov.br/test",
            r"PNADC_2023_visita1(?:_\d{8})?\.zip"
        )
        # Deve escolher a versão de publicação mais recente (20250822 > 20240101)
        assert res == "PNADC_2023_visita1_20250822.zip"


def test_arquivo_inexistente_lanca_erro_claro():
    html_mock = "<html><body>Vazio</body></html>"
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html_mock
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Nenhum arquivo correspondente ao padrão"):
            _resolve_ibge_filename(
                "https://ftp.ibge.gov.br/test",
                r"PNADC_999999\.zip"
            )
