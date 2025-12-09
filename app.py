from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps
from sqlalchemy import text, func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import shutil
import hashlib
import ipaddress

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quoteforge-secret-key-2025-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quoteforge.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

db = SQLAlchemy(app)

GST_RATE = 0.10  # 10% GST
# Password hash for 'davidbudgewoijanet' - generated once, stored securely
APP_PASSWORD_HASH = generate_password_hash('davidbudgewoijanet')
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = timedelta(minutes=30)

# ============== AUTH & SECURITY ==============

def get_client_ip():
    """Get client IP address, handling proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'

def is_ip_locked(ip_address):
    """Check if IP is locked due to too many failed attempts"""
    attempt = LoginAttempt.query.filter_by(ip_address=ip_address).first()
    if not attempt:
        return False
    
    if attempt.locked_until and attempt.locked_until > datetime.now(timezone.utc):
        return True
    
    # Clear lock if expired
    if attempt.locked_until and attempt.locked_until <= datetime.now(timezone.utc):
        attempt.attempts = 0
        attempt.locked_until = None
        db.session.commit()
    
    return False

def record_failed_login(ip_address):
    """Record a failed login attempt and lock if threshold reached"""
    attempt = LoginAttempt.query.filter_by(ip_address=ip_address).first()
    
    if not attempt:
        attempt = LoginAttempt(ip_address=ip_address, attempts=1)
        db.session.add(attempt)
    else:
        attempt.attempts += 1
        attempt.last_attempt = datetime.now(timezone.utc)
    
    # Lock after MAX_LOGIN_ATTEMPTS failures
    if attempt.attempts >= MAX_LOGIN_ATTEMPTS:
        attempt.locked_until = datetime.now(timezone.utc) + LOCKOUT_DURATION
    
    db.session.commit()
    return attempt.attempts

def clear_login_attempts(ip_address):
    """Clear failed attempts on successful login"""
    attempt = LoginAttempt.query.filter_by(ip_address=ip_address).first()
    if attempt:
        attempt.attempts = 0
        attempt.locked_until = None
        db.session.commit()

def sanitize_input(text, max_length=None):
    """Sanitize user input to prevent XSS and SQL injection"""
    if not text:
        return ''
    # Remove null bytes
    text = text.replace('\x00', '')
    # Limit length if specified
    if max_length:
        text = text[:max_length]
    return text.strip()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    ip_address = get_client_ip()
    
    # Check if IP is locked
    if is_ip_locked(ip_address):
        attempt = LoginAttempt.query.filter_by(ip_address=ip_address).first()
        if attempt and attempt.locked_until:
            remaining = attempt.locked_until - datetime.now(timezone.utc)
            minutes = int(remaining.total_seconds() / 60) + 1
            flash(f'Too many failed login attempts. Account locked for {minutes} more minutes.', 'error')
            return render_template('login.html')
    
    if request.method == 'POST':
        # Sanitize input
        password = sanitize_input(request.form.get('password', ''), max_length=200)
        
        # Verify password using hash
        if password and check_password_hash(APP_PASSWORD_HASH, password):
            # Successful login - clear attempts
            clear_login_attempts(ip_address)
            session['logged_in'] = True
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
            # Regenerate session ID on login (prevent session fixation)
            session.permanent = True
            next_page = request.args.get('next')
            # Sanitize redirect URL to prevent open redirect
            if next_page and (next_page.startswith('/') or next_page.startswith(url_for('index'))):
                flash('Welcome to QuoteForge!', 'success')
                return redirect(next_page)
            flash('Welcome to QuoteForge!', 'success')
            return redirect(url_for('index'))
        else:
            # Failed login - record attempt
            attempts = record_failed_login(ip_address)
            remaining = MAX_LOGIN_ATTEMPTS - attempts
            if remaining > 0:
                flash(f'Incorrect password. {remaining} attempt(s) remaining.', 'error')
            else:
                flash(f'Too many failed attempts. Account locked for {LOCKOUT_DURATION.seconds // 60} minutes.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ============== MODELS ==============

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    address = db.Column(db.Text)
    jobs = db.relationship('Job', backref='customer', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    quote_number = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float, default=0)  # Price ex GST
    deposit = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='quoted')
    notes = db.Column(db.Text)
    date = db.Column(db.Date, default=lambda: date.today())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Materials relationship
    materials = db.relationship('Material', backref='job', lazy=True, cascade='all, delete-orphan')
    
    @property
    def gst(self):
        return (self.price or 0) * GST_RATE
    
    @property
    def price_inc_gst(self):
        return (self.price or 0) * (1 + GST_RATE)
    
    @property
    def total_cogs(self):
        return sum(m.cost or 0 for m in self.materials)
    
    @property
    def gross_profit(self):
        return (self.price or 0) - self.total_cogs

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    category = db.Column(db.String(50), default='Materials')  # Labour, Materials, Freight, etc.
    description = db.Column(db.String(500))
    cost = db.Column(db.Float, default=0)  # COGS
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    filename = db.Column(db.String(200))
    original_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    size = db.Column(db.Integer)

class LoginAttempt(db.Model):
    """Track failed login attempts for security"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)  # IPv6 max length
    attempts = db.Column(db.Integer, default=1)
    locked_until = db.Column(db.DateTime, nullable=True, index=True)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

