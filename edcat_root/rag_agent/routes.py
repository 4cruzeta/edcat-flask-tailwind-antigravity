from flask import Blueprint, request, jsonify, current_app, render_template, g
from edcat_root.auth import login_required, load_user_profile

rag_agent_bp = Blueprint("rag_agent_bp", __name__)

@rag_agent_bp.route("/agente_ia", methods=["GET"])
@login_required
@load_user_profile
def render_chat(lang_code):
    """Renderiza a página visual (Frontend) do Agente."""
    return render_template("chat_agent.html")

@rag_agent_bp.route("/api/chat", methods=["POST"])
@login_required
@load_user_profile
def chat(lang_code):
    """Recebe mensagem do front-end, processa com Langchain (RAG) e devolve a string."""
    data = request.get_json()
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "Nenhuma mensagem recebida."}), 400

    try:
        # Acesso preguiçoso ao Agente RAG.
        # Se ele falhou no __init__, ele devolve uma mensagem de erro controlada invés de quebrar o app.
        rag_agent = getattr(current_app, 'rag_agent', None)
        
        if not rag_agent:
            return jsonify({"response": "Erro interno: Agente LangChain não foi acoplado à aplicação."})
            
        assistant_response = rag_agent.invoke({"messages": [("user", user_message)]})

        return jsonify({"response": assistant_response})

    except Exception as e:
        error_message = f"Ocorreu um erro ao processar sua mensagem: {e}"
        print(f"RAG Endpoint Error: {error_message}")
        return jsonify({"error": "O servidor LangChain encontrou um erro."}), 500
