"""
Utilitário de retry com backoff exponencial para requisições de rede.
"""

import time
from typing import Callable, Any, Optional


def executar_com_retry(
    func: Callable[[], Any],
    max_tentativas: int = 3,
    delay_inicial: float = 1.0,
    verbose: bool = True,
    rotulo: str = "Requisição"
) -> Any:
    """
    Executa uma função com repetição (retry) e backoff exponencial em caso de erro.

    Parameters
    ----------
    func : Callable[[], Any]
        Função a ser executada sem argumentos.
    max_tentativas : int, default 3
        Número máximo de tentativas.
    delay_inicial : float, default 1.0
        Tempo inicial de espera em segundos.
    verbose : bool, default True
        Se True, exibe mensagens de progresso.
    rotulo : str, default "Requisição"
        Rótulo identificador da operação para exibição de log.

    Returns
    -------
    Any
        Retorno da função executada.
    """
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
                raise RuntimeError(
                    f"{rotulo} falhou após {max_tentativas} tentativas. Erro final: {e}"
                ) from e
        tentativa += 1
