from deepagents import HarnessProfile, register_harness_profile
import datetime

def register_calendar_harness():
    """
    Registra o perfil de Harness para o Agente de Calendário.
    Isso centraliza a configuração do comportamento do agente e garante
    que ele siga o protocolo de agendamento rigorosamente.
    """
    
    # 1. Preparação da data atual para o prompt
    hoje = datetime.datetime.now().strftime("%A, %d de %B de %Y")
    # Traduções simples para PT-BR
    dias = {
        "Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"
    }
    meses = {
        "January": "janeiro", "February": "fevereiro", "March": "março", "April": "abril",
        "May": "maio", "June": "junho", "July": "julho", "August": "agosto",
        "September": "setembro", "October": "outubro", "November": "novembro", "December": "dezembro"
    }
    for en, pt in dias.items(): hoje = hoje.replace(en, pt)
    for en, pt in meses.items(): hoje = hoje.replace(en, pt)

    # 2. Definição do Perfil do Harness (Simplificado para não interferir no protocolo)
    calendar_profile = HarnessProfile(
        base_system_prompt=(
            f"Hoje é {hoje}.\n"
            "Você é o Agente de Agendamento da EdCat. Siga rigorosamente o protocolo de 8 passos.\n"
            "1. Mostre a tabela de horários usando `get_available_booking_slots_tool`.\n"
            "2. Colete Nome, Telefone e Motivo.\n"
            "3. Use o `MAPA_DE_SLOTS_UTF8` para confirmar o ISO exato.\n"
            "4. Nunca invente confirmações sem o ID da ferramenta `confirm_booking_tool`."
        ),
        system_prompt_suffix="\nResponda em Português do Brasil.",
        excluded_tools={"execute", "write_file", "read_file", "ls", "grep"}
    )

    # 3. Registro do perfil para o seu modelo atual
    register_harness_profile("google_genai:gemini-3.5-flash", calendar_profile)
    register_harness_profile("google_genai:gemini-2.5-flash", calendar_profile)
    register_harness_profile("google_genai:gemini-2.0-flash", calendar_profile)

if __name__ == "__main__":
    # Teste local de registro
    register_calendar_harness()
    print("Harness Profile para Calendário registrado com sucesso.")