##############################################
# ============== DB INDEX / FTS HELPERS ==============
##############################################


def setup_indexes_and_fts():
    """
    Create database indexes for faster search queries.
    Simple indexed LIKE queries are fast enough for our dataset size.
    """
    from sqlalchemy import text
    
    # Plain B-tree indexes on frequently searched columns
    index_statements = [
        # Customer indexes
        "CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_customer_phone ON customer(phone)",
        "CREATE INDEX IF NOT EXISTS idx_customer_email ON customer(email COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_customer_address ON customer(address COLLATE NOCASE)",
        # Job indexes
        "CREATE INDEX IF NOT EXISTS idx_job_quote_number ON job(quote_number COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_job_description ON job(description COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_job_notes ON job(notes COLLATE NOCASE)",
        # Composite index for common filters
        "CREATE INDEX IF NOT EXISTS idx_job_customer_date ON job(customer_id, date)",
    ]

    with db.engine.begin() as conn:
        # Create indexes
        for stmt in index_statements:
            conn.execute(text(stmt))
        print("✓ Database indexes created")


##############################################
# ============== FINANCIAL YEAR HELPERS ==============
##############################################

def get_financial_year(d):
    """Get Australian financial year (July-June) for a date. Returns start year."""
    if d.month >= 7:
        return d.year
    return d.year - 1

def get_fy_dates(fy_year):
    """Get start and end dates for a financial year"""
    start = date(fy_year, 7, 1)
    end = date(fy_year + 1, 6, 30)
    return start, end

def get_fy_quarter(d):
    """Get financial year quarter (Q1=Jul-Sep, Q2=Oct-Dec, Q3=Jan-Mar, Q4=Apr-Jun)"""
    if d.month in [7, 8, 9]:
        return 1
    elif d.month in [10, 11, 12]:
        return 2
    elif d.month in [1, 2, 3]:
        return 3
    else:
        return 4

def get_quarter_dates(fy_year, quarter):
    """Get start and end dates for a financial quarter"""
    if quarter == 1:
        return date(fy_year, 7, 1), date(fy_year, 9, 30)
    elif quarter == 2:
        return date(fy_year, 10, 1), date(fy_year, 12, 31)
    elif quarter == 3:
        return date(fy_year + 1, 1, 1), date(fy_year + 1, 3, 31)
    else:
        return date(fy_year + 1, 4, 1), date(fy_year + 1, 6, 30)

def get_available_fys():
    """Get list of financial years with data"""
    min_date = db.session.query(db.func.min(Job.date)).scalar()
    max_date = db.session.query(db.func.max(Job.date)).scalar()
    if not min_date or not max_date:
        return [get_financial_year(date.today())]
    
    start_fy = get_financial_year(min_date)
    end_fy = get_financial_year(max_date)
    return list(range(end_fy, start_fy - 1, -1))

# ============== TEMPLATE FILTERS ==============

@app.template_filter('currency')
def currency_filter(value):
    try:
        return f"${float(value):,.2f}"
    except:
        return "$0.00"

@app.template_filter('currency_gst')
def currency_gst_filter(value):
    """Format currency with GST breakdown"""
    try:
        val = float(value)
        gst = val * GST_RATE
        inc = val * (1 + GST_RATE)
        return f"${val:,.2f} (+${gst:,.2f} GST = ${inc:,.2f})"
    except:
        return "$0.00"

@app.template_filter('with_gst')
def with_gst_filter(value):
    """Add GST to value"""
    try:
        return float(value) * (1 + GST_RATE)
    except:
        return 0

@app.template_filter('gst_only')
def gst_only_filter(value):
    """Calculate GST amount"""
    try:
        return float(value) * GST_RATE
    except:
        return 0

