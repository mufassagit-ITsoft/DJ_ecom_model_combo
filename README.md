Authored by Mustafizur Prodhan
Date started (from prototype): 12/20/2025
Date Deployed: 5/8/2026

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

The build.sh file is a shell script that Render runs automatically every time you deploy your application. It executes all the preparation steps needed to make your Django app ready to serve traffic before Gunicorn starts.

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
Line by Line

#!/usr/bin/env bash
Called a shebang line. Tells the operating system to run this file using the Bash shell. Without it, the system would not know how to interpret the commands that follow.

set -o errexit
Tells Bash to stop immediately if any command fails. Without this, the script would continue running even if pip install failed — potentially deploying a broken app. With it, a failure at any step aborts the entire build and Render marks the deployment as failed rather than serving a broken application.

pip install -r requirements.txt
Installs all Python packages your project needs. Render's build environment starts fresh on every deploy, so every dependency must be installed each time. This reads from requirements.txt which was exported from Poetry:

    poetry export -f requirements.txt --output requirements.txt --without-hashes

python manage.py collectstatic --no-input
Gathers all static files — CSS, JavaScript, fonts, images from STATICFILES_DIRS — and copies them into the STATIC_ROOT directory (staticfiles/). WhiteNoise then serves them from there in production.

The --no-input flag suppresses the interactive confirmation prompt that Django normally shows when overwriting existing static files — required in automated environments where there is no human to press Enter.

python manage.py migrate
Applies any pending database migrations to the PostgreSQL database on Render. This ensures your database schema is always in sync with your models before the app starts serving traffic. If you add a new model field and push to GitHub, the migration runs automatically on the next deploy without any manual intervention.

The Full Deployment Sequence on Render

You push code to GitHub
        ↓
Render detects the push
        ↓
Render runs build.sh
    ├── pip install -r requirements.txt
    ├── python manage.py collectstatic --no-input
    └── python manage.py migrate
        ↓
Build succeeds
        ↓
Render reads Procfile
        ↓
Render starts: gunicorn ecom_store.wsgi:application
        ↓
App is live and serving traffic

If build.sh fails at any step, Render halts the deployment and keeps the previous working version running — meaning your live site stays up even if a bad deployment is pushed.

Why It Must Be Executable
Before Render can run build.sh, the file must have execute permissions set:

    chmod +x build.sh

Without this, Render would see the file but be unable to run it, causing the build to fail immediately. This is set once locally and committed to Git — the permission is preserved in the repository.

Configured on Render
In your Render Web Service settings the Build Command is pointed at this file:

    Build Command: ./build.sh


The ./ prefix means "run this file from the current directory" — necessary because build.sh is not a system command, it is a file in your project root.

### 8b — Create `Procfile` at project root

The Procfile is a plain text file that tells Render (and other platforms like Heroku) how to start your web application. It defines the process types your app runs and the exact command used to start each one.

```
web: gunicorn ecom_store.wsgi:application
```
This one line contains two parts:
web — the process type. Render recognises web as the process that receives HTTP traffic from the internet. It automatically assigns it a port and routes incoming requests to it.

gunicorn ecom_store.wsgi:application — the command that starts your application server. 

Breaking it down further:

gunicorn: The production WSGI server that runs your Django app

ecom_store: The Django project package name — the folder containing settings.py and wsgi.py

wsgi: The wsgi.py module inside that package

application: The WSGI callable object inside wsgi.py that Gunicorn calls to handle each request

Why Not Just Use manage.py runserver
Django's runserver is a development-only tool. It is single-threaded, has no request queuing, serves one request at a time, and Django explicitly documents it as unsafe for production.
Gunicorn is a production-grade WSGI server that:

    - Handles multiple concurrent requests using worker processes
    - Manages worker lifecycle and restarts crashed workers
    - Integrates with Render's port and process management
    - Is battle-tested at scale

What Happens on Render
When you deploy, Render reads the Procfile and runs the web command to start your application. The sequence is:

Render reads Procfile
        ↓
Runs: gunicorn ecom_store.wsgi:application
        ↓
Gunicorn loads ecom_store/wsgi.py
        ↓
wsgi.py initialises Django with your settings
        ↓
Gunicorn spawns worker processes
        ↓
Workers listen for HTTP requests on the assigned port
        ↓
Render routes incoming traffic to those workers
Without the Procfile, Render would not know how to start your application and the deployment would fail.

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
- ** MIT during developmental cycle

The MIT License is one of the most permissive and widely used open source software licenses in existence. It originates from the Massachusetts Institute of Technology and has been the default license for countless open source projects including Django itself, jQuery, React, and many of the packages in your Gamestore project.

What It Grants
In plain language, the MIT License gives anyone who receives your code four core freedoms:
FreedomMeaningUseRun the software for any purpose — personal, commercial, governmentModifyChange the source code however you wantDistributeShare the original or modified version with anyoneSublicenseRe-license your modified version under different terms
The only condition attached to all of these is that the original copyright notice and license text must be included in any copy or substantial portion of the software distributed.

What It Does Not Grant
The MIT License is explicit about what it does not cover:
No warranty — the software is provided as-is. If it breaks something, causes data loss, or fails in production, the original author bears no legal responsibility. This is the AS IS clause in the license text.
No trademark rights — using MIT-licensed code does not give you the right to use the original author's name, logo, or brand to endorse your product.
No patent rights — MIT does not explicitly grant patent rights, which is a distinction from licenses like Apache 2.0 that do.

In Development
When you use MIT-licensed packages during development, the license requires nothing from you beyond keeping the license text intact when you distribute software that includes those packages. In practice this means:
Your pyproject.toml and requirements.txt list packages like Django, WhiteNoise, and Cloudinary. All of these carry their own MIT or compatible licenses. You are free to build commercial software on top of them, charge customers for it, and keep your own source code completely private — MIT places no restriction on any of this.
If you were building an open source project and distributing your source code, you would include the license texts of your dependencies, typically handled automatically by package managers.

In Production

Deploying MIT-licensed code to production on Render, selling products through your Gamestore, and charging customers for those products is entirely permitted. The MIT License has no revenue clause, no attribution requirement in your UI, and no obligation to open source your own code.
The practical production implications are:
You keep full ownership of your code. The MIT License on your dependencies does not transfer any ownership of your original work. Your Gamestore application, its business logic, its database schema, and its custom CSS theme are yours entirely.
No copyleft obligation. Unlike the GPL license, MIT does not require you to release your source code if you distribute or deploy software that incorporates MIT-licensed components. You can build on Django and keep your entire codebase proprietary.
No royalties. No package author can claim a percentage of revenue generated by software built on their MIT-licensed work.

MIT vs Other Common Licenses

LicenseCan use commerciallyMust open source your codeMust include licensePatent grantMITYesNoYesNoApache 2.0YesNoYesYesGPL v3YesYesYesYesBSD 2-ClauseYesNoYesNoProprietaryOnly if purchasedNoNoNo

Relevance to evoGames LLC

For evoGames LLC operating as a commercial entity, MIT is the most favorable type of license to encounter in your dependency stack because it imposes essentially no obligations on your business. Your store, your customer data, your payment flows, and your branding are all yours to protect however you choose while freely building on the open source ecosystem beneath them.
If you release any of your own tools or utilities publicly — such as the Tkinter datastore GUI or the barcode scanning integration — applying the MIT License to those would allow the developer community to use and improve them while you retain the copyright and credit.MIT

MIT License Agreement

MIT License

Copyright (c) [year] [your name or organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

© 2026 evoGames LLC. All rights reserved.