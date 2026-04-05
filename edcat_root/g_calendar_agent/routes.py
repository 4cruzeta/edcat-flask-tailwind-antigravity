import logging
import os
from flask import Blueprint, render_template, request, jsonify, g
from edcat_root.auth import login_required, load_user_profile
from langchain_core.messages import HumanMessage
from .agent import calendar_graph_agent

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
        
        if not user_message:
            return jsonify({'response': 'Mensagem vazia.', 'status': 'error'}), 400

        logging.info(f"[LangGraph Calendar] Recebido input: {user_message}")

        # Mensagem inicial do usuário no formato esperado pelo StateGraph
        inputs = {"messages": [HumanMessage(content=user_message)]}

        # A invocação agora retorna diretamente o texto final higienizado
        # Se houver erro de configuração (ex: falta de segredos), o Agente retorna o erro controlado.
        final_message = calendar_graph_agent.invoke(inputs)

        return jsonify({"response": final_message, "status": "success"})

    except Exception as e:
        logging.error(f"[LangGraph Calendar] Erro: {e}", exc_info=True)
        return jsonify({'response': f"Vixe, algo deu errado: {str(e)}", 'status': 'error'}), 500