@app.template_filter('ausdate')
def ausdate_filter(value):
    if value:
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d').date()
            except:
                return value
        return value.strftime('%d/%m/%Y')
    return ''

@app.template_filter('isodate')
def isodate_filter(value):
    """Format date for HTML date input (YYYY-MM-DD)"""
    if value:
        if isinstance(value, str):
            return value
        return value.strftime('%Y-%m-%d')
    return date.today().strftime('%Y-%m-%d')

@app.template_filter('datetime')
def datetime_filter(value):
    if value:
        return value.strftime('%d/%m/%Y %H:%M')
    return ''

@app.template_filter('filesize')
def filesize_filter(value):
    try:
        value = int(value)
        if value < 1024:
            return f"{value} B"
        elif value < 1024 * 1024:
            return f"{value / 1024:.1f} KB"
        else:
            return f"{value / (1024 * 1024):.1f} MB"
    except:
        return "0 B"

@app.template_filter('fy_label')
def fy_label_filter(fy_year):
    """Format financial year label"""
    return f"FY{fy_year}/{str(fy_year+1)[-2:]}"

# ============== HELPER FUNCTIONS ==============

def generate_quote_number():
    last_job = Job.query.order_by(Job.id.desc()).first()
    if last_job and last_job.quote_number:
        try:
            num = int(last_job.quote_number.replace('Q', '').split('-')[0])
            return f"Q{num + 1:05d}"
        except:
            pass
    return "Q00001"

def parse_aus_date(date_str):
    """Parse Australian date format DD/MM/YYYY or ISO format"""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            return parsed_date
        except (ValueError, AttributeError):
            continue
    return None

