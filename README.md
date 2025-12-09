# QuoteForge v2.0

**Professional Upholstery Quote Management System**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Enterprise-red.svg)](SECURITY.md)

QuoteForge is a comprehensive Flask-based web application for managing quotes, jobs, customers, and financial reporting for upholstery businesses. Built with Australian financial year reporting, GST calculations, materials tracking (COGS), interactive charts, and enterprise-grade security.

## 🚀 Features

### Core Functionality
- ✅ **Job Management**: Create, edit, delete jobs with auto-generated quote numbers
- ✅ **Customer Management**: Full customer database with advanced AJAX search
- ✅ **Materials Tracking**: Track materials with categories (Labour, Materials, Freight, Subcontractor, Other)
- ✅ **GST Calculation**: Automatic 10% GST on all pricing (Australian tax compliant)
- ✅ **Financial Reporting**: Australian Financial Year (July-June) reporting with quarterly/monthly breakdowns
- ✅ **Interactive Charts**: 5+ chart types for data visualization (Chart.js)
- ✅ **Backup & Restore**: Automated daily backups with manual restore capability

### Search & Filtering
- 🔍 **AJAX Search**: Live search as you type (300ms delay) - no page reloads
- 📱 **Phone Normalization**: Searches work with or without spaces/dashes in phone numbers
- 🔎 **Full Text Search**: Search across name, phone, email, address, quote number, description, notes
- 📅 **Date Filtering**: Filter by Financial Year, Quarter, or Month
- 🏷️ **Status Filtering**: Filter jobs by status (Quoted, Deposit Paid, In Progress, Completed, Cancelled)

### Charts & Analytics
- 📈 **Monthly Revenue Trend**: Line chart showing revenue over time
- 📊 **Revenue vs Profit vs COGS**: Stacked bar chart showing cost breakdown
- 📉 **Quarterly Comparison**: Bar chart comparing all quarters
- 🥧 **Revenue by Status**: Doughnut chart showing status distribution
- 📆 **Year-over-Year Comparison**: Bar chart for historical comparison

### Security Features
- 🔒 **Login Attempt Tracking**: 3 failed attempts → 30-minute lockout
- 🛡️ **IP-based Lockout**: Tracks failed attempts by IP address
- 🔐 **Password Hashing**: Uses werkzeug.security with bcrypt algorithm
- 🧹 **Input Sanitization**: All user inputs sanitized to prevent injection attacks
- 🚫 **Path Traversal Protection**: Secure file operations for backups
- 🔒 **Security Headers**: XSS, CSRF, and clickjacking protection
- 🔑 **Session Security**: Secure session management with ID regeneration

### Australian Formatting
- 🇦🇺 **Dates**: All dates display in DD/MM/YYYY format
- 📅 **Financial Year**: July-June financial year reporting
- 💰 **Currency**: Australian dollar formatting with GST breakdown

## 📋 Requirements

- Python 3.12+
- Flask 3.0+
- SQLite 3.x
- Modern web browser

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Badkirked/quoteforge.git
cd quoteforge
```

### 2. Install Dependencies
```bash
pip3 install flask flask-sqlalchemy apscheduler openpyxl werkzeug
```

### 3. Initialize Database
```bash
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 4. Run the Application
```bash
python3 app.py
```

The app will run on `http://0.0.0.0:8001`

**Default Login**: `davidbudgewoijanet` (change in `app.py`)

## 📁 Project Structure

```
quoteforge/
├── app.py                 # Main Flask application
├── instance/
│   └── quoteforge.db     # SQLite database
├── templates/            # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   ├── jobs.html
│   ├── job_form.html
│   ├── job_detail.html
│   ├── customers.html
│   ├── customer_detail.html
│   ├── reports.html
│   ├── backup.html
│   └── login.html
├── backups/              # Database backups
├── QUOTEFORGE.md         # Detailed documentation
└── README.md             # This file
```

## 🗄️ Database Schema

### Customer
- `id` (Primary Key)
- `name` (String, Required)
- `phone` (String, Unique)
- `email` (String)
- `address` (Text)
- `created_at` (DateTime)

