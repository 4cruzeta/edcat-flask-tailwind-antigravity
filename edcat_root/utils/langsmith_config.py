import os
import logging
from contextlib import contextmanager

@contextmanager
def tracing_context(project_name="default", enabled=True):
    """
    Context Manager dummy para LangSmith. 
    Se a API KEY estiver presente, o LangChain cuidará do tracing automaticamente
    devido às variáveis de ambiente setadas no agent.py.
    """
    try:
        logging.info(f"[LangSmith] Iniciando contexto de tracing: {project_name}")
        yield
    finally:
        logging.info(f"[LangSmith] Finalizando contexto de tracing.")
