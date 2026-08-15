# pnadcpainel 🐍

> **Painel Consolidado Pessoa e Domicílio da PNAD Contínua (IBGE)**
> *Implementação em Python com metodologia de identificação longitudinal do Data Zoom (PUC-Rio).*

[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://pypi.org/project/pnadcpainel/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Também disponível em R

Este pacote é a implementação oficial em **Python** do `pnadcpainel`. Se você programa em R ou prefere utilizar o ecossistema R/CRAN, acesse o repositório original:
👉 **[giordanobueno/pnadcpainel (Versão R)](https://github.com/giordanobueno/pnadcpainel)**

A sintaxe e as opções de chamada foram projetadas para serem **praticamente idênticas** entre as duas linguagens.

---

## ⚠️ Nota de Isenção

Este pacote é uma iniciativa independente criada para facilitar a pesquisa quantitativa com dados da PNAD Contínua no ecossistema Python. A metodologia de identificação dos domicílios e indivíduos segue as diretrizes desenvolvidas pelo projeto **Data Zoom (PUC-Rio)**. Este pacote **não é um produto oficial** do IBGE nem do Data Zoom.

Para maiores detalhes sobre a metodologia original e publicações acadêmicas do Data Zoom, acesse:
🔗 [datazoom.puc-rio.br](https://www.econ.puc-rio.br/datazoom/)

---

## 🚀 Instalação

```bash
pip install pnadcpainel
```

Ou instale a versão de desenvolvimento diretamente do GitHub:

```bash
pip install git+https://github.com/giordanobueno/pnadcpainel-py.git
```

---

## 💻 Exemplo Rápido de Uso

```python
from pnadcpainel import gerar_painel_pnadc, diagnosticar_painel

# Gera o painel consolidado para o ano de 2023
painel_2023 = gerar_painel_pnadc(ano=2023)

# Exibe as primeiras linhas do DataFrame
print(painel_2023.head())

# Visualizar a tabela de diagnóstico de preenchimento
print(painel_2023.attrs["diagnostico"])
```

---

## ⚙️ Customização de Variáveis

Você pode selecionar apenas as variáveis de seu interesse para acelerar o download e economizar memória RAM:

```python
painel_custom = gerar_painel_pnadc(
    ano=2023,
    vars_tri=["V2009", "VD4020"],        # Idade e Renda habitualmente recebida
    vars_visita=["VD5002", "S01013"],    # Renda per capita e Água encanada
    balancear=True
)
```

Para baixar todas as colunas disponíveis:

```python
painel_completo = gerar_painel_pnadc(
    ano=2023,
    vars_tri="todas",
    vars_visita="todas"
)
```

---

## 🧠 Gestão de Memória RAM

Para computadores com pouca memória RAM ou ao processar anos extensos, ative a opção `low_memory=True`:

```python
painel_leve = gerar_painel_pnadc(
    ano=2023,
    low_memory=True
)
```

Esta opção grava arquivos intermediários de cada trimestre em disco temporário e os combina ao final.

---

## 📊 Atributo e Função de Diagnóstico

No resultado retornado (`DataFrame`), a tabela de diagnóstico do painel fica salva no dicionário de atributos `.attrs`:

```python
diag_df = painel_2023.attrs["diagnostico"]
print(diag_df)
```

Você também pode chamar a função explícita `diagnosticar_painel`:

```python
diag_df = diagnosticar_painel(painel_2023, colunas=["VD5002", "S01013"])
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [`LICENSE`](LICENSE) para mais detalhes.
