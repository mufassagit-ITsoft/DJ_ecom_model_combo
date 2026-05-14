# Gamestore — Django E-Commerce Project

A full-stack Django e-commerce application for selling video games, trading card games, and more. Built with Django 6.0, PostgreSQL, Cloudinary CDN, PayPal payments, and a Super Mario Bros. NES-themed frontend.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [1. Poetry Setup](#1-poetry-setup)
- [2. Django Project Setup](#2-django-project-setup)
- [3. App Setup](#3-app-setup)
- [4. Environment Variables](#4-environment-variables)
- [5. Database Setup](#5-database-setup)
- [6. Static and Media Files](#6-static-and-media-files)
- [7. Running Locally](#7-running-locally)
- [8. Deployment on Render](#8-deployment-on-render)
- [9. Project Structure](#9-project-structure)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0 |
| Language | Python 3.12 |
| Package Manager | Poetry |
| Database (Production) | PostgreSQL (Render) |
| Database (Local) | SQLite3 |
| Media CDN | Cloudinary |
| Static Files | WhiteNoise |
| Payments | PayPal REST SDK |
| Frontend | Bootstrap 5 (Bootswatch Flatly) + Press Start 2P font |
| Deployment | Render.com |

---

## Prerequisites

Ensure the following are installed before starting:

- Python 3.12+
- Poetry
- Git

Install Poetry if not already installed:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Verify installations:

```bash
python --version     # Python 3.12+
poetry --version     # Poetry 2.x
git --version
```

---

## 1. Poetry Setup

### 1a — Initialise a new Poetry project

```bash
mkdir ecom_combo
cd ecom_combo
poetry init
```

Follow the prompts:
- **Package name:** `ecom-combo`
- **Version:** `0.1.0`
- **Description:** Gamestore Django e-commerce application
- **Author:** Your name
- **Python version:** `^3.12`
- **Define dependencies interactively:** No (we add them next)

### 1b — Add core dependencies

```bash
poetry add django
poetry add python-decouple
poetry add psycopg2-binary
poetry add gunicorn
poetry add whitenoise
poetry add dj-database-url
poetry add pillow
poetry add django-crispy-forms
poetry add crispy-bootstrap5
poetry add cloudinary
poetry add django-cloudinary-storage
poetry add requests
poetry add six
```

### 1c — Activate the virtual environment

```bash
poetry shell
```

### 1d — Export requirements.txt for Render deployment

```bash
poetry export -f requirements.txt --output requirements.txt --without-hashes
```
This is to be used only, if there is already a requirements file with all apps already stated. This is also the most time saving aspect, without having to use the process in 1b, as that is only done, if a developer is missing any dependencies or just starting a project. 
---

## 2. Django Project Setup

### 2a — Create the Django project

```bash
django-admin startproject ecom_store .
```

> The `.` keeps `manage.py` at the project root level.

### 2b — Verify the structure

```
ecom_combo/
├── manage.py
├── ecom_store/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── pyproject.toml
├── requirements.txt
└── .env
```

### 2c — Create the `.env` file

```bash
touch .env
```

Populate with your credentials — see [Environment Variables](#4-environment-variables) below.

### 2d — Update `ecom_store/settings.py`

Key settings to configure:

```python
from pathlib import Path
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', cast=bool, default=False)

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'your-app-name.onrender.com',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'cloudinary',
    'django.contrib.sites',
    'store',
    'account',
    'payment',
    'cart',
    'crispy_forms',
    'crispy_bootstrap5',
    'sync',
]

SITE_ID = 1
CRISPY_TEMPLATE_PACK = 'bootstrap5'
```

### 2e — Configure the root `urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('account/', include('account.urls')),
    path('cart/', include('cart.urls')),
    path('payment/', include('payment.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 3. App Setup

### 3a — Create the apps

```bash
python manage.py startapp store
python manage.py startapp account
python manage.py startapp payment
python manage.py startapp cart
python manage.py startapp sync
```

### 3b — App descriptions

| App | Purpose |
|---|---|
| `store` | Product catalogue, categories, topics, brands, search, barcode scanning |
| `account` | User registration, login, email verification, dashboard, shipping, rewards history |
| `payment` | Checkout, PayPal integration, orders, refunds, refund tracking |
| `cart` | Session-based shopping cart with quantity management |
| `sync` | Backup database router and signal-based sync to backup PostgreSQL |

### 3c — Store app (`store/`)

Key files:

```
store/
├── models.py        # Topic, Category, Product (with UPC barcode field)
├── views.py         # Store, product info, category, brand, search, barcode lookup
├── urls.py          # All store routes including barcode endpoints
├── admin.py         # ProductAdmin with inline barcode scanner widget
└── templates/
    └── store/
        ├── base.html
        ├── nav.html
        ├── store.html
        ├── product-info.html
        ├── list-category.html
        ├── list-topic.html
        ├── brand.html
        ├── search-results.html
        ├── search-suggestions.html
        └── barcode-scanner.html
```

### 3d — Account app (`account/`)

Key files:

```
account/
├── models.py        # RewardAccount, RewardTransaction, calculate_reward_points
├── views.py         # Register, login, logout, dashboard, profile, shipping, rewards
├── urls.py          # All account routes
├── forms.py         # CreateUserForm, LoginForm, UpdateUserForm
├── token.py         # Email verification token generator
└── templates/
    └── account/
        ├── dashboard.html
        ├── my-login.html
        ├── register.html
        ├── track-orders.html
        ├── rewards_hist.html
        └── manage-shipping.html
```

### 3e — Payment app (`payment/`)

Key files:

```
payment/
├── models.py        # ShippingAddress, Order, OrderItem, RefundRequest, RefundItem
├── views.py         # Checkout, complete_order, PayPal integration, refund views
├── urls.py          # Payment and refund routes
├── admin.py         # OrderAdmin, RefundRequestAdmin with stepped refund workflow
├── forms.py         # ShippingForm
└── templates/
    └── payment/
        ├── checkout.html
        ├── payment-success.html
        ├── payment-failed.html
        ├── refund-landing.html
        ├── request-refund.html
        └── refund-status.html
```

### 3f — Cart app (`cart/`)

Key files:

```
cart/
├── cart.py              # Cart class — session-based, Decimal arithmetic
├── views.py             # cart_summary, cart_add, cart_delete, cart_update
├── urls.py              # Cart routes
├── context_processors.py # Makes cart available in all templates
└── templates/
    └── cart/
        └── cart-summary.html
```

### 3g — Sync app (`sync/`)

Key files:

```
sync/
├── router.py                    # BackupRouter — routes reads/writes
├── signals.py                   # post_save/post_delete signals for real-time sync
└── management/
    └── commands/
        ├── __init__.py
        └── sync_to_backup.py    # Full sync management command
```

### 3h — Make and run migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py migrate --database=backup
```

### 3i — Create a superuser

```bash
python manage.py createsuperuser
```

### 3j — Collect static files

```bash
python manage.py collectstatic
```

---

## 4. Environment Variables

Create a `.env` file at the project root with the following:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# Render hostname (production only)
RENDER_HOSTNAME=(check)

# Database — PostgreSQL (Render)
DATABASE_URL=(check)
BACKUP_DATABASE_URL=(check)

# Cloudinary CDN
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Email (Gmail SMTP)
EMAIL_BACKEND=(check)
EMAIL_HOST=(check)
EMAIL_PORT=(check)
EMAIL_USE_TLS=(check)
EMAIL_HOST_USER=(check)
EMAIL_HOST_PASSWORD=(check)

# PayPal
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_SECRET=your-paypal-secret
```

> **Note:** Never commit `.env` to version control. Add it to `.gitignore`.

---

## 5. Database Setup

### Local development (SQLite — automatic)

No setup needed. Django creates `db.sqlite3` automatically on first migrate.

### Production (PostgreSQL on Render)

1. Create a PostgreSQL database on Render
2. Copy the **Internal Database URL** into `DATABASE_URL` on Render's environment variables
3. Use the **External Database URL** in your local `.env` for local development against the production database

```bash
# Run migrations on production database
python manage.py migrate

# Sync data to backup database
python manage.py sync_to_backup
```

### Update the Sites table after first deploy

```
https://your-app-name.onrender.com/admin/sites/site/1/change/
```

Set **Domain name** to `your-app-name.onrender.com` so email verification links work correctly.

---

## 6. Static and Media Files

### Static files (CSS, JS, fonts)

Served by **WhiteNoise** in production. Collected to `staticfiles/` directory:

```bash
python manage.py collectstatic
```

Structure:
```
static/
├── css/
│   ├── styles.css
│   ├── base.css
│   └── arcade.css       # Super Mario Bros. NES theme
├── js/
│   └── app.js
└── media/
    └── images/
        └── evoGames_logo_icon.png
```

### Media files (product images)

Served by **Cloudinary CDN** in production. Configure in `settings.py`:

```python
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY':    config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}

if all([CLOUDINARY_STORAGE['CLOUD_NAME'], ...]):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
```

---

## 7. Running Locally

```bash
# Activate virtual environment
poetry shell

# Run development server
python manage.py runserver
```
note: this is just an example
Visit: `http://127.0.0.1:8000`

Admin: `http://127.0.0.1:8000/admin`

---

## 8. Deployment on Render

### 8a — Create `build.sh` at project root

```bash
#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

Make it executable:
```bash
chmod +x build.sh
```

### 8b — Create `Procfile` at project root

```
web: gunicorn ecom_store.wsgi:application
```

### 8c — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### 8d — Create Web Service on Render

| Field | Value |
|---|---|
| Environment | Python |
| Build Command | `./build.sh` |
| Start Command | `gunicorn ecom_store.wsgi:application` |
| Branch | `main` |

### 8e — Set environment variables on Render

Add all variables from your `.env` file to the Render Web Service environment tab. Use the **Internal Database URL** for `DATABASE_URL`.

---

## 9. Project Structure

```
ecom_combo/
├── manage.py
├── Procfile
├── build.sh
├── requirements.txt
├── pyproject.toml
├── .env                         # Never commit this
├── .gitignore
│
├── ecom_store/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── store/                       # Product catalogue app
├── account/                     # User accounts & rewards app
├── payment/                     # Checkout & refunds app
├── cart/                        # Shopping cart app
├── sync/                        # Database backup sync app
│
└── static/
    ├── css/
    ├── js/
    └── media/
```

---

## Key Features

- **Product catalogue** with topics, categories, and brands
- **Barcode scanning** via camera, USB/Bluetooth hand scanner, or manual UPC entry with UPCitemdb API lookup
- **Shopping cart** with session persistence and real-time stock validation
- **PayPal integration** with rewards redemption at checkout
- **7-tier rewards system** earning points on every purchase
- **Full refund workflow** with admin verification, PayPal API refund, and email notifications at every stage
- **Email verification** for new account registration
- **Backup database** with real-time signal-based sync to PostgreSQL backup
- **Super Mario Bros. NES theme** via `arcade.css` with Press Start 2P pixel font
- **Cloudinary CDN** for product image delivery
- **WhiteNoise** for static file serving in production

---

## License

© 2026 evoGames LLC. All rights reserved.