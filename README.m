# ChetSpy | Evidence Management System

ChetSpy — изолированная система управления цифровыми уликами и оперативными данными с интеграцией Discord.

Система предназначена для централизованного сбора, хранения и модерации доказательств с контролем доступа и локальным хранением данных без внешних хостингов.

## Features

* Role-based access control (RBAC): `user`, `check`, `full`
* Discord OAuth2 authentication (без паролей)
* Автоматическая эскалация прав для владельца сервера
* Локальное хранение файлов и медиа (self-hosted storage)
* Генерация постоянных URL для загруженных файлов
* Discord Webhook интеграция для отправки embed-уведомлений
* Административная панель управления кейсами и статусами
* Управление статусами улик:

  * Pending
  * In Case
  * Operation
  * Rejected

## Tech Stack

* **Backend:** FastAPI (Python)
* **Database:** SQLite + SQLAlchemy ORM
* **Frontend:** Jinja2 + Tailwind CSS
* **Auth:** Discord OAuth2
* **Integration:** Discord Webhooks
* **Storage:** Local filesystem


## Architecture

* Fully isolated backend with no external file dependencies
* Local media storage with persistent public URLs
* Event-driven updates via Discord webhooks
* Security-first design with OAuth2 authentication
* Minimalist UI (Dark Glassmorphism style)

---

## Installation

### 1. Clone repository

```bash
git clone <REPOSITORY_URL>
cd ChetSpy
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn sqlalchemy python-multipart httpx python-jose jinja2 aiofiles python-dotenv
```

---

## Configuration

Create `.env` file in root directory:

```env
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=http://localhost:8000/auth/callback
DISCORD_WEBHOOK_URL=your_webhook_url
SECRET_KEY=your_secret_key
ADMIN_DISCORD_ID=your_discord_id
```

> Make sure `DISCORD_REDIRECT_URI` matches your Discord Developer Portal OAuth2 settings.

---

## Run Server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

On first launch, the system will automatically:

* Create required directories (`static/uploads`, `templates`)
* Initialize database (`chetspy.db`)

## Access Control

1. Set `ADMIN_DISCORD_ID` in `.env`
2. Login via Discord OAuth2
3. System assigns `full` role automatically to admin
4. Additional roles managed via admin panel

## Roadmap

* Advanced case linking system
* Audit logs for all actions
* API token support for external services
* Encryption layer for sensitive evidence
* Multi-server deployment mode

## License

Specify your license here (e.g. MIT / Proprietary).
