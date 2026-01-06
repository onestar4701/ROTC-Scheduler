import os
import logging
import hashlib
import random
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# 별도의 models.py 파일에 정의된 객체들을 가져옵니다.
from models import db, Person, WeeklyAvailability, Roster, Duty, RosterSlot

app = Flask(__name__)

# --- [설정] 데이터베이스 및 보안 설정 ---
# 1. DB 주소 설정: Render 환경변수가 있으면 사용, 없으면 로컬 SQLite 사용
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    # SQLAlchemy 1.4+ 버전 호환성을 위해 프로토콜 이름 변경
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///roster.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# 2. 시크릿 키: 배포 환경에서는 환경변수 사용 권장
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key')

# --- [설정] 로깅 ---
logging.basicConfig(filename='error_log.txt', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

# --- [설정] Flask-Login 및 DB 초기화 ---
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Person.query.get(int(user_id))

# 앱 컨텍스트 내에서 테이블 생성
with app.app_context():
    db.create_all()

# --- [Global Error Handler] ---
@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return f"Internal Server Error: {e}", 500

# --- [Helper Functions] ---
COLOR_PALETTE = [
    ('#fee2e2', '#991b1b'), ('#ffedd5', '#9a3412'), ('#fef9c3', '#854d0e'),
    ('#ecfccb', '#3f6212'), ('#dcfce7', '#166534'), ('#d1fae5', '#065f46'),
    ('#ccfbf1', '#115e59'), ('#cffafe', '#155e75'), ('#e0f2fe', '#075985'),
    ('#dbeafe', '#1e40af'), ('#e0e7ff', '#3730a3'), ('#ede9fe', '#5b21b6'),
    ('#fae8ff', '#86198f'), ('#fce7f3', '#9d174d'), ('#ffe4e6', '#9f1239'),
    ('#f1f5f9', '#475569'), ('#f3f4f6', '#4b5563'), ('#fca5a5', '#7f1d1d'),
    ('#fdba74', '#7c2d12'), ('#fde047', '#713f12'), ('#bef264', '#365314'),
    ('#86efac', '#14532d'), ('#67e8f9', '#0e7490'), ('#93c5fd', '#1e3a8a'),
    ('#c4b5fd', '#4c1d95'), ('#f9a8d4', '#831843'),
]

def get_color(index):
    if isinstance(index, str):
        return get_color(int(hashlib.md5(index.encode()).hexdigest(), 16))
    return COLOR_PALETTE[index % len(COLOR_PALETTE)]

# --- [Routes: 기본 및 인증] ---
@app.route('/')
def index():
    return redirect(url_for('roster_list'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Person.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        if Person.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))
        is_first = Person.query.count() == 0
        role = 'admin' if is_first else 'user'
        new_user = Person(username=username, name=name, role=role)
        new_user.set_password(password)
        db
