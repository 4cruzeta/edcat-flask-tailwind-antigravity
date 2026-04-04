import logging
import os
from flask import Blueprint, render_template, request, jsonify, g
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

@g_calendar_agent_bp.route('/calendar/test', methods=['GET'])
def calendar_test(lang_code=None):
    """Renderiza o dashboard de testes do agente de calendário."""
    # O idioma vem do contexto da request, se customizado no Babel (no app Flask principal)
    lang_code = g.get('lang_code', 'pt_BR')
    return render_template('calendar_test.html', lang_code=lang_code)

@g_calendar_agent_bp.route('/calendar/ask', methods=['POST'])
def calendar_ask(lang_code=None):
    """Endpoint de chat síncrono para o agente de calendário (LangGraph)."""
    try:
        if "GOOGLE_API_KEY" not in os.environ:
            return jsonify({'response': 'Atenção desenvolvedor: GOOGLE_API_KEY ausente no .env!', 'status': 'error'}), 500

        data = request.json
        user_message = data.get('message', '') if data else ""
        
        if not user_message:
            return jsonify({'response': 'Mensagem vazia.', 'status': 'error'}), 400

        logging.info(f"[LangGraph Calendar] Recebido input: {user_message}")

        # Mensagem inicial do usuário no formato esperado pelo StateGraph
        inputs = {"messages": [HumanMessage(content=user_message)]}

        # Invoca o Grafo Síncronamente
        # Isso rodará o llm node, chamará as ferramentas via tool node se necessário, e continuará o loop
        result = calendar_graph_agent.invoke(inputs)

        # A última mensagem no dicionário 'messages' é a resposta textual final do LLM
        final_message = result['messages'][-1].content
        
        # O Gemini frequentemente retorna 'content' como uma lista de dicionários quando há mix de texto e actions
        if isinstance(final_message, list):
            text_parts = [
                part["text"] if isinstance(part, dict) and "text" in part else str(part)
                for part in final_message
            ]
            final_message = " ".join(text_parts)
        
        if not final_message or str(final_message).strip() == "":
            final_message = "Ação concluída com sucesso (O agente não retornou texto)."

        # Garante que seja sempre uma string
        final_message = str(final_message)

        return jsonify({"response": final_message, "status": "success"})

    except Exception as e:
        logging.error(f"[LangGraph Calendar] Erro: {e}", exc_info=True)
        return jsonify({'response': f"Vixe, algo deu errado: {str(e)}", 'status': 'error'}), 500
