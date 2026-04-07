import os
import logging
import json
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage
import langsmith as ls
from google.cloud import secretmanager

# Project utilities
from edcat_root.utils.get_google_secrets import get_secret
from .tools import CALENDAR_TOOLS

class CalendarAgent:
    """O Agente de Calendário unificado com a segurança e segredos do RAG."""

    def __init__(self, safe_mode=True):
        logging.info("Initializing Calendar Agent...")
        self.agent = None
        self.status_message = "Agent fully operational."

        if not self._load_secrets():
            # O status_message já foi preenchido com os detalhes dentro do _load_secrets
            if not safe_mode: raise Exception(self.status_message)
            return

        try:
            model = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai", temperature=0.0, output_version="v1")
            
            system_prompt = (
                "Você é a recepcionista virtual de um consultório de Odontologia.\n\n"
                
                "== COMO VOCÊ OPERA (SEM CONTEXTO PASSADO) ==\n"
                "Sua comunicação sempre recomeça do zero. Siga as REGRAS abaixo dependendo do que o cliente escrever no balão atual:\n\n"
                
                "CENÁRIO 1:"
                "1- Ação: Use a ferramenta `get_available_booking_slots_tool`."
                "2- Após receber a Tabela de Horários, mostre a Tabela EXATAMENTE como foi retornada"
                "3- DIGA ao cliente: Mande uma mensagem com o seu Nome, Telefone, Dia, Hora e Motivo para marcar a hora.\n\n Exemplo: Seu Nome, 75999999999, segunda, 10 horas, dor de dente.\n\n"
                
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

            self.agent = create_agent(model, CALENDAR_TOOLS, system_prompt=system_prompt)
            logging.info("LangGraph/LangChain create_agent successful.")

        except Exception as e:
            msg = f"Failed to create LangChain agent: {e}"
            if not safe_mode: raise Exception(msg)
            self.status_message = msg
            return

    def _load_secrets(self) -> bool:
        """Configura os segredos no ambiente global do container."""
        # Lista mandatária de segredos (Gemini + LangSmith)
        required = ["GOOGLE_API_KEY", "LANGSMITH_API_KEY"]
        missing = []

        for sec in required:
            val = get_secret(sec)
            if val:
                os.environ[sec] = val
                # Log de diagnóstico seguro
                masked = val[0] + "..." + val[-1] if len(val) > 2 else "***"
                logging.info(f"[CalendarAgent] Successfully retrieved '{sec}' (Value: {masked}).")
            else:
                missing.append(sec)

        if missing:
            self.status_message = f"Configuração incompleta. Segredos ausentes na nuvem: {', '.join(missing)}"
            return False
            
        # Ativa o tracing
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGSMITH_API_KEY", "")
        
        return True

    def invoke(self, input_data: dict) -> str:
        """Invoca o backend do LangGraph ignorando o stream parcial."""
        if not self.agent:
            return f"Desculpe, o agente de IA está indisponível: {self.status_message}"
        
        try:
            final_response = ""
            # Tracing isolado v1.0
            with ls.tracing_context(project_name="calendar_agent-v3.0", enabled=True):
                for event in self.agent.stream(
                    input_data, 
                    stream_mode="values"
                ):
                    last_message = event["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        final_response = last_message.text
            
            if not final_response:
                return "O agente operou, mas não gerou texto de resposta."

            return str(final_response)

        except Exception as e:
            logging.error(f"Erro no Agente de Calendário invocado: {e}")
            return f"Erro de inteligência: {e}"

# Instância Singleton para uso em rotas
calendar_graph_agent = CalendarAgent()
