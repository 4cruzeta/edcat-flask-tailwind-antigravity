import os
import datetime
import logging
import pytz
from typing import List, Dict
import holidays

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tzlocal import get_localzone

# Configurações globais
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# --- REGRAS DE NEGÓCIO DA CLÍNICA ---
# Fuso horário base do negócio
BUSINESS_TIMEZONE = "America/Sao_Paulo"

# Horários bloqueados manualmente (formato 'YYYY-MM-DD')
# Você pode adicionar novas datas de folgas/pontes aqui.
BLACKOUT_DATES = [
    '2026-04-17' 
]

# Configuração de Expediente: Dia da semana (0=Segunda, 6=Domingo) -> Lista de Horas disponíveis
# Os horários são representados pelo início do bloco (ex: 8 = das 08h às 09h).
WORKING_HOURS = {
    0: [8, 9, 10, 14, 15, 16], # Segunda Feira
    1: [8, 9, 10, 14, 15, 16], # Terça Feira
    2: [],                     # Quarta Feira (Folga/Fechado)
    3: [8, 9, 10, 14, 15, 16], # Quinta Feira
    4: [8, 9, 10, 14, 15, 16], # Sexta Feira
    5: [8, 9, 10],             # Sábado (Apenas Manhã)
    6: []                      # Domingo (Fechado)
}

# Tradução do número da hora para a string humanizada (UX Rule)
HUMAN_SLOT_MAP = {
    8: "8h-manhã",
    9: "9h-manhã",
    10: "10h-manhã",
    14: "2h-tarde",
    15: "3h-tarde",
    16: "4h-tarde"
}

import json
from google.cloud import secretmanager

# ... Keep other imports intact

