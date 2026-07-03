import logging
from flask import Blueprint, render_template, request, jsonify
from edcat_root.auth import login_required, load_user_profile

# Importamos o worker para garantir que suas rotas sejam registradas
from .worker import worker_bp, get_agent

# Defina o Blueprint principal para a interface Web
g_calendar_agent_bp = Blueprint(
    'g_calendar_agent',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Registramos o worker_bp como um "filho" ou apenas compartilhamos as rotas
# Dependendo de como o create_app registra, podemos adicionar as rotas do worker aqui
g_calendar_agent_bp.register_blueprint(worker_bp)

@g_calendar_agent_bp.route('/calendar_agent', methods=['GET'])
@login_required
@load_user_profile
def calendar_agent_page(lang_code):
    """Renderiza a página principal do agente de agendamento."""
    return render_template('calendar_agent.html', lang_code=lang_code)

@g_calendar_agent_bp.route('/calendar_agent/ask', methods=['POST'])
@login_required
@load_user_profile
def calendar_ask(lang_code):
    """
    Endpoint de chat SÍNCRONO para o agente de agendamento.
    Invoca o agente diretamente e retorna a resposta sem polling.
    Em produção (Cloud Run), o Cloud Tasks dispara o worker de forma assíncrona.
    """
    try:
        data = request.json
        user_message = data.get('message', '') if data else ""
        session_id = data.get('session_id', 'test_session')
        
        if not user_message:
            return jsonify({'response': 'Mensagem vazia.', 'status': 'error'}), 400

        logging.info(f"[Routes] [Sessão: {session_id}] Processando mensagem: {user_message[:30]}...")

        # Invoca o agente diretamente (a mesma instância singleton)
        from edcat_root.utils.tasks import run_agent_with_retry
        agent = get_agent()
        response_text = run_agent_with_retry(
            agent=agent,
            message=user_message,
            session_id=session_id,
            metadata={"lang": lang_code, "source": "web_cli"}
        )

        logging.info(f"[Routes] [Sessão: {session_id}] Resposta gerada: {response_text[:50]}...")

        return jsonify({
            "response": response_text,
            "status": "completed"
        })

    except Exception as e:
        logging.error(f"[Routes] Erro ao processar: {e}", exc_info=True)
        return jsonify({'response': "Erro ao processar sua mensagem.", 'status': 'error'}), 500
