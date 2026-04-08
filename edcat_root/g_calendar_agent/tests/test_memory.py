import sys
import os
import uuid

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from edcat_root.g_calendar_agent.agent import CalendarAgent

def test_multiturn_memory():
    # Usamos o mesmo session_id para os dois turnos
    session_id = f"test_user_{uuid.uuid4().hex[:8]}"
    agent = CalendarAgent()
    
    print(f"--- Iniciando teste de memória multi-turno [ID: {session_id}] ---")
    
    # Turno 1: Fornecer apenas o nome
    print("\n[Turno 1]: 'Olá, meu nome é Ricardo.'")
    resp1 = agent.invoke("Olá, meu nome é Ricardo.", session_id=session_id)
    print(f"Agente: {resp1}")
    
    # Turno 2: Perguntar o que o agente já sabe
    print("\n[Turno 2]: 'Você lembra o meu nome?'")
    resp2 = agent.invoke("Você lembra o meu nome?", session_id=session_id)
    print(f"Agente: {resp2}")
    
    if "Ricardo" in resp2:
        print("\n[RESULTADO]: SUCESSO! O agente lembrou o nome do usuário entre os turnos.")
    else:
        print("\n[RESULTADO]: FALHA. O agente parece ter esquecido o contexto anterior.")

if __name__ == "__main__":
    test_multiturn_memory()
