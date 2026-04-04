from langchain_core.tools import tool
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from . import services

# 1. Ferramenta de Consulta de Slots
class GetSlotsArgs(BaseModel):
    days_ahead: int = Field(6, description="Quantidade de dias úteis projetados para frente.")

@tool(args_schema=GetSlotsArgs)
def get_available_booking_slots_tool(days_ahead: int = 6) -> str:
    """Busca os horários e dias disponíveis na agenda do consultório para mostrar ao cliente.
    Retorna uma Tabela em formato Markdown. Exiba esta tabela para o cliente exatamente como ela for retornada.
    NÃO ALTERE O NOME DOS HORÁRIOS RETORNADOS, ELES SÃO ESTRITAMENTE NECESSÁRIOS PARA A FERRAMENTA DE BOOKING ("8h-manhã").
    """
    try:
        grid = services.get_available_booking_slots(days_ahead)
        if "error" in grid:
            return grid["error"]

        # Formatação pesada da Tabela Markdown solicitada pelo usuário
        days = list(grid.keys())
        matrix_output = []
        
        # Agrupar colunas 3 a 3 para ficar responsivo
        for chunk_idx in range(0, len(days), 3):
            column_names = days[chunk_idx:chunk_idx+3]
            matrix_output.append("|" + "|".join(column_names) + "|")
            matrix_output.append("|" + "|".join(["-" * len(c) for c in column_names]) + "|")
            
            # Precisamos achar o tamanho máximo de linhas de um dia nesta grade
            max_slots = max([len(grid[d]) for d in column_names]) if column_names else 0
            
            for i in range(max_slots):
                row = []
                for d in column_names:
                    if i < len(grid[d]):
                        iso_val = grid[d][i]["iso"]
                        human_val = grid[d][i]["human"]
                        # Embutindo o valor ISO em um comentário HTML invisível ao lado do número
                        # Assim o agente pode extrair com Regex ou ler, sem sujar a tela do user
                        row.append(f"{human_val} <!--{iso_val}-->")
                    else:
                        row.append(" ")
                matrix_output.append("|" + "|".join(row) + "|")
            
            matrix_output.append("\n") # Separa blocos

        return "\n".join(matrix_output)

    except Exception as e:
        return f"Erro na formatação da grade: {str(e)}"

# 2. Ferramenta de Confirmação (Booking Final)
class BookingArgs(BaseModel):
    name: str = Field(..., description="O nome completo do cliente coletado no chat.")
    phone: str = Field(..., description="O número de telefone fornecido pelo cliente.")
    reason: str = Field(..., description="O motivo principal do atendimento (ex: dor de dente, limpeza).")
    slot_iso: str = Field(..., description="O valor de Data/Hora no formato ISO 8601 UTC. Esse valor estava escondido dentro da tag <!-- --> na tabela ao lado do horário escolhido.")

@tool(args_schema=BookingArgs)
def confirm_booking_tool(name: str, phone: str, reason: str, slot_iso: str) -> str:
    """Ferramenta que Efetiva a reserva no sistema. Só chame ela APÓS coletar Nome, Telefone e Motivo, e APÓS o cliente escolher um dos horários da tabela.
    Passar os dados extamente como solicitados."""
    try:
        return services.confirm_booking(name, phone, reason, slot_iso)
    except Exception as e:
        return f"Falha crítica no agendamento. Diga ao cliente: {str(e)}"

# Tools Consolidadas (Substituindo o arsenal genérico por um focado)
CALENDAR_TOOLS = [
    get_available_booking_slots_tool,
    confirm_booking_tool
]
