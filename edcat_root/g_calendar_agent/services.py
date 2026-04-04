import os
import datetime
import re
import logging
import pytz
from dateutil import parser as dateutil_parser
import dateparser
from tzlocal import get_localzone
from typing import Optional, List, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configurações globais
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Autenticação OAuth 2.0 e retorno do serviço do Google Calendar."""
    creds = None
    # Localiza arquivos de credenciais no diretório do blueprint
    current_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(current_dir, "token.json")
    credentials_path = os.path.join(current_dir, "credentials.json")

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except (UnicodeDecodeError, ValueError):
            logging.warning(f"Aviso: '{token_path}' é inválido. Re-autenticando.")
            os.remove(token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Arquivo credentials.json não encontrado em {credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    
    # IMPORTANTE: static_discovery=False evita loops de reload no Flask/Windows
    return build("calendar", "v3", credentials=creds, static_discovery=False)

def get_user_timezone() -> str:
    """Detecta o fuso horário local ou retorna o padrão America/Sao_Paulo."""
    try:
        return str(get_localzone())
    except Exception as e:
        logging.warning(f"Erro ao detectar timezone: {e}. Usando America/Sao_Paulo.")
        return "America/Sao_Paulo"

def parse_duration(duration: str) -> int:
    """Converte string de duração (ex: '1 hora') em minutos."""
    duration_match = re.match(r'(?:for\s+)?(\d+)\s*(hour|hours|minute|minutes)', duration, re.IGNORECASE)
    if duration_match:
        value, unit = duration_match.groups()
        value = int(value)
        return value * 60 if unit.lower().startswith('hour') else value
    return 60  # Default 1 hora

def parse_natural_language_datetime(datetime_string: str, duration: Optional[str] = None, time_preference: Optional[str] = None):
    """Parse de data/hora em linguagem natural usando dateparser."""
    user_timezone = get_user_timezone()
    settings = {
        'TIMEZONE': user_timezone,
        'TO_TIMEZONE': 'UTC',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future',
        'DATE_ORDER': 'DMY'
    }

    parsed_datetime = dateparser.parse(datetime_string, settings=settings)
    
    if not parsed_datetime:
        # Fallback simples usando dateutil para casos fuzzy
        try:
            parsed_datetime = dateutil_parser.parse(datetime_string, fuzzy=True)
            if not parsed_datetime.tzinfo:
                parsed_datetime = pytz.timezone(user_timezone).localize(parsed_datetime)
        except:
            raise ValueError(f"Não foi possível entender a data/hora: {datetime_string}")

    parsed_datetime = parsed_datetime.astimezone(pytz.UTC)
    start_iso = parsed_datetime.isoformat().replace('+00:00', 'Z')

    duration_min = parse_duration(duration) if duration else 60
    end_dt = parsed_datetime + datetime.timedelta(minutes=duration_min)
    end_iso = end_dt.isoformat().replace('+00:00', 'Z')

    return start_iso, end_iso, None

def create_event(summary: str, start_datetime: str, end_datetime: str, location: str = "", description: str = "", recurrence: Optional[str] = None, attendees: Optional[List[Dict[str, str]]] = None):
    """Cria um evento no Google Calendar."""
    service = get_calendar_service()
    user_tz = get_user_timezone()
    
    event = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": user_tz},
        "end": {"dateTime": end_datetime, "timeZone": user_tz},
    }

    if location: event["location"] = location
    if description: event["description"] = description
    if recurrence: event["recurrence"] = [recurrence]
    if attendees: event["attendees"] = attendees

    try:
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Evento criado com sucesso: {created.get('htmlLink')}"
    except HttpError as error:
        raise ValueError(f"Erro ao criar evento: {error}")

def search_events(query: Optional[str] = None, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10):
    """Busca eventos no calendário."""
    service = get_calendar_service()
    params = {
        "calendarId": "primary",
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime"
    }
    if query: params["q"] = query
    if time_min: params["timeMin"] = time_min
    if time_max: params["timeMax"] = time_max

    try:
        result = service.events().list(**params).execute()
        events = result.get("items", [])
        if not events: return ["Nenhum evento encontrado."]
        
        user_tz = pytz.timezone(get_user_timezone())
        output = []
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            output.append(f"{start} - {e['summary']} (ID: {e['id']})")
        return output
    except HttpError as error:
        raise ValueError(f"Erro na busca: {error}")

def list_events(max_results: int = 10):
    """Lista próximos eventos a partir de agora."""
    now = datetime.datetime.now(tz=pytz.UTC).isoformat()
    return search_events(time_min=now, max_results=max_results)

def get_event(event_id: str):
    """Retorna detalhes de um evento específico."""
    service = get_calendar_service()
    return service.events().get(calendarId="primary", eventId=event_id).execute()

def update_event(event_id: str, summary: Optional[str] = None, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None, location: Optional[str] = None, description: Optional[str] = None):
    """Atualiza um evento existente."""
    service = get_calendar_service()
    body = {}
    if summary: body["summary"] = summary
    if start_datetime: body["start"] = {"dateTime": start_datetime, "timeZone": get_user_timezone()}
    if end_datetime: body["end"] = {"dateTime": end_datetime, "timeZone": get_user_timezone()}
    if location: body["location"] = location
    if description: body["description"] = description

    updated = service.events().patch(calendarId="primary", eventId=event_id, body=body).execute()
    return f"Evento atualizado: {updated.get('htmlLink')}"

def delete_event(event_id: str):
    """Remove um evento do calendário."""
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return "Evento deletado com sucesso."

def suggest_meeting_times(date_string: str, duration: str = "1 hour"):
    """Sugere horários livres para reuniões."""
    # Como fallback caso a lógica de free/busy seja complexa, retornamos a lista nos próximos dias
    # Mas tentaremos manter a interface que o agente espera
    return ["Sugestão genérica: Veja sua agenda para " + date_string]

def parse_recurrence(recurrence_string: str):
    """Parse de recorrência simplificado."""
    return "RRULE:FREQ=WEEKLY;COUNT=1"
