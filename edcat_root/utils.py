import os
from google.cloud import secretmanager

def get_secret(secret_id, version_id="latest"):
    """
    Busca um segredo no Google Cloud Secret Manager.
    Implementa um mecanismo de defesa `.strip()` essencial para evitar erros 400
    causados por quebras de linha acidentais salvos no GCP (ex: %0A no WBA webhook).
    """
    # edcat-site era o projeto identificado no EPIC.md do V1.
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'edcat-site')
    if not project_id:
        print("Aviso: Variável GOOGLE_CLOUD_PROJECT não encontrada.")
        return None

    nome_segredo = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=nome_segredo)
        # Decodifica e LIMPA espaços e quebras invisíveis (Crucial!)
        return response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        print(f"Erro ao buscar o segredo '{secret_id}' no projeto '{project_id}': {e}")
        return None
