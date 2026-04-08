import os
import sys
import logging
from typing import List, Dict, Optional

# LangChain components
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

# Project utilities
from edcat_root.utils.get_google_secrets import get_secret
from .tools import CALENDAR_TOOLS
from .firestore_history import FirestoreChatMessageHistory
import edcat_root.utils.langsmith_config as ls

class CalendarAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """Inicializa o Agente de Calendário com suporte a Memória Firestore."""
        logging.info("Initializing Calendar Agent...")
        self._load_secrets()
        
        try:
            model = init_chat_model(model_name, model_provider="google_genai", temperature=0.0, output_version="v1")
            
            system_prompt = (
                "Você é a Assistente de Agendamentos da EdCat. Sua missão é gerenciar a agenda do Google Calendar com PRECISÃO ABSOLUTA.\n\n"
                
                "== PROCESSO DE PENSAMENTO (OBRIGATÓRIO) ==\n"
                "Sempre que precisar responder sobre horários ou dias disponíveis, siga estes passos:\n"
                "1. Analise o histórico e localize a Tabela Markdown MAIS RECENTE e o metadado `DISPONIBILIDADE_TOTAL`.\n"
                "2. Antes de responder, verifique se o dia mencionado pelo usuário (ex: Terça) possui slots com o código invisível `<!--...-->`.\n"
                "3. Se o dia possuir slots na tabela ou no metadado, ele ESTÁ disponível. Nunca diga o contrário.\n\n"

                "== REGRAS DE OURO ==\n"
                "1. Início de Conversa: Se o usuário disser 'Oi', 'Olá' ou se for o comando 'MOSTRAR_HORARIOS_INICIAIS', chame imediatamente a ferramenta `get_available_booking_slots_tool`.\n"
                "2. Transparência: Não invente horários. Se não estiver na tabela, não existe.\n"
                "3. Confirmação: Para agendar, você precisa de: Nome, Telefone, Dia, Hora e Motivo (pegue o que puder do histórico).\n\n"

                "== FLUXO DE TRABALHO ==\n"
                "FASE 1: Consulta (Ferramenta)\n"
                "- Ação: Utilize `get_available_booking_slots_tool`.\n"
                "- Resposta: Mostre a tabela Markdown completa e os slots. Diga: 'Estes são os horários disponíveis. Para marcar, envie: Nome, Telefone, Dia, Hora e Motivo.'\n\n"

                "FASE 2: Agendamento\n"
                "- Quando tiver todos os 5 dados (vistos no histórico ou informados agora):\n"
                "  1. Pegue o código ISO correspondente na tabela.\n"
                "  2. Chame `confirm_booking_tool`.\n"
                "  3. Comunique o sucesso.\n\n"

                "REGRAS VITAIS:\n"
                "- Revise TODA a tabela (inclusive colunas à direita) antes de informar indisponibilidade.\n"
                "- Use o histórico para evitar perguntas repetitivas."
            )

            # Criamos o agente base (LangGraph-based)
            self.agent = create_agent(model, CALENDAR_TOOLS, system_prompt=system_prompt)
            
        except Exception as e:
            logging.error(f"[CalendarAgent] Erro na inicialização: {e}")
            raise

    def _load_secrets(self):
        """Configura os segredos no ambiente global do container."""
        required = ["GOOGLE_API_KEY", "LANGSMITH_API_KEY"]
        for sec in required:
            val = get_secret(sec)
            if val:
                os.environ[sec] = val
            else:
                logging.warning(f"[CalendarAgent] Chave '{sec}' não encontrada.")

    def invoke(self, message: str, session_id: str, metadata: Optional[Dict] = None) -> str:
        """Executa um turno do agente com gestão manual de memória via Firestore."""
        try:
            # 1. Recupera o histórico do Firestore
            history_manager = FirestoreChatMessageHistory(session_id)
            messages = history_manager.messages
            
            # 2. Prepara a nova mensagem
            input_text = message
            
            if metadata and "phone" in metadata:
                input_text = f"[SISTEMA: Usuário identificado via WhatsApp com telefone {metadata['phone']}]\n{message}"
            
            new_human_msg = HumanMessage(content=input_text)
            current_messages = messages + [new_human_msg]
            input_payload = {"messages": current_messages}
                
            final_response = ""
            # 4. Executa o Agente (Streaming para capturar a resposta final)
            with ls.tracing_context(project_name="calendar_agent-v5.0", enabled=True):
                for event in self.agent.stream(
                    input_payload, 
                    stream_mode="values"
                ):
                    last_msg = event["messages"][-1]
                    if isinstance(last_msg, AIMessage):
                        final_response = last_msg.text if hasattr(last_msg, 'text') else last_msg.content

            if not final_response:
                return "O agente processou sua mensagem, mas não gerou uma resposta de texto."

            # 5. Salva no Firestore
            history_manager.add_message(new_human_msg)
            history_manager.add_message(AIMessage(content=str(final_response)))

            return str(final_response)

        except Exception as e:
            logging.error(f"[CalendarAgent] Erro crítico no invoke: {e}", exc_info=True)
            return (
                "Desculpe, tive um problema técnico ao processar sua solicitação. "
                "Por favor, tente novamente em alguns instantes ou verifique sua conexão."
            )
