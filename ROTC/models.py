from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Person(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    stats_reset_date = db.Column(db.DateTime, nullable=True)
    reset_duty_count = db.Column(db.Integer, default=0)
    stats_hours = db.Column(db.Integer, default=0)
    
    # 인증 관련 필드
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255)) 
    role = db.Column(db.String(20), default='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    availabilities = db.relationship('WeeklyAvailability', backref='person', lazy=True, cascade="all, delete-orphan")
    duties = db.relationship('Duty', backref='person', lazy=True)

class WeeklyAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0=월, 1=화...
    available_time = db.Column(db.String(100)) 

class Roster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.String(50), nullable=True)
    people_per_shift = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    duties = db.relationship('Duty', backref='roster', lazy=True, cascade="all, delete-orphan")
    slots = db.relationship('RosterSlot', backref='roster', lazy=True, cascade="all, delete-orphan")

class RosterSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False) 
    required_count = db.Column(db.Integer, default=1)

class Duty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    hour = db.Column(db.Integer, nullable=False, default=9)
    shift_type = db.Column(db.String(50), default='Day')