def get_backup_dir():
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def create_backup(prefix='backup'):
    backup_dir = get_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'quoteforge_{prefix}_{timestamp}.db'
    src = os.path.join(os.path.dirname(__file__), 'instance', 'quoteforge.db')
    dst = os.path.join(backup_dir, backup_name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        return backup_name
    return None

def scheduled_backup():
    with app.app_context():
        create_backup('auto')
        print(f"[{datetime.now()}] Automatic backup created")

# ============== STATUS HELPERS ==============

STATUS_LABELS = {
    'quoted': 'Quoted',
    'deposit_paid': 'Deposit Paid',
    'in_progress': 'In Progress',
    'completed': 'Completed',
    'cancelled': 'Cancelled'
}

STATUS_COLORS = {
    'quoted': 'bg-yellow-500',
    'deposit_paid': 'bg-blue-500',
    'in_progress': 'bg-purple-500',
    'completed': 'bg-green-500',
    'cancelled': 'bg-red-500'
}

@app.context_processor
def utility_processor():
    return {
        'STATUS_LABELS': STATUS_LABELS,
        'STATUS_COLORS': STATUS_COLORS,
        'GST_RATE': GST_RATE,
        'today': date.today(),
        'current_fy': get_financial_year(date.today())
    }

# ============== ROUTES ==============

@app.route('/')
@login_required
def index():
    total_jobs = Job.query.count()
    total_customers = Customer.query.count()
    
    # Current financial year
    current_fy = get_financial_year(date.today())
    fy_start, fy_end = get_fy_dates(current_fy)
    
    # Total revenue (ex GST)
    total_revenue = db.session.query(db.func.sum(Job.price)).filter(
        Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
    ).scalar() or 0
    
    # FY revenue
    fy_revenue = db.session.query(db.func.sum(Job.price)).filter(
        Job.status.in_(['completed', 'deposit_paid', 'in_progress']),
        Job.date >= fy_start,
        Job.date <= fy_end
    ).scalar() or 0
    
    # Pending jobs count
    pending_jobs = Job.query.filter(
        Job.status.in_(['quoted', 'deposit_paid', 'in_progress'])
    ).count()
    
    # Recent jobs
    recent_jobs = Job.query.order_by(Job.date.desc()).limit(10).all()
    
    # Jobs by status
    status_counts = {}
    for status in STATUS_LABELS.keys():
        status_counts[status] = Job.query.filter(Job.status == status).count()
    
    return render_template('index.html', 
                         total_jobs=total_jobs,
                         total_customers=total_customers, 
                         total_revenue=total_revenue,
                         fy_revenue=fy_revenue,
                         pending_jobs=pending_jobs,
                         recent_jobs=recent_jobs,
                         status_counts=status_counts,
                         current_fy=current_fy)

@app.route('/index/lcars')
@login_required
def lcars_dashboard():
    """LCARS-style alternate dashboard"""
    total_jobs = Job.query.count()
    total_customers = Customer.query.count()
    
    # Current financial year
    current_fy = get_financial_year(date.today())
    fy_start, fy_end = get_fy_dates(current_fy)
    
    # Total revenue (ex GST)
    total_revenue = db.session.query(db.func.sum(Job.price)).filter(
        Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
    ).scalar() or 0
    
    # FY revenue
    fy_revenue = db.session.query(db.func.sum(Job.price)).filter(
        Job.status.in_(['completed', 'deposit_paid', 'in_progress']),
        Job.date >= fy_start,
        Job.date <= fy_end
    ).scalar() or 0
    
    # Pending jobs count
    pending_jobs = Job.query.filter(
        Job.status.in_(['quoted', 'deposit_paid', 'in_progress'])
    ).count()
    
    # Recent jobs
    recent_jobs = Job.query.order_by(Job.date.desc()).limit(10).all()
    
    # Jobs by status
    status_counts = {}
    for status in STATUS_LABELS.keys():
        status_counts[status] = Job.query.filter(Job.status == status).count()
    
    return render_template('lcars_dashboard.html', 
                         total_jobs=total_jobs,
                         total_customers=total_customers, 
                         total_revenue=total_revenue,
                         fy_revenue=fy_revenue,
                         pending_jobs=pending_jobs,
                         recent_jobs=recent_jobs,
                         status_counts=status_counts,
                         current_fy=current_fy)

@app.route('/index/lcars/jobs')
@login_required
def lcars_jobs():
    """LCARS Jobs List"""
    status = request.args.get('status')
    search = request.args.get('q', '')
    query = Job.query.order_by(Job.date.desc())
    
    if status:
        query = query.filter(Job.status == status)
        
    if search:
        search = search.strip()
        # Normalize: remove spaces and dashes for phone matching
        search_normalized = search.replace(' ', '').replace('-', '')
        
        # Build multiple search patterns
        query = query.join(Customer).filter(
            db.or_(
                Customer.name.ilike(f'%{search}%'),
                Customer.phone.ilike(f'%{search}%'),
                # Match normalized phone: remove spaces/dashes from both sides
                db.text(f"REPLACE(REPLACE(customer.phone, ' ', ''), '-', '') LIKE '%{search_normalized}%'"),
                Job.quote_number.ilike(f'%{search}%'),
                Job.description.ilike(f'%{search}%')
            )
        )
        
    jobs = query.limit(50).all()
    return render_template('lcars_jobs.html', jobs=jobs, search_query=search)

@app.route('/index/lcars/job/new')
@login_required
def lcars_new_job():
    """LCARS New Job Form"""
    return render_template('lcars_job_form.html', job=None)

@app.route('/index/lcars/customers')
@login_required
def lcars_customers():
    """LCARS Customers List"""
    customers = Customer.query.order_by(Customer.name).limit(50).all()
    return render_template('lcars_customers.html', customers=customers)

@app.route('/index/lcars/reports')
@login_required
def lcars_reports():
    """LCARS Reports (Redirect for now)"""
    return redirect(url_for('reports'))

@app.route('/index/lcars/backup')
@login_required
def lcars_backup():
    """LCARS Backup (Redirect for now)"""
    return redirect(url_for('backup_page'))

# ============== JOBS ROUTES ==============

@app.route('/jobs')
@login_required
def jobs():
    # Sanitize all inputs
    status_filter = sanitize_input(request.args.get('status', ''), max_length=50)
    search = sanitize_input(request.args.get('search', ''), max_length=200)
    fy_filter = sanitize_input(request.args.get('fy', ''), max_length=10)
    month_filter = sanitize_input(request.args.get('month', ''), max_length=10)
    quarter_filter = sanitize_input(request.args.get('quarter', ''), max_length=10)
    
    query = Job.query
    
    if status_filter:
        query = query.filter(Job.status == status_filter)
    
    # Financial year filter
    if fy_filter:
        try:
            fy = int(fy_filter)
            fy_start, fy_end = get_fy_dates(fy)
            query = query.filter(Job.date >= fy_start, Job.date <= fy_end)
        except:
            pass
    
    # Month filter (format: YYYY-MM)
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)
            query = query.filter(Job.date >= month_start, Job.date <= month_end)
        except:
            pass
    
    # Quarter filter (format: FY-Q, e.g., 2024-Q1)
    if quarter_filter and fy_filter:
        try:
            q = int(quarter_filter.replace('Q', ''))
            fy = int(fy_filter)
            q_start, q_end = get_quarter_dates(fy, q)
            query = query.filter(Job.date >= q_start, Job.date <= q_end)
        except:
            pass
    
    # Search - use indexed LIKE queries for fuzzy search
    if search:
        search = search.strip()
        if search:
            # Normalize search for phone matching (remove spaces/dashes)
            search_normalized = search.replace(' ', '').replace('-', '')
            
            # Search across key fields with phone normalization
            query = query.join(Customer).filter(
                db.or_(
                    Customer.name.ilike(f'%{search}%'),
                    Customer.phone.ilike(f'%{search}%'),
                    # Also match phone with spaces/dashes removed
                    func.replace(func.replace(Customer.phone, ' ', ''), '-', '').ilike(f'%{search_normalized}%'),
                    Customer.email.ilike(f'%{search}%'),
                    Job.quote_number.ilike(f'%{search}%'),
                    Job.description.ilike(f'%{search}%'),
                    Job.notes.ilike(f'%{search}%'),
                )
            )
    
    jobs_list = query.order_by(Job.date.desc()).all()
    available_fys = get_available_fys()
    
    return render_template('jobs.html', 
                         jobs=jobs_list, 
                         status_filter=status_filter, 
                         search=search,
                         fy_filter=fy_filter,
                         month_filter=month_filter,
                         quarter_filter=quarter_filter,
                         available_fys=available_fys)

