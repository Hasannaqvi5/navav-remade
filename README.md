# NavAv

**Modern attendance tracking for organizational efficiency.**

**Live Demo**: [navav-remade.onrender.com](https://navav-remade.onrender.com)

---

## Features
- **PWA Ready**: Installable on iOS and Android with a native-app feel.
- **Instant Push Notifications**: Shift-change alerts and new event broadcasts via WebPush.
- **Automated Reminders**: Smart 24-hour RSVP deadline alerts to keep engagement high.
- **Admin Dashboard**: Manage members, track attendance, and export data with ease.
- **Flexible Time Formats**: Toggle between 12-hour and 24-hour clocks per organization.

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10+
- Database (SQLite for dev, PostgreSQL for prod)

### 2. Setup
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment
Copy `.env.example` to `.env` and configure your VAPID keys and database URL.

### 4. Run
```powershell
python run.py
```

---

## Project Structure

```
navav-remade/
├── app/
│   ├── models/          # Database schemas
│   ├── auth/            # Login, Registration & Push Handshake
│   ├── admin/           # Unit Management & Event Controls
│   ├── member/          # User Dashboard & RSVP Logic
│   ├── static/          # Modernized CSS & PWA Service Worker
│   └── templates/       # Redesigned NavAv Templates
├── config.py            # Global Application Settings
├── run.py               # Entry Point
└── requirements.txt
```

---

## Development Status
1. [x] Project rebranding and modernized UI
2. [x] PWA Service Worker implementation
3. [x] VAPID Push Notification system
4. [x] Automated 24h RSVP deadline reminders
5. [x] Multi-browser support (Chrome, Edge, Safari)
6. [x] Admin dashboard and event management
7. [x] Attendance tracking and CSV exports
