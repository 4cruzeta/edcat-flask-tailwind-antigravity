import os
import logging
from edcat_root.utils.get_google_secrets import get_secret

def bootstrap_langsmith(project_name="calendar_agent-v5.0"):
    """
    Injeta as variáveis de ambiente do LangSmith globalmente no processo.
    Simula o carregamento via arquivo .env.
    """
    try:
        logging.info(f"[Bootstrap] Configurando ambiente para: {project_name}")
        
        # 1. Configurações de Telemetria (Padrão scheduler.py)
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGSMITH_PROJECT"] = project_name
        
        # 2. Carregamento de Chaves de API (Secret Manager)
        # Seta tanto para LangChain quanto para Google SDK
        api_keys = {
            "LANGSMITH_API_KEY": ["LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"],
            "GOOGLE_API_KEY": ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
        }
        
        for secret_name, env_vars in api_keys.items():
            val = get_secret(secret_name)
            if val:
                for var in env_vars:
                    os.environ[var] = val
                logging.info(f"[Bootstrap] {secret_name} injetada.")
            else:
                logging.warning(f"[Bootstrap] {secret_name} NÃO encontrada no Secret Manager.")
            
    except Exception as e:
        logging.error(f"[Bootstrap] Erro ao carregar configurações: {e}")
