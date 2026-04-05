
import os
import logging

# Google Cloud and security
from google.cloud import secretmanager
from google.api_core import exceptions

# Project utilities
from edcat_root.utils.get_google_secrets import get_secret

# LangChain core components
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.messages import AIMessage, HumanMessage
import langsmith as ls

# LangChain integrations
from langchain_chroma import Chroma

# --- Custom Exception for Initialization Errors ---
class RagAgentInitializationError(Exception):
    """Custom exception for errors during RagAgent initialization. Now handled silently by default."""
    pass

# --- The RAG Agent Class ---
class RagAgent:
    """A Retrieval-Augmented Generation agent designed to gracefully fail on misconfiguration."""

    def __init__(self, safe_mode=True):
        """Initializes the entire RAG pipeline."""
        logging.info("Initializing RAG Agent...")
        self.agent = None
        self.status_message = "Agent fully operational."

        if not self._load_secrets():
            msg = "Agent initialization disabled: Could not retrieve required secrets (OPENAI_API_KEY/LANGSMITH)."
            if not safe_mode: raise RagAgentInitializationError(msg)
            self.status_message = msg
            return

        try:
            script_dir = os.path.dirname(os.path.realpath(__file__))
            # edcat_root is '..', resources is inside edcat_root
            project_root = os.path.abspath(os.path.join(script_dir, '..'))
            CHROMA_PATH = os.path.join(project_root, 'resources', 'chroma_db')
            logging.info(f"Connecting to ChromaDB at: {CHROMA_PATH}")
            
            if not os.path.isdir(CHROMA_PATH):
                raise RagAgentInitializationError(f"ChromaDB directory not found: {CHROMA_PATH}")

            embeddings = init_embeddings("openai:text-embedding-3-large")
            self.vector_store = Chroma(
                collection_name="Jung_Individuacao",
                embedding_function=embeddings,
                persist_directory=CHROMA_PATH,
            )
            logging.info("Successfully connected to ChromaDB.")
        except Exception as e:
            msg = f"Failed to connect to ChromaDB: {e}"
            if not safe_mode: raise RagAgentInitializationError(msg) from e
            self.status_message = msg
            return

        @tool
        def search_handbook(query: str) -> str:
            """OBRIGATÓRIO: Use esta ferramenta para pesquisar no banco de dados ChromaDB sobre os padrões estruturais de Jung e Arquétipos antes de elaborar a resposta."""
            logging.info(f"[Agent Tool] Searching handbook for: '{query}'")
            results = self.vector_store.similarity_search(query, k=3)
            if not results:
                return "Nenhuma informação explícita encontrada na base de conhecimento."
            return "\n\n---\n\n".join(
                f"Fonte: {doc.metadata.get('source', 'N/A')}\nConteúdo: {doc.page_content}"
                for doc in results
            )

        try:
            model = init_chat_model("gpt-5-mini", model_provider="openai", output_version="v1")
            tools = [search_handbook]
            system_prompt = ("Seu papel único é pesquisar OBRIGATORIAMENTE na base de dados Chroma (usando a ferramenta) para responder à pergunta do usuário.\n"
                             "Se a ferramenta não retornar informações suficientes ou úteis, responda exatamente com: 'Cruzeta, o meu MESTRE, ordenou que eu não responda nada que não seja relacionado ao assunto determinado por ele.'\n"
                             "É vital que você nunca tente responder sem antes consultar a ferramenta!")
            
            # Revertido de volta para a vanguarda do LangChain 0.3+: create_agent substituiu o create_react_agent
            self.agent = create_agent(model, tools, system_prompt=system_prompt)
            logging.info("LangGraph/LangChain agent created successfully.")
        except Exception as e:
            msg = f"Failed to create LangChain agent: {e}"
            if not safe_mode: raise RagAgentInitializationError(msg) from e
            self.status_message = msg
            return

    def _load_secrets(self) -> bool:
        """Loads all necessary API keys."""
        secrets_to_load = ["OPENAI_API_KEY", "LANGSMITH_API_KEY"]
        
        # O central get_secret já retorna o valor, mas não seta o env de forma mágica.
        # Precisamos manter a injeção no os.environ.
        all_loaded = True
        for secret in secrets_to_load:
            val = get_secret(secret)
            if val:
                os.environ[secret] = val
            else:
                all_loaded = False
        
        # Configurando tracing explicitamente
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGSMITH_TRACING"] = "true"
        return all_loaded

    def invoke(self, input_data: dict) -> str:
        """Invokes the agent's stream and returns only the final, synthesized response."""
        if not self.agent:
            return f"Desculpe, o agente de IA está indisponível: {self.status_message}"
        
        try:
            user_message = ""
            messages = input_data.get("messages", [])
            if messages and isinstance(messages, list):
                user_entries = [msg for msg in messages if isinstance(msg, (list, tuple)) and len(msg) == 2 and msg[0] == 'user']
                if user_entries:
                    user_message = user_entries[-1][1]

            if not user_message:
                return "Formato de mensagem de entrada inválido ou mensagem de usuário não encontrada."

            input_payload = {"messages": [{"role": "user", "content": user_message}]}

            # --- INTELLIGENCE FILTER --- 
            # We iterate through the stream and only keep the content of the *last* AI Message.
            # This ensures we don't return intermediate steps like tool calls, only the final answer.
            final_response = ""
            # Isolando o trace no projeto específico via LangSmith Context
            with ls.tracing_context(project_name="rag_agent-v7.0", enabled=True):
                for event in self.agent.stream(
                    input_payload, 
                    stream_mode="values"
                ):
                    last_message = event["messages"][-1]
                    # Check if the newest message in the stream is from the AI.
                    if isinstance(last_message, AIMessage):
                        # Overwrite the final response. The last one in the stream wins.
                        # Usando a nova propriedade .text do LangChain v1.0
                        final_response = last_message.text
            
            if not final_response:
                 return "O agente processou a informação, mas não gerou uma resposta final."

            return final_response

        except Exception as e:
            logging.error(f"An error occurred during agent invocation: {e}")
            return "Ocorreu um erro ao processar sua solicitação."
