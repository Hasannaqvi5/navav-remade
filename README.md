# NavAv

**Purpose-built attendance tracking for Canadian Naval Reserve units.**

A modern replacement for NavAv (navav.net) with a military-flavoured UI, muster roll dashboard, invite-only registration, and per-unit Twilio SMS support.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Docker Desktop (for PostgreSQL)

### 1. Clone / navigate to the project


### 2. Start the database
```powershell
docker compose up -d
```

### 3. Create and activate a virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 4. Install dependencies
```powershell
pip install -r requirements.txt
```

### 5. Set up environment variables
```powershell
copy .env.example .env
# Edit .env with your settings
```

### 6. Initialize the database
```powershell
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

### 7. Run the app
```powershell
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Project Structure

```
navres-attendance/
├── app/
│   ├── models/          # SQLAlchemy models
│   ├── auth/            # Auth blueprint (login, register, password reset)
│   ├── admin/           # Admin blueprint (events, muster roll, settings)
│   ├── member/          # Member blueprint (dashboard, responses, profile)
│   ├── main/            # Landing page
│   ├── notifications/   # Email (Flask-Mail) and SMS (Twilio) helpers
│   ├── static/          # CSS, JS, images
│   └── templates/       # Jinja2 HTML templates
├── config.py            # Dev/prod config classes
├── run.py               # Entry point
├── docker-compose.yml   # Local PostgreSQL
├── Procfile             # Railway.app
└── requirements.txt
```

## Deployment (Railway.app)

1. Create a new Railway project and add a PostgreSQL plugin
2. Set environment variables in Railway dashboard (copy from `.env.example`)
3. Set `FLASK_ENV=production` and `DATABASE_URL` (Railway provides this automatically)
4. Deploy — Railway uses the `Procfile` to start `gunicorn`

---

## Build Order

1. [x] Project scaffold + DB models
2. [ ] User authentication (this is next)
3. [ ] Unit creation and invite system
4. [ ] Role-based views
5. [ ] Event creation and responses
6. [ ] Attendance tracking and muster roll
7. [ ] Member profiles
8. [ ] Attendance export (CSV)
9. [ ] Email notifications
10. [ ] SMS notifications (per-unit Twilio)
