from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow info/warning logs
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_mail import Mail, Message
from models import db, User, Scan, Feedback
from auth import auth_bp
from ml_route import ml_bp
from settings_route import settings_bp

mail = Mail()


def create_app():
    app = Flask(__name__)
    os.makedirs(app.instance_path, exist_ok=True)  # instance folder banao agar na ho

    # ── Config ──────────────────────────────────────────────────────────────
    # Secret key for session signing and CSRF protection
    app.config['SECRET_KEY']                     = os.environ['SECRET_KEY']
    # Use DATABASE_URL if set (e.g. PostgreSQL on production), else fall back to local SQLite
    app.config['SQLALCHEMY_DATABASE_URI']        = (
        os.environ.get('DATABASE_URL') or
        f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable change tracking to save memory
    # Google OAuth credentials for social login
    app.config['GOOGLE_CLIENT_ID']               = os.environ['GOOGLE_CLIENT_ID']
    app.config['GOOGLE_CLIENT_SECRET']           = os.environ['GOOGLE_CLIENT_SECRET']

    # ── Mail config ──────────────────────────────────────────────────────────
    # SMTP settings for sending email notifications (defaults to Gmail)
    app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS']        = os.environ.get('MAIL_USE_TLS',  'True') == 'True'
    app.config['MAIL_USE_SSL']        = os.environ.get('MAIL_USE_SSL',  'False') == 'True'
    app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@dentalai.pk')

    # ── Extensions ───────────────────────────────────────────────────────────
    db.init_app(app)    # Bind SQLAlchemy to this app instance
    mail.init_app(app)  # Bind Flask-Mail to this app instance

    # Set up Flask-Login; unauthenticated users are redirected to the login page
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    # Tells Flask-Login how to reload a user object from the session (by user ID)
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Blueprints ───────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)      # Auth routes: /auth/login, /auth/register, etc.
    app.register_blueprint(ml_bp)        # ML routes: image upload, prediction, etc.
    app.register_blueprint(settings_bp)  # Settings routes: profile updates, password, etc.

    # ── Routes ───────────────────────────────────────────────────────────────

    # Home/landing page — accessible to all users
    @app.route('/')
    def index():
        return render_template('index.html')

    # Dental scan analysis page — login required
    @app.route('/analyze')
    @login_required
    def analyze_page():
        return render_template('analyze.html')

    # About page — redirects visitors straight to sign up
    @app.route('/about')
    def about_page():
        return render_template('about.html')

    # Scan history page — shows all past scans for the logged-in user, newest first
    @app.route('/history')
    @login_required
    def history():
        # Fetch all scans belonging to the current user, ordered by date descending
        scans = (Scan.query
                 .filter_by(user_id=current_user.id)
                 .order_by(Scan.created_at.desc())
                 .all())

        # Parse JSON string fields back into dicts for use in the template
        for s in scans:
            s.probs  = json.loads(s.all_probabilities)      if s.all_probabilities      else {}
            s.models = json.loads(s.individual_predictions) if s.individual_predictions else {}

        total = len(scans)

        # Find the most frequently predicted condition across all scans
        most_common = None
        if scans:
            from collections import Counter
            most_common = Counter(s.predicted_class for s in scans).most_common(1)[0][0]

        return render_template('history.html', scans=scans, total=total, most_common=most_common)

    # Delete a specific scan — only the owner can delete their own scans
    @app.route('/history/delete/<int:scan_id>', methods=['POST'])
    @login_required
    def delete_scan(scan_id):
        # 404 if scan doesn't exist or doesn't belong to the current user
        scan = Scan.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
        db.session.delete(scan)
        db.session.commit()
        from flask import redirect, url_for, flash
        flash('Scan deleted.', 'info')
        return redirect(url_for('history'))

    # User settings page — login required
    @app.route('/settings')
    @login_required
    def settings_page():
        return render_template('settings.html')

    # Feedback submission endpoint — accepts JSON POST from the feedback form
    @app.route('/feedback', methods=['POST'])
    def submit_feedback():
        data = request.get_json()

        # Extract and sanitize all form fields
        name    = data.get('name',    '').strip()
        email   = data.get('email',   '').strip()
        city    = data.get('city',    '').strip()
        message = data.get('message', '').strip()
        rating  = data.get('rating',  0)

        # Validate that all required fields are present
        if not name or not email or not message or not rating:
            return jsonify({'error': 'Please fill in all required fields.'}), 400
        # Validate rating is within the allowed 1–5 range
        if not (1 <= int(rating) <= 5):
            return jsonify({'error': 'Rating must be between 1 and 5.'}), 400

        # Save feedback entry to the database
        feedback = Feedback(name=name, email=email, city=city, message=message, rating=int(rating))
        db.session.add(feedback)
        db.session.commit()

        # ── Email notification ───────────────────────────────────────────────
        # Notify the site owner by email whenever new feedback is submitted
        try:
            notify_email = os.environ.get('NOTIFY_EMAIL', 'laibasparkles@gmail.com')
            msg = Message(
                subject=f'New Feedback from {name} — {rating}★',
                recipients=[notify_email],
                body=f"""New feedback received on DentalAI:

Name:    {name}
Email:   {email}
City:    {city or 'N/A'}
Rating:  {rating}/5
Message: {message}
"""
            )
            mail.send(msg)
        except Exception as e:
            # Log the failure but don't crash — feedback is already saved to the DB
            print(f"[Email notification failed]: {e}")

        return jsonify({'success': True}), 201

    # ── DB ───────────────────────────────────────────────────────────────────
    # Create all database tables on startup if they don't already exist
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, use_reloader=False)  # Run in production mode (no debug/auto-reload)