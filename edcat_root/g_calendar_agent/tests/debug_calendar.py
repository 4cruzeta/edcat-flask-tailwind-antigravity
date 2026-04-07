import os
import sys

# Garante que o diretório raiz esteja no path para as importações do edcat_root funcionarem
sys.path.append(os.getcwd())

from edcat_root.g_calendar_agent.services import get_available_booking_slots
from edcat_root.g_calendar_agent.tools import get_available_booking_slots_tool

def run_test():
    print("\n=== [DEBUG] TESTANDO INTEGRAÇÃO GOOGLE CALENDAR ===")
    try:
        # TESTE 1: Função de Serviço
        print("1. Consultando slots via services.get_available_booking_slots(days_ahead=7)...")
        res = get_available_booking_slots(days_ahead=7)
        if "error" in res:
            print(f"   -> ERRO: {res['error']}")
        else:
            print(f"   -> SUCESSO! Encontrados {len(res)} dias com horários.")
            for dia, slots in res.items():
                 print(f"      - {dia}: {len(slots)} horários")

        # TESTE 2: Saída da Tool (Markdown)
        print("\n2. Gerando tabela Markdown via tools.get_available_booking_slots_tool()...")
        tabela = get_available_booking_slots_tool.invoke({"days_ahead": 7})
        print("\nCONTEÚDO DA TABELA:")
        print("-" * 40)
        print(tabela if tabela.strip() else "[TABELA VAZIA]")
        print("-" * 40)

    except Exception as e:
        print(f"\n[ERRO NA EXECUÇÃO DO TESTE]: {str(e)}")

if __name__ == "__main__":
    run_test()
