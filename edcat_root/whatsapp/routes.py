import logging
from collections import deque
from flask import Blueprint, request, current_app

from .services import get_whatsapp_credentials, send_whatsapp_message

logging.basicConfig(level=logging.INFO)

# Defesa Global contra Meta Retries (Evitando bot spam)
_processed_messages = deque(maxlen=2000)

# Blueprint modernizado sem views acopladas (é uma API estrita invisível)
whatsapp_bp = Blueprint("whatsapp_bp", __name__)

@whatsapp_bp.route("/webhooks/whatsapp", methods=["GET", "POST", "PUT"])
def handle_webhook():
    """Handles webhook verification and incoming user messages."""
    
    # 1. Handle webhook verification (Meta Ping)
    if request.method == "GET":
        credentials = get_whatsapp_credentials()
        
        # Modo Fallback: se os segredos não constarem, o bot se defende (503)
        if not credentials:
            logging.error("Webhook Verification requested but WhatsApp Secrets are missing.")
            return "Service Unavailable", 503

        verify_token = credentials.get("verify_token")
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode == "subscribe" and token == verify_token:
            logging.info("SUCCESS: WhatsApp Webhook verified by Meta.")
            return challenge, 200
        else:
            logging.warning("WhatsApp Webhook verification failed due to bad token.")
            return "Forbidden", 403

    # 2. Handle incoming WhatsApp Events
    elif request.method in ["POST", "PUT"]:
        try:
            data = request.get_json()
            if not data or not data.get("entry"):
                return "OK", 200

            value = data["entry"][0]["changes"][0].get("value", {})

            # Tratar mensagem de texto chegando do usuário
            if value.get("messages"):
                message_data = value["messages"][0]
                sender_phone = message_data.get("from")
                message_body = message_data.get("text", {}).get("body", "")
                message_id = message_data.get("id")
                
                if not message_body or not message_id:
                    return "OK", 200

                # DEDUPLICAÇÃO DE MENSAGENS (DEFESA CONTRA META RETRIES)
                # A Meta derruba a conexão se a IA demorar mais de 15s e envia o 
                # MESMO payload de novo várias vezes achando que deu erro, 
                # causando loops infinitos do bot.
                if message_id in _processed_messages:
                    logging.info(f"DUPLICATE BLOCKED - Webhook ignorando o retry do ID: {message_id}")
                    return "OK", 200
                _processed_messages.append(message_id)

                logging.info(f'Received WhatsApp message from {sender_phone} (ID: {message_id}): "{message_body}"')

                # Repasse para Inteligência Artificial da V2
                logging.info("Sending query to RAG Agent...")
                agent = current_app.rag_agent
                
                agent_response = agent.invoke({"messages": [("user", message_body)]})

                logging.info(f"Sending Agent response to {sender_phone}: \"{agent_response}\"")
                # Disparo de volta protegido pelo Fallback do Services
                send_whatsapp_message(to=sender_phone, message_text=agent_response)

            elif value.get("message_echoes"):
                echo_data = value["message_echoes"][0]
                logging.info(f"Received a WhatsApp message echo for message ID: {echo_data.get('id')}")

        except Exception as e:
            logging.error(f"Error processing WhatsApp webhook event: {e}", exc_info=True)

        # Meta always expects a 200 OK so it doesn't loop retries unnecessarily
        return "OK", 200

    return "Not Found", 404
