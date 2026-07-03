import logging
from flask import Blueprint, request, jsonify
from .agent import CalendarAgent

worker_bp = Blueprint('calendar_worker', __name__)

# Instância única do agente para evitar re-inicialização pesada em cada tarefa
# O Harness é inicializado uma vez.
_agent_instance = None

def get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = CalendarAgent()
    return _agent_instance

@worker_bp.route('/_ah/tasks/process_agent', methods=['POST'])
def process_agent_task(lang_code=None):
    """
    Endpoint invocado pelo Cloud Tasks para processar a lógica do agente
    de forma assíncrona.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        message = data.get('message')
        session_id = data.get('session_id')
        metadata = data.get('metadata', {})

        if not message or not session_id:
            return jsonify({"status": "error", "message": "Missing message or session_id"}), 400

        logging.info(f"[Worker] Processando tarefa para Sessão: {session_id}")

        # 1. Executa o Agente (Harness) com retentativas/resiliência de fila
        from edcat_root.utils.tasks import run_agent_with_retry
        agent = get_agent()
        response = run_agent_with_retry(
            agent=agent,
            message=message,
            session_id=session_id,
            metadata=metadata
        )

        logging.info(f"[Worker] Resposta gerada para {session_id}: {response[:50]}...")

        return jsonify({"status": "success", "response": response}), 200

    except Exception as e:
        logging.error(f"[Worker] Erro crítico no processamento da tarefa: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
