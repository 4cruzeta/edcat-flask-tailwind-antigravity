import datetime
import logging

def parse_iso_datetime(date_string: str) -> datetime.datetime:
    """
    Parses an ISO 8601 string to a datetime object, with manual fixes for common AI model
    inconsistencies (like 'Z' suffix in older Python versions or varied microsecond precision).
    """
    if not date_string:
        raise ValueError("Empty date string provided to parse_iso_datetime.")

    # Aumentando a robustez: Remove tags de comentário HTML caso o agente tenha capturado o valor bruto
    # Ex: "<!--2026-04-07T13:00:00Z-->" -> "2026-04-07T13:00:00Z"
    clean_date = date_string.strip().replace('<!--', '').replace('-->', '')

    # 1. Standardize 'Z' (Zulu time) for older Python compatibility (even though 3.11+ supports it)
    # and to ensure a uniform format.
    clean_date = clean_date.replace('Z', '+00:00')

    try:
        # 2. Use the built-in fromisoformat
        return datetime.datetime.fromisoformat(clean_date)
    except ValueError as e:
        # 3. Fallback for potential formatting quirks (like non-standard separators)
        logging.warning(f"Standard fromisoformat failed for '{date_string}', trying secondary parsing. Error: {e}")
        try:
            # Simple fallback for most common date-time only strings
            # If it's just 'YYYY-MM-DD HH:MM:SS', replace space with T
            if ' ' in clean_date:
                clean_date = clean_date.replace(' ', 'T')
            return datetime.datetime.fromisoformat(clean_date)
        except Exception as final_err:
            logging.error(f"Failed to parse date string '{date_string}': {final_err}")
            raise ValueError(f"Could not parse ISO datetime: {date_string}") from final_err
