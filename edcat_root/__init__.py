import os
from flask import Flask, request, redirect, url_for, g
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_babel import Babel
from dotenv import load_dotenv

def create_app():
    # Inicializa variáveis base do .env 
    load_dotenv()
    
    # Instancia o App do Flask focado no Application Factory e define os diretórios
    app = Flask(__name__, template_folder='pages/templates', static_folder='static')

    # Security: CRÍTICO para rodar no Google Cloud Run, arrumando cabeçalhos de HTTPS
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Placeholder para a Chave Secreta base (agora puxada do Secret Manager!)
    from .utils.get_google_secrets import get_secret
    import json
    import firebase_admin
    from firebase_admin import credentials
    from google.cloud import firestore
    
    # 1. Puxar Configurações com Fallback de Dev
    secret = get_secret("website-secrets")
    app.config['SECRET_KEY'] = secret if secret else os.environ.get('SECRET_KEY', 'dev-key-fallback')

    # Security: Apenas cookies __session podem passar no Hosting (Lição V1)
    is_prod = os.environ.get('GAE_ENV', '').startswith('standard') or os.environ.get('K_SERVICE')
    app.config['SESSION_COOKIE_SECURE'] = bool(is_prod)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'None' # Necessário para rodar iframes no site
    
    # IMPORTANTE: Definir uma sessão vazia evita que o Flask atrapalhe o __session
    app.config['SESSION_COOKIE_NAME'] = 'flask_fallback_session' 

    # 2. Inicializacao do Firebase Admin SDK usando o Secret 
    global db
    db = None
    try:
        firebase_creds_json = get_secret("firebase-credentials")
        if firebase_creds_json:
            firebase_creds = json.loads(firebase_creds_json)
            cred = credentials.Certificate(firebase_creds)
            # Evita inicializar 2x no hot-reload
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            print("[\u2713] Firebase Admin SDK incializado")
        else:
            print("[!] Aviso: Firebase Credenciais nao achadas no GCP.")
    except Exception as e:
        print(f"[X] ERRO ao inicializar Firebase Admin: {e}")

    try:
        db = firestore.Client()
        # Atalho de segurança injetado globalmente:
        app.db = db
        print("[\u2713] Banco Firestore ativo")
    except Exception as e:
        print(f"[X] Avisoes Firestore falhou: {e}")

    # ==========================================
    # Integração do Langchain / RAG Agent
    # ==========================================
    from .rag_agent.agent import RagAgent
    
    # Modo Lazy de carregamento: site sobrevive mesmo ser as chaves API da OpenAI derem pau.
    app.rag_agent = RagAgent(safe_mode=True)
    if app.rag_agent.agent:
        print("[\u2713] RAG Agent IA engatilhada online")
    else:
        print(f"[!] Aviso: RAG Agent Offlline - {app.rag_agent.status_message}")
        
    # ==========================================
    # Babel Settings (i18n)
    # ==========================================
    app.config['LANGUAGES'] = {'pt_BR': 'Português', 'en_US': 'English'}
    app.config['BABEL_DEFAULT_LOCALE'] = 'pt_BR'
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(basedir, 'translations')

    def get_locale():
        if g.get('lang_code') and g.lang_code in app.config['LANGUAGES']:
            return g.lang_code
        return request.accept_languages.best_match(app.config['LANGUAGES'].keys())

    Babel(app, locale_selector=get_locale)

    # ==========================================
    # Contexto e Registro de Blueprints
    # ==========================================
    with app.app_context():
        from .views import views
        from .auth import auth_bp
        from .rag_agent.routes import rag_agent_bp
        from .whatsapp.routes import whatsapp_bp
        from .g_calendar_agent import g_calendar_agent_bp

        @app.before_request
        def set_lang_code():
            # Injeta a língua selecionada na sessão baseada na URL
            g.lang_code = request.view_args.get('lang_code') if request.view_args else None
            # Corrige rotas vazias forçando nulo para fallback natural
            if g.lang_code not in app.config['LANGUAGES']:
                g.lang_code = None

        # Monta os Blueprints principais sob o prefixo condicional de língua
        app.register_blueprint(views, url_prefix='/<lang_code>')
        app.register_blueprint(auth_bp, url_prefix='/<lang_code>/auth')
        app.register_blueprint(rag_agent_bp, url_prefix='/<lang_code>')
        app.register_blueprint(g_calendar_agent_bp, url_prefix='/<lang_code>')
        
        # Webhook raiz estrito (Mas respeitando o prefixo histórico de configuração da Meta API)
        app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')

        @app.context_processor
        def inject_lang_changer():
            def change_lang_url(new_lang):
                if request.endpoint:
                    kwargs = dict(request.view_args or {})
                    kwargs['lang_code'] = new_lang
                    return url_for(request.endpoint, **kwargs)
                return f"/{new_lang}/home"
            return dict(change_lang_url=change_lang_url)

        # Redireciona a raiz bruta "/" para o idioma preferido do navegador ou o default
        @app.route('/')
        def root():
            # Descobre match do idioma pela header request e envia para a home
            matched_lang = request.accept_languages.best_match(app.config['LANGUAGES'].keys())
            final_lang = matched_lang if matched_lang else app.config.get('BABEL_DEFAULT_LOCALE', 'pt_BR')
            return redirect(url_for('views.home', lang_code=final_lang))

    return app
