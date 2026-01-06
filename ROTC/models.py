from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Person(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stats_reset_date = db.Column(db.DateTime, nullable=True)  # Track when statistics were reset
    reset_duty_count = db.Column(db.Integer, default=0)  # Total duties at reset time
    stats_hours = db.Column(db.Integer, default=0)  # Current statistics hours (separate from actual duties)
    
    # Auth fields
    username = db.Column(db.String(80), unique=True, nullable=True) # Nullable for migration safety, enforce in app
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user') # 'user' or 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    availabilities = db.relationship('WeeklyAvailability', backref='person', lazy=True, cascade="all, delete-orphan")
    duties = db.relationship('Duty', backref='person', lazy=True)

class WeeklyAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0=Mon, 1=Tue, ... 6=Sun
    available_time = db.Column(db.String(50)) # e.g. "18:00-22:00"
    # No date column needed, it's general availability

class Roster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.String(50), nullable=True) # e.g. "09:00 - 18:00"
    people_per_shift = db.Column(db.Integer, nullable=True) # Number of people per time slot. Null means all available.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    duties = db.relationship('Duty', backref='roster', lazy=True, cascade="all, delete-orphan")
    slots = db.relationship('RosterSlot', backref='roster', lazy=True, cascade="all, delete-orphan")

class RosterSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False) # 6-24
    required_count = db.Column(db.Integer, default=1) # Nullable? Default to 1 or higher? Let's say default 1.

class Duty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True) # Nullable for unassigned slots
    hour = db.Column(db.Integer, nullable=False, default=9) # 0-23
    shift_type = db.Column(db.String(50), default='Day') # Can be expanded
