import os
import logging
from typing import List, Dict, Optional

# Deep Agents & LangChain
from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import tracing_context
from langgraph.checkpoint.memory import MemorySaver

# Project utilities
from .tools import CALENDAR_TOOLS
from .harness import register_calendar_harness
from edcat_root.utils.env_bootstrap import bootstrap_langsmith

# Registra o perfil do Harness para este blueprint
register_calendar_harness()

class CalendarAgent:
    def __init__(self, model_name: str = "google_genai:gemini-3.5-flash"):
        """
        Inicializa o Agente de Calendário usando o Harness e o State em memória (MemorySaver).
        Sem envolvimento de banco de dados durante a conversa — somente RAM.
        """
        try:
            bootstrap_langsmith()
            
            # Inicializa o Checkpointer de Estado (Persistência em RAM — sem latência de rede)
            self.checkpointer = MemorySaver()
            
            # Criação do Agente via Harness acoplado ao Checkpointer
            self.agent = create_deep_agent(
                model=model_name,
                tools=CALENDAR_TOOLS,
                checkpointer=self.checkpointer
            )
            logging.info(f"[CalendarAgent] Harness inicializado com Memória de Estado (MemorySaver).")
            
        except Exception as e:
            logging.error(f"[CalendarAgent] Erro na inicialização: {e}")
            raise

    def invoke(self, message: str, session_id: str, metadata: Optional[Dict] = None) -> str:
        """
        Executa um turno do agente usando o LangGraph State.
        Retorna a resposta final como texto limpo.
        """
        try:
            # Prepara o input conforme o State do LangGraph
            input_text = message
            if metadata and "phone" in metadata:
                input_text = f"[SISTEMA: Usuário WhatsApp {metadata['phone']}]\n{input_text}"
            
            # Configuração da Thread (Chave do State)
            config = {"configurable": {"thread_id": session_id}}
            
            with tracing_context(project_name="edcat-v2-calendar"):
                # No LangGraph, passamos apenas a nova mensagem. 
                # O Checkpointer carrega o histórico automaticamente.
                input_payload = {"messages": [HumanMessage(content=input_text)]}
                
                logging.info(f"[CalendarAgent] [State] Invocando LangGraph. Thread: {session_id} | MSG: {input_text[:30]}...")
                
                # Execução do Agente com State
                result = self.agent.invoke(input_payload, config=config)
                
                logging.info(f"[CalendarAgent] [State] Resposta recebida da IA.")
                
                # Extração da resposta final do Estado
                final_messages = result.get("messages", [])
                if not final_messages:
                    return "Não foi possível gerar uma resposta."
                
                last_msg = final_messages[-1]
                content = last_msg.content
                
                if isinstance(content, list):
                    final_response = "".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in content])
                else:
                    final_response = str(content)

            return final_response

        except Exception as e:
            logging.error(f"[CalendarAgent] Erro no State invoke: {e}", exc_info=True)
            return "Erro técnico no processamento do Estado."
