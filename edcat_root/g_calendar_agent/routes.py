import logging
import os
from flask import Blueprint, render_template, request, jsonify, g
from edcat_root.auth import login_required, load_user_profile
from langchain_core.messages import HumanMessage
from .agent import CalendarAgent
calendar_graph_agent = CalendarAgent()

# Inicialize o logger do Blueprint
logging.basicConfig(level=logging.INFO)

# Defina o Blueprint
g_calendar_agent_bp = Blueprint(
    'g_calendar_agent',
    __name__,
    template_folder='templates',
    static_folder='static'
)

@g_calendar_agent_bp.route('/calendar_agent', methods=['GET'])
@login_required
@load_user_profile
def calendar_agent_page(lang_code):
    """Renderiza a página principal do agente de agendamento."""
    # O idioma vem do contexto da request/prefixo da blueprint
    return render_template('calendar_agent.html', lang_code=lang_code)

@g_calendar_agent_bp.route('/calendar_agent/ask', methods=['POST'])
@login_required
@load_user_profile
def calendar_ask(lang_code):
    """Endpoint de chat síncrono para o agente de agendamento."""
    try:
        data = request.json
        user_message = data.get('message', '') if data else ""
        session_id = data.get('session_id', 'test_session') # Identificador de conversa
        
        if not user_message:
            return jsonify({'response': 'Mensagem vazia.', 'status': 'error'}), 400

        logging.info(f"[LangGraph Calendar] [Session: {session_id}] Recebido input: {user_message}")

        # A invocação agora recebe diretamente o texto e a sessão
        final_message = calendar_graph_agent.invoke(user_message, session_id=session_id)

        return jsonify({"response": final_message, "status": "success"})

    except Exception as e:
        logging.error(f"[LangGraph Calendar] Erro: {e}", exc_info=True)
        return jsonify({'response': f"Vixe, algo deu errado no processamento: {str(e)}", 'status': 'error'}), 500
