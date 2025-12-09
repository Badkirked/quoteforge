# QuoteForge - Job Quoting System

**Version**: 2.0 LCARS Edition  
**Location**: 192.168.0.144:8001  
**Persistent URL**: quoteforge.notermsandconditions.com  
**GitHub**: https://github.com/badkirked/quoteforge

## Overview

QuoteForge is a Flask-based job quoting and customer management system for an upholstery workshop. Features both a modern Tailwind CSS interface and an authentic LCARS (Star Trek) themed interface.

## Access

- **Standard Dashboard**: http://192.168.0.144:8001/
- **LCARS Dashboard**: http://192.168.0.144:8001/index/lcars
- **Persistent Tunnel**: https://quoteforge.notermsandconditions.com

## Login

- **Password**: davidbudgewoijanet
- **Security**: 3 failed attempts = 30 minute lockout

## Features

### Core Features
- Customer management with full search
- Job/quote tracking with quote numbers
- Material tracking with categories (Labour, Materials, Freight, Equipment, Other)
- COGS (Cost of Goods Sold) tracking
- GST calculation (10%) on all financial fields
- Australian date format (DD/MM/YYYY)
- Financial year reporting (July-June Australian FY)

### Search & Filtering
- Fuzzy search across all name/phone fields
- Phone number normalisation (finds "0412 314081" and "0412314081")
- Filter by year, month, quarter
- Filter by job status (Pending, Completed, Paid)

### Reports
- Revenue reports with interactive charts
- Monthly/quarterly/yearly breakdowns
- GST summaries
- Customer statistics

### Backup & Restore
- Automatic daily backups
- Manual backup download
- Database restore from backup

### LCARS Interface
- Authentic Star Trek LCARS design
- Boot sequence with progress bar
- 8-bit sound effects (click to enable audio)
- Sequential panel loading animation
- Full functionality matching standard interface

## Technical Details

### Stack
- **Backend**: Flask, SQLAlchemy, SQLite
- **Frontend**: Tailwind CSS, JavaScript, Chart.js
- **LCARS**: Custom CSS, Web Audio API for sounds
- **Tunnel**: Cloudflare Tunnel (persistent)

### Database
- SQLite with indexed columns for fast search
- Models: Customer, Job, Material, LoginAttempt

### Security
- Password hashing (Werkzeug)
- Session management
- Login attempt tracking
- SQL injection protection (parameterised queries)
- Rate limiting on login

### Files
- `app.py` - Main application
- `templates/` - Jinja2 templates
- `templates/base_lcars.html` - LCARS base template
- `quoteforge.db` - SQLite database
- `backups/` - Backup directory

## Cloudflare Tunnel

### Persistent Tunnel
- **Tunnel ID**: fa0cb218-2d39-4651-a444-0a2ac50a9c3b
- **Service**: cloudflared (systemd)
- **Hostname**: quoteforge.notermsandconditions.com

### Management
```bash
# Check tunnel status
sudo systemctl status cloudflared

# Restart tunnel
sudo systemctl restart cloudflared

# View logs
sudo journalctl -u cloudflared -f
```

## Quick Start

```bash
cd /home/bad/Desktop/David/quoteforge
python3 app.py
```

## Data Import

Excel files for import should be placed in the quoteforge directory:
- `quotes version 1 autosave.xlsx`

Run import script:
```bash
python3 import_xlsx.py
```

## Maintenance

### Start App
```bash
cd /home/bad/Desktop/David/quoteforge
python3 app.py &
```

### Check Status
```bash
ps aux | grep "python3 app.py"
curl http://localhost:8001/
```

### Restart
```bash
pkill -f "python3 app.py"
python3 app.py &
```

## Last Updated
- Date: 9 December 2025
- Features: LCARS sound effects, full search, GST, materials, charts