@app.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def job_new():
    if request.method == 'POST':
        # Sanitize all form inputs
        customer_name = sanitize_input(request.form.get('customer_name', ''), max_length=200)
        customer_phone = sanitize_input(request.form.get('customer_phone', ''), max_length=50)
        customer_email = sanitize_input(request.form.get('customer_email', ''), max_length=200)
        customer_address = sanitize_input(request.form.get('customer_address', ''), max_length=500)
        
        # Find existing customer by phone first, then by name
        customer = None
        if customer_phone:
            customer = Customer.query.filter(Customer.phone == customer_phone).first()
        if not customer and customer_name:
            customer = Customer.query.filter(Customer.name.ilike(customer_name)).first()
        
        if not customer:
            customer = Customer(
                name=customer_name,
                phone=customer_phone,
                email=customer_email,
                address=customer_address
            )
            db.session.add(customer)
            db.session.flush()
        else:
            if customer_email and not customer.email:
                customer.email = customer_email
            if customer_address and not customer.address:
                customer.address = customer_address
            if customer_phone and not customer.phone:
                customer.phone = customer_phone
        
        # Create job
        job = Job(
            customer_id=customer.id,
            quote_number=generate_quote_number(),
            description=request.form.get('description', ''),
            price=float(request.form.get('price', 0) or 0),
            deposit=float(request.form.get('deposit', 0) or 0),
            status=request.form.get('status', 'quoted'),
            notes=request.form.get('notes', '')
        )
        
        # Parse date - default to today
        date_str = request.form.get('date', '').strip()
        parsed_date = parse_aus_date(date_str)
        job.date = parsed_date if parsed_date else date.today()
        
        db.session.add(job)
        db.session.flush()
        
        # Add materials
        material_descs = request.form.getlist('material_desc[]')
        material_costs = request.form.getlist('material_cost[]')
        material_categories = request.form.getlist('material_category[]')
        for desc, cost, category in zip(material_descs, material_costs, material_categories):
            if desc.strip():
                material = Material(
                    job_id=job.id,
                    category=category or 'Materials',
                    description=desc.strip(),
                    cost=float(cost or 0)
                )
                db.session.add(material)
        
        db.session.commit()
        flash(f'Job {job.quote_number} created successfully!', 'success')
        return redirect(url_for('job_detail', job_id=job.id))
    
    return render_template('job_form.html', job=None)

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return render_template('job_detail.html', job=job)

