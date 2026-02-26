# 🏪 Dokan API

A **multi-tenant business management REST API** built with Django and Django REST Framework. Dokan provides a complete backend for managing companies, products, inventory, purchases, sales, customers, suppliers, accounting, payments, and expenses — all with strict per-company data isolation.

---

## ✨ Features

- 🏢 **Multi-Tenant Architecture** — full data isolation between companies via `CompanyMiddleware`
- 🔐 **JWT Authentication** — secure token-based auth using `djangorestframework-simplejwt`
- 📦 **Inventory & Stock Management** — automatic stock updates on purchases and sales
- 📊 **Accounting Module** — track financial transactions per company
- 📄 **PDF Generation** — invoice/report export via WeasyPrint & xhtml2pdf
- 📚 **Auto API Docs** — Swagger UI and ReDoc powered by `drf-yasg`
- 🐳 **Docker Ready** — containerised with Gunicorn for production

---

## 🗂️ Project Structure

```
dokan/
├── accounting/        # Accounting & financial transactions
├── company/           # Company & user-company management, CompanyMiddleware
├── core/              # Dashboard stats, shared utilities
├── customer/          # Customer management
├── expense/           # Expense tracking
├── inventory/         # Stock & stock transaction management
├── payment/           # Payment processing
├── product/           # Product & unit management
├── purchase/          # Purchase orders
├── sale/              # Sales management
├── supplier/          # Supplier management
├── warehouse/         # Warehouse management
├── dokan/             # Django project settings & URL router
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── manage.py
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Docker & Docker Compose (optional)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dokan
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your values
```

Key variables:

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key | insecure dev key |
| `DEBUG` | Debug mode | `True` |
| `DJANGO_SETTINGS_MODULE` | Settings module | `dokan.settings.dev` |
| `DATABASE_NAME` | PostgreSQL DB name | `dokan_db` |
| `DATABASE_USER` | PostgreSQL user | `dokan_user` |
| `DATABASE_PASSWORD` | PostgreSQL password | `dokan_password` |
| `DATABASE_HOST` | DB host | `db` |
| `DATABASE_PORT` | DB port | `5432` |
| `ALLOWED_HOSTS` | Allowed hosts | `*` |
| `CORS_ALLOW_ALL_ORIGINS` | Allow all CORS | `True` |

### 5. Apply Migrations

```bash
python manage.py migrate
```

### 6. Create a Superuser

```bash
python manage.py createsuperuser
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`.

---

## 🐳 Docker Setup

### Build and Run

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000` (or the port set in `API_PORT`).

The container automatically runs:
1. `python manage.py migrate`
2. `python manage.py collectstatic`
3. Starts Gunicorn

### Stop

```bash
docker compose down
```

---

## 🔑 Authentication

This API uses **JWT (JSON Web Tokens)**.

### Obtain Token

```bash
POST /api/token/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

### Refresh Token

```bash
POST /api/token/refresh/
Content-Type: application/json

{
  "refresh": "<your_refresh_token>"
}
```

### Use Token in Requests

```bash
Authorization: Bearer <your_access_token>
```

---

## 📡 API Endpoints

| Module | Base URL |
|---|---|
| Companies | `/api/companies/` |
| Products | `/api/products/` |
| Suppliers | `/api/suppliers/` |
| Customers | `/api/customers/` |
| Warehouses | `/api/warehouses/` |
| Inventory | `/api/inventory/` |
| Purchases | `/api/purchases/` |
| Sales | `/api/sales/` |
| Payments | `/api/payments/` |
| Accounting | `/api/accounting/` |
| Expenses | `/api/expenses/` |
| Dashboard Stats | `/api/dashboard/stats/` |
| Admin Panel | `/admin/` |

### API Documentation (Interactive)

| Tool | URL |
|---|---|
| Swagger UI | `http://localhost:8000/swagger/` |
| ReDoc | `http://localhost:8000/redoc/` |
| OpenAPI JSON | `http://localhost:8000/swagger.json` |

---

## 🏢 Multi-Tenant Architecture

Every authenticated user is linked to a **Company** via the `CompanyUser` model. The `CompanyMiddleware` automatically attaches the company to each request (`request.company`), ensuring:

- ✅ All queries are filtered by company
- ✅ Company is auto-assigned on create — clients cannot spoof it
- ✅ Cross-company data access is blocked at the service and view layers
- ✅ Model-level validation enforces data consistency

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.x |
| REST API | Django REST Framework 3.x |
| Auth | djangorestframework-simplejwt |
| Database | PostgreSQL (SQLite for dev) |
| PDF Export | WeasyPrint, xhtml2pdf |
| API Docs | drf-yasg (Swagger / ReDoc) |
| CORS | django-cors-headers |
| Filtering | django-filter |
| Web Server | Gunicorn + WhiteNoise |
| Container | Docker |

---

## ⚙️ Settings

| Environment | Module |
|---|---|
| Development | `dokan.settings.dev` (SQLite, `DEBUG=True`) |
| Production | `dokan.settings.prod` |

Switch by setting the `DJANGO_SETTINGS_MODULE` environment variable.

---

## 🧪 Running Tests

```bash
pytest
```

---

## 📁 Environment Variables Reference

See [`.env.example`](.env.example) for a full list of configurable variables including optional Email and AWS S3 settings.

---

## 📄 License

BSD License — see `LICENSE` for details.
