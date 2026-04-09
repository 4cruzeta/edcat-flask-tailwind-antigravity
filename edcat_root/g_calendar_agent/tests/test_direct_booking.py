import os
import sys
import datetime
import pytz

# Ajusta o path para importar o edcat_root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from edcat_root.g_calendar_agent import services

def run_diagnostic():
    print("=== DIAGNÓSTICO DE AGENDAMENTO DIRETO ===")
    
    # 1. Gerar um ISO de teste (Amanhã às 10h)
    target_date = datetime.date.today() + datetime.timedelta(days=1)
    business_tz = pytz.timezone(services.BUSINESS_TIMEZONE)
    dt = business_tz.localize(datetime.datetime.combine(target_date, datetime.time(10, 0)))
    test_iso = dt.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
    
    print(f"[1] Testando com ISO: {test_iso}")
    print(f"[2] Dados: Nome=TESTE, Fone=999, Motivo=DIAGNÓSTICO")
    
    try:
        result = services.confirm_booking(
            name="TESTE DIAGNÓSTICO",
            phone="999999999",
            reason="Validação de Sincronia de API",
            slot_iso=test_iso
        )
        print(f"\n[✓] SUCESSO: {result}")
    except Exception as e:
        print(f"\n[X] ERRO DETECTADO:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostic()
