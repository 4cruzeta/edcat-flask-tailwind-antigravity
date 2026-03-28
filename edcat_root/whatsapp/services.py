import os
import requests
import logging

from edcat_root.utils import get_secret

# A simple in-memory cache to avoid fetching the same secret multiple times
# within the same application instance lifecycle.
_secret_cache = {}

def _access_secret_version(secret_id: str) -> str | None:
    """
    Access the latest version of a secret from Google Secret Manager.
    Uses the V2 global get_secret wrapper for resilient loading.
    """
    if secret_id in _secret_cache:
        return _secret_cache[secret_id]

    secret_value = get_secret(secret_id)
    if secret_value:
        _secret_cache[secret_id] = secret_value
    
    return secret_value

def get_whatsapp_credentials() -> dict | None:
    """
    Retrieves all necessary WhatsApp credentials from Google Secret Manager.

    Returns:
        A dictionary containing all required credentials or None if ANY fails.
    """
    access_token = _access_secret_version("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _access_secret_version("WHATSAPP_PHONE_NUMBER_ID")
    verify_token = _access_secret_version("WHATSAPP_VERIFY_TOKEN")
    waba_id = _access_secret_version("WHATSAPP_WABA_ID") 
    pin = _access_secret_version("WHATSAPP_PIN") 

    if not all([access_token, phone_number_id, verify_token, waba_id, pin]):
        logging.error(
            "CRITICAL WARNING (Fail-Safe): One or more WhatsApp credentials could not be retrieved. "
            "WhatsApp features will be disabled for this request."
        )
        return None

    return {
        "access_token": access_token,
        "phone_number_id": phone_number_id,
        "verify_token": verify_token,
        "waba_id": waba_id,
        "pin": pin, 
    }

def send_whatsapp_message(to: str, message_text: str) -> requests.Response | None:
    """
    Sends a WhatsApp message using the Meta Graph API.

    Args:
        to: The recipient's phone number in international format.
        message_text: The text of the message to send.

    Returns:
        The response object from the requests library or None if credentials failed.
    """
    credentials = get_whatsapp_credentials()
    if not credentials:
        logging.error(f"Cannot send message to {to} due to missing WhatsApp Secrets.")
        return None

    api_version = "v24.0" 
    url = f"https://graph.facebook.com/{api_version}/{credentials['phone_number_id']}/messages"
    
    headers = {
        "Authorization": f"Bearer {credentials['access_token']}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message_text},
    }

    logging.info(f"Attempting to send message to {to}...")
    response = requests.post(url, json=payload, headers=headers)
    
    logging.info(f"Meta API Response Status: {response.status_code}")
    if response.status_code != 200:
        logging.error(f"Meta API Response Error Body: {response.json()}")
    
    try:
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to post to Meta Graph API: {e}")
    
    return response
