from langchain_core.tools import tool
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from . import services

# Opcional: Modelos Pydantic para os argumentos podem garantir que o Gemini envie o formato correto
class ParseDatetimeArgs(BaseModel):
    datetime_string: str = Field(..., description="String em linguagem natural (ex: 'próxima sexta às 15h').")
    duration: Optional[str] = Field(None, description="Duração opcional do evento (ex: '1 hour', 'para 30 minutos').")
    time_preference: Optional[str] = Field(None, description="Preferência de tempo (ex: 'morning').")

@tool(args_schema=ParseDatetimeArgs)
def parse_natural_language_datetime_tool(datetime_string: str, duration: Optional[str] = None, time_preference: Optional[str] = None) -> str:
    """Interpreta data e hora em linguagem natural para o formato UTC exigido pela API do calendário."""
    try:
        start_iso, end_iso, _ = services.parse_natural_language_datetime(datetime_string, duration, time_preference)
        return f"Start: {start_iso}, End: {end_iso}"
    except Exception as e:
        return f"Erro no parse: {str(e)}"

class CreateEventArgs(BaseModel):
    summary: str = Field(..., description="Título do evento.")
    start_datetime: str = Field(..., description="Data e hora de início em formato ISO UTC (use parse_natural_language_datetime_tool primeiro).")
    end_datetime: str = Field(..., description="Data e hora de término em formato ISO UTC.")
    location: Optional[str] = Field("", description="Local do evento.")
    description: Optional[str] = Field("", description="Descrição das atividades do evento.")
    recurrence: Optional[str] = Field(None, description="String RRULE para eventos que se repetem.")
    attendees: Optional[List[Dict[str, str]]] = Field(None, description="Lista de emails dos participantes, ex: [{'email': 'a@b.com'}].")

@tool(args_schema=CreateEventArgs)
def create_event_tool(summary: str, start_datetime: str, end_datetime: str, location: str = "", description: str = "", recurrence: Optional[str] = None, attendees: Optional[List[Dict[str, str]]] = None) -> str:
    """Ferramenta para criar um NOVO evento no Google Calendar do usuário."""
    try:
        return services.create_event(summary, start_datetime, end_datetime, location, description, recurrence, attendees)
    except Exception as e:
        return f"Erro ao criar evento: {str(e)}"

class SearchEventArgs(BaseModel):
    query: Optional[str] = Field(None, description="Palavras-chave para buscar um evento específico.")
    time_min: Optional[str] = Field(None, description="Limite inferior de tempo (ISO 8601 UTC).")
    time_max: Optional[str] = Field(None, description="Limite superior de tempo (ISO 8601 UTC).")
    max_results: Optional[int] = Field(10, description="Número máximo de resultados.")

@tool(args_schema=SearchEventArgs)
def search_events_tool(query: Optional[str] = None, time_min: Optional[str] = None, time_max: Optional[str] = None, max_results: int = 10) -> str:
    """Usa esta ferramenta para buscar eventos existentes, seja por palavra-chave ou período. IMPORTANTE: Use para descobrir o ID do evento."""
    try:
        results = services.search_events(query, time_min, time_max, max_results)
        return "\n".join(results)
    except Exception as e:
        return f"Erro na busca: {str(e)}"

class ListEventArgs(BaseModel):
    max_results: Optional[int] = Field(10, description="Número máximo de eventos a serem retornados.")

@tool(args_schema=ListEventArgs)
def list_events_tool(max_results: int = 10) -> str:
    """Lista até max_results dos próximos eventos agendados, a partir deste exato momento."""
    try:
        results = services.list_events(max_results)
        return "\n".join(results)
    except Exception as e:
        return f"Erro ao listar eventos: {str(e)}"

class DeleteEventArgs(BaseModel):
    event_id: str = Field(..., description="O identificador (ID) único do evento que deve ser apagado. Obtenha isso usando a ferramenta search_events_tool.")

@tool(args_schema=DeleteEventArgs)
def delete_event_tool(event_id: str) -> str:
    """Remove um evento da agenda. Exige o Event ID."""
    try:
        return services.delete_event(event_id)
    except Exception as e:
        return f"Erro ao deletar evento: {str(e)}"

# A lista consolidada que passaremos para o LLM
CALENDAR_TOOLS = [
    parse_natural_language_datetime_tool,
    create_event_tool,
    search_events_tool,
    list_events_tool,
    delete_event_tool
]