@app.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def job_edit(job_id):
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        job.description = request.form.get('description', '')
        job.price = float(request.form.get('price', 0) or 0)
        job.deposit = float(request.form.get('deposit', 0) or 0)
        job.status = request.form.get('status', 'quoted')
        job.notes = request.form.get('notes', '')
        
        job.customer.name = request.form.get('customer_name', job.customer.name)
        job.customer.phone = request.form.get('customer_phone', job.customer.phone)
        job.customer.email = request.form.get('customer_email', job.customer.email)
        job.customer.address = request.form.get('customer_address', job.customer.address)
        
        date_str = request.form.get('date', '').strip()
        if date_str:
            parsed_date = parse_aus_date(date_str)
            if parsed_date:
                job.date = parsed_date
        
        # Update materials - delete existing and add new
        Material.query.filter_by(job_id=job.id).delete()
        material_descs = request.form.getlist('material_desc[]')
        material_costs = request.form.getlist('material_cost[]')
        material_categories = request.form.getlist('material_category[]')
        for desc, cost, category in zip(material_descs, material_costs, material_categories):
            if desc.strip():
                material = Material(
                    job_id=job.id,
                    category=category or 'Materials',
                    description=desc.strip(),
                    cost=float(cost or 0)
                )
                db.session.add(material)
        
        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('job_detail', job_id=job.id))
    
    return render_template('job_form.html', job=job)

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def job_delete(job_id):
    job = Job.query.get_or_404(job_id)
    quote_num = job.quote_number
    db.session.delete(job)
    db.session.commit()
    flash(f'Job {quote_num} deleted.', 'success')
    return redirect(url_for('jobs'))

# ============== CUSTOMERS ROUTES ==============

@app.route('/customers')
@login_required
def customers():
    # Sanitize search input
    search = sanitize_input(request.args.get('search', ''), max_length=200)
    query = Customer.query
    
    if search:
        search = search.strip()
        if search:
            # Normalize search for phone matching (remove spaces)
            search_normalized = search.replace(' ', '').replace('-', '')
            
            # Search across key fields, with phone normalization
            query = query.filter(
                db.or_(
                    Customer.name.ilike(f'%{search}%'),
                    Customer.phone.ilike(f'%{search}%'),
                    # Also match phone with spaces removed
                    func.replace(func.replace(Customer.phone, ' ', ''), '-', '').ilike(f'%{search_normalized}%'),
                    Customer.email.ilike(f'%{search}%'),
                    Customer.address.ilike(f'%{search}%'),
                )
            )
    
    customers_list = query.order_by(Customer.name).all()
    return render_template('customers.html', customers=customers_list, search=search)

@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    total_spent = sum(j.price for j in customer.jobs if j.status in ['completed', 'deposit_paid', 'in_progress'])
    return render_template('customer_detail.html', customer=customer, total_spent=total_spent)

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def customer_edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        customer.name = request.form.get('name', customer.name)
        customer.phone = request.form.get('phone', customer.phone)
        customer.email = request.form.get('email', customer.email)
        customer.address = request.form.get('address', customer.address)
        db.session.commit()
        flash('Customer updated!', 'success')
        return redirect(url_for('customer_detail', customer_id=customer.id))
    
    return render_template('customer_form.html', customer=customer)

# ============== API ROUTES ==============

@app.route('/api/customers/search')
@login_required
def api_customer_search():
    # Sanitize search query
    q = sanitize_input(request.args.get('q', ''), max_length=200)
    if len(q) < 1:
        return jsonify([])

    # Normalize for phone matching (remove spaces/dashes)
    q_normalized = q.replace(' ', '').replace('-', '')
    
    # Search for autocomplete with phone normalization
    customers = (
        Customer.query.filter(
            db.or_(
                Customer.name.ilike(f'%{q}%'),
                Customer.phone.ilike(f'%{q}%'),
                # Also match phone with spaces/dashes removed
                func.replace(func.replace(Customer.phone, ' ', ''), '-', '').ilike(f'%{q_normalized}%'),
                Customer.email.ilike(f'%{q}%'),
            )
        )
        .order_by(Customer.name)
        .limit(15)
        .all()
    )
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'phone': c.phone or '',
        'email': c.email or '',
        'address': c.address or ''
    } for c in customers])

@app.route('/api/customers/search/full')
@login_required
def api_customer_search_full():
    """Full customer search for AJAX - returns all matches with job count"""
    # Sanitize search query
    q = sanitize_input(request.args.get('q', ''), max_length=200)
    
    query = Customer.query
    
    if q:
        # Normalize for phone matching
        q_normalized = q.replace(' ', '').replace('-', '')
        
        query = query.filter(
            db.or_(
                Customer.name.ilike(f'%{q}%'),
                Customer.phone.ilike(f'%{q}%'),
                func.replace(func.replace(Customer.phone, ' ', ''), '-', '').ilike(f'%{q_normalized}%'),
                Customer.email.ilike(f'%{q}%'),
                Customer.address.ilike(f'%{q}%'),
            )
        )
    
    customers = query.order_by(Customer.name).limit(500).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'phone': c.phone or '',
        'email': c.email or '',
        'address': c.address or '',
        'job_count': len(c.jobs)
    } for c in customers])

