import os
from edcat_root import create_app

app = create_app()

if __name__ == '__main__':
    # Usado primariamente para desenvolvimento local. 
    # Em produção (Cloud Run), o Gunicorn ignora este bloco e foca no objeto `app`.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
