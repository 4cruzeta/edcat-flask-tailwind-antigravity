import os
import logging
from typing import List, Dict, Optional

# LangChain components
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

# Project utilities
from .tools import CALENDAR_TOOLS
from .firestore_history import FirestoreChatMessageHistory
from edcat_root.utils.env_bootstrap import bootstrap_langsmith
import edcat_root.utils.langsmith_config as ls

class CalendarAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        """
        Inicializa o Agente de Calendário seguindo o padrão moderno (Scheduler Style).
        Configura a telemetria globalmente no bootstrap.
        """
        logging.info("Initializing Calendar Agent (Modernized)...")
        
        # 1. Bootstrapping de Ambiente (Substitui o .env)
        # Seta LANGSMITH_TRACING, ENDPOINT, PROJECT e API_KEY globalmente
        bootstrap_langsmith(project_name="calendar_agent-v5.0")
        
        try:
            # 2. Configuração do Modelo (Idêntico ao scheduler.py)
            model = init_chat_model(model_name, model_provider="google_genai", temperature=0.0, output_version="v1")
            
            # 3. Prompt de Sistema (Cadeia de Pensamento + Regras)
            system_prompt = (
                "Sua missão é agendar horários no Google Calendar.\n\n"
                
                "== SIGA O SEGUINTE PROCEDIMENTO: ==\n"
                "1.Sempre que receber o comando `MOSTRAR\\_HORARIOS\\_INICIAIS`, use a ferramenta `get_available_booking_slots_tool`, para receber a Tabela atualizada. Ignore COMPLETAMENTE qualquer tabela vista no histórico no contato inicial."
                "2. Após receber a Tabela de Horários, mostre a Tabela no formato markdown, com os dados retornados, sem acrescentar nem retirar informações."
                "3.Logo abaixo da tabela escreva a seguinte mensagem: 'Estes são os dias e horários disponíveis para agendamento.\n\nPara agendar, por favor, mande uma única mensagem com seu nome, telefone, dia, hora e motivo do agendamento.\n\nExemplo:\nSeu Nome, 912345678, segunda, 8 horas, dor de dente\n\n'"
                "4. Analise o histórico e localize a Tabela Markdown MAIS RECENTE e o metadado `DISPONIBILIDADE_TOTAL`.\n"
                "5. Antes de responder, verifique se o dia mencionado possui slots com o código invisível `<!--...-->`. Identifique o valor ISO (ex: <!--2026-04-10T08:00:00Z-->) exato do slot escolhido.\n"
                "6. Se o dia possuir slots, ele ESTÁ disponível. Nunca diga o contrário.\n\n"
                "7. Use OBRIGATORIAMENTE a ferramenta `confirm_booking_tool` para efetivar a marcação assim que tiver o Nome, Telefone, Motivo e o ISO correto extraído da tabela.\n"
                "8. Depois de marcar o horário, responda com a seguinte mensagem EXATA: 'Horário para [Nome], no dia [Dia] às [Hora], para cuidar de [Motivo], marcado com sucesso!\n\nAgradecemos a preferência!'"
            )
            # 4. Criação do Agente com lista de ferramentas (Padrão scheduler.py)
            self.agent = create_agent(model, CALENDAR_TOOLS, system_prompt=system_prompt)
            
        except Exception as e:
            logging.error(f"[CalendarAgent] Erro na inicialização: {e}")
            raise

    def invoke(self, message: str, session_id: str, metadata: Optional[Dict] = None) -> str:
        """Executa um turno do agente com gestão de memória Firestore."""
        try:
            history_manager = FirestoreChatMessageHistory(session_id)
            messages = history_manager.messages
            
            # Prepara a nova mensagem
            input_text = message
            if metadata and "phone" in metadata:
                input_text = f"[SISTEMA: Usuário identificado via WhatsApp com telefone {metadata['phone']}]\n{message}"
            
            new_human_msg = HumanMessage(content=input_text)
            current_messages = messages + [new_human_msg]
            input_payload = {"messages": current_messages}
                
            final_response = ""
            
            # Executa com tracing (As variáveis individuais já estão no ambiente pelo bootstrap)
            for event in self.agent.stream(input_payload, stream_mode="values"):
                last_msg = event["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    final_response = last_msg.text if hasattr(last_msg, 'text') else last_msg.content

            if not final_response:
                return "O agente processou sua mensagem, mas não gerou uma resposta de texto."

            # Salva no Firestore se o atendimento não acabou
            # Mas se acabou com sucesso, limpamos tudo para evitar cache!
            if "marcado com sucesso" in str(final_response).lower():
                logging.info(f"[CalendarAgent] Agendamento concluído. Limpando sessão: {session_id}")
                history_manager.clear()
            else:
                history_manager.add_message(new_human_msg)
                history_manager.add_message(AIMessage(content=str(final_response)))

            return str(final_response)

        except Exception as e:
            logging.error(f"[CalendarAgent] Erro crítico no invoke: {e}", exc_info=True)
            return "Desculpe, tive um problema técnico. Por favor, tente novamente em instantes."
