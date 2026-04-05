import os
import logging
from google.cloud import secretmanager

def get_secret(secret_id: str, version_id: str = "latest") -> str | None:
    """
    Retrieves a secret from Google Cloud Secret Manager.
    
    Implements a .strip() defense to avoid HTTP 400 errors caused by accidental 
    line breaks in the Cloud Console.
    """
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'edcat-site')
    if not project_id:
        logging.warning("GOOGLE_CLOUD_PROJECT environment variable not found. Defaulting to 'edcat-site'.")
        project_id = 'edcat-site'

    secret_name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_name})
        # Decode and clean invisible characters (Crucial for API keys!)
        return response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        logging.error(f"Error retrieving secret '{secret_id}' from project '{project_id}': {e}")
        return None
