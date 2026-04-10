import json
import logging
from typing import List
from google.cloud import firestore
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

class FirestoreChatMessageHistory(BaseChatMessageHistory):
    """
    Implementação leve e customizada para armazenar o histórico de conversas no Firestore.
    Evita dependências externas pesadas e conflitos de versão do langchain-core.
    """

    def __init__(self, session_id: str, collection: str = "agent_sessions"):
        self.session_id = session_id
        db = firestore.Client()
        logging.info(f"[FirestoreHistory] Usando projeto: {db.project} | Sessão: {session_id}")
        self.doc_ref = db.collection(collection).document(session_id)

    @property
    def messages(self) -> List[BaseMessage]:
        """Recupera as mensagens do Firestore."""
        try:
            doc = self.doc_ref.get()
            if doc.exists:
                data = doc.to_dict().get("messages", [])
                return messages_from_dict(data)
        except Exception as e:
            logging.error(f"[FirestoreHistory] Erro ao carregar mensagens: {e}")
        return []

    def add_message(self, message: BaseMessage) -> None:
        """Adiciona uma nova mensagem ao histórico no Firestore."""
        try:
            # Converte a mensagem atual para o formato dict do LangChain
            new_message_dict = messages_to_dict([message])[0]
            
            # Usa arrayUnion para atomicidade (evita race conditions)
            self.doc_ref.set({
                "messages": firestore.ArrayUnion([new_message_dict]),
                "last_update": firestore.SERVER_TIMESTAMP
            }, merge=True)
        except Exception as e:
            logging.error(f"[FirestoreHistory] Erro ao salvar mensagem: {e}")

    def clear(self) -> None:
        """Limpa o histórico da sessão."""
        try:
            self.doc_ref.delete()
        except Exception as e:
            logging.error(f"[FirestoreHistory] Erro ao deletar sessão: {e}")
