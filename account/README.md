# Account App — Gamestore Django Project

The `account` app handles all user-facing account functionality for the Gamestore website. This includes user registration with email verification, authentication, profile management, shipping address management, order tracking, and a full rewards points history system.

---

## Table of Contents

- [Overview](#overview)
- [App Structure](#app-structure)
- [Models](#models)
- [Views](#views)
- [URLs](#urls)
- [Forms](#forms)
- [Token Generator](#token-generator)
- [Templates](#templates)
- [Rewards System](#rewards-system)
- [Email Verification Flow](#email-verification-flow)
- [Password Reset Flow](#password-reset-flow)
- [Setup and Installation](#setup-and-installation)
- [Dependencies](#dependencies)

---

## Overview

The account app integrates tightly with Django's built-in `auth` system and extends it with:

- Email verification on registration — accounts are inactive until verified
- A rewards points system earning dollar-value points on every purchase
- Full rewards transaction history viewable from the user dashboard
- Shipping address management linked to the checkout process
- Order tracking with rewards earned per order displayed inline

---

## App Structure

```
account/
├── __init__.py
├── apps.py
├── models.py                  # RewardAccount, RewardTransaction
├── views.py                   # All account views
├── urls.py                    # URL routing
├── forms.py                   # User creation, login, update forms
├── token.py                   # Email verification token generator
├── admin.py                   # RewardAccount and RewardTransaction admin
└── templates/
    └── account/
        ├── dashboard.html
        ├── my-login.html
        ├── profile-management.html
        ├── delete-account.html
        ├── manage-shipping.html
        ├── track-orders.html
        ├── rewards_hist.html
        ├── registration/
        │   ├── register.html
        │   ├── email-verification.html
        │   ├── email-verification-sent.html
        │   ├── email-verification-success.html
        │   └── email-verification-failed.html
        └── password/
            ├── password-reset.html
            ├── password-reset-sent.html
            ├── password-reset-form.html
            └── password-reset-complete.html
```

---

## Models

### `RewardAccount`

Stores the cumulative rewards balance for each registered user. Created automatically on first purchase via `get_or_create`.

```python
class RewardAccount(models.Model):
    user            = models.OneToOneField(User, on_delete=models.CASCADE)
    total_points    = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lifetime_points = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
```

| Field | Description |
|---|---|
| `total_points` | Current spendable balance — decreases when rewards are redeemed |
| `lifetime_points` | Total ever earned — never decreases, used for tier display |
| `created_at` | When the reward account was first created |
| `updated_at` | Last time the balance changed |

---

### `RewardTransaction`

Records every individual rewards event — purchases, redemptions, and adjustments. Provides the full audit trail shown in the rewards history page.

```python
class RewardTransaction(models.Model):
    user             = models.ForeignKey(User, on_delete=models.CASCADE)
    order            = models.OneToOneField(Order, on_delete=models.CASCADE, null=True)
    order_total      = models.DecimalField(max_digits=10, decimal_places=2)
    points_earned    = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=[
        ('PURCHASE',   'Purchase Reward'),
        ('REDEEMED',   'Points Redeemed'),
        ('ADJUSTMENT', 'Manual Adjustment'),
    ])
    description      = models.TextField(blank=True, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)
```

| Field | Description |
|---|---|
| `order` | Linked order — null for manual adjustments |
| `order_total` | The order amount that determined the reward |
| `points_earned` | Positive for earned, negative for deducted |
| `transaction_type` | `PURCHASE`, `REDEEMED`, or `ADJUSTMENT` |
| `description` | Human-readable explanation of the transaction |

---

### Helper Functions

#### `calculate_reward_points(order_total)`

Calculates reward points based on the 7-tier structure:

```python
def calculate_reward_points(order_total):
    total = Decimal(str(order_total))
    if total <= 0:           return Decimal('0.00')
    elif total <= 10.00:     return Decimal('1.00')
    elif total <= 20.00:     return Decimal('2.00')
    elif total <= 30.00:     return Decimal('3.00')
    elif total <= 40.00:     return Decimal('4.00')
    elif total <= 100.00:    return Decimal('5.00')
    elif total <= 200.00:    return Decimal('10.00')
    else:
        # $201+: $10 base + $5 per additional $100 bracket
        base = Decimal('10.00')
        amount_over_200 = total - Decimal('200.00')
        brackets = int(amount_over_200 / Decimal('100.00'))
        additional = Decimal(str(brackets)) * Decimal('5.00')
        if amount_over_200 % Decimal('100.00') > 0:
            additional += Decimal('5.00')
        return base + additional
```

#### `award_points_for_order(user, order, order_total)`

Awards calculated points to a user after a successful payment. Called from `payment/views.py` `complete_order` view:

```python
def award_points_for_order(user, order, order_total):
    points = calculate_reward_points(order_total)
    reward_account, created = RewardAccount.objects.get_or_create(user=user)
    reward_account.total_points    += points
    reward_account.lifetime_points += points
    reward_account.save()
    transaction = RewardTransaction.objects.create(
        user=user, order=order,
        order_total=Decimal(str(order_total)),
        points_earned=points,
        transaction_type='PURCHASE',
        description=f'Reward points earned from order #{order.id}'
    )
    return transaction
```

---

## Views

| View | URL Name | Auth Required | Description |
|---|---|---|---|
| `register` | `register` | No | New user registration with email verification |
| `email_verification` | `email-verification` | No | Activates account via token link |
| `email_verification_sent` | `email-verification-sent` | No | Confirmation page after registration |
| `email_verification_success` | `email-verification-success` | No | Account activated successfully |
| `email_verification_failed` | `email-verification-failed` | No | Token invalid or expired |
| `my_login` | `my-login` | No | User login |
| `user_logout` | `user-logout` | No | Clears session and redirects to store |
| `dashboard` | `dashboard` | Yes | Rewards balance, recent transactions, navigation hub |
| `profile_management` | `profile-management` | Yes | Update username and email |
| `delete_account` | `delete-account` | Yes | Permanently delete user account |
| `manage_shipping` | `manage-shipping` | Yes | Add or update shipping address |
| `track_orders` | `track-orders` | Yes | All orders with rewards earned per order |
| `rewards_history` | `rewards-history` | Yes | Complete rewards transaction history |

---

## URLs

```python
# account/urls.py

urlpatterns = [
    # Registration
    path('register', views.register, name='register'),

    # Email verification
    path('email-verification/<str:uidb64>/<str:token>/',
         views.email_verification, name='email-verification'),
    path('email-verification-sent',
         views.email_verification_sent, name='email-verification-sent'),
    path('email-verification-success',
         views.email_verification_success, name='email-verification-success'),
    path('email-verification-failed',
         views.email_verification_failed, name='email-verification-failed'),

    # Authentication
    path('my-login', views.my_login, name='my-login'),
    path('user-logout', views.user_logout, name='user-logout'),

    # Dashboard and profile
    path('dashboard', views.dashboard, name='dashboard'),
    path('profile-management', views.profile_management, name='profile-management'),
    path('delete-account', views.delete_account, name='delete-account'),

    # Password management (Django built-in views)
    path('reset_password',
         auth_views.PasswordResetView.as_view(...), name='reset_password'),
    path('reset_password_sent',
         auth_views.PasswordResetDoneView.as_view(...), name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(...), name='password_reset_confirm'),
    path('reset_password_complete',
         auth_views.PasswordResetCompleteView.as_view(...), name='password_reset_complete'),

    # Shipping and orders
    path('manage-shipping', views.manage_shipping, name='manage-shipping'),
    path('track-orders', views.track_orders, name='track-orders'),

    # Rewards
    path('rewards-history', views.rewards_history, name='rewards-history'),
]
```

All account URLs are prefixed with `account/` from the root `urls.py`:

```python
path('account/', include('account.urls')),
```

So the full URL for login is `/account/my-login`.

---

## Forms

### `CreateUserForm`

Extends Django's `UserCreationForm` to include email as a required field:

```python
class CreateUserForm(UserCreationForm):
    class Meta:
        model  = User
        fields = ['username', 'email', 'password1', 'password2']
```

### `LoginForm`

Wraps Django's built-in `AuthenticationForm` — handles username/password validation and error messaging via crispy forms:

```python
class LoginForm(AuthenticationForm):
    class Meta:
        model  = User
        fields = ['username', 'password']
```

### `UpdateUserForm`

Allows authenticated users to update their username and email from the profile management page:

```python
class UpdateUserForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['username', 'email']
```

---

## Token Generator

`token.py` provides a custom token generator for email verification links. It extends Django's `PasswordResetTokenGenerator` with a hash that includes the user's active status so the token is invalidated once the account is activated:

```python
class UserVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) +
            str(timestamp) +
            str(user.is_active)   # ← invalidated after activation
        )

user_tokenizer_generate = UserVerificationTokenGenerator()
```

The token is embedded in the verification email URL:

```
https://your-domain.com/account/email-verification/<uidb64>/<token>/
```

Once clicked, `is_active` changes from `False` to `True`, which changes the hash value, making the token impossible to reuse.

---

## Templates

### `dashboard.html`

Displays:
- Current rewards balance (`reward_account.total_points`)
- Lifetime points earned (`reward_account.lifetime_points`)
- Last 5 reward transactions
- Navigation cards to orders, profile, shipping, rewards history
- Rewards tier structure explanation

### `track-orders.html`

Displays all `OrderItem` records for the authenticated user. Uses the custom `rewards_tags` template tag (`get_item`) to match each order to its `RewardTransaction` and display points earned alongside each order.

### `rewards_hist.html`

Complete chronological list of all `RewardTransaction` records for the user. Color-coded by transaction type — green for purchases, red for redemptions.

### `email-verification.html`

Plain text email template (not HTML) rendered via `render_to_string` in the `register` view:

```
Hi,

Thank you for registering on our website.

Please verify your email by clicking the link below:

http://{{ domain }}{% url 'email-verification' uidb64=uid token=token %}
```

> **Production note:** The protocol is dynamically set to `https` in production by passing `protocol: 'https' if request.is_secure() else 'http'` from the view context.

---

## Rewards System

### Tier Structure

| Order Total | Points Awarded |
|---|---|
| $0.01 — $10.00 | $1.00 |
| $10.01 — $20.00 | $2.00 |
| $20.01 — $30.00 | $3.00 |
| $30.01 — $40.00 | $4.00 |
| $40.01 — $100.00 | $5.00 |
| $100.01 — $200.00 | $10.00 |
| $200.01+ | $10.00 + $5.00 per additional $100 |

### Redemption

At checkout, authenticated users can apply rewards points to reduce their order total. The rewards redemption amount is sent from the checkout JavaScript to `payment/views.py` `complete_order` which:

1. Validates the redemption amount does not exceed available balance or order total
2. Deducts from `RewardAccount.total_points`
3. Creates a `RewardTransaction` with `transaction_type='REDEEMED'`
4. Awards new points based on the final amount paid after redemption

### Refund Adjustment

When a refund is completed via the admin workflow, `process_rewards_refund()` in `payment/models.py` deducts the points originally earned from the purchase by creating an `ADJUSTMENT` transaction with a negative `points_earned` value.

---

## Email Verification Flow

```
1. User submits registration form
        ↓
2. Account created with is_active=False
        ↓
3. Verification email sent with signed token URL
        ↓
4. User clicks link in email
        ↓
5. email_verification view checks token validity
        ↓
   Valid → is_active=True → redirect to success page
   Invalid → redirect to failed page
        ↓
6. User logs in with now-active account
```

**Required settings for email:**

```python
EMAIL_BACKEND     = config('EMAIL_BACKEND')
EMAIL_HOST        = config('EMAIL_HOST')
EMAIL_PORT        = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS     = config('EMAIL_USE_TLS', cast=bool)
EMAIL_HOST_USER   = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
```

**Required for `get_current_site()` to work correctly:**

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django.contrib.sites',
]
SITE_ID = 1
```

After first deployment, update the Sites table in admin:

```
/admin/sites/site/1/change/
```

Set **Domain name** to your actual domain so verification links resolve correctly.

---

## Password Reset Flow

Handled entirely by Django's built-in `PasswordResetView` and related class-based views. Custom templates are provided for each step:

```
1. User submits email on /account/reset_password
        ↓
2. Django sends password reset email with signed link
        ↓
3. User clicks link → /account/reset/<uidb64>/<token>/
        ↓
4. User enters new password twice
        ↓
5. Password updated → redirect to complete page
        ↓
6. User logs in with new password
```

---

## Setup and Installation

### 1 — Register the app

```python
# ecom_store/settings.py
INSTALLED_APPS = [
    ...
    'account',
    ...
]
```

### 2 — Include URLs

```python
# ecom_store/urls.py
path('account/', include('account.urls')),
```

### 3 — Run migrations

```python
python manage.py makemigrations account
python manage.py migrate
```

### 4 — Register signals (if using sync app)

Ensure the sync app's `AppConfig.ready()` imports account signals:

```python
# sync/apps.py
def ready(self):
    import sync.signals
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `django.contrib.auth` | Built-in user model, authentication, password reset |
| `django.contrib.sites` | Required for `get_current_site()` in email verification |
| `django-crispy-forms` | Form rendering with Bootstrap 5 styling |
| `crispy-bootstrap5` | Bootstrap 5 template pack for crispy forms |
| `python-decouple` | Environment variable management |

---

## Admin Registration

`RewardAccount` and `RewardTransaction` are registered in `account/admin.py` with:

- List display showing balance, lifetime points, and transaction count
- Search by username and email
- Date filters
- Collapsible timestamps
- `recalculate_user_points` admin action — recalculates total points from transaction history for selected accounts, useful for correcting balance discrepancies

---

## Notes

- All account views requiring authentication use `@login_required(login_url='my-login')` — unauthenticated users are redirected to the login page rather than Django's default `/accounts/login/`
- The `user_logout` view preserves the cart session (`session_key`) while clearing all other session data so the cart survives logout
- `RewardAccount` is created lazily via `get_or_create` — it does not need to exist for a user to register or browse the store
- Points are calculated and awarded in `payment/views.py` after PayPal confirms payment, not at order creation time, ensuring rewards are only given for completed transactions