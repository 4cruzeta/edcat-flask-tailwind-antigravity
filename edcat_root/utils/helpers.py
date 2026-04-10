import datetime
import logging

def parse_iso_datetime(date_string: str) -> datetime.datetime:
    """
    Parses an ISO 8601 string to a datetime object, with manual fixes for common AI model
    inconsistencies (like 'Z' suffix in older Python versions or varied microsecond precision).
    """
    if not date_string:
        raise ValueError("Empty date string provided to parse_iso_datetime.")

    # 1. Limpeza de ruídos de formatação
    clean_date = date_string.strip()
    clean_date = clean_date.replace('<!--', '').replace('-->', '')
    clean_date = clean_date.replace(' UTC', '').replace('Z', '')
    
    # 2. Normaliza espaço entre Data e Hora
    if ' ' in clean_date:
        clean_date = clean_date.replace(' ', 'T')

    try:
        # Tenta o parsing direto do que sobrar
        # Se for YYYY-MM-DDTHH:MM:SS, teremos um Naive Datetime perfeito.
        return datetime.datetime.fromisoformat(clean_date)
    except Exception as e:
        # Fallback de emergência (pega os primeiros 19 caracteres: YYYY-MM-DDTHH:MM:SS)
        logging.warning(f"Standard fromisoformat failed for '{date_string}', using fallback. Error: {e}")
        try:
            return datetime.datetime.fromisoformat(clean_date[:19])
        except Exception as final_err:
            logging.error(f"Critical failure parsing date '{date_string}': {final_err}")
            raise ValueError(f"Could not parse ISO datetime: {date_string}") from final_err