def get_secret(project_id, secret_id, version_id="latest") -> str:
    """Extrai um segredo do Google Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8").strip()
        return secret_value
    except Exception as e:
        logging.error(f"Failed to retrieve secret '{secret_id}': {e}")
        return None

def get_calendar_service():
    """Autenticação OAuth 2.0 (Stateless) usando Google Secret Manager."""
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'edcat-site')
    
    # Busca da nuvem (Sem carregar do disco)
    token_str = get_secret(project_id, "GOOGLE_CALENDAR_TOKEN")
    
    if not token_str:
        raise Exception("Token OAuth (GOOGLE_CALENDAR_TOKEN) Inexistente na Nuvem.")
    
    token_info = json.loads(token_str)
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    
    # Se o token estiver expirado de forma bruta no Cloud Run, ele vai usar o refresh_token embutido.
    # O langchain (googleapiclient) fará isso silenciosamente em memória no `creds.refresh`
    if creds and creds.expired and creds.refresh_token:
        # AQUI garantimos a atualização "in_memory". 
        # A API fará a chamada via http usando Requests e gerará o refresh sem salvar no HDD.
        creds.refresh(Request())
        
        # Num cenário ideal super-restrito nós também atualizariamos o segredo lá na nuvem.
        # Mas para MVP Cloud run apenas iterar o Request durante o container ativo é suficiente!
    
    return build("calendar", "v3", credentials=creds, static_discovery=False)

def get_available_booking_slots(days_ahead=6) -> Dict:
    """Calcula os horários comerciais livres para agendamento nos próximos N dias úteis."""
    service = get_calendar_service()
    business_tz = pytz.timezone(BUSINESS_TIMEZONE)
    br_holidays = holidays.BR()
    
    # 1. Obter a data inicial (agora) e gerar a grade teórica
    now = datetime.datetime.now(business_tz)
    
    # Prepara a estrutura do calendário livre
    theoretical_slots = {}
    time_min = None
    time_max = None
    
    # Gera os blocos teóricos para os próximos dias (ignorando dias inválidos)
    current_date = now.date()
    valid_days_added = 0
    days_checked = 0
    
    while valid_days_added < days_ahead and days_checked < 30: # limite de segurança 30 dias
        date_str = current_date.strftime('%Y-%m-%d')
        week_day = current_date.weekday()
        
        # Ignora Feriados Nacionais, Domingos, Quartas, e Bloqueios Customizados
        if (current_date in br_holidays) or \
           (date_str in BLACKOUT_DATES) or \
           (len(WORKING_HOURS.get(week_day, [])) == 0):
            current_date += datetime.timedelta(days=1)
            days_checked += 1
            continue
            
        valid_days_added += 1
        
        # Cria os datetimes ISO dos horários potenciais desta data
        allowed_hours = WORKING_HOURS[week_day]
        for hour in allowed_hours:
            dt = business_tz.localize(datetime.datetime.combine(current_date, datetime.time(hour, 0)))
            dt_iso = dt.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
            
            if dt > now: # Só projeta horas p/ o futuro (relevante pro próprio dia atual)
                if not time_min: 
                    time_min = dt_iso
                time_max = (dt + datetime.timedelta(hours=1)).astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
                
                theoretical_slots[dt_iso] = {
                    "day_label": current_date.strftime('%A-%d').replace('Monday', 'segunda').replace('Tuesday', 'terça').replace('Thursday', 'quinta').replace('Friday', 'sexta').replace('Saturday', 'sábado'),
                    "human_hour": HUMAN_SLOT_MAP.get(hour, f"{hour}h"),
                    "dt_obj": dt
                }
                
        current_date += datetime.timedelta(days=1)
        days_checked += 1

    if not theoretical_slots:
        return {"error": "Nenhum horário comercial encontrado para os próximos dias."}

    # 2. Consultar o Calendar API (Free/Busy query batch) para cruzar com a grade teórica
    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": "UTC",
            "items": [{"id": "primary"}]
        }
        eventsResult = service.freebusy().query(body=body).execute()
        busy_periods = eventsResult.get('calendars', {}).get('primary', {}).get('busy', [])
        
        # Elimina da grade teórica qualquer horário que colida com um block "busy"
        available_grid = {}
        
        for slot_iso, meta in theoretical_slots.items():
            slot_start = meta['dt_obj'].astimezone(pytz.UTC)
            slot_end = slot_start + datetime.timedelta(hours=1)
            is_busy = False
            
            for busy in busy_periods:
                b_start = datetime.datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
                b_end = datetime.datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                # Lógica de intersecção básica de tempo
                if max(slot_start, b_start) < min(slot_end, b_end):
                    is_busy = True
                    break
                    
            if not is_busy:
                label = meta['day_label']
                if label not in available_grid:
                    available_grid[label] = []
                available_grid[label].append({"iso": slot_iso, "human": meta['human_hour']})
                
        return available_grid

    except HttpError as error:
        raise ValueError(f"Erro na api freebusy: {error}")

def confirm_booking(name: str, phone: str, reason: str, slot_iso: str):
    """Cria o compromisso oficial do paciente/cliente extraindo as infomações do chat."""
    service = get_calendar_service()
    
    # 1 hr de duração fixa
    start_dt = datetime.datetime.fromisoformat(slot_iso.replace('Z', '+00:00'))
    end_dt = start_dt + datetime.timedelta(hours=1)
    
    # O Padrão de Nomenclatura Estrita do Consultório
    event_title = f"{name} - {phone} - {reason}"
    
    event = {
        "summary": event_title,
        "start": {"dateTime": start_dt.astimezone(pytz.timezone(BUSINESS_TIMEZONE)).isoformat()},
        "end": {"dateTime": end_dt.astimezone(pytz.timezone(BUSINESS_TIMEZONE)).isoformat()},
        "description": "Marcado automaticamente pelo Agente Inteligente EDCAT."
    }

    try:
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Sucesso! Atendimento agendado para o identificador {created.get('id')}."
    except HttpError as error:
        raise ValueError(f"Erro ao inserir reserva no calendário: {error}")