# ============== REPORTS ROUTES ==============

@app.route('/reports')
@login_required
def reports():
    fy_filter = request.args.get('fy', '')
    quarter_filter = request.args.get('quarter', '')
    month_filter = request.args.get('month', '')
    
    available_fys = get_available_fys()
    current_fy = get_financial_year(date.today())
    
    # Default to current FY
    selected_fy = int(fy_filter) if fy_filter else current_fy
    fy_start, fy_end = get_fy_dates(selected_fy)
    
    # Build date filter
    date_start, date_end = fy_start, fy_end
    
    if quarter_filter:
        try:
            q = int(quarter_filter.replace('Q', ''))
            date_start, date_end = get_quarter_dates(selected_fy, q)
        except:
            pass
    elif month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            date_start = date(year, month, 1)
            if month == 12:
                date_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                date_end = date(year, month + 1, 1) - timedelta(days=1)
        except:
            pass
    
    # Revenue data
    total_revenue = db.session.query(db.func.sum(Job.price)).filter(
        Job.date >= date_start,
        Job.date <= date_end,
        Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
    ).scalar() or 0
    
    total_cogs = db.session.query(db.func.sum(Material.cost)).join(Job).filter(
        Job.date >= date_start,
        Job.date <= date_end,
        Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
    ).scalar() or 0
    
    gross_profit = total_revenue - total_cogs
    total_gst = total_revenue * GST_RATE
    
    # Monthly breakdown for selected period
    monthly_data = []
    current = date_start
    while current <= date_end:
        month_start = date(current.year, current.month, 1)
        if current.month == 12:
            month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)
        
        revenue = db.session.query(db.func.sum(Job.price)).filter(
            Job.date >= month_start,
            Job.date <= month_end,
            Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
        ).scalar() or 0
        
        cogs = db.session.query(db.func.sum(Material.cost)).join(Job).filter(
            Job.date >= month_start,
            Job.date <= month_end,
            Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
        ).scalar() or 0
        
        # Format month in Australian style (DD MMM YYYY)
        monthly_data.append({
            'month': month_start.strftime('%d %b %Y'),  # e.g., "01 Jul 2025"
            'revenue': revenue,
            'cogs': cogs,
            'gst': revenue * GST_RATE,
            'profit': revenue - cogs
        })
        
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    
    # Quarterly breakdown
    quarterly_data = []
    for q in range(1, 5):
        q_start, q_end = get_quarter_dates(selected_fy, q)
        revenue = db.session.query(db.func.sum(Job.price)).filter(
            Job.date >= q_start,
            Job.date <= q_end,
            Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
        ).scalar() or 0
        
        # Format quarter period in Australian style
        quarterly_data.append({
            'quarter': f'Q{q}',
            'period': f"{q_start.strftime('%d %b')} - {q_end.strftime('%d %b %Y')}",  # e.g., "01 Jul - 30 Sep 2025"
            'revenue': revenue,
            'gst': revenue * GST_RATE
        })
    
    # Revenue by status
    revenue_by_status = db.session.query(
        Job.status,
        db.func.sum(Job.price).label('revenue')
    ).filter(
        Job.date >= date_start,
        Job.date <= date_end
    ).group_by(Job.status).all()
    
    # Top customers
    top_customers = db.session.query(
        Customer,
        db.func.sum(Job.price).label('total')
    ).join(Job).filter(
        Job.date >= date_start,
        Job.date <= date_end,
        Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
    ).group_by(Customer.id).order_by(db.desc('total')).limit(10).all()
    
    # Year-over-year comparison (if multiple years available)
    year_comparison = []
    if len(available_fys) > 1:
        for fy in sorted(available_fys)[-5:]:  # Last 5 years
            fy_s, fy_e = get_fy_dates(fy)
            fy_revenue = db.session.query(db.func.sum(Job.price)).filter(
                Job.date >= fy_s,
                Job.date <= fy_e,
                Job.status.in_(['completed', 'deposit_paid', 'in_progress'])
            ).scalar() or 0
            year_comparison.append({
                'year': fy,
                'revenue': fy_revenue
            })
    
    return render_template('reports.html', 
                         monthly_data=monthly_data,
                         quarterly_data=quarterly_data,
                         top_customers=top_customers,
                         revenue_by_status=revenue_by_status,
                         year_comparison=year_comparison,
                         total_revenue=total_revenue,
                         total_cogs=total_cogs,
                         gross_profit=gross_profit,
                         total_gst=total_gst,
                         available_fys=available_fys,
                         selected_fy=selected_fy,
                         fy_filter=fy_filter,
                         quarter_filter=quarter_filter,
                         month_filter=month_filter,
                         date_start=date_start,
                         date_end=date_end)

