import secrets
import requests
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, current_app, session)
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlencode
from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ── Google OAuth URLs ────────────────────────────────
GOOGLE_AUTH_URL  = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_URL  = 'https://www.googleapis.com/oauth2/v3/userinfo'
SCOPES           = 'openid email profile'


# ─────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        first_name       = request.form.get('first_name', '').strip()
        last_name        = request.form.get('last_name',  '').strip()
        email            = request.form.get('email',      '').strip().lower()
        password         = request.form.get('password',  '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([first_name, email, password]):
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')

        user = User(first_name=first_name, last_name=last_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f'Welcome to DentalAI, {user.first_name}!', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


# ─────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html')

        login_user(user)
        flash(f'Welcome back, {user.first_name}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    return render_template('login.html')


# ─────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ─────────────────────────────────────────────────────
# GOOGLE LOGIN — Step 1: redirect to Google
# ─────────────────────────────────────────────────────
@auth_bp.route('/google')
def google_login():
    client_id    = current_app.config['GOOGLE_CLIENT_ID']
    redirect_uri = url_for('auth.google_callback', _external=True)

    # Generate CSRF state token
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    params = {
        'client_id':     client_id,
        'redirect_uri':  redirect_uri,
        'response_type': 'code',
        'scope':         SCOPES,
        'access_type':   'offline',
        'prompt':        'select_account',
        'state':         state,
    }
    return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(params)}')


# ─────────────────────────────────────────────────────
# GOOGLE CALLBACK — Step 2: Google sends user back here
# ─────────────────────────────────────────────────────
@auth_bp.route('/callback')
def google_callback():
    # Verify state to prevent CSRF
    state = request.args.get('state')
    if state != session.pop('oauth_state', None):
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    error = request.args.get('error')
    if error:
        flash('Google login was cancelled or failed.', 'error')
        return redirect(url_for('auth.login'))

    code          = request.args.get('code')
    client_id     = current_app.config['GOOGLE_CLIENT_ID']
    client_secret = current_app.config['GOOGLE_CLIENT_SECRET']
    redirect_uri  = url_for('auth.google_callback', _external=True)

    # Exchange code for tokens
    token_resp = requests.post(GOOGLE_TOKEN_URL, data={
        'code':          code,
        'client_id':     client_id,
        'client_secret': client_secret,
        'redirect_uri':  redirect_uri,
        'grant_type':    'authorization_code',
    })

    if token_resp.status_code != 200:
        print('TOKEN ERROR:', token_resp.status_code, token_resp.text)
        flash('Failed to authenticate with Google. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    tokens       = token_resp.json()
    access_token = tokens.get('access_token')

    # Get user info from Google
    user_resp = requests.get(GOOGLE_USER_URL,
                             headers={'Authorization': f'Bearer {access_token}'})

    if user_resp.status_code != 200:
        print('USER INFO ERROR:', user_resp.status_code, user_resp.text)
        flash('Could not retrieve your Google account info.', 'error')
        return redirect(url_for('auth.login'))

    google_data = user_resp.json()
    google_id   = google_data.get('sub')
    email       = google_data.get('email', '').lower()
    first_name  = google_data.get('given_name',  '')
    last_name   = google_data.get('family_name', '')
    avatar      = google_data.get('picture',     '')

    # Find or create user
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
            user.avatar    = avatar
        else:
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                google_id=google_id,
                avatar=avatar,
            )
            db.session.add(user)

    db.session.commit()
    login_user(user)
    flash(f'Welcome, {user.first_name}!', 'success')
    return redirect(url_for('index'))


# ─────────────────────────────────────────────────────
# FORGOT PASSWORD
# ─────────────────────────────────────────────────────
@auth_bp.route('/forgot-password')
def forgot_password():
    flash('Password reset is not yet available. Please use Google login.', 'info')
    return redirect(url_for('auth.login'))