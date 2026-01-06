from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Person, WeeklyAvailability, Roster, Duty, RosterSlot
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///roster.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'dev_key'

import logging
logging.basicConfig(filename='error_log.txt', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

# Global Error Handler
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, int): # Not likely in Flask usually, but handling generic
        return e
    app.logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return f"Internal Server Error: {e}", 500

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Person.query.get(int(user_id))


@app.route('/')
def index():
    return redirect(url_for('roster_list'))

# --- Helper Functions ---
import hashlib
# Distinct color palette for up to 50 people
# Distinct color palette (26 colors)
COLOR_PALETTE = [
    ('#fee2e2', '#991b1b'), # Red
    ('#ffedd5', '#9a3412'), # Orange
    ('#fef9c3', '#854d0e'), # Yellow
    ('#ecfccb', '#3f6212'), # Lime
    ('#dcfce7', '#166534'), # Green
    ('#d1fae5', '#065f46'), # Emerald
    ('#ccfbf1', '#115e59'), # Teal
    ('#cffafe', '#155e75'), # Cyan
    ('#e0f2fe', '#075985'), # Sky
    ('#dbeafe', '#1e40af'), # Blue
    ('#e0e7ff', '#3730a3'), # Indigo
    ('#ede9fe', '#5b21b6'), # Violet
    ('#fae8ff', '#86198f'), # Purple
    ('#fce7f3', '#9d174d'), # Fuchsia
    ('#ffe4e6', '#9f1239'), # Pink
    ('#f1f5f9', '#475569'), # Slate
    ('#f3f4f6', '#4b5563'), # Gray
    ('#fca5a5', '#7f1d1d'), # Light Red
    ('#fdba74', '#7c2d12'), # Light Orange
    ('#fde047', '#713f12'), # Bright Yellow
    ('#bef264', '#365314'), # Bright Lime
    ('#86efac', '#14532d'), # Bright Green
    ('#67e8f9', '#0e7490'), # Bright Cyan
    ('#93c5fd', '#1e3a8a'), # Bright Blue
    ('#c4b5fd', '#4c1d95'), # Bright Violet
    ('#f9a8d4', '#831843'), # Bright Pink
]

def get_color(index):
    """Get color from palette by index"""
    if isinstance(index, str):
        # Fallback for legacy calls or strings
        import hashlib
        return get_color(int(hashlib.md5(index.encode()).hexdigest(), 16))
    return COLOR_PALETTE[index % len(COLOR_PALETTE)]

