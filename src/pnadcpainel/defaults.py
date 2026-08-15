"""
Variáveis padrão e chaves obrigatórias da PNAD Contínua (IBGE).
"""

from typing import List

# Variáveis padrão da base trimestral para construção do painel de pessoas
vars_tri_default: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "Trimestre", "UF",
    "V2007", "V2008", "V20081", "V20082",
    "V2001", "V2005", "V2009",
    "VD3004", "V3001",
    "VD4001", "VD4002", "VD4009", "VD4020", "VD4010"
]

# Variáveis padrão de Visita 1 (Domicílio) para caracterização domiciliar e renda per capita
vars_visita_default: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "UF",
    "V5001A",
    "VD5002", "V5002A",
    "S01013", "S01006", "S01010"
]

# Chaves obrigatórias que sempre devem ser baixadas na base trimestral
chaves_obrig_tri: List[str] = [
    "UPA", "V1008", "V1014", "V2008", "V20081", "V20082", "V2007", "UF", "Ano", "Trimestre"
]

# Chaves obrigatórias que sempre devem ser baixadas na base de Visita 1
chaves_obrig_visita: List[str] = [
    "UPA", "V1008", "V1014", "Ano", "UF"
]
