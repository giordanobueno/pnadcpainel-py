"""
Validação cross-language entre saídas do R e Python através de artefatos serializados (Parquet/JSON/CSV).
"""

import os
import json
import hashlib
import tempfile
import pytest
import pandas as pd
from pnadcpainel._ibge_source import set_mock_provider
from pnadcpainel.core import gerar_painel_pnadc
from pnadcpainel.diagnostico import diagnosticar_painel
from tests.fixtures.synthetic_pnadc import criar_mock_provider


def _compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def test_geracao_de_artefatos_cross_language():
    set_mock_provider(criar_mock_provider())

    painel = gerar_painel_pnadc(ano=2023, verbose=False)
    diag = painel.attrs["diagnostico"]

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = os.path.join(tmpdir, "panel.parquet")
        schema_path = os.path.join(tmpdir, "schema.json")
        diag_path = os.path.join(tmpdir, "diagnostico.csv")
        meta_path = os.path.join(tmpdir, "metadata.json")

        # 1. Salvar Parquet (limpando attrs para permitir serialização PyArrow)
        painel_clean = painel.copy()
        painel_clean.attrs = {}
        painel_clean.to_parquet(parquet_path, index=False)

        # 2. Salvar Schema
        schema_info = {col: str(dtype) for col, dtype in painel.dtypes.items()}
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema_info, f, indent=2)

        # 3. Salvar Diagnóstico
        diag.to_csv(diag_path, index=False)

        # 4. Salvar Metadata
        metadata = {
            "ano": 2023,
            "shape": list(painel.shape),
            "columns": list(painel.columns),
            "hashes": {
                "panel_parquet": _compute_sha256(parquet_path),
                "schema_json": _compute_sha256(schema_path),
                "diagnostico_csv": _compute_sha256(diag_path),
            }
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Asserções de validação de estrutura dos artefatos
        assert os.path.exists(parquet_path)
        assert os.path.exists(schema_path)
        assert os.path.exists(diag_path)
        assert os.path.exists(meta_path)

        read_panel = pd.read_parquet(parquet_path)
        assert len(read_panel) == len(painel)
        assert list(read_panel.columns) == list(painel.columns)
        assert read_panel["id_dom"].equals(painel["id_dom"])
        assert read_panel["id_ind"].equals(painel["id_ind"])