# --- Availability Management ---
@app.route('/availability')
def availability_page():
    return redirect(url_for('history'))


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Person.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
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
        
        # Check if this is the first user (make admin)
        is_first = Person.query.count() == 0
        role = 'admin' if is_first else 'user'
        
        new_user = Person(username=username, name=name, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- Admin Management ---
@app.route('/admin')
@login_required
def admin_page():
    if current_user.role != 'admin':
        return "권한이 없습니다. (Admin Only)", 403
    
    users = Person.query.order_by(Person.name).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/reset_password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    if current_user.role != 'admin':
        return "권한이 없습니다.", 403
    
    user = Person.query.get_or_404(id)
    new_pass = request.form.get('new_password')
    new_pass = request.form.get('new_password')
    if new_pass:
        user.set_password(new_pass)
        db.session.commit()
    return redirect(url_for('admin_page'))

@app.route('/admin/update_user/<int:id>', methods=['POST'])
@login_required
def admin_update_user(id):
    if current_user.role != 'admin':
        return "권한이 없습니다.", 403
    
    user = Person.query.get_or_404(id)
    new_name = request.form.get('name')
    new_username = request.form.get('username')
    
    new_role = request.form.get('role')
    
    if new_name:
        user.name = new_name
    if new_username:
        # Check uniqueness if changed
        if user.username != new_username:
             existing = Person.query.filter_by(username=new_username).first()
             if existing:
                 flash(f"Username '{new_username}' is already taken.")
                 return redirect(url_for('admin_page'))
             user.username = new_username
    
    # Handle Role Update
    if new_role:
        if new_role not in ['admin', 'user']:
            flash("Invalid role.")
        else:
            user.role = new_role
             
    db.session.commit()
    return redirect(url_for('admin_page'))

# --- Personnel Management ---
@app.route('/people', methods=['GET', 'POST'])
def people_list():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_person = Person(name=name)
            db.session.add(new_person)
            db.session.commit()
        return redirect(url_for('people_list'))
    
    # Permission check for viewing list? Maybe allowed for all logged in users.
    # But adding new person should be Admin only?
    if request.method == 'POST' and current_user.role != 'admin':
         return "인원 추가는 관리자만 가능합니다.", 403

    people = Person.query.order_by(Person.name).all()
    return render_template('people_list.html', people=people)

@app.route('/people/<int:id>/edit', methods=['POST'])
@login_required
def edit_person(id):
    person = Person.query.get_or_404(id)
    
    # Permission Check: Only Admin or Self can edit
    if current_user.role != 'admin' and current_user.id != person.id:
        return "권한이 없습니다.", 403

    person.name = request.form.get('name')
    db.session.commit()
    return redirect(url_for('people_list'))

@app.route('/people/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_person(id):
    if current_user.role != 'admin':
        return "관리자만 실행할 수 있습니다.", 403
    person = Person.query.get_or_404(id)
    person.is_active = not person.is_active
    db.session.commit()
    return redirect(url_for('people_list'))

@app.route('/people/<int:id>')
@login_required
def person_detail(id):
    # Permission Check
    if current_user.role != 'admin' and current_user.id != id:
        return "본인의 정보만 확인할 수 있습니다.", 403

    person = Person.query.get_or_404(id)
    # Default show current month or range? For simplicity, we'll handle date range in frontend or just show next 30 days.
    # Let's pass a default range or handle via API.
    return render_template('person_detail.html', person=person)

@app.route('/people/<int:id>/availability', methods=['GET', 'POST'])
@login_required
def person_availability(id):
    person = Person.query.get_or_404(id)
    
    # Permission Check
    is_admin = (current_user.role == 'admin')
    is_owner = (current_user.id == id)
    can_edit = is_admin or is_owner

    if request.method == 'POST':
        if not can_edit:
             return "권한이 없습니다.", 403

        # Clear existing
        WeeklyAvailability.query.filter_by(person_id=id).delete()
        
        # Add new
        # Form data: day_0, day_1, ... day_6
        for i in range(7):
            time_str = request.form.get(f'day_{i}')
            
            # Find existing or create new (Wait, we deleted above, so always create new)
            if not time_str: continue

            # Create new
            avail = WeeklyAvailability(person_id=id, day_of_week=i, available_time=time_str)
            db.session.add(avail)
            
        db.session.commit()
        return redirect(url_for('people_list'))

    # GET
    avails = WeeklyAvailability.query.filter_by(person_id=id).all()
    # Map to 0-6
    avail_map = {a.day_of_week: a.available_time for a in avails}
    
    days = ['월', '화', '수', '목', '금', '토', '일']
    return render_template('person_availability.html', 
                           person=person, 
                           days=days, 
                           avail_map=avail_map, 
                           readonly=(not can_edit))


@app.route('/people/<int:id>/delete', methods=['POST'])
@login_required
def delete_person(id):
    if current_user.role != 'admin':
        return "관리자만 삭제할 수 있습니다.", 403
        
    person = Person.query.get_or_404(id)
    db.session.delete(person)
    db.session.commit()
    return redirect(url_for('people_list'))

# --- Roster Management ---
@app.route('/rosters')
def roster_list():
    rosters = Roster.query.order_by(Roster.start_date.desc()).all()
    return render_template('roster_list.html', rosters=rosters)

@app.route('/rosters/create', methods=['POST'])
@login_required
def create_roster():
    if current_user.role != 'admin':
        return "관리자만 근무표를 생성할 수 있습니다.", 403
        
    title = request.form.get('title')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
    event_time = request.form.get('event_time')
    people_per_shift = request.form.get('people_per_shift')
    
    if people_per_shift:
        people_per_shift = int(people_per_shift)
    else:
        people_per_shift = None
    
    new_roster = Roster(title=title, start_date=start_date, end_date=end_date, event_time=event_time, people_per_shift=people_per_shift)
    db.session.add(new_roster)
    db.session.commit()
    # Redirect to capacity configuration instead of list
    return redirect(url_for('roster_capacity', id=new_roster.id))

@app.route('/rosters/<int:id>/delete', methods=['POST'])
@login_required
def delete_roster(id):
    if current_user.role != 'admin':
         return "관리자만 근무표를 삭제할 수 있습니다.", 403

    roster = Roster.query.get_or_404(id)
    db.session.delete(roster)
    db.session.commit()
    return redirect(url_for('roster_list'))

@app.route('/rosters/<int:id>/capacity', methods=['GET'])
@login_required
def roster_capacity(id):
    if current_user.role != 'admin':
        return "관리자만 설정을 수정할 수 있습니다.", 403
    roster = Roster.query.get_or_404(id)
    
    from datetime import timedelta
    days = []
    curr = roster.start_date
    while curr <= roster.end_date:
        days.append(curr)
        curr += timedelta(days=1)
        
    # Fetch existing slots
    slots = RosterSlot.query.filter_by(roster_id=id).all()
    slot_map = {(s.date, s.hour): s.required_count for s in slots}
    
    return render_template('roster_capacity.html', roster=roster, days=days, slot_map=slot_map)

@app.route('/rosters/<int:id>/save_capacity', methods=['POST'])
@login_required
def save_roster_capacity(id):
    if current_user.role != 'admin':
        return "관리자만 설정을 저장할 수 있습니다.", 403
    try:
        import json
        data_json = request.form.get('capacity_data')
        if data_json:
            app.logger.info(f"Save Capacity Data received: {data_json[:100]}... (truncated)")
            data = json.loads(data_json)
            
            # Check first item for debug
            if data:
                app.logger.info(f"First item data: {data[0]}")
            
            # Optimize: Delete all existing slots and re-create? Or upsert?
            # Delete all for simplicity as it's a full form submit
            RosterSlot.query.filter_by(roster_id=id).delete()
            
            for item in data:
                date_obj = datetime.strptime(item['date'], '%Y-%m-%d').date()
                hour = int(item['hour'])
                count = int(item['count'])
                
                # Only save if different from default? No, save all for explicit control
                slot = RosterSlot(roster_id=id, date=date_obj, hour=hour, required_count=count)
                db.session.add(slot)
                
            db.session.commit()
            
        return redirect(url_for('roster_detail', id=id))
    except Exception as e:
        app.logger.error(f"Error in save_roster_capacity: {e}")
        return f"An error occurred: {e}", 500

@app.route('/rosters/<int:id>')
def roster_detail(id):
    roster = Roster.query.get_or_404(id)
    from datetime import timedelta
    days = []
    curr = roster.start_date
    while curr <= roster.end_date:
        days.append(curr)
        curr += timedelta(days=1)

    # Fetch existing duties
    # Fetch existing duties
    duties = Duty.query.filter_by(roster_id=id).all()
    # Map by (date, hour) -> list of duties
    duty_map = {}
    for d in duties:
        key = (d.date, d.hour)
        if key not in duty_map:
            duty_map[key] = []
        duty_map[key].append(d)
    
    # Fetch all active people for manual assignment dropdown
    people = Person.query.filter_by(is_active=True).order_by(Person.name).all()
    
    # Fetch all people for name lookup (even inactive ones) to avoid "Unknown"
    all_people = Person.query.order_by(Person.name).all()
    person_map = {p.id: p for p in all_people}
    
    # Assign distinct colors based on sorted index
    person_colors = {}
    for idx, p in enumerate(all_people):
        person_colors[p.id] = get_color(idx)

    # Group duties by person for "Personal Schedule" tab
    duties_by_person = {p.id: [] for p in all_people}
    for d in duties:
        if d.person_id:
            duties_by_person[d.person_id].append(d)
    
    # Sort duties by date/time for each person
    for pid in duties_by_person:
        duties_by_person[pid].sort(key=lambda x: (x.date, x.hour))

    # Prepare duties for JS consumption (JSON serializable)
    duties_by_person_json = {}
    for pid, p_duties in duties_by_person.items():
        duties_by_person_json[pid] = [
            {'date': d.date.strftime('%Y-%m-%d'), 'hour': d.hour}
            for d in p_duties
        ]
        
    # Collect unassigned duties
    unassigned_duties = [d for d in duties if d.person_id is None]
    unassigned_duties_json = [
        {'date': d.date.strftime('%Y-%m-%d'), 'hour': d.hour}
        for d in unassigned_duties
    ]

    # Fetch availability for all people for the roster dates
    # Structure: { date: { person_id: available_time } }
    availability_map = {}
    for day in days:
        weekday = day.weekday()
        # Get weekly availability for this weekday for all people
        avails = WeeklyAvailability.query.filter_by(day_of_week=weekday).all()
        
        # Grid structure: { hour (6-24): [ {name, color_bg, color_text} ] }
        day_grid = {h: [] for h in range(6, 25)}
        
        for a in avails:
            if a.available_time:
                person = person_map.get(a.person_id)
                if not person: continue
                
                bg, txt = person_colors[person.id]
                p_info = {'name': person.name, 'bg': bg, 'text': txt}
                
                # Parse "8,9,10" or "18,19,20"
                try:
                    hours = [int(h) for h in a.available_time.split(',') if h.strip()]
                    for h in hours:
                        if 6 <= h <= 24:
                            day_grid[h].append(p_info)
                except ValueError:
                    pass # Ignore invalid format
                    
        availability_map[day] = day_grid

    # Calculate Unassigned (Active but no duties) and Excluded (Inactive)
    # roster_detail already fetches active people as `people` and all as `all_people`
    
    # Excluded: Inactive
    excluded_people = [p for p in all_people if not p.is_active]
    
    # Unassigned: Active but not in duties_by_person keys or empty value
    # duties_by_person keys are ALL people. 
    # Check if they have entries.
    unassigned_people_list = []
    for p in people: # Iterate active people
        if not duties_by_person.get(p.id):
            unassigned_people_list.append(p)

    return render_template('roster_detail.html', 
                           roster=roster, 
                           days=days, 
                           duty_map=duty_map, 
                           people=people, 
                           availability_map=availability_map, 
                           person_colors=person_colors, 
                           duties_by_person=duties_by_person,
                           duties_by_person_json=duties_by_person_json,
                           unassigned_duties_json=unassigned_duties_json,
                           unassigned_people=unassigned_people_list,
                           excluded_people=excluded_people)

@app.route('/rosters/<int:id>/auto_schedule', methods=['POST'])
@login_required
def auto_schedule(id):
    if current_user.role != 'admin':
        return "관리자만 자동 배정을 실행할 수 있습니다.", 403
    roster = Roster.query.get_or_404(id)
    
    # Clear existing duties
    Duty.query.filter_by(roster_id=id).delete()
    
    from datetime import timedelta
    curr = roster.start_date
    
    # Get all active people
    people = Person.query.filter_by(is_active=True).all()
    
    # Track duty counts for fairness
    # Initialize with existing duties to keep fairness across history (optional, or just for this roster)
    # Using global stats_hours can be better if we want fairness over time.
    # Let's count current duty load plus stats_hours? No, simpler to just trust stats_hours or recount.
    # For this implementation, let's use the local count within this generation + base offset if we want.
    # But usually, it's better to balance newly assigned ones.
    # Track duty counts for fairness
    # Initialize with existing duties to keep fairness across history (optional, or just for this roster)
    # Using global stats_hours can be better if we want fairness over time.
    # Let's count current duty load plus stats_hours? No, simpler to just trust stats_hours or recount.
    # For this implementation, let's use the local count within this generation + base offset if we want.
    # But usually, it's better to balance newly assigned ones.
    duty_counts = {p.id: Duty.query.filter_by(person_id=p.id).count() for p in people}
    
    # Load Roster Slots
    slots = RosterSlot.query.filter_by(roster_id=id).all()
    # Use string date for robust lookup
    slot_map = {(str(s.date), s.hour): s.required_count for s in slots}
    
    # Debug logging
    app.logger.info(f"Auto Schedule for Roster {id}")
    app.logger.info(f"Loaded {len(slots)} slots.")
    
    while curr <= roster.end_date:
        weekday = curr.weekday()
        curr_str = str(curr)
        
        # Hourly scheduling 06:00 - 00:00 (24:00)
        # For continuity, we need to know who worked the previous hour
        previous_hour_people = set()
        
        for hour in range(6, 25):
            # Find available candidates
            candidates = []
            for p in people:
                avail = WeeklyAvailability.query.filter_by(person_id=p.id, day_of_week=weekday).first()
                if not avail or not avail.available_time:
                    continue
                
                # Check if hour is in available_time
                try:
                    hours = [int(h) for h in avail.available_time.split(',') if h.strip()]
                    if hour in hours:
                        candidates.append(p)
                except ValueError:
                    pass
            
            # Determine Target Count
            # Priority: RosterSlot specific > Roster global default > All Available
            specific_count = slot_map.get((curr_str, hour))
            
            if specific_count is not None:
                target_count = specific_count
            elif roster.people_per_shift:
                target_count = roster.people_per_shift
            else:
                target_count = len(candidates) # All available
            
            # Debug log for verification
            if specific_count is not None:
                 app.logger.info(f"Slot {curr_str} {hour}: Found specific count {specific_count}")

            if not candidates:
                # No one available at all
                # Create empty slots for the entire target count
                for _ in range(target_count):
                     new_duty = Duty(roster_id=id, date=curr, hour=hour, person_id=None)
                     db.session.add(new_duty)
                
                previous_hour_people = set()
                continue

            # Selection Logic
            scored_candidates = []
            for p in candidates:
                score = duty_counts[p.id]
                
                # Continuity Bonus
                if p.id in previous_hour_people:
                    score -= 1000  # Massive bonus to ensure continuity
                
                scored_candidates.append((score, p))
            
            # Sort and Select
            import random
            random.shuffle(scored_candidates)
            scored_candidates.sort(key=lambda x: x[0])
            
            selected = scored_candidates[:target_count]
            
            current_hour_people = set()
            for score, p in selected:
                new_duty = Duty(roster_id=id, date=curr, hour=hour, person_id=p.id)
                db.session.add(new_duty)
                duty_counts[p.id] += 1
                current_hour_people.add(p.id)
            
            # Fill remaining slots with empty duties if candidates were fewer than target
            assigned_count = len(selected)
            if assigned_count < target_count:
                for _ in range(target_count - assigned_count):
                    new_duty = Duty(roster_id=id, date=curr, hour=hour, person_id=None)
                    db.session.add(new_duty)
            
            previous_hour_people = current_hour_people
            
        curr += timedelta(days=1)
    
    db.session.commit()
    return redirect(url_for('roster_detail', id=id))

@app.route('/rosters/<int:id>/update_duty', methods=['POST'])
@login_required
def update_duty(id):
    if current_user.role != 'admin':
        return "관리자만 근무표를 수정할 수 있습니다.", 403
    date_str = request.form.get('date')
    person_id = request.form.get('person_id')
    hour = request.form.get('hour')
    # If action is 'remove', we look for a specific person to remove
    # If just adding, we create a new entry
    
    if not hour:
        return "Hour is required", 400
        
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    hour = int(hour)
    
    if person_id:
        # Check if we are adding or removing?
        # The UI will send person_id='' for remove?
        # Improved Logic: 
        # If person_id is provided, we ADD a new duty record.
        # But wait, looking at my plan: "removeDuty: Calls endpoint to remove a specific person"
        # Let's support an 'action' parameter or infer.
        # If person_id is empty, it might be ambiguous WHICH one to remove if there are multiple?
        # Actually, the original code used empty person_id to 'delete'.
        # With multiple people, we need to know WHO to delete.
        pass

    # Read action context from form if possible, or infer
    # Let's standardize: 
    # To ADD: provide person_id
    # To REMOVE: provide person_id AND action='remove'? Or just look at what the frontend sends.
    # The frontend `assignDuty` sends `person_id`.
    # The frontend `removeDuty` sends `person_id` (of the person to remove) and... wait, previously it sent empty string.
    
    # Revised plan:
    # ADD: person_id = '123'
    # REMOVE: person_id = '123', action = 'remove'
    
    action = request.form.get('action')
    
    if action == 'remove':
        if person_id:
             duty = Duty.query.filter_by(roster_id=id, date=date_obj, hour=hour, person_id=int(person_id)).first()
             if duty:
                 # Instead of deleting, set person_id to None to keep the slot as "Unassigned"
                 duty.person_id = None
                 db.session.commit()
    else:
        # Add (or assign)
        if person_id:
             p_id_int = int(person_id)
             # Check for duplicate assignment
             existing_duty = Duty.query.filter_by(roster_id=id, date=date_obj, hour=hour, person_id=p_id_int).first()
             if existing_duty:
                 return "이미 해당 시간에 편성되어 있습니다.", 400

             # Check for an empty slot first to fill
             empty_duty = Duty.query.filter_by(roster_id=id, date=date_obj, hour=hour, person_id=None).first()
             if empty_duty:
                 empty_duty.person_id = p_id_int
             else:
                 # Create new duty if no empty slot matches
                 duty = Duty(roster_id=id, date=date_obj, hour=hour, person_id=p_id_int)
                 db.session.add(duty)
            
    db.session.commit()
    return redirect(url_for('roster_detail', id=id))

@app.route('/history')
def history():
    people = Person.query.order_by(Person.name).all()
    stats = []
    for p in people:
        # Get recent duties for display
        all_duties = Duty.query.filter_by(person_id=p.id).order_by(Duty.date.desc()).all()
        
        stats.append({
            'person': p,
            'count': p.stats_hours,  # Use stats_hours directly
            'recent_duties': all_duties[:5] # Show last 5
        })
    
    # Sort by count desc
    stats.sort(key=lambda x: x['count'], reverse=True)

    labels = [s['person'].name for s in stats]
    data = [s['count'] for s in stats]
    
    # Generate colors for stats
    colors = [get_color(p.name)[0] for p in [s['person'] for s in stats]]
    
    return render_template('history.html', stats=stats, labels=labels, data=data, colors=colors)

@app.route('/person/<int:id>/reset_stats', methods=['POST'])
@login_required
def reset_stats(id):
    if current_user.role != 'admin':
         return "권한이 없습니다.", 403
    person = Person.query.get_or_404(id)
    # Reset statistics hours to 0
    person.stats_hours = 0
    person.stats_reset_date = datetime.now()
    db.session.commit()
    return redirect(url_for('history'))

@app.route('/rosters/<int:id>/apply_stats', methods=['POST'])
@login_required
def apply_stats(id):
    if current_user.role != 'admin':
         return "권한이 없습니다.", 403
    # Sync stats_hours with actual duty counts for all people
    people = Person.query.all()
    for p in people:
        duty_count = Duty.query.filter_by(person_id=p.id).count()
        p.stats_hours = duty_count
    db.session.commit()
    return redirect(url_for('roster_detail', id=id))


if __name__ == '__main__':
    from pyngrok import ngrok
    
    # ngrok 토큰 설정 (여기에 토큰을 입력하세요)
    NGROK_AUTH_TOKEN = "371PFdAaEUFksr5MdQ4VOS4ftHp_JhGQ9ziTxiZcAtBST3Qb"
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    
    with app.app_context():
        db.create_all()
    
    # Start ngrok tunnel
    public_url = ngrok.connect(5000)
    print(f"\n=== 외부 접속 URL ===")
    print(f"{public_url}")
    print("=====================\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
