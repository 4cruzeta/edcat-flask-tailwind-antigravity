import os
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

from .tools import CALENDAR_TOOLS

# Carregar variáveis (importante para GOOGLE_API_KEY)
load_dotenv()

# Instanciar o modelo usando langchain-google-genai
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.0
).bind_tools(CALENDAR_TOOLS)

class State(TypedDict):
    """Estado do LangGraph contendo um histórico de mensagens."""
    messages: Annotated[list[BaseMessage], add_messages]

def llm_node(state: State):
    """Nó que aciona o modelo Gemini com acesso às ferramentas de calendário."""
    system_prompt = SystemMessage(
        content=(
            "Você é um assistente de calendário preciso. Seu objetivo é ajudar o usuário "
            "a gerenciar o Google Calendar dele. Sempre responda no idioma do usuário ou "
            "em português por padrão.\n\n"
            "Regras de Ouro:\n"
            "1. Sempre converta expressões naturais de tempo ('meio dia amanhã') usando a "
            "ferramenta 'parse_natural_language_datetime_tool' ANTES de tentar criar o evento, "
            "pois a API exige estritamente o formato ISO 8601 UTC.\n"
            "2. Responda num tom direto e amigável.\n"
            "3. Se falhar ao buscar o ID de um evento, avise que não encontrou."
        )
    )
    
    # Adicionamos o prompt de sistema e repassamos ao modelo
    messages = [system_prompt] + state["messages"]
    response = llm.invoke(messages)
    
    return {"messages": [response]}

# Montar o Grafo de Estados (StateGraph)
graph_builder = StateGraph(State)

# Adicionar os NÓS
graph_builder.add_node("llm", llm_node)
graph_builder.add_node("tools", ToolNode(tools=CALENDAR_TOOLS))

# Adicionar as ARESTAS (Fluxo lógico)
graph_builder.add_edge(START, "llm")
# tools_condition roteia automaticamente se o LLM pediu ferramenta ou não
graph_builder.add_conditional_edges("llm", tools_condition)
graph_builder.add_edge("tools", "llm")

# Compilar o agente pronto para uso
calendar_graph_agent = graph_builder.compile()
