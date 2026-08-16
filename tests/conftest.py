"""
Configurações e fixtures globais do Pytest.
"""

import pytest
from pnadcpainel import set_mock_provider


@pytest.fixture(autouse=True)
def clean_mock_provider():
    """Garante limpeza do mock provider antes e depois de cada teste."""
    set_mock_provider(None)
    yield
    set_mock_provider(None)