### Job
- `id` (Primary Key)
- `customer_id` (Foreign Key → Customer)
- `quote_number` (String, Unique) - Format: Q00001, Q00002, etc.
- `description` (Text)
- `price` (Float) - Price ex GST
- `deposit` (Float)
- `status` (String) - Default: 'quoted'
- `notes` (Text)
- `date` (Date) - Defaults to today
- `created_at` (DateTime)

**Properties**:
- `gst` - Calculated GST (10% of price)
- `price_inc_gst` - Price including GST
- `total_cogs` - Sum of all material costs
- `gross_profit` - Price minus COGS

### Material
- `id` (Primary Key)
- `job_id` (Foreign Key → Job)
- `category` (String) - Labour, Materials, Freight, Subcontractor, Other
- `description` (String)
- `cost` (Float) - COGS
- `created_at` (DateTime)

## 🔧 Configuration

### Cloudflare Tunnel (Optional)
For public access, configure a Cloudflare Tunnel:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Create tunnel
cloudflared tunnel create quoteforge

# Configure tunnel
# Add Public Hostname: quoteforge.yourdomain.com → http://localhost:8001
```

### Scheduled Backups
Backups run automatically daily at 2:00 AM via APScheduler.

## 🔐 Security

### Authentication
- Password-protected login (default: `davidbudgewoijanet`)
- 3 failed attempts → 30-minute IP lockout
- Secure password hashing with bcrypt
- Session management with secure regeneration

### Input Protection
- All inputs sanitized (max lengths, null byte removal)
- SQL injection protection via SQLAlchemy ORM
- XSS protection via Jinja2 auto-escaping
- Path traversal protection for file operations

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security`

## 📊 API Routes

### Public Routes
- `GET /login` - Login page

### Protected Routes (require login)
- `GET /` - Dashboard
- `GET /jobs` - Job list with filters
- `GET /jobs/new` - Create new job
- `GET /jobs/<id>` - Job detail
- `GET /jobs/<id>/edit` - Edit job
- `POST /jobs/<id>/delete` - Delete job
- `GET /customers` - Customer list
- `GET /customers/<id>` - Customer detail
- `GET /customers/<id>/edit` - Edit customer
- `GET /reports` - Financial reports with charts
- `GET /backup` - Backup management

### API Endpoints
- `GET /api/customers/search?q=<query>` - Customer autocomplete
- `GET /api/customers/search/full?q=<query>` - Full customer search (AJAX)

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process using port 8001
lsof -i :8001

# Kill process
kill <PID>

# Restart QuoteForge
python3 app.py
```

### Database Issues
```bash
# Recreate database (WARNING: Deletes all data)
rm instance/quoteforge.db
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### Login Lockout
Wait 30 minutes or clear login attempts:
```python
from app import app, db, LoginAttempt
with app.app_context():
    LoginAttempt.query.delete()
    db.session.commit()
```

## 📝 Development

### Adding New Features
1. Update database models in `app.py`
2. Create migrations if needed
3. Update templates in `templates/`
4. Add routes in `app.py`
5. Update `QUOTEFORGE.md` documentation

### Code Style
- Follow PEP 8 Python style guide
- Use type hints where possible
- Document complex functions
- Keep templates DRY (Don't Repeat Yourself)

## 📄 License

MIT License - See LICENSE file for details

## 👤 Author

**badkirked**
- GitHub: [@Badkirked](https://github.com/Badkirked)

## 🙏 Acknowledgments

- Flask team for the excellent framework
- Chart.js for beautiful charts
- Tailwind CSS for styling
- Cloudflare for tunnel services

## 📚 Documentation

For detailed documentation, see [QUOTEFORGE.md](QUOTEFORGE.md)

## 🔄 Version History

### v2.0 (Current)
- ✅ Enterprise-grade security features
- ✅ Interactive charts (Chart.js)
- ✅ AJAX search functionality
- ✅ Phone number normalization
- ✅ Comprehensive input sanitization
- ✅ Security headers and protection

### v1.0
- Initial release
- Basic job and customer management
- Financial reporting
- Backup system

---

**Made with ❤️ for upholstery businesses**

