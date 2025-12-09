# QuoteForge - Upholstery Quote Management System

**Version**: 2.0
**Location**: `/home/bad/Desktop/David/quoteforge`
**Port**: `8001`
**URL**: `https://quoteforge.notermsandconditions.com`
**Password**: `davidbudgewoijanet`

## Overview

QuoteForge is a Flask-based web application for managing quotes, jobs, customers, and financial reporting for an upholstery business. Features include Australian financial year reporting, GST calculations, materials tracking (COGS), comprehensive search capabilities, interactive charts, and enterprise-grade security.

## Features

### Core Functionality
- **Job Management**: Create, edit, delete jobs with quote numbers
- **Customer Management**: Full customer database with advanced search
- **Materials Tracking**: Track materials with categories (Labour, Materials, Freight, Subcontractor, Other)
- **GST Calculation**: Automatic 10% GST on all pricing
- **Financial Reporting**: Australian Financial Year (July-June) reporting with quarterly/monthly breakdowns
- **Interactive Charts**: 5+ chart types for data visualization
- **Backup & Restore**: Database backup system with scheduled daily backups

### Search & Filtering
- **AJAX Search**: Live search as you type (300ms delay) - no page reloads
- **Phone Normalization**: Searches work with or without spaces/dashes in phone numbers
- **Full Text Search**: Search across name, phone, email, address, quote number, description, notes
- **Date Filtering**: Filter by Financial Year, Quarter, or Month
- **Status Filtering**: Filter jobs by status (Quoted, Deposit Paid, In Progress, Completed, Cancelled)

### Charts & Analytics
- **Monthly Revenue Trend**: Line chart showing revenue over time
- **Revenue vs Profit vs COGS**: Stacked bar chart showing cost breakdown
- **Quarterly Comparison**: Bar chart comparing all quarters
- **Revenue by Status**: Doughnut chart showing status distribution
- **Year-over-Year Comparison**: Bar chart for historical comparison

### Security Features
- **Login Attempt Tracking**: 3 failed attempts → 30-minute lockout
- **IP-based Lockout**: Tracks failed attempts by IP address
- **Password Hashing**: Uses werkzeug.security for secure password storage
- **Input Sanitization**: All user inputs sanitized to prevent injection attacks
- **Path Traversal Protection**: Secure file operations for backups
- **Security Headers**: XSS, CSRF, and clickjacking protection
- **Session Security**: Secure session management with ID regeneration

### Australian Formatting
- **Dates**: All dates display in DD/MM/YYYY format
- **Financial Year**: July-June financial year reporting
- **Currency**: Australian dollar formatting with GST breakdown

## Technology Stack

- **Framework**: Flask (Python)
- **Database**: SQLite (`instance/quoteforge.db`)
- **ORM**: SQLAlchemy
- **Scheduler**: APScheduler (daily backups at 2am)
- **Frontend**: Tailwind CSS, Jinja2 templates
- **Tunnel**: Cloudflare Tunnel (persistent named tunnel)

## Database Schema

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

## Installation & Setup

### Prerequisites
```bash
pip3 install flask flask-sqlalchemy apscheduler openpyxl werkzeug
```

### Database Initialization
```bash
cd /home/bad/Desktop/David/quoteforge
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### Running the Application
```bash
cd /home/bad/Desktop/David/quoteforge
python3 app.py
```

The app will run on `http://0.0.0.0:8001`

## Cloudflare Tunnel Setup

### Persistent Tunnel (Systemd Service)

The app runs behind a persistent Cloudflare Tunnel configured as a systemd service.

**Tunnel ID**: `fa0cb218-2d39-4651-a444-0a2ac50a9c3b`  
**Connector ID**: `f039400b-8fa4-4271-a3b4-0fb3ff6e77c4`  
**Service**: `cloudflared.service`

**Configuration**:
- **Hostname**: `quoteforge.notermsandconditions.com`
- **Service**: `http://192.168.0.144:8001`
- **Tunnel Token**: Configured in systemd service

**Service Management**:
```bash
# Check status
sudo systemctl status cloudflared

# Restart tunnel
sudo systemctl restart cloudflared

# View logs
sudo journalctl -u cloudflared -f
```

**Important**: Ensure QuoteForge is running on port 8001. If another app takes port 8001, QuoteForge won't be accessible.

## Routes

### Public Routes
- `/login` - Login page (password: `davidbudgewoijanet`)

### Protected Routes (require login)
- `/` - Dashboard
- `/jobs` - Job list with filters and AJAX search
- `/jobs/new` - Create new job
- `/jobs/<id>` - Job detail
- `/jobs/<id>/edit` - Edit job
- `/jobs/<id>/delete` - Delete job (POST)
- `/customers` - Customer list with AJAX search
- `/customers/<id>` - Customer detail
- `/customers/<id>/edit` - Edit customer
- `/reports` - Financial reports with interactive charts
- `/backup` - Backup management

### API Routes
- `/api/customers/search?q=<query>` - Customer autocomplete (sanitized)
- `/api/customers/search/full?q=<query>` - Full customer search for AJAX

## Key Features Explained

