import os
import logging
import hashlib
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# models.py에서 정의한 객체들
from models import db, Person, WeeklyAvailability, Roster, Duty, RosterSlot

app = Flask(__name__)

# --- [1. 데이터베이스 설정] ---
# 환경 변수에서 주소를 가져와 바로 설정을 먹입니다. (불필요한 변수 선언 최적화)
raw_db_url = os.environ.get('DATABASE_URL')
if raw_db_url and raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

# 이 줄이 Flask-SQLAlchemy에게 "이 주소로 접속해!"라고 명령하는 핵심 줄입니다.
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'secure_roster_2026')

# --- [2. 서비스 초기화] ---
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Person.query.get(int(user_id))

with app.app_context():
    db.create_all()

# --- [3. 26가지 고유 색상 팔레트] ---
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
        index = int(hashlib.md5(index.encode()).hexdigest(), 16)
    return COLOR_PALETTE[index % len(COLOR_PALETTE)]

# --- [4. 인증 라우트] ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Person.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('roster_list'))
        flash('로그인 실패')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        if Person.query.filter_by(username=request.form.get('username')).first():
            flash('아이디 중복')
            return redirect(url_for('signup'))
        new_user = Person(username=request.form.get('username'), 
                          name=request.form.get('name'), 
                          role='admin' if Person.query.count() == 0 else 'user')
        new_user.set_password(request.form.get('password'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('roster_list'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- [5. 근무표 및 인원 관리] ---
@app.route('/')
@app.route('/rosters')
def roster_list():
    rosters = Roster.query.order_by(Roster.start_date.desc()).all()
    return render_template('roster_list.html', rosters=rosters)

@app.route('/rosters/<int:id>')
def roster_detail(id):
    roster = Roster.query.get_or_404(id)
    days = [roster.start_date + timedelta(days=i) for i in range((roster.end_date - roster.start_date).days + 1)]
    duty_map = {}
    for d in Duty.query.filter_by(roster_id=id).all():
        duty_map.setdefault((d.date, d.hour), []).append(d)
    all_people = Person.query.order_by(Person.name).all()
    colors = {p.id: get_color(idx) for idx, p in enumerate(all_people)}
    return render_template('roster_detail.html', roster=roster, days=days, duty_map=duty_map, 
                           people=[p for p in all_people if p.is_active], person_colors=colors)

@app.route('/rosters/<int:id>/auto_schedule', methods=['POST'])
@login_required
def auto_schedule(id):
    if current_user.role != 'admin': return "Admin Only", 403
    roster = Roster.query.get_or_404(id)
    Duty.query.filter_by(roster_id=id).delete()
    people = Person.query.filter_by(is_active=True).all()
    duty_counts = {p.id: Duty.query.filter_by(person_id=p.id).count() for p in people}
    
    curr = roster.start_date
    while curr <= roster.end_date:
        weekday = curr.weekday()
        prev_hour_ids = set()
        for hour in range(6, 25):
            candidates = [p for p in people if (avail := WeeklyAvailability.query.filter_by(person_id=p.id, day_of_week=weekday).first()) 
                          and avail.available_time and str(hour) in avail.available_time.split(',')]
            target = roster.people_per_shift or 1
            scored = sorted([(duty_counts[p.id] - (1000 if p.id in prev_hour_ids else 0), p) for p in candidates], key=lambda x: x[0])
            selected = scored[:target]
            curr_hour_ids = set()
            for _, p in selected:
                db.session.add(Duty(roster_id=id, date=curr, hour=hour, person_id=p.id))
                duty_counts[p.id] += 1
                curr_hour_ids.add(p.id)
            for _ in range(target - len(selected)):
                db.session.add(Duty(roster_id=id, date=curr, hour=hour, person_id=None))
            prev_hour_ids = curr_hour_ids
        curr += timedelta(days=1)
    db.session.commit()
    return redirect(url_for('roster_detail', id=id))

# --- [6. 실행 (Render 환경)] ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
