# PORTING_NOTES.md — Especificação Técnica de Migração R -> Python

## 1. Mapeamento de Funções Exportadas

| Função R (original) | Assinatura R completa | Função Python (nova) | Tipo de Parâmetros e Defaults (Python) | Tipo de Retorno |
| :--- | :--- | :--- | :--- | :--- |
| `gerar_painel_pnadc` | `gerar_painel_pnadc(ano, vars_tri = NULL, vars_visita = NULL, balancear = TRUE, low_memory = FALSE, verbose = TRUE)` | `gerar_painel_pnadc` | `ano: int`, `vars_tri: Optional[Union[List[str], str]] = None`, `vars_visita: Optional[Union[List[str], str]] = None`, `balancear: bool = True`, `low_memory: bool = False`, `verbose: bool = True` | `pd.DataFrame` (com `df.attrs["diagnostico"]`) |
| `criar_ids_datazoom` | `criar_ids_datazoom(dados)` | `criar_ids_datazoom` | `dados: pd.DataFrame` | `pd.DataFrame` |
| `consolidar_base_habitacao` | `consolidar_base_habitacao(ano, vars_visita = vars_visita_default, verbose = TRUE)` | `consolidar_base_habitacao` | `ano: int`, `vars_visita: Optional[Union[List[str], str]] = vars_visita_default`, `verbose: bool = True` | `pd.DataFrame` |
| `diagnosticar_painel` | `diagnosticar_painel(painel, colunas = NULL)` | `diagnosticar_painel` | `painel: pd.DataFrame`, `colunas: Optional[List[str]] = None` | `pd.DataFrame` |
| `mensagem_diagnostico` | `mensagem_diagnostico(diagnostico, painel_antes, painel_depois, ano)` | `mensagem_diagnostico` | `diagnostico: pd.DataFrame`, `painel_antes: Optional[pd.DataFrame]`, `painel_depois: Optional[pd.DataFrame]`, `ano: int` | `str` |
| `vars_tri_default` | Vetor de strings | `vars_tri_default` | Lista de strings (`List[str]`) | `List[str]` |
| `vars_visita_default` | Vetor de strings | `vars_visita_default` | Lista de strings (`List[str]`) | `List[str]` |

---

## 2. Regras de Negócio Detalhadas & Casos de Borda

### 2.1 Identificação Longitudinal Data Zoom (`criar_ids_datazoom`)
- **Colunas Obrigatórias**: `UPA`, `V1008`, `V1014`, `V2008`, `V20081`, `V20082`, `V2007`, `UF`. Se faltar alguma, lança erro: `"Colunas obrigatorias ausentes para criar IDs Data Zoom: ..."`
- **Filtro de Exclusão de Linhas**:
  - `V2008 != 99` (Dia de nascimento válido)
  - `V20081 != 99` (Mês de nascimento válido)
  - `V20082 != 9999` (Ano de nascimento válido)
  - `V2007` não pode ser `NA` / `NaN` (Sexo preenchido)
- **Concatenação de Strings**:
  - `dia`: `V2008` preenchido com zero à esquerda até 2 dígitos (`zfill(2)`).
  - `mes`: `V20081` preenchido com zero à esquerda até 2 dígitos (`zfill(2)`).
  - `ano`: `V20082` convertido para string.
  - `sexo`: `V2007` convertido para string.
  - `uf`: `UF` convertido para string.
  - **`id_dom`**: `UPA + V1008 + V1014` (sem separador, concatenação de string). Ex: `UPA="110000016"`, `V1008="01"`, `V1014="10"` -> `"1100000160110"`.
  - **`id_ind`**: `id_dom + dia + mes + ano + sexo + uf` (sem separador, concatenação de string). Ex: `"110000016011022081992111"`.
- **Limpeza de Colunas Auxiliares**:
  - Remove as colunas temporárias `dia`, `mes`, `ano`, `sexo`, `uf` e as colunas originais de data de nascimento `V2008`, `V20081`, `V20082`.

### 2.2 Downcast de Tipos (`downcast_pnadc`)
- Converte para tipo inteiro de 32-bits (usando `Int32` do pandas que suporta `NA`) as seguintes colunas se presentes:
  `["V2007", "V2008", "V20081", "V20082", "V2001", "V2005", "V2009", "VD3004", "V3001", "VD4001", "VD4002", "VD4009", "VD4010", "V5001A", "V5002A", "S01013", "S01006", "S01010", "Ano", "Trimestre", "UF"]`

### 2.3 Consolidação de Habitação (Visita 1)
- Tenta baixar dados de Visita 1 para `ano` e para `ano - 1` (se `ano - 1 >= 2012`).
- Se o ano anterior falhar por erro de rede/IBGE, lança um `warning` não fatal e prossegue usando apenas `ano`. Se `ano` corrente falhar, lança erro fatal.
- Combina as duas tabelas (`pd.concat`).
- Agrupa por `id_dom` e escolhe a **primeira resposta não-NA** de cada variável de habitação (`dropna().iloc[0]`). Se todas forem NA, mantém a primeira.

### 2.4 Diagnóstico & Balanceamento
- Diagnóstico gera `total_linhas`, `com_dado`, `sem_dado`, `pct_disponivel = round((com_dado / total_linhas) * 100, 2)`.
- Se `balancear=True`, filtra mantendo apenas linhas onde todas as variáveis específicas de Visita 1 selecionadas sejam não-NA.
- Variáveis da base trimestral **NÃO** causam exclusão de linha no balanceamento.

### 2.5 Mock Provider & Testes Offline
- Permite registrar um provider customizado `pnadcpainel.set_mock_provider(fn)` para interceptar chamadas ao IBGE nos testes.