# ============== BACKUP ROUTES ==============

@app.route('/backup')
@login_required
def backup_page():
    backup_dir = get_backup_dir()
    backups = []
    
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.db'):
                path = os.path.join(backup_dir, f)
                backups.append({
                    'filename': f,
                    'size': os.path.getsize(path),
                    'date': datetime.fromtimestamp(os.path.getmtime(path))
                })
    
    return render_template('backup.html', backups=backups)

@app.route('/backup/create', methods=['POST'])
@login_required
def backup_create():
    backup_name = create_backup('manual')
    if backup_name:
        flash(f'Backup created: {backup_name}', 'success')
    else:
        flash('Backup failed!', 'error')
    return redirect(url_for('backup_page'))

@app.route('/backup/download/<filename>')
@login_required
def backup_download(filename):
    # Sanitize filename to prevent path traversal
    filename = secure_filename(filename)
    if not filename or '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backup_page'))
    
    backup_dir = get_backup_dir()
    filepath = os.path.join(backup_dir, filename)
    # Ensure file is within backup directory (prevent path traversal)
    if not os.path.abspath(filepath).startswith(os.path.abspath(backup_dir)):
        flash('Invalid file path', 'error')
        return redirect(url_for('backup_page'))
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Backup file not found', 'error')
    return redirect(url_for('backup_page'))

@app.route('/backup/restore/<filename>', methods=['POST'])
@login_required
def backup_restore(filename):
    # Sanitize filename to prevent path traversal
    filename = secure_filename(filename)
    if not filename or '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backup_page'))
    
    backup_dir = get_backup_dir()
    backup_path = os.path.join(backup_dir, filename)
    # Ensure file is within backup directory
    if not os.path.abspath(backup_path).startswith(os.path.abspath(backup_dir)):
        flash('Invalid file path', 'error')
        return redirect(url_for('backup_page'))
    
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'quoteforge.db')
    
    if not os.path.exists(backup_path):
        flash('Backup file not found', 'error')
        return redirect(url_for('backup_page'))
    
    safety_backup = create_backup('pre_restore_safety')
    db.session.remove()
    db.engine.dispose()
    shutil.copy2(backup_path, db_path)
    
    flash(f'Database restored from {filename}. Safety backup: {safety_backup}', 'success')
    return redirect(url_for('backup_page'))

@app.route('/backup/delete/<filename>', methods=['POST'])
@login_required
def backup_delete(filename):
    # Sanitize filename to prevent path traversal
    filename = secure_filename(filename)
    if not filename or '..' in filename or '/' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('backup_page'))
    
    backup_dir = get_backup_dir()
    filepath = os.path.join(backup_dir, filename)
    # Ensure file is within backup directory
    if not os.path.abspath(filepath).startswith(os.path.abspath(backup_dir)):
        flash('Invalid file path', 'error')
        return redirect(url_for('backup_page'))
    
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'Backup {filename} deleted', 'success')
    else:
        flash('Backup file not found', 'error')
    return redirect(url_for('backup_page'))

# ============== SECURITY MIDDLEWARE ==============

@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Remove server header
    response.headers.pop('Server', None)
    return response

def cleanup_old_login_attempts():
    """Clean up login attempts older than 24 hours"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    LoginAttempt.query.filter(LoginAttempt.last_attempt < cutoff).delete()
    db.session.commit()

# ============== MAIN ==============

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Setup indexes and FTS for fast fuzzy search
        try:
            setup_indexes_and_fts()
        except Exception as e:
            # Do not crash app if FTS is not available; log to console instead
            print(f"[WARN] Failed to setup indexes/FTS: {e}")
        
        # Clean up old login attempts on startup
        try:
            cleanup_old_login_attempts()
        except Exception as e:
            print(f"[WARN] Failed to cleanup login attempts: {e}")
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_backup, trigger='cron', hour=2, minute=0)
    # Clean up old login attempts every hour
    scheduler.add_job(func=cleanup_old_login_attempts, trigger='cron', hour='*', minute=0)
    scheduler.start()
    
    app.run(host='0.0.0.0', port=8001, debug=False)
