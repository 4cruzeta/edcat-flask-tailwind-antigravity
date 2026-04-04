import os
import logging
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.tracers import LangChainTracer
from dotenv import load_dotenv

from .tools import CALENDAR_TOOLS
from .services import get_secret

load_dotenv()

class CalendarAgent:
    """Um Agente de Agendamento baseado na arquitetura da Vanguarda LangChain."""

    def __init__(self, safe_mode=True):
        logging.info("Initializing Calendar Agent...")
        self.agent = None
        self.status_message = "Agent fully operational."

        if not self._load_secrets():
            msg = "Agent initialization disabled: Could not configure LangSmith environment."
            if not safe_mode: raise Exception(msg)
            self.status_message = msg
            return

        try:
            # Substituindo ChatGoogleGenerativeAI por init_chat_model com o provider correto
            model = init_chat_model("gemini-2.5-flash", model_provider="google_genai", temperature=0.0)
            
            # O sistema operacional de Recepcionista Odontológica do MVP
            system_prompt = (
                "Você é a recepcionista virtual de um consultório de Odontologia.\n\n"
                
                "== COMO VOCÊ OPERA (SEM CONTEXTO PASSADO) ==\n"
                "Sua comunicação sempre recomeça do zero. Siga as REGRAS abaixo dependendo do que o cliente escrever no balão atual:\n\n"
                
                "CENÁRIO 1: O cliente pediu os horários ou apenas disse 'Oi / Quero marcar'\n"
                "Ação: Use a ferramenta `get_available_booking_slots_tool`. Após receber a Tabela de Horários, mostre ela EXATAMENTE como foi retornada EXPLICANDO ao cliente que ele deve mandar uma única mensagem com o 'Horário Exato copiado da tabela', seu 'Nome', 'Telefone' e 'Motivo' para marcar a hora.\n\n"
                
                "CENÁRIO 2: O cliente já mandou as informações (Nome, Telefone, Motivo e Horário)\n"
                "Ação:\n"
                "1. Primeiro, sem dizer nada ao usuário, use a ferramenta `get_available_booking_slots_tool` novamente contra o sistema para gerar mentalmente a Tabela de Horários mais atual com os códigos ISO.\n"
                "2. Encontre na tabela retornada o código invisível ISO `<!--...-->` que corresponde ao dia da semana e horário amigável que o cliente escolheu no texto dele.\n"
                "3. Chame a ferramenta `confirm_booking_tool` usando os dados do texto do cliente e o slot_iso que você acabou de extrair da tabela mental.\n"
                "4. Confirme para o cliente que está agendado e seja educada.\n\n"
                
                "REGRAS VITAIS:\n"
                "- Nunca adivinhe ou fabrique horários ISO. Sempre consulte a tabela de slots disponíveis primeiro no mesmo turno.\n"
                "- Aja sempre de forma direta."
            )

            # A abstração master que inutilizou StateGraph manual
            self.agent = create_agent(model, CALENDAR_TOOLS, system_prompt=system_prompt)
            logging.info("LangGraph/LangChain create_agent successful.")

        except Exception as e:
            msg = f"Failed to create LangChain agent: {e}"
            if not safe_mode: raise Exception(msg)
            self.status_message = msg
            return

    def _load_secrets(self) -> bool:
        """Configurações mandatérias nativas no código prescritas no laboratório."""
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'edcat-site')
        
        # O agente de calendário também precisa buscar a chave do LangSmith na nuvem
        langsmith_key = get_secret(project_id, "LANGSMITH_API_KEY")
        if langsmith_key:
            os.environ["LANGSMITH_API_KEY"] = langsmith_key
            os.environ["LANGCHAIN_API_KEY"] = langsmith_key # Redundância de segurança
            
        # Configurando tracing explicitamente no próprio agente para separar do RAG
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGSMITH_TRACING"] = "true"
        
        # Confirma que a API foi providenciada globalmente
        return "GOOGLE_API_KEY" in os.environ and "LANGSMITH_API_KEY" in os.environ

    def invoke(self, input_data: dict) -> str:
        """Invoca o backend do LangGraph ignorando o stream parcial."""
        if not self.agent:
            return f"Desculpe, o agente de IA está indisponível: {self.status_message}"
        
        try:
            # Filtro de Inteligência (Retirado do seu lab!)
            # Isolando o trace no projeto específico via Callback Tracer
            tracer = LangChainTracer(project_name="g_calendar_agent")
            final_response = ""
            for event in self.agent.stream(
                input_data, 
                stream_mode="values",
                config={"callbacks": [tracer]}
            ):
                last_message = event["messages"][-1]
                if isinstance(last_message, AIMessage):
                    final_response = last_message.content
            
            # Sanitiza a extração (em caso the tool calling the object pydantic format in Gemini)
            if isinstance(final_response, list):
                text_parts = [
                    part["text"] if isinstance(part, dict) and "text" in part else str(part)
                    for part in final_response
                ]
                final_response = " ".join(text_parts)

            if not final_response:
                return "Ação executada em background sem formatação de texto."

            return str(final_response)

        except Exception as e:
            logging.error(f"Erro no Agente de Calendário invocado: {e}")
            return f"Erro de inteligência: {e}"

# Instância Singelton para uso em rotas
calendar_graph_agent = CalendarAgent()
