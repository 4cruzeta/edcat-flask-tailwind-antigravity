import functools
from flask import Blueprint, request, jsonify, redirect, url_for, g, current_app
from firebase_admin import auth as firebase_auth
from datetime import datetime

# Utiliza as funções recriadas imunes a quebras
from .utils import get_secret

auth_bp = Blueprint('auth_bp', __name__)

# =========================================================
# DECORATORS DE FLUXO STATE-LESS (LIÇÕES V1 APLICADAS)
# =========================================================

def login_required(view):
    """
    Garante acesso baseando-se unica e exclusivamente no cookie `__session`.
    Esse detalhe burla a censura de cache do CDN do Firebase Hosting.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        lang_code = kwargs.get('lang_code', 'pt_BR')
        id_token = request.cookies.get('__session')

        if not id_token:
            return redirect(url_for('views.login', lang_code=lang_code, next=request.path))

        try:
            # Firebase assume a validação
            g.user = firebase_auth.verify_id_token(id_token)
        except (firebase_auth.InvalidIdTokenError, firebase_auth.ExpiredIdTokenError) as e:
            response = redirect(url_for('views.login', lang_code=lang_code, next=request.path))
            response.set_cookie('__session', '', expires=0)
            return response
        except Exception as e:
            print(f"Erro Crítico Firebase Auth: {e}")
            return "Erro Interno no Servidor de Autenticação", 500

        return view(**kwargs)
    return wrapped_view

def load_user_profile(view):
    """
    Lê a árvore do Firestore e atribui o `Role` do usuário (Admin, Tester, User).
    Roda SEMPRE depois do login_required para se amarrar no `g.user`.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not hasattr(g, 'user'):
            return "Nenhuma credencial viável encontrada", 500
        
        uid = g.user['uid']
        email = g.user.get('email')
        db = current_app.db
        user_profile_data = {}

        if db:
            user_ref = db.collection('users').document(uid)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                user_profile_data = user_doc.to_dict()
            else:
                # O usuário acabou de logar e não tem cadastro. Criando com cargos via Secret:
                admin_emails_str = get_secret('ADMIN_USERS') or ""
                tester_emails_str = get_secret('TESTER_USERS') or ""
                
                admin_emails = [e.strip() for e in admin_emails_str.split(',')]
                tester_emails = [e.strip() for e in tester_emails_str.split(',')]

                initial_role = 'user'
                if email in admin_emails:
                    initial_role = 'admin'
                elif email in tester_emails:
                    initial_role = 'tester'

                initial_profile = {
                    'email': email,
                    'full_name': g.user.get('name', ''),
                    'role': initial_role,
                    'status': 'active',
                    'creation_date': datetime.utcnow(),
                }
                user_ref.set(initial_profile)
                user_profile_data = initial_profile

        # Associa os dados extraídos/construídos para disponibilidade no Frontend Jinja
        g.user_profile = {
            'uid': uid,
            'email': email,
            'full_name': user_profile_data.get('full_name', g.user.get('name', '')),
            'role': user_profile_data.get('role', 'user'),
            'status': user_profile_data.get('status', 'active')
        }

        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not getattr(g, 'user_profile', {}).get('role') == 'admin':
            lang_code = kwargs.get('lang_code', 'pt_BR')
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Acesso Negado (Admin Required)"}), 403
            return redirect(url_for('views.user_home', lang_code=lang_code))
        return view(**kwargs)
    return wrapped_view

def tester_or_admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        user_role = getattr(g, 'user_profile', {}).get('role')
        if user_role not in ['admin', 'tester']:
            lang_code = kwargs.get('lang_code', 'pt_BR')
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Acesso Negado."}), 403
            return redirect(url_for('views.user_home', lang_code=lang_code))
        return view(**kwargs)
    return wrapped_view

# =========================================================
# ENDPOINTS VITAIS DO FIREBASE
# =========================================================

@auth_bp.route('/session_login', methods=['POST'])
def session_login(lang_code):
    """
    A espinha dorsal de segurança recriada perfeitamente do V1.
    Gera o __session com SameSite=None e secure=True pra contornar restrições.
    """
    try:
        id_token = request.json['token']
        response = jsonify({"success": True})
        
        response.set_cookie(
            '__session', 
            id_token, 
            httponly=True, 
            secure=True, 
            samesite='None'
        )
        return response
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route("/logout")
def logout(lang_code):
    response = redirect(url_for('views.home', lang_code=lang_code))
    response.set_cookie('__session', '', expires=0)
    return response
