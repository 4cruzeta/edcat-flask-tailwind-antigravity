from flask import Blueprint, render_template, request, redirect, url_for, g
from .auth import login_required, load_user_profile, admin_required
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from datetime import datetime

views = Blueprint('views', __name__)

@views.route('/home')
def home(lang_code):
    return render_template("index.html")

import json
from .utils import get_secret
from flask import current_app, jsonify

@views.route('/login', methods=['GET'])
def login(lang_code):
    # O param `next` captura pra onde o usuário tentou ir antes do barramento
    next_url = request.args.get('next')
    
    # Busca dinamicamente os parametros do Firebase Web Client do Secret Manager
    # Isso impede que config sensiveis vazem no git
    fb_config_str = get_secret("firebase-client-config")
    firebase_config = json.loads(fb_config_str) if fb_config_str else {}
    
    return render_template("login.html", next_url=next_url, firebase_config=firebase_config)

# ==========================================
# ROTAS PROTEGIDAS / DASHBOARDS (V1 Mapped)
# ==========================================

@views.route("/dashboard")
@login_required
@load_user_profile
def dashboard(lang_code):
    """Redirecionador central baseado em Role/Cargo."""
    if getattr(g, 'user_profile', {}).get('role') == 'admin':
        return redirect(url_for('views.admin_home', lang_code=lang_code))
    return redirect(url_for('views.user_home', lang_code=lang_code))

@views.route("/user_home")
@login_required
@load_user_profile
def user_home(lang_code):
    return render_template("user_home.html")

@views.route("/admin_home")
@login_required
@load_user_profile
@admin_required
def admin_home(lang_code):
    users_list = []
    db = getattr(current_app, 'db', None)
    if not db:
        return render_template("admin_home.html", users=users_list, error="Database not connected")
    
    try:
        users_ref = db.collection('users').stream()
        for user in users_ref:
            user_data = user.to_dict()
            user_data['uid'] = user.id
            users_list.append(user_data)
    except FirebaseError as e:
        print(f"Error fetching users: {e}")
        return render_template("admin_home.html", users=[], error=f"Error fetching users: {e}")
    
    return render_template("admin_home.html", users=users_list)

# ==========================================
# GESTÃO DE USUÁRIOS (ADMIN DASHBOARD)
# ==========================================

@views.route("/api/user/<uid>", methods=['GET'])
@login_required
@load_user_profile
@admin_required
def get_user_data(lang_code, uid):
    """API para injetar os dados dinamicamente no Modal de Editar Usuário (Flowbite)"""
    db = getattr(current_app, 'db', None)
    if not db: 
        return jsonify({"success": False, "error": "Database not connected"}), 500
    try:
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if 'creation_date' in user_data and hasattr(user_data['creation_date'], 'isoformat'):
                user_data['creation_date'] = user_data['creation_date'].isoformat()
            return jsonify(user_data)
        return jsonify({"success": False, "error": "User not found"}), 404
    except FirebaseError as e:
        return jsonify({"success": False, "error": f"Firestore error: {e}"}), 500

@views.route("/create_user", methods=['POST'])
@login_required
@load_user_profile
@admin_required
def create_user(lang_code):
    db = getattr(current_app, 'db', None)
    if not db: 
        return redirect(url_for('views.admin_home', lang_code=lang_code, error="db_error"))
    try:
        email = request.form['email']
        password = request.form['password']
        full_name = request.form.get('fullName', '')
        status = request.form.get('status', 'active')
        
        # Cria no Firebase Authentication
        new_user_auth = auth.create_user(email=email, password=password, display_name=full_name)
        
        # Define privilégios comparando contra Cloud Secret Manager
        admin_emails_str = get_secret('ADMIN_USERS')
        tester_emails_str = get_secret('TESTER_USERS')
        admin_emails = [e.strip() for e in admin_emails_str.split(',')] if admin_emails_str else []
        tester_emails = [e.strip() for e in tester_emails_str.split(',')] if tester_emails_str else []

        if email in admin_emails:
            role = 'admin'
        elif email in tester_emails:
            role = 'tester'
        else:
            role = 'user'

        # Persiste no Firestore
        user_data = {
            'email': email,
            'full_name': full_name,
            'role': role,
            'status': status,
            'creation_date': datetime.utcnow(),
        }
        db.collection('users').document(new_user_auth.uid).set(user_data)

    except Exception as e:
        print(f"Error creating user: {e}")

    return redirect(url_for('views.admin_home', lang_code=lang_code))

@views.route("/admin/update_user/<uid>", methods=['POST'])
@login_required
@load_user_profile
@admin_required
def update_user(lang_code, uid):
    """Atualizações cirúrgicas vindas da lista ou modal na UI."""
    db = getattr(current_app, 'db', None)
    if not db: 
        return jsonify({"success": False, "error": "Database not connected"}), 500
    
    try:
        data_to_update = {}
        allowed_fields = ['fullName', 'status', 'role']

        for field in allowed_fields:
            if field in request.form:
                data_to_update[field] = request.form[field]

        if data_to_update:
            if 'fullName' in data_to_update:
                try:
                    auth.update_user(uid, display_name=data_to_update['fullName'])
                except Exception as e:
                    print(f"Auth Update erro / Passando: {e}")
                data_to_update['full_name'] = data_to_update.pop('fullName')

            db.collection('users').document(uid).update(data_to_update)
        
        return redirect(url_for('views.admin_home', lang_code=lang_code))

    except Exception as e:
        print(f"Error updating user {uid}: {e}")
        return redirect(url_for('views.admin_home', lang_code=lang_code, error="update_failed"))

@views.route("/admin/delete_user/<uid>", methods=['POST'])
@login_required
@load_user_profile
@admin_required
def delete_user(lang_code, uid):
    """NOVO NA V2: Exclusão rígida (Hard Delete) suportada por Modal visual."""
    db = getattr(current_app, 'db', None)
    if not db:
        return redirect(url_for('views.admin_home', lang_code=lang_code, error="db_error"))
    try:
        # 1. Apaga do Firebase Auth Base
        auth.delete_user(uid)
        # 2. Apaga da coleção Cloud Firestore
        db.collection('users').document(uid).delete()
    except Exception as e:
        print(f"Deleção falhou: {e}")

    return redirect(url_for('views.admin_home', lang_code=lang_code))
