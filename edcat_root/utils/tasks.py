import os
import json
import logging
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import datetime

# Logger para tarefas
logger = logging.getLogger("edcat.tasks")

def enqueue_agent_task(payload: dict, queue_name: str = "calendar-agent-queue"):
    """
    Enfileira uma tarefa para o processamento do agente.
    Suporta Cloud Tasks em produção e processamento síncrono/threading em dev.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("CLOUD_RUN_LOCATION", "us-central1")
    
    # Se não houver projeto (ambiente local), simulamos o worker
    if not project or os.environ.get("LOCAL_DEV") == "true":
        logger.info("[Tasks] Modo LOCAL: Simulando despacho de tarefa.")
        return _simulate_local_task(payload)

    # Configuração do Cloud Tasks
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue_name)
    
    # O worker será um endpoint interno do nosso próprio app
    # Em produção, o Cloud Run fornece a URL via variável de ambiente
    base_url = os.environ.get("SERVICE_URL") 
    url = f"{base_url}/_ah/tasks/process_agent"

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(payload).encode(),
        }
    }

    # Opcional: Adicionar autenticação OIDC para o Cloud Run
    service_account_email = os.environ.get("SERVICE_ACCOUNT_EMAIL")
    if service_account_email:
        task["http_request"]["oidc_token"] = {
            "service_account_email": service_account_email,
        }

    try:
        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"[Tasks] Tarefa criada com sucesso: {response.name}")
        return response.name
    except Exception as e:
        logger.error(f"[Tasks] Erro ao criar tarefa no Cloud Tasks: {e}")
        # Fallback para processamento imediato em caso de erro na fila
        return _simulate_local_task(payload)

def run_agent_with_retry(agent, message, session_id, metadata=None, max_retries=3, initial_delay=1):
    """
    Executa a chamada ao agente (Harness) aplicando tratamento e retentativas com backoff exponencial.
    Ideal para proteger contra erros de rate-limiting (Gemini) ou falhas transientes no Firestore/Calendar.
    """
    import time
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Harness] Invocando agente (Tentativa {attempt}/{max_retries})...")
            return agent.invoke(message, session_id=session_id, metadata=metadata)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"[Harness] Falha definitiva após {max_retries} tentativas: {e}", exc_info=True)
                raise
            logger.warning(f"[Harness] Tentativa {attempt} falhou: {e}. Retentando em {delay}s...")
            time.sleep(delay)
            delay *= 2

def _simulate_local_task(payload: dict):
    """
    Simula a execução do agente localmente de forma SÍNCRONA.
    Usa o singleton do worker para garantir que o mesmo MemorySaver
    seja compartilhado entre as requisições (preservando o contexto multi-turno).
    """
    try:
        # Importação Lazy do singleton
        from edcat_root.g_calendar_agent.worker import get_agent
        
        session_id = payload['session_id']
        message = payload['message']
        
        logger.info(f"[Tasks] [LOCAL] Iniciando processamento SÍNCRONO para: {session_id}")
        agent = get_agent()
        
        # Invocação usando Harness de Resiliência (Retentativas)
        response = run_agent_with_retry(
            agent=agent,
            message=message,
            session_id=session_id,
            metadata=payload.get('metadata')
        )
        logger.info(f"[Tasks] [LOCAL] Processamento síncrono finalizado com sucesso.")
        return response
    except Exception as e:
        logger.error(f"[Tasks] [LOCAL] Erro na execução síncrona do agente: {e}", exc_info=True)
        return "Erro técnico no processamento."
