import os
import datetime
import json
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
from google.cloud import firestore

# Project utilities
from edcat_root.utils.get_google_secrets import get_secret
from edcat_root.utils.helpers import parse_iso_datetime

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
    0: [8, 9, 10, 11, 14, 15, 16, 17], # Segunda Feira
    1: [8, 9, 10, 11, 14, 15, 16, 17], # Terça Feira
    2: [],                     # Quarta Feira (Folga/Fechado)
    3: [8, 9, 10, 11, 14, 15, 16, 17], # Quinta Feira
    4: [8, 9, 10, 11, 14, 15, 16, 17], # Sexta Feira
    5: [8, 9, 10, 11],             # Sábado (Apenas Manhã)
    6: []                      # Domingo (Fechado)
}


def get_calendar_service():
    """Autenticação OAuth 2.0 (Stateless) usando Google Secret Manager."""
    # Busca da nuvem (Sem carregar do disco)
    token_str = get_secret("GOOGLE_CALENDAR_TOKEN")
    
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
    time_min = now.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
    time_max = (now + datetime.timedelta(days=7)).astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
    
    # Prepara a estrutura do calendário livre
    theoretical_slots = {}
    
    # Gera os blocos teóricos para os próximos 7 dias corridos
    current_date = now.date()
    days_checked = 0
    
    while days_checked < 7:
        date_str = current_date.strftime('%Y-%m-%d')
        week_day = current_date.weekday()
        
        # Ignora Feriados Nacionais, Domingos, e Bloqueios Customizados
        if (current_date in br_holidays) or \
           (date_str in BLACKOUT_DATES) or \
           (len(WORKING_HOURS.get(week_day, [])) == 0):
            current_date += datetime.timedelta(days=1)
            days_checked += 1
            continue
            
        # Cria os datetimes ISO dos horários potenciais desta data
        allowed_hours = WORKING_HOURS[week_day]
        for hour in allowed_hours:
            dt = business_tz.localize(datetime.datetime.combine(current_date, datetime.time(hour, 0)))
            dt_iso = dt.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")
            
            if dt > now: 
                theoretical_slots[dt_iso] = {
                    "day_label": current_date.strftime('%A-%d').replace('Monday', 'segunda').replace('Tuesday', 'terça').replace('Thursday', 'quinta').replace('Friday', 'sexta').replace('Saturday', 'sábado'),
                    "hour": hour,
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
                b_start = parse_iso_datetime(busy['start'])
                b_end = parse_iso_datetime(busy['end'])
                # Lógica de intersecção básica de tempo
                if max(slot_start, b_start) < min(slot_end, b_end):
                    is_busy = True
                    break
                    
            if not is_busy:
                label = meta['day_label']
                if label not in available_grid:
                    available_grid[label] = []
                available_grid[label].append({"iso": slot_iso, "hour": meta['hour']})
                
        return available_grid

    except HttpError as error:
        raise ValueError(f"Erro na api freebusy: {error}")

def confirm_booking(name: str, phone: str, reason: str, slot_iso: str):
    """Cria o compromisso oficial no Google Calendar e espelha no Firebase."""
    service = get_calendar_service()
    db = firestore.Client()
    
    # 1 hr de duração fixa
    start_dt = parse_iso_datetime(slot_iso)
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
        # 1. Registro no Google Calendar
        created = service.events().insert(calendarId="primary", body=event).execute()
        event_id = created.get('id')

        # 2. Registro no Firebase (Coleção agendamentos)
        booking_data = {
            "name": name,
            "phone": phone,
            "reason": reason,
            "slot_iso": slot_iso,
            "google_event_id": event_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            "status": "confirmed"
        }
        db.collection("agendamentos").add(booking_data)
        logging.info(f"[CalendarService] Agendamento {event_id} registrado no Firebase.")

        return f"Sucesso! Atendimento agendado para o identificador {event_id}."
    except HttpError as error:
        logging.error(f"Erro no agendamento: {error}")
        raise ValueError(f"Erro ao inserir reserva no calendário: {error}")
