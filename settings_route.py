from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user, logout_user
from models import db, User, PatientProfile, UserSettings

settings_bp = Blueprint('settings', __name__)


def get_or_create_settings():
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    return settings


def get_or_create_profile():
    profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = PatientProfile(
            user_id=current_user.id,
            full_name=current_user.full_name,
            email=current_user.email,
        )
        db.session.add(profile)
        db.session.commit()
    return profile


# ── GET all settings data ─────────────────────────────────────────────────────
@settings_bp.route('/settings/data', methods=['GET'])
@login_required
def get_settings():
    settings = get_or_create_settings()
    profile = get_or_create_profile()
    return jsonify({
        'profile': {
            'first_name': current_user.first_name or '',
            'last_name': current_user.last_name or '',
            'email': current_user.email or '',
            'phone': profile.phone or '',
            'gender': profile.gender or '',
            'dob': profile.dob or '',
        },
        'clinic': settings.to_dict(),
        'has_password': bool(current_user.password_hash),
    }), 200


# ── Save profile ──────────────────────────────────────────────────────────────
@settings_bp.route('/settings/profile', methods=['POST'])
@login_required
def save_profile():
    data = request.get_json()

    current_user.first_name = data.get('first_name', current_user.first_name or '').strip()
    current_user.last_name = data.get('last_name', current_user.last_name or '').strip()

    profile = get_or_create_profile()
    profile.full_name = f"{current_user.first_name} {current_user.last_name}".strip()
    profile.email = current_user.email
    profile.phone = data.get('phone', profile.phone or '').strip()
    profile.gender = data.get('gender', profile.gender or '')
    profile.dob = data.get('dob', profile.dob or '').strip()

    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated.'}), 200


# ── Save clinic info ──────────────────────────────────────────────────────────
@settings_bp.route('/settings/clinic', methods=['POST'])
@login_required
def save_clinic():
    data = request.get_json()
    settings = get_or_create_settings()
    settings.clinic_name = data.get('clinic_name', '').strip()
    settings.doctor_name = data.get('doctor_name', '').strip()
    settings.clinic_address = data.get('clinic_address', '').strip()
    settings.clinic_phone = data.get('clinic_phone', '').strip()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Clinic info saved.'}), 200


# ── Save analysis preferences ─────────────────────────────────────────────────
@settings_bp.route('/settings/analysis', methods=['POST'])
@login_required
def save_analysis():
    data = request.get_json()
    settings = get_or_create_settings()
    settings.confidence_threshold = float(data.get('confidence_threshold', 0))
    settings.show_individual_models = bool(data.get('show_individual_models', True))
    settings.show_gradcam = bool(data.get('show_gradcam', True))
    settings.show_probability_chart = bool(data.get('show_probability_chart', True))
    settings.include_gradcam_in_pdf = bool(data.get('include_gradcam_in_pdf', True))
    settings.auto_save_reports = bool(data.get('auto_save_reports', True))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Preferences saved.'}), 200


# ── Change password ───────────────────────────────────────────────────────────
@settings_bp.route('/settings/password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm_pw = data.get('confirm_password', '')

    if len(new_pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400
    if new_pw != confirm_pw:
        return jsonify({'error': 'Passwords do not match.'}), 400
    if current_user.password_hash:
        if not current_user.check_password(current_pw):
            return jsonify({'error': 'Current password is incorrect.'}), 400

    current_user.set_password(new_pw)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password updated successfully.'}), 200


# ── Delete account ────────────────────────────────────────────────────────────
@settings_bp.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    data = request.get_json()
    if data.get('confirm') != 'DELETE':
        return jsonify({'error': 'Type DELETE to confirm.'}), 400

    user_id = current_user.id

    # Delete related records first
    PatientProfile.query.filter_by(user_id=user_id).delete()
    UserSettings.query.filter_by(user_id=user_id).delete()

    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'redirect': '/'}), 200
