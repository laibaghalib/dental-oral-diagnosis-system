import os
import io
import json
import base64
import numpy as np
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from PIL import Image
from models import db, Scan, PatientProfile, UserSettings
 
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ml_models'))
from predict import predict
from pdf_report import generate_pdf
 
ml_bp = Blueprint('ml', __name__)
 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}
MAX_FILE_MB = 10
 
 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
 
def image_to_b64(img_array):
    pil = Image.fromarray(img_array)
    buf = io.BytesIO()
    pil.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')
 
 
def get_scan(scan_id):
    scan = Scan.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
    scan.probs  = json.loads(scan.all_probabilities)      if scan.all_probabilities      else {}
    scan.models = json.loads(scan.individual_predictions) if scan.individual_predictions else {}
    return scan
 
 
def save_patient_profile(form):
    """Create or update the PatientProfile for the current user from form data."""
    profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = PatientProfile(user_id=current_user.id)
        db.session.add(profile)
 
    profile.full_name           = form.get('name',                '').strip() or profile.full_name
    profile.email               = form.get('email',               '').strip() or profile.email
    profile.dob                 = form.get('dob',                 '').strip() or profile.dob
    profile.age                 = form.get('age',                 '').strip() or profile.age
    profile.gender              = form.get('gender',              '').strip() or profile.gender
    profile.phone               = form.get('phone',               '').strip() or profile.phone
    profile.medical_history     = form.get('medical_history',     '').strip() or profile.medical_history
    profile.allergies           = form.get('allergies',           '').strip() or profile.allergies
    profile.current_medications = form.get('current_medications', '').strip() or profile.current_medications
    profile.notes               = form.get('notes',               '').strip() or profile.notes
 
    db.session.commit()
    return profile
 
 
# ── GET saved patient profile (called when modal opens) ───────────────────────
@ml_bp.route('/patient-profile', methods=['GET'])
@login_required
def get_patient_profile():
    profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        return jsonify(profile.to_dict()), 200
    # Return defaults from user account if no profile yet
    return jsonify({
        'name':                current_user.full_name,
        'email':               current_user.email,
        'dob':                 '',
        'age':                 '',
        'gender':              '',
        'phone':               '',
        'medical_history':     '',
        'allergies':           '',
        'current_medications': '',
        'notes':               '',
    }), 200
 
 
# ── Analyze ───────────────────────────────────────────────────────────────────
@ml_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file. Use key "image".'}), 400
 
    file = request.files['image']
 
    if file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400
 
    if not allowed_file(file.filename):
        return jsonify({'error': f'Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}'}), 400
 
    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    if size_mb > MAX_FILE_MB:
        return jsonify({'error': f'File too large. Max {MAX_FILE_MB} MB.'}), 413
 
    try:
        pil_img   = Image.open(file.stream).convert('RGB')
        img_array = np.array(pil_img)
    except Exception as e:
        return jsonify({'error': f'Could not read image: {str(e)}'}), 422
 
    try:
        result = predict(img_array)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'Inference failed: {str(e)}'}), 500
 
    try:
        scan = Scan(
            user_id                = current_user.id,
            image_b64              = image_to_b64(img_array),
            predicted_class        = result['predicted_class'],
            confidence             = result['confidence'],
            all_probabilities      = json.dumps(result['all_probabilities']),
            individual_predictions = json.dumps(result['individual_predictions']),
            gradcam_b64            = result.get('gradcam', {}).get('ensemble'),
        )
        db.session.add(scan)
        db.session.commit()
        result['scan_id'] = scan.id
    except Exception as e:
        import traceback; traceback.print_exc()
        db.session.rollback()
        return jsonify({
            'error':  'Analysis completed but failed to save scan. Please try again.',
            'detail': str(e)
        }), 500
 
    return jsonify(result), 200
 
 
# ── PDF Download ──────────────────────────────────────────────────────────────
@ml_bp.route('/report/pdf/<int:scan_id>', methods=['POST'])
@login_required
def download_pdf(scan_id):
    scan         = get_scan(scan_id)
    profile      = save_patient_profile(request.form)
    patient_info = profile.to_dict()
 
    try:
        pdf_bytes = generate_pdf(scan, patient_info)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500
 
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'DentalAI_Report_DX{scan_id:05d}.pdf',
    )
 
 
# ── Email Report ──────────────────────────────────────────────────────────────
@ml_bp.route('/report/email/<int:scan_id>', methods=['POST'])
@login_required
def email_report(scan_id):
    scan         = get_scan(scan_id)
    profile      = save_patient_profile(request.form)
    patient_info = profile.to_dict()
 
    recipient = patient_info['email']
    if not recipient:
        return jsonify({'error': 'No email address in profile.'}), 400
 
    try:
        pdf_bytes = generate_pdf(scan, patient_info)
    except Exception as e:
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500
 
    try:
        _send_email(recipient, patient_info['name'], scan, pdf_bytes)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'Email sending failed: {str(e)}'}), 500
 
    return jsonify({'success': True, 'message': f'Report sent to {recipient}'}), 200
 
 
def _send_email(to_email, patient_name, scan, pdf_bytes):
    import smtplib
    from email.mime.multipart   import MIMEMultipart
    from email.mime.text        import MIMEText
    from email.mime.application import MIMEApplication
    from flask import current_app
 
    msg            = MIMEMultipart()
    msg['From']    = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@dentalai.pk')
    msg['To']      = to_email
    msg['Subject'] = f'Your DentalAI Dental Report — {scan.predicted_class}'
 
    body = f"""
Dear {patient_name},
 
Please find your DentalAI diagnostic report attached.
 
Detected Condition : {scan.predicted_class}
Confidence         : {scan.confidence:.1f}%
Scan Date          : {scan.created_at.strftime('%d %b %Y, %I:%M %p')}
 
This report was generated by DentalAI's 3-model AI ensemble (ResNet18, DenseNet121, EfficientNetV2).
 
DISCLAIMER: This is an AI-generated screening report. Please consult a licensed dental
professional before making any clinical decisions.
 
— DentalAI Team
info@dentalai.pk | dentalai.pk
    """.strip()
 
    msg.attach(MIMEText(body, 'plain'))
    att = MIMEApplication(pdf_bytes, _subtype='pdf')
    att.add_header('Content-Disposition', 'attachment',
                   filename=f'DentalAI_Report_DX{scan.id:05d}.pdf')
    msg.attach(att)
 
    with smtplib.SMTP(current_app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
                      current_app.config.get('MAIL_PORT', 587)) as server:
        server.starttls()
        server.login(current_app.config.get('MAIL_USERNAME', ''),
                     current_app.config.get('MAIL_PASSWORD', ''))
        server.send_message(msg)
 
 
# ── Scan Stats ────────────────────────────────────────────────────────────────
@ml_bp.route('/settings/stats', methods=['GET'])
@login_required
def get_scan_stats():
    from collections import Counter
    scans = Scan.query.filter_by(user_id=current_user.id).order_by(Scan.created_at.desc()).all()
    total = len(scans)
    most_common = None
    last_scan   = None
    if scans:
        most_common = Counter(s.predicted_class for s in scans).most_common(1)[0][0]
        last_scan   = scans[0].created_at.strftime('%d %b %Y')
    return jsonify({
        'total':       total,
        'most_common': most_common,
        'last_scan':   last_scan,
    }), 200
 