### Financial Year Reporting
- Australian Financial Year: July 1 - June 30
- Reports show FY2024/25, FY2025/26, etc.
- Quarterly breakdown: Q1 (Jul-Sep), Q2 (Oct-Dec), Q3 (Jan-Mar), Q4 (Apr-Jun)
- Monthly breakdown within selected period

### GST Calculation
- All prices stored **ex GST**
- GST calculated at 10%
- Display shows: Price ex GST, GST amount, Total inc GST
- Reports include GST summary for BAS

### Materials & COGS
- Materials categorized: Labour, Materials, Freight, Subcontractor, Other
- Total COGS calculated automatically
- Gross Profit = Revenue - COGS
- Margin percentage calculated

### Search Functionality
- **Live/Fuzzy Search**: Updates as you type (300ms delay)
- Searches: Name, Phone, Email, Address, Quote Number, Description, Notes
- No Enter key required - automatic submission

## Backup System

### Automatic Backups
- Scheduled daily at 2:00 AM
- Stored in `backups/` directory
- Format: `quoteforge_auto_YYYYMMDD_HHMMSS.db`

### Manual Backups
- Create via `/backup` page
- Format: `quoteforge_manual_YYYYMMDD_HHMMSS.db`

### Restore
- Select backup from `/backup` page
- Creates safety backup before restore
- Restores entire database

## Troubleshooting

### Port Conflict
If another app is using port 8001:
```bash
# Find what's using port 8001
ss -tlnp | grep :8001

# Kill the process
kill <PID>

# Restart QuoteForge
cd /home/bad/Desktop/David/quoteforge
python3 app.py &
```

### Tunnel Not Working
```bash
# Check tunnel status
sudo systemctl status cloudflared

# Check tunnel logs
sudo journalctl -u cloudflared -n 50

# Verify app is running
curl http://localhost:8001/login

# Restart tunnel
sudo systemctl restart cloudflared
```

### Database Issues
```bash
# Recreate database (WARNING: Deletes all data)
cd /home/bad/Desktop/David/quoteforge
rm instance/quoteforge.db
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

## File Structure

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
└── cloudflared           # Cloudflared binary
```

## Charts & Analytics

The reports page includes 5 interactive chart types:

1. **Monthly Revenue Trend** (Line Chart)
   - Shows revenue ex GST and inc GST over time
   - Smooth curves with filled areas

2. **Revenue vs Profit vs COGS** (Stacked Bar Chart)
   - Monthly breakdown showing cost composition
   - Red: COGS, Green: Gross Profit

3. **Quarterly Comparison** (Bar Chart)
   - Compares all 4 quarters side-by-side
   - Shows revenue ex GST and GST separately

4. **Revenue by Status** (Doughnut Chart)
   - Pie chart showing revenue distribution by job status
   - Interactive tooltips with percentages

5. **Year-over-Year Comparison** (Bar Chart)
   - Compares revenue across multiple financial years
   - Only shows when multiple years of data exist

All charts use Chart.js library and are responsive for mobile/desktop.

## Search Features

### AJAX Search
- **Live Search**: Updates results as you type (300ms debounce)
- **No Page Reloads**: Smooth user experience with AJAX
- **Phone Normalization**: Searches work regardless of phone formatting
- **Full Text**: Searches across all relevant fields

### Search Fields
- **Jobs**: Customer name, phone, email, quote number, description, notes
- **Customers**: Name, phone, email, address
- **Autocomplete**: Phone and name search in job forms

## Development Notes

- **Date Format**: All dates use Australian format (DD/MM/YYYY)
- **Default Date**: New jobs default to today's date
- **Quote Numbers**: Auto-generated sequential (Q00001, Q00002, etc.)
- **Session**: Login sessions last 30 days with secure regeneration
- **Debug Mode**: Disabled in production
- **AJAX**: Frontend uses AJAX for search to prevent page reloads
- **Charts**: Interactive charts using Chart.js for data visualization

## Security

### Authentication & Authorization
- **Password Protection**: All routes protected except `/login`
- **Session Management**: Flask sessions with 30-day expiry and secure regeneration
- **Login Attempt Tracking**: Tracks failed login attempts by IP address
- **Account Lockout**: 3 failed attempts → 30-minute lockout period
- **Password Hashing**: Uses werkzeug.security with bcrypt algorithm

### Input Security
- **SQL Injection Protection**: All queries use parameterized SQLAlchemy ORM
- **XSS Protection**: Jinja2 auto-escaping + input sanitization
- **Input Sanitization**: All user inputs sanitized (max lengths, null byte removal)
- **Path Traversal Protection**: Secure filename handling for backup operations
- **Phone Normalization**: Searches work with or without formatting in phone numbers

### Network Security
- **Security Headers**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` (anti-clickjacking)
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security` (HSTS)
  - Server header removed
- **Cloudflare Tunnel**: Encrypted tunnel with zero-trust security
- **IP-based Protection**: Failed login tracking by IP address

### Data Protection
- **Backup Security**: Encrypted database backups with secure paths
- **File Upload Protection**: No file uploads currently (safe from upload vulnerabilities)
- **Session Security**: Secure session cookie settings

## Future Enhancements

- Export to PDF/Excel
- Email notifications
- Multi-user support
- Document attachments
- Invoice generation
- Payment tracking

