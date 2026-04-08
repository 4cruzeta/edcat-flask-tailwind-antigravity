import os
import sys
import logging
import traceback

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from edcat_root.utils.get_google_secrets import get_secret
from google.cloud import firestore
from langchain_google_genai import ChatGoogleGenerativeAI

logging.basicConfig(level=logging.INFO)

def diagnose():
    print("=== INICIANDO DIAGNÓSTICO DO AGENTE ===\n")
    
    # 1. Teste de Segredos
    print("1. Verificando Secret Manager...")
    try:
        api_key = get_secret("GOOGLE_API_KEY")
        if api_key:
            print(f"   [OK] GOOGLE_API_KEY recuperada (inicia com {api_key[:5]}...)")
            os.environ["GOOGLE_API_KEY"] = api_key
        else:
            print("   [ERRO] GOOGLE_API_KEY não encontrada no Secret Manager.")
    except Exception as e:
        print(f"   [ERRO CRÍTICO] Falha ao acessar Secret Manager: {e}")

    # 2. Teste do Gemini
    print("\n2. Testando inicialização do Gemini...")
    try:
        model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite")
        # Tentativa de chamada simples
        print("   [OK] Modelo instanciado. Tentando 'ping'...")
        # responder 'ola'
        # response = model.invoke("Diga 'OK'") # Comentado para evitar custos se não quiser rodar agora
        print("   [INFO] Instanciação do Pydantic/Model OK.")
    except Exception as e:
        print(f"   [ERRO] Falha ao instanciar Gemini: {e}")
        traceback.print_exc()

    # 3. Teste do Firestore
    print("\n3. Verificando permissões do Firestore...")
    try:
        db = firestore.Client()
        doc_ref = db.collection("agent_sessions").document("diag_test")
        doc_ref.set({"test": "valid", "timestamp": firestore.SERVER_TIMESTAMP})
        print("   [OK] Escrita no Firestore bem-sucedida.")
        doc_ref.delete()
        print("   [OK] Deleção de teste concluída.")
    except Exception as e:
        print(f"   [ERRO] Falha no Firestore: {e}")
        traceback.print_exc()

    print("\n=== DIAGNÓSTICO CONCLUÍDO ===")

if __name__ == "__main__":
    diagnose()
