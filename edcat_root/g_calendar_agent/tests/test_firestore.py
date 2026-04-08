import sys
import os

# Adiciona o diretório raiz ao path para encontrar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from edcat_root.g_calendar_agent.firestore_history import FirestoreChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

def test_history():
    session_id = "test_session_123"
    history = FirestoreChatMessageHistory(session_id)
    
    print(f"--- Iniciando teste para sessão: {session_id} ---")
    
    # 1. Limpar histórico anterior (se existir)
    history.clear()
    print("Sessão limpa.")
    
    # 2. Adicionar mensagens
    history.add_message(HumanMessage(content="Olá, meu nome é João."))
    history.add_message(AIMessage(content="Olá João! Como posso te ajudar hoje?"))
    print("Mensagens adicionadas.")
    
    # 3. Recuperar mensagens
    msgs = history.messages
    print(f"Recuperadas {len(msgs)} mensagens do Firestore:")
    for m in msgs:
        type_str = "Humano" if isinstance(m, HumanMessage) else "IA"
        print(f"[{type_str}]: {m.content}")
    
    if len(msgs) == 2 and "João" in msgs[0].content:
        print("\n[RESULTADO]: SUCESSO! O conector está funcionando perfeitamente.")
    else:
        print("\n[RESULTADO]: FALHA no teste. Verifique os logs.")

if __name__ == "__main__":
    test_history()
