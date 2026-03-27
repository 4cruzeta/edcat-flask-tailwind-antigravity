from flask import Blueprint, render_template, request, redirect, url_for, g
from .auth import login_required, load_user_profile, admin_required

views = Blueprint('views', __name__)

@views.route('/home')
def home(lang_code):
    return render_template("index.html")

import json
from .utils import get_secret

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
    return render_template("admin_home.html")
