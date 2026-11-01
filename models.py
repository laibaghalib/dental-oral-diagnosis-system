from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
 
db = SQLAlchemy()
 
 
class User(UserMixin, db.Model):
    __tablename__ = 'users'
 
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80),  nullable=False, default='')
    last_name     = db.Column(db.String(80),  nullable=False, default='')
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    google_id     = db.Column(db.String(120), unique=True, nullable=True)
    avatar        = db.Column(db.String(300), nullable=True)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    is_admin      = db.Column(db.Boolean,     default=False)
 
    scans         = db.relationship('Scan', backref='user', lazy=True,
                                    cascade='all, delete-orphan')
 
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
 
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
 
    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email
 
    @property
    def initials(self):
        parts = self.full_name.split()
        return ''.join(p[0].upper() for p in parts[:2]) if parts else '?'
 
    def __repr__(self):
        return f'<User {self.email}>'
 
 
class Scan(db.Model):
    __tablename__ = 'scans'
 
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
 
    # Uploaded image stored as base64 string
    image_b64      = db.Column(db.Text, nullable=True)
 
    # Main result
    predicted_class = db.Column(db.String(100), nullable=False)
    confidence      = db.Column(db.Float,        nullable=False)
 
    # All 6 class probabilities stored as JSON string
    all_probabilities        = db.Column(db.Text, nullable=True)  # JSON
 
    # Individual model predictions stored as JSON string
    individual_predictions   = db.Column(db.Text, nullable=True)  # JSON
 
    # GradCAM heatmap as base64 string
    gradcam_b64    = db.Column(db.Text, nullable=True)
    gradcam_densenet_b64 = db.Column(db.Text, nullable=True)
 
    def __repr__(self):
        return f'<Scan {self.id} — {self.predicted_class} {self.confidence}%>'
 
 
class Feedback(db.Model):
    __tablename__ = 'feedback'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), nullable=False)
    city       = db.Column(db.String(80),  nullable=True)
    message    = db.Column(db.Text,        nullable=False)
    rating     = db.Column(db.Integer,     nullable=False)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    def __repr__(self):
        return f'<Feedback {self.id} — {self.name} ({self.rating}★)>'
 
 
class PatientProfile(db.Model):
    __tablename__ = 'patient_profiles'
 
    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    full_name           = db.Column(db.String(150), default='')
    email               = db.Column(db.String(150), default='')
    dob                 = db.Column(db.String(20),  default='')
    age                 = db.Column(db.String(10),  default='')
    gender              = db.Column(db.String(20),  default='')
    phone               = db.Column(db.String(30),  default='')
    medical_history     = db.Column(db.Text,        default='')
    allergies           = db.Column(db.Text,        default='')
    current_medications = db.Column(db.Text,        default='')
    notes               = db.Column(db.Text,        default='')
 
    def to_dict(self):
        return {
            'name':                self.full_name           or '',
            'email':               self.email               or '',
            'dob':                 self.dob                 or '',
            'age':                 self.age                 or '',
            'gender':              self.gender              or '',
            'phone':               self.phone               or '',
            'medical_history':     self.medical_history     or '',
            'allergies':           self.allergies           or '',
            'current_medications': self.current_medications or '',
            'notes':               self.notes               or '',
        }
 
 
class UserSettings(db.Model):
    __tablename__ = 'user_settings'
 
    id                        = db.Column(db.Integer, primary_key=True)
    user_id                   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
 
    # Clinic / Report Info
    clinic_name               = db.Column(db.String(150), default='')
    doctor_name               = db.Column(db.String(150), default='')
    clinic_address            = db.Column(db.String(300), default='')
    clinic_phone              = db.Column(db.String(50),  default='')
 
    # Analysis Preferences
    confidence_threshold      = db.Column(db.Float,   default=0.0)
    show_individual_models    = db.Column(db.Boolean, default=True)
    show_gradcam              = db.Column(db.Boolean, default=True)
    show_probability_chart    = db.Column(db.Boolean, default=True)
 
    # Report Preferences
    include_gradcam_in_pdf    = db.Column(db.Boolean, default=True)
    auto_save_reports         = db.Column(db.Boolean, default=True)
 
    def to_dict(self):
        return {
            'clinic_name':            self.clinic_name            or '',
            'doctor_name':            self.doctor_name            or '',
            'clinic_address':         self.clinic_address         or '',
            'clinic_phone':           self.clinic_phone           or '',
            'confidence_threshold':   self.confidence_threshold   or 0.0,
            'show_individual_models': self.show_individual_models,
            'show_gradcam':           self.show_gradcam,
            'show_probability_chart': self.show_probability_chart,
            'include_gradcam_in_pdf': self.include_gradcam_in_pdf,
            'auto_save_reports':      self.auto_save_reports,
        }