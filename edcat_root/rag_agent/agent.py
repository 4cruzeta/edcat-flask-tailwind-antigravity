
import os
import logging

# Google Cloud and security
from google.cloud import secretmanager
from google.api_core import exceptions

# LangChain core components
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage # <-- STRATEGIC ADDITION

# LangChain integrations
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# --- Custom Exception for Initialization Errors ---
class RagAgentInitializationError(Exception):
    """Custom exception for errors during RagAgent initialization. Now handled silently by default."""
    pass

# --- Utility Functions ---
def get_secret(project_id, secret_id, version_id="latest"):
    """Retrieves a secret from Google Secret Manager and sets it as an env var."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8").strip()
        os.environ[secret_id] = secret_value
        logging.info(f"Successfully retrieved and set env var for '{secret_id}'.")
        return True
    except Exception as e:
        logging.error(f"--- FAILED to retrieve secret '{secret_id}': {e} ---")
        return False

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

            embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
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
            model = init_chat_model("gpt-5-mini", model_provider="openai")
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
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'edcat-site')
        secrets_to_load = ["OPENAI_API_KEY", "LANGSMITH_API_KEY"]
        results = [get_secret(project_id, secret) for secret in secrets_to_load]
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_PROJECT"] = "rag-v6"
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
        return all(results)

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
            for event in self.agent.stream(input_payload, stream_mode="values"):
                last_message = event["messages"][-1]
                # Check if the newest message in the stream is from the AI.
                if isinstance(last_message, AIMessage):
                    # Overwrite the final response. The last one in the stream wins.
                    final_response = last_message.content
            
            if not final_response:
                 return "O agente processou a informação, mas não gerou uma resposta final."

            return final_response

        except Exception as e:
            logging.error(f"An error occurred during agent invocation: {e}")
            return "Ocorreu um erro ao processar sua solicitação."
