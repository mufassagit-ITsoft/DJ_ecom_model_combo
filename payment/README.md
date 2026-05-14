# Payment App — Gamestore Django Project

The `payment` app handles all transactional functionality for the Gamestore website. This includes PayPal checkout integration, order creation, order item management, a complete refund workflow with admin verification gates, programmatic PayPal refund API calls, and email notifications at every stage of the refund lifecycle.

---

## Table of Contents

- [Overview](#overview)
- [App Structure](#app-structure)
- [Models](#models)
- [Views](#views)
- [URLs](#urls)
- [Forms](#forms)
- [Admin](#admin)
- [PayPal Integration](#paypal-integration)
- [Refund Workflow](#refund-workflow)
- [Email Notifications](#email-notifications)
- [Helper Functions](#helper-functions)
- [Setup and Installation](#setup-and-installation)
- [Environment Variables](#environment-variables)
- [Dependencies](#dependencies)
- [Notes](#notes)

---

## Overview

The payment app connects the shopping cart to PayPal, records all orders and order items, manages shipping addresses, and provides a full refund pipeline. It integrates tightly with the account app's rewards system — deducting rewards on refunds and awarding new points on successful purchases.

Key design decisions:

- PayPal capture IDs are stored on the `Order` model at checkout enabling programmatic refunds from the admin without manual PayPal dashboard intervention
- Every refund stage transition sends an automated email to the customer
- Admin actions enforce a strict verification gate before any financial processing can occur
- Inventory is automatically restocked when returned items are in acceptable condition

---

## App Structure

```
payment/
├── __init__.py
├── apps.py
├── models.py              # All payment models and helper functions
├── views.py               # Checkout, order processing, refund views
├── urls.py                # Payment and refund URL routing
├── forms.py               # ShippingForm
├── admin.py               # Full admin for orders, refunds, and shipping
└── templates/
    └── payment/
        ├── checkout.html
        ├── payment-success.html
        ├── payment-failed.html
        ├── refund-landing.html
        ├── request-refund.html
        ├── refund-status.html
        ├── guest-refund-request.html
        └── guest-refund-status.html
```

---

## Models

### `ShippingAddress`

Stores a shipping address linked to a registered user. Created or updated from the `manage-shipping` view in the account app. Pre-populates the checkout form for authenticated users.

```python
class ShippingAddress(models.Model):
    full_name  = models.CharField(max_length=300)
    email      = models.EmailField(max_length=255)
    address1   = models.CharField(max_length=300)
    address2   = models.CharField(max_length=300, null=True, blank=True)
    city       = models.CharField(max_length=255)
    state      = models.CharField(max_length=255)
    zipcode    = models.CharField(max_length=255)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
```

---

### `Order`

Records a completed order after PayPal payment is confirmed. Created in `complete_order` after all stock validation passes.

```python
class Order(models.Model):
    full_name             = models.CharField(max_length=300)
    email                 = models.EmailField(max_length=255)
    shipping_address      = models.TextField(max_length=10000)
    amount_paid           = models.DecimalField(max_digits=8, decimal_places=2)
    date_ordered          = models.DateTimeField(auto_now_add=True)
    user                  = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    paypal_transaction_id = models.CharField(max_length=200, blank=True, null=True)
```

| Field | Description |
|---|---|
| `amount_paid` | Final charge after rewards redemption — not original cart total |
| `paypal_transaction_id` | PayPal capture ID — required for programmatic refunds via API |
| `user` | Null for guest checkouts |

---

### `OrderItem`

Records each individual product in an order. One `Order` can have multiple `OrderItem` records.

```python
class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    product  = models.ForeignKey('store.Product', on_delete=models.CASCADE, null=True)
    quantity = models.PositiveBigIntegerField(default=1)
    price    = models.DecimalField(max_digits=8, decimal_places=2)
    user     = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
```

---

### `RefundRequest`

Tracks the full lifecycle of a customer refund request from initial submission through to PayPal completion.

```python
class RefundRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING_RETURN',    'Pending Product Return'),
        ('PRODUCT_RECEIVED',  'Product Received - Processing Refund'),
        ('PROCESSING_REFUND', 'Processing PayPal Refund'),
        ('COMPLETED',         'Refund Completed'),
        ('REJECTED',          'Refund Rejected'),
        ('CANCELLED',         'Cancelled by Customer'),
    ]

    REASON_CHOICES = [
        ('DEFECTIVE',        'Product is defective'),
        ('WRONG_ITEM',       'Wrong item received'),
        ('NOT_AS_DESCRIBED', 'Not as described'),
        ('CHANGED_MIND',     'Changed my mind'),
        ('OTHER',            'Other reason'),
    ]

    order            = models.ForeignKey(Order, on_delete=models.CASCADE)
    user             = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    customer_email   = models.EmailField()
    customer_name    = models.CharField(max_length=300)
    status           = models.CharField(max_length=30, choices=STATUS_CHOICES)
    reason           = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_details   = models.TextField(blank=True)
    refund_amount    = models.DecimalField(max_digits=10, decimal_places=2)
    rewards_used     = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tracking_number  = models.CharField(max_length=200, blank=True)
    admin_verified   = models.BooleanField(default=False)
    verified_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='verified_refunds')
    verified_at      = models.DateTimeField(null=True, blank=True)
    admin_notes      = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    paypal_refund_id = models.CharField(max_length=200, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    product_received_at  = models.DateTimeField(null=True, blank=True)
    refund_completed_at  = models.DateTimeField(null=True, blank=True)
```

| Field | Description |
|---|---|
| `refund_amount` | Amount to be refunded — `order.amount_paid` minus any non-refundable portion |
| `rewards_used` | Rewards redeemed in original purchase — not auto-restored on refund |
| `admin_verified` | Gate flag — must be `True` before any payment processing action runs |
| `paypal_refund_id` | Returned by PayPal API after refund is issued |

---

### `RefundItem`

Records individual products within a refund request with condition assessment and restock tracking.

```python
class RefundItem(models.Model):
    refund_request     = models.ForeignKey(RefundRequest, on_delete=models.CASCADE)
    order_item         = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity_to_refund = models.PositiveIntegerField()
    refund_amount      = models.DecimalField(max_digits=10, decimal_places=2)
    condition_acceptable = models.BooleanField(default=False)
    condition_notes    = models.TextField(blank=True)
    restocked          = models.BooleanField(default=False)
```

---

## Views

### `checkout`

Renders the checkout page with the cart total and, for authenticated users, their rewards balance for optional redemption.

```python
def checkout(request):
    cart = Cart(request)
    context = {'cart': cart, 'cart_total': cart.get_total()}
    if request.user.is_authenticated:
        reward_account, _ = RewardAccount.objects.get_or_create(user=request.user)
        context['reward_account'] = reward_account
    return render(request, 'payment/checkout.html', context)
```

---

### `complete_order`

The core order processing view. Called via AJAX POST from `checkout.html` after PayPal approves the payment. Handles:

1. Rewards redemption validation and deduction
2. Stock validation across all cart items
3. Order and OrderItem creation
4. `product.process_sale()` call on each item — decrements stock
5. New rewards points awarding via `award_points_for_order()`
6. Order confirmation email to customer
7. PayPal capture ID storage on the Order record

```python
# Simplified flow
def complete_order(request):
    if request.POST.get('action') == 'post':

        # 1. Read form data and PayPal capture ID
        paypal_transaction_id = request.POST.get('paypal_transaction_id', '')
        rewards_to_apply      = Decimal(request.POST.get('rewards_applied', '0'))

        # 2. Initialise cart and calculate final total
        cart           = Cart(request)
        original_total = cart.get_total()
        total_cost     = original_total - rewards_redeemed

        # 3. Validate all stock before creating any records
        for item in cart:
            if not product.can_fulfill_order(quantity):
                return JsonResponse({'success': False, 'error': '...'})

        # 4. Create Order with PayPal capture ID
        order = Order.objects.create(
            ...,
            paypal_transaction_id=paypal_transaction_id
        )

        # 5. Create OrderItems and decrement stock
        for item in cart:
            OrderItem.objects.create(...)
            product.process_sale(quantity, total_item_price)

        # 6. Award rewards
        award_points_for_order(user, order, total_cost)

        # 7. Send confirmation email
        send_mail(...)

        return JsonResponse({'success': True, ...})
```

---

### `payment_success`

Clears the cart session key after successful payment and renders the success page:

```python
def payment_success(request):
    for key in list(request.session.keys()):
        if key == 'session_key':
            del request.session[key]
    return render(request, 'payment/payment-success.html')
```

---

### `payment_failed`

Renders the payment failed page — reached when the PayPal AJAX call errors:

```python
def payment_failed(request):
    return render(request, 'payment/payment-failed.html')
```

---

### `paypal_client_id`

Context processor registered in `settings.py` — makes the PayPal client ID available in all templates without passing it from each view:

```python
def paypal_client_id(request):
    return {'paypal_client_id': settings.PAYPAL_CLIENT_ID}
```

---

### `refund_landing`

Landing page where customers choose between registered account refund and guest refund flows.

---

### `request_refund`

Authenticated users submit refund requests from their order tracking page. Checks for existing active refunds, calculates refund amount, creates `RefundRequest` and `RefundItem` records, and sends a confirmation email.

---

### `refund_status`

Displays the current refund status to an authenticated customer. Allows cancellation if status is still `PENDING_RETURN`.

---

### `guest_refund_request`

Allows guest users to submit refunds using their Order ID and checkout email address.

---

### `guest_refund_status`

Displays refund status to guest users using their Refund Request ID — no authentication required.

---

## URLs

```python
# payment/urls.py

urlpatterns = [
    path('checkout',                          views.checkout,            name='checkout'),
    path('complete-order',                    views.complete_order,      name='complete-order'),
    path('payment-success',                   views.payment_success,     name='payment-success'),
    path('payment-failed',                    views.payment_failed,      name='payment-failed'),
    path('refunds/',                          views.refund_landing,      name='refund-landing'),
    path('request-refund/<int:order_id>/',    views.request_refund,      name='request-refund'),
    path('refund-status/<int:refund_id>/',    views.refund_status,       name='refund-status'),
    path('guest-refund/',                     views.guest_refund_request,name='guest-refund-request'),
    path('guest-refund-status/<int:refund_id>/', views.guest_refund_status, name='guest-refund-status'),
]
```

All payment URLs are prefixed with `payment/` from the root `urls.py`.

---

## Forms

### `ShippingForm`

ModelForm for `ShippingAddress` — used in the `manage-shipping` view of the account app:

```python
class ShippingForm(forms.ModelForm):
    class Meta:
        model  = ShippingAddress
        fields = ['full_name', 'email', 'address1', 'address2',
                  'city', 'state', 'zipcode']
        exclude = ['user']
```

---

## Admin

### `OrderAdmin`

Full list display with customer name, username, amount paid, item count, PayPal ID indicator, and live refund status badge. Clicking into an order shows all `OrderItem` records inline via `OrderItemInline`.

### `OrderItemAdmin`

Standalone list showing customer name, username, product, quantity, unit price, computed line total, and timestamp of sale. All columns are sortable.

### `ShippingAddressAdmin`

Searchable by name, email, address fields, and username. All fields are read-only — shipping addresses are customer-entered data.

### `RefundRequestAdmin`

The most feature-rich admin section. Contains a stepped action workflow enforcing the correct refund sequence:

| Step | Action | Description |
|---|---|---|
| 1 | `verify_refund_requests` | Admin reviews and approves — sets `admin_verified=True` |
| 2 | `mark_product_received` | Product returned and inspected — auto-restocks acceptable items |
| 3 | `process_paypal_refund` | Calls PayPal REST API to issue refund programmatically |
| 4 | `complete_refund` | Marks complete — deducts earned rewards — sends completion email |
| — | `reject_refund` | Rejects request — notifies customer |
| — | `restore_rewards_goodwill` | Admin goodwill: restores used rewards for defective/error cases |

All processing actions are blocked unless `admin_verified=True` — preventing accidental financial actions on unreviewed requests.

---

## PayPal Integration

### Frontend (checkout.html)

The PayPal JS SDK is loaded with the client ID from the context processor:

```html
<script src="https://www.paypal.com/sdk/js?client-id={{ paypal_client_id }}"></script>
```

The PayPal Buttons component handles the full payment flow:

```javascript
paypal.Buttons({
    createOrder: (data, actions) => {
        return actions.order.create({
            purchase_units: [{ amount: { value: total_price } }]
        });
    },
    onApprove: (data, actions) => {
        return actions.order.capture().then((details) => {
            // Capture ID stored for programmatic refunds
            const paypalCaptureId =
                details.purchase_units[0].payments.captures[0].id;

            $.ajax({
                type: 'POST',
                url:  '{% url "complete-order" %}',
                data: {
                    ...form_fields,
                    rewards_applied:      appliedRewardsAmount.toFixed(2),
                    paypal_transaction_id: paypalCaptureId,
                    csrfmiddlewaretoken:  '{{ csrf_token }}',
                    action: 'post'
                },
                success: function(json) {
                    window.location.replace('{% url "payment-success" %}');
                },
                error: function() {
                    window.location.replace('{% url "payment-failed" %}');
                }
            });
        });
    },
    onError: (err) => { console.error(err); }
}).render('#paypal-button-container');
```

### Backend — Programmatic Refund API

`issue_paypal_refund()` in `models.py` calls the PayPal REST API to issue refunds directly from the Django admin:

```python
def issue_paypal_refund(refund_request):
    # Step 1: Get OAuth access token
    token_response = requests.post(
        'https://api-m.paypal.com/v1/oauth2/token',
        auth=(client_id, secret),
        data={'grant_type': 'client_credentials'}
    )
    access_token = token_response.json()['access_token']

    # Step 2: Issue refund against the stored capture ID
    refund_response = requests.post(
        f'https://api-m.paypal.com/v2/payments/captures/{transaction_id}/refund',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'amount': {
                'value':         str(refund_request.refund_amount),
                'currency_code': 'USD'
            },
            'note_to_payer': f'Refund for Order #{refund_request.order.id}'
        }
    )
    return success, paypal_refund_id, error_message
```

> **Important:** Orders placed before `paypal_transaction_id` was added to the `Order` model cannot be refunded programmatically — they require manual processing in the PayPal dashboard. The admin action displays a clear warning for these cases.

---

## Refund Workflow

```
Customer submits refund request
            ↓
    Status: PENDING_RETURN
    Email:  Request received — ship product back
            ↓
Admin: (1) Verify & approve refund request
            ↓
Admin: (2) Mark product received
    Status: PRODUCT_RECEIVED
    Action: Auto-restock items in acceptable condition
    Email:  Product received — processing refund
            ↓
Admin: (3) Issue PayPal refund via API
    Status: PROCESSING_REFUND
    Action: PayPal REST API called programmatically
    Email:  PayPal refund issued — funds on the way
            ↓
Admin: (4) Complete refund
    Status: COMPLETED
    Action: Earned rewards deducted from account
    Email:  Refund complete confirmation
```

### Rewards on Refund

When a refund is completed:

- **Earned rewards are deducted** — points awarded from the original purchase are removed via `process_rewards_refund()`
- **Used rewards are NOT automatically restored** — the customer already received a cash refund for the amount they paid; restoring used rewards would give double value
- **Admin goodwill restoration** — an admin can manually restore used rewards for defective products or company errors using the `restore_rewards_goodwill` action

---

## Email Notifications

Emails are sent automatically at every stage of the refund lifecycle via `send_refund_status_email()`:

| Trigger | Subject |
|---|---|
| Refund request submitted | `Refund Request #N Received` |
| Product received by store | `Return Received — Refund #N Being Processed` |
| PayPal refund issued | `PayPal Refund Issued — Refund #N` |
| Refund completed | `Refund Complete — Refund #N` |
| Refund rejected | `Refund Request #N — Decision` |
| Customer cancels request | `Refund Request #N Cancelled` |
| Admin restores rewards | `Rewards Restored — Order #N` |

```python
def send_refund_status_email(refund, subject, body):
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[refund.customer_email],
        fail_silently=False,
    )
```

---

## Helper Functions

All helper functions live in `payment/models.py`:

### `send_refund_status_email(refund, subject, body)`

Central email sender used by all refund views and admin actions. Errors are caught and logged without crashing the calling action.

### `process_rewards_refund(refund_request)`

Deducts rewards earned from the original purchase when a refund is completed. Creates an `ADJUSTMENT` transaction record for the audit trail.

### `restock_refunded_items(refund_request)`

Iterates `RefundItem` records — for items marked `condition_acceptable=True` and not yet restocked, increments `product.quantity_available` and sets `restocked=True`.

### `restore_used_rewards(refund_request)`

Admin-only goodwill function. Restores rewards that were redeemed in the original purchase. Checks for existing restoration to prevent double-crediting. Returns `True` on success, `False` if already restored or ineligible.

### `issue_paypal_refund(refund_request)`

Calls the PayPal REST API to issue a programmatic refund. Returns a tuple of `(success: bool, paypal_refund_id: str, error_message: str)`.

---

## Setup and Installation

### 1 — Register the app

```python
# ecom_store/settings.py
INSTALLED_APPS = [
    ...
    'payment',
    ...
]
```

### 2 — Register context processor

```python
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            ...
            'payment.views.paypal_client_id',
        ],
    },
}]
```

### 3 — Include URLs

```python
# ecom_store/urls.py
path('payment/', include('payment.urls')),
```

### 4 — Run migrations

```bash
python manage.py makemigrations payment
python manage.py migrate
```

### 5 — Add PayPal credentials to `.env`

```env
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_SECRET=your-paypal-secret
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `PAYPAL_CLIENT_ID` | Yes | PayPal app client ID — loaded in checkout template |
| `PAYPAL_SECRET` | Yes | PayPal app secret — used for programmatic refund API calls |

Both are obtained from the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).

> **Sandbox vs Live:** Use sandbox credentials for testing and live credentials for production. The PayPal SDK URL does not change — the credentials determine which environment is used.

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to PayPal REST API for programmatic refunds |
| `decimal` | Python standard library — precise monetary arithmetic throughout |
| `django.core.mail` | Sending refund status emails |
| `cart.cart.Cart` | Reading cart contents in `complete_order` |
| `account.models` | `RewardAccount`, `RewardTransaction`, `award_points_for_order` |

---

## Notes

- **PayPal capture ID** — the `paypal_transaction_id` field on `Order` was added after initial deployment. Orders without it cannot be refunded via the API and require manual PayPal dashboard processing. The admin action displays a clear warning for these cases.
- **Guest refunds** — guest users submit refunds using Order ID and checkout email. No authentication is required. The refund is tied to the `Order` record, not a user account, so rewards adjustments are skipped.
- **Stock validation order** — all items are validated before any `Order` or `OrderItem` records are created. This prevents partial orders where some items succeed and others fail.
- **Rewards on zero-cost orders** — if rewards cover the full order total (`total_cost == 0`), no new points are awarded since there was no actual spend.
- **`SECURE_CROSS_ORIGIN_OPENER_POLICY`** — set to `same-origin-allow-popups` in `settings.py` to allow PayPal's popup-based payment flow to communicate with the parent window without being blocked by the browser.
- **Refund amount** — `refund_amount` on `RefundRequest` is set to `order.amount_paid` — the cash amount the customer actually paid after rewards redemption, not the original cart total.