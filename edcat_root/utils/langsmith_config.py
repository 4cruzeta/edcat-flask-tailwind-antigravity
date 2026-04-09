import os
import logging
from contextlib import contextmanager

@contextmanager
def tracing_context(project_name="default", enabled=True):
    """
    Context Manager para isolamento de telemetria no LangSmith.
    Define o projeto atual e restaura o anterior após a execução.
    """
    if not enabled:
        yield
        return

    # Salva estado anterior
    old_project = os.environ.get("LANGCHAIN_PROJECT")
    
    # Seta novas variáveis
    os.environ["LANGCHAIN_PROJECT"] = project_name
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    
    # O LangChain às vezes espera LANGCHAIN_API_KEY em vez de LANGSMITH_API_KEY
    if "LANGSMITH_API_KEY" in os.environ and "LANGCHAIN_API_KEY" not in os.environ:
        os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]

    try:
        logging.info(f"[LangSmith] Telemetria ativa no projeto: {project_name}")
        yield
    finally:
        # Restaura estado anterior
        if old_project:
            os.environ["LANGCHAIN_PROJECT"] = old_project
        else:
            os.environ.pop("LANGCHAIN_PROJECT", None)
        logging.info(f"[LangSmith] Telemetria finalizada.")
