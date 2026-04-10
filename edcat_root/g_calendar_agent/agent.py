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
        try:
            # 1. Bootstrap de API Keys e LangSmith (Garante tracing no Cloud Run/Local)
            bootstrap_langsmith()
            
            # 2. Inicialização do Modelo (Cadeia de Pensamento Ativa)
            model = init_chat_model(model_name, model_provider="google_genai")
            
            # 3. Prompt de Sistema (Cadeia de Pensamento + Regras)
            import datetime
            hoje = datetime.datetime.now().strftime("%A, %d de %B de %Y")
            # Tradução para PT-BR
            hoje = hoje.replace("Monday", "Segunda-feira").replace("Tuesday", "Terça-feira").replace("Wednesday", "Quarta-feira").replace("Thursday", "Quinta-feira").replace("Friday", "Sexta-feira").replace("Saturday", "Sábado").replace("Sunday", "Domingo")
            hoje = hoje.replace("April", "abril").replace("May", "maio").replace("June", "junho").replace("July", "julho").replace("August", "agosto")
            
            system_prompt = (
                f"Hoje é {hoje}.\n"
                "Sua missão é agendar horários no Google Calendar.\n\n"
                
                "== SIGA O SEGUINTE PROCEDIMENTO: ==\n"
                "1. Sempre que receber o comando `MOSTRAR\\_HORARIOS\\_INICIAIS`, use a ferramenta `get_available_booking_slots_tool`, para receber a Tabela atualizada. Ignore COMPLETAMENTE qualquer tabela vista no histórico no contato inicial.\n"
                "2. Após receber a Tabela de Horários, exiba-a LITERALMENTE como foi retornada pela ferramenta. NÃO remova as barras verticais (`|`), NÃO troque por espaços ou tabs, e NÃO tente reformatar. O Markdown precisa das barras `|` para funcionar.\n"
                "3. Logo abaixo da tabela escreva a seguinte mensagem: 'Estes são os dias e horários disponíveis para agendamento.\\n\\nPara agendar, por favor, mande uma única mensagem com seu nome, telefone, dia, hora e motivo do agendamento.\\n\\nExemplo:\\nSeu Nome, 912345678, segunda, 8 horas, dor de dente\\n\\n'\n"
                "4. Analise o histórico e localize a Tabela Markdown MAIS RECENTE e o metadado `MAPA_DE_SLOTS_UTF8`.\n"
                "5. Antes de responder, identifique o Dia e Hora escolhidos (ex: terça-14h). Procure esse par no dicionário JSON oculto `MAPA_DE_SLOTS_UTF8` no final da mensagem da ferramenta para obter o valor ISO exato.\n"
                "6. Se o dia e hora estiverem no mapa, eles ESTÃO disponíveis. Nunca diga o contrário.\n"
                "7. Use OBRIGATORIAMENTE a ferramenta `confirm_booking_tool` para efetivar a marcação. Você está terminantemente PROIBIDO de dizer que marcou sem antes chamar essa ferramenta e receber o ID de sucesso dela.\n"
                "8. Somente após a ferramenta confirmar o agendamento, responda com: 'Horário para [Nome], na [Dia] às [Hora], para cuidar de [Motivo], marcado com sucesso!\n\nAgradecemos a preferência!'"
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
            
            # Executa com tracing e prints de auditoria
            for event in self.agent.stream(input_payload, stream_mode="values"):
                last_msg = event["messages"][-1]
                                
                if isinstance(last_msg, AIMessage):
                    final_response = last_msg.text if hasattr(last_msg, 'text') else last_msg.content

            if not final_response:
                return "O agente processou sua mensagem, mas não gerou uma resposta de texto."

            # Salva no Firestore se o atendimento não acabou
            # Mas se acabou com sucesso, limpamos tudo para evitar cache!
            if "marcado com sucesso" in str(final_response).lower():
                history_manager.clear()
            else:
                try:
                    history_manager.add_message(new_human_msg)
                    history_manager.add_message(AIMessage(content=str(final_response)))
                except Exception as hist_err:
                    print(f"[SESSÃO] ERRO CRÍTICO ao gravar no Firestore: {hist_err}")

            return str(final_response)
        except Exception as e:
            logging.error(f"[CalendarAgent] Erro na invocação: {e}")
            return "Desculpe, tive um problema técnico. Por favor, tente novamente em instantes."
