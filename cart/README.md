# Cart App — Gamestore Django Project

The `cart` app handles all shopping cart functionality for the Gamestore website. It implements a session-based cart system that persists across page loads without requiring a database table, supports real-time stock validation, quantity updates, and integrates directly with the checkout and rewards systems.

---

## Table of Contents

- [Overview](#overview)
- [App Structure](#app-structure)
- [Cart Class](#cart-class)
- [Views](#views)
- [URLs](#urls)
- [Context Processor](#context-processor)
- [Templates](#templates)
- [Stock Validation](#stock-validation)
- [Integration with Checkout](#integration-with-checkout)
- [AJAX Operations](#ajax-operations)
- [Setup and Installation](#setup-and-installation)
- [Dependencies](#dependencies)
- [Notes](#notes)

---

## Overview

The cart app uses Django's session framework to store cart data server-side without a dedicated database model. Each cart item is stored as a dictionary in the session keyed by product ID, containing the unit price and quantity. This approach means:

- No database writes on every cart operation — faster performance
- Cart persists across browser sessions as long as the Django session is active
- Guest users and authenticated users both get a cart automatically
- The cart session key (`session_key`) is deliberately preserved on logout so returning users do not lose their cart

---

## App Structure

```
cart/
├── __init__.py
├── apps.py
├── cart.py                  # Core Cart class — all cart logic lives here
├── views.py                 # cart_summary, cart_add, cart_delete, cart_update
├── urls.py                  # Cart URL routing
├── context_processors.py    # Makes cart available in all templates globally
└── templates/
    └── cart/
        └── cart-summary.html
```

---

## Cart Class

The `Cart` class in `cart/cart.py` is the core of the entire cart system. It wraps the Django session and provides a clean interface for all cart operations.

### Initialisation

```python
class Cart():
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('session_key')
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}
        self.cart = cart
```

On every request, the cart reads from the session. If no cart exists yet (new user or cleared session), an empty dict is created and stored under `session_key`.

### Session Data Structure

Each item in the cart is stored as:

```python
{
    "product_id_string": {
        "price": "59.99",    # stored as string to avoid float precision issues
        "qty": 2
    }
}
```

Product IDs are stored as strings because Django session data is JSON-serialised and JSON keys must be strings.

---

### Methods

#### `add(product, product_qty)`

Adds a product to the cart or updates its quantity if already present:

```python
def add(self, product, product_qty):
    product_id = str(product.id)
    if product_id in self.cart:
        self.cart[product_id]['qty'] = product_qty
    else:
        self.cart[product_id] = {
            'price': str(product.price),
            'qty': product_qty
        }
    self.session.modified = True
```

> **Note:** Setting `self.session.modified = True` is required whenever the session dict is mutated in place — Django only auto-detects modifications to the session dict itself, not nested changes.

#### `delete(product)`

Removes a product from the cart by product ID:

```python
def delete(self, product):
    product_id = str(product)
    if product_id in self.cart:
        del self.cart[product_id]
    self.session.modified = True
```

#### `update(product, qty)`

Updates the quantity of an existing cart item:

```python
def update(self, product, qty):
    product_id = str(product)
    if product_id in self.cart:
        self.cart[product_id]['qty'] = qty
    self.session.modified = True
```

#### `__len__()`

Returns the total number of individual items across all products in the cart (not number of unique products). Used by the navbar cart badge:

```python
def __len__(self):
    return sum(item['qty'] for item in self.cart.values())
```

#### `__iter__()`

Iterates over cart items, fetching full `Product` objects from the database and computing line totals using `Decimal` arithmetic:

```python
def __iter__(self):
    all_product_ids = self.cart.keys()
    products = Product.objects.filter(id__in=all_product_ids)
    cart = self.cart.copy()
    for product in products:
        cart[str(product.id)]['product'] = product
    for item in cart.values():
        item['price'] = Decimal(item['price'])
        item['total'] = item['price'] * item['qty']   # ← line total
        yield item
```

The `item['total']` computed here is used directly in `cart-summary.html` as `{{ item.total|floatformat:2 }}` — this replaced the previous `mathfilters` `|mul:` template tag dependency.

#### `get_total()`

Returns the cart grand total as a `Decimal`:

```python
def get_total(self):
    return sum(
        Decimal(item['price']) * item['qty']
        for item in self.cart.values()
    )
```

Used in both `cart-summary.html` and `checkout.html` for displaying and processing the order total.

---

## Views

### `cart_summary`

Renders the full cart page with all items, stock warnings, quantity selectors, and the proceed to checkout button.

```python
def cart_summary(request):
    cart = Cart(request)
    return render(request, 'cart/cart-summary.html', {'cart': cart})
```

### `cart_add`

AJAX POST endpoint called from the product info page when a user clicks Add to Cart. Validates stock before adding:

```python
def cart_add(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        product = get_object_or_404(Product, id=product_id)

        if not product.can_fulfill_order(product_quantity):
            return JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available.',
                'qty': cart.__len__()
            })

        if not product.is_in_stock():
            return JsonResponse({
                'error': True,
                'message': 'This product is currently out of stock.',
                'qty': cart.__len__()
            })

        cart.add(product=product, product_qty=product_quantity)
        return JsonResponse({
            'error': False,
            'message': 'Product added to cart successfully!',
            'qty': cart.__len__()
        })
```

### `cart_delete`

AJAX POST endpoint called from the cart summary page delete button:

```python
def cart_delete(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        cart.delete(product=product_id)
        return JsonResponse({
            'qty':   cart.__len__(),
            'total': cart.get_total()
        })
```

### `cart_update`

AJAX POST endpoint called from the cart summary page update button. Validates stock availability before updating:

```python
def cart_update(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        product = get_object_or_404(Product, id=product_id)

        if not product.can_fulfill_order(product_quantity):
            return JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available.',
                'qty':   cart.__len__(),
                'total': cart.get_total()
            })

        cart.update(product=product_id, qty=product_quantity)
        return JsonResponse({
            'error': False,
            'qty':   cart.__len__(),
            'total': cart.get_total()
        })
```

---

## URLs

```python
# cart/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('',        views.cart_summary, name='cart-summary'),
    path('add/',    views.cart_add,     name='cart-add'),
    path('delete/', views.cart_delete,  name='cart-delete'),
    path('update/', views.cart_update,  name='cart-update'),
]
```

All cart URLs are prefixed with `cart/` from the root `urls.py`:

```python
path('cart/', include('cart.urls')),
```

| Full URL | View | Name |
|---|---|---|
| `/cart/` | `cart_summary` | `cart-summary` |
| `/cart/add/` | `cart_add` | `cart-add` |
| `/cart/delete/` | `cart_delete` | `cart-delete` |
| `/cart/update/` | `cart_update` | `cart-update` |

---

## Context Processor

`context_processors.py` makes the `cart` object available in every template across the entire site without needing to pass it manually from each view:

```python
# cart/context_processors.py

from .cart import Cart

def cart(request):
    return {'cart': Cart(request)}
```

Registered in `settings.py`:

```python
TEMPLATES = [{
    ...
    'OPTIONS': {
        'context_processors': [
            ...
            'cart.context_processors.cart',
        ],
    },
}]
```

This is what powers the cart quantity badge in the navbar:

```html
{% with qty_amount=cart|length %}
    {% if qty_amount > 0 %}{{ qty_amount }}{% else %}0{% endif %}
{% endwith %}
```

And the cart total in `checkout.html`:

```html
{{ cart.get_total|floatformat:2 }}
```

---

## Templates

### `cart-summary.html`

Displays all items currently in the cart with:

- Product image and title linked to the product detail page
- Per-item stock warnings (out of stock, low stock, quantity exceeds available)
- Line total per item using `{{ item.total|floatformat:2 }}` — computed by `Cart.__iter__()` using native Python `Decimal` multiplication
- Quantity selector limited to available stock (max 4 or stock count, whichever is lower)
- Update button — triggers `cart_update` AJAX call
- Delete button — triggers `cart_delete` AJAX call
- Cart grand total using `{{ cart.get_total|floatformat:2 }}`
- Proceed to Checkout button

**Important:** The cart summary template does not use `{% load mathfilters %}`. All arithmetic is handled in `Cart.__iter__()` in Python, keeping the template clean and dependency-free.

---

## Stock Validation

Stock is validated at two points in the cart flow:

### 1 — On Add (`cart_add`)

Before adding to cart, the view checks:
- `product.is_in_stock()` — quantity > 0
- `product.can_fulfill_order(quantity)` — quantity_available >= requested quantity

If either check fails, a JSON error response is returned and the product is not added.

### 2 — On Display (`cart-summary.html`)

When the cart is rendered, each item is checked against current stock:

```html
{% if product.quantity_available == 0 %}
    <!-- Out of stock warning -->
{% elif item.qty > product.quantity_available %}
    <!-- Quantity exceeds available warning -->
{% elif product.quantity_available < 5 %}
    <!-- Low stock warning -->
{% endif %}
```

This catches edge cases where stock changed after an item was added to the cart (e.g. another customer purchased the last unit).

### 3 — On Checkout (`complete_order` in payment app)

A final stock check runs on all cart items before any order is created or payment processed. If any item has insufficient stock, the entire order is rejected with a detailed error message listing each affected product.

---

## Integration with Checkout

The cart integrates with the payment app at checkout via two mechanisms:

### 1 — Cart total passed to PayPal

In `checkout.html`, the cart total is read into a JavaScript variable:

```javascript
const originalTotal = parseFloat('{{ cart.get_total|floatformat:2 }}');
let total_price = originalTotal.toFixed(2);
```

After rewards are applied, `total_price` is reduced and passed to PayPal's `createOrder` as the charge amount.

### 2 — Cart cleared after payment

In `payment_success` view, the cart session is cleared:

```python
def payment_success(request):
    for key in list(request.session.keys()):
        if key == 'session_key':
            del request.session[key]
    return render(request, 'payment/payment-success.html')
```

Only `session_key` is deleted — all other session data (authentication, messages) is preserved.

---

## AJAX Operations

All cart mutations (add, delete, update) use jQuery AJAX calls with CSRF token protection. Responses update the UI without a full page reload.

### Add to Cart (from `product-info.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-add" %}',
    data: {
        product_id:       $('#add-button').val(),
        product_quantity: $('#select option:selected').text(),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        if (json.error) {
            // Show error alert
        } else {
            document.getElementById('cart-qty').textContent = json.qty;
            // Show success alert
        }
    }
});
```

### Delete from Cart (from `cart-summary.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-delete" %}',
    data: {
        product_id: $(this).data('index'),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        location.reload();
        document.getElementById('cart-qty').textContent  = json.qty;
        document.getElementById('total').textContent = json.total;
    }
});
```

### Update Quantity (from `cart-summary.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-update" %}',
    data: {
        product_id:       $(this).data('index'),
        product_quantity: $('#select' + theproductid + ' option:selected').text(),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        if (json.error) {
            // Show # Cart App — Gamestore Django Project

The `cart` app handles all shopping cart functionality for the Gamestore website. It implements a session-based cart system that persists across page loads without requiring a database table, supports real-time stock validation, quantity updates, and integrates directly with the checkout and rewards systems.

---

## Table of Contents

- [Overview](#overview)
- [App Structure](#app-structure)
- [Cart Class](#cart-class)
- [Views](#views)
- [URLs](#urls)
- [Context Processor](#context-processor)
- [Templates](#templates)
- [Stock Validation](#stock-validation)
- [Integration with Checkout](#integration-with-checkout)
- [AJAX Operations](#ajax-operations)
- [Setup and Installation](#setup-and-installation)
- [Dependencies](#dependencies)
- [Notes](#notes)

---

## Overview

The cart app uses Django's session framework to store cart data server-side without a dedicated database model. Each cart item is stored as a dictionary in the session keyed by product ID, containing the unit price and quantity. This approach means:

- No database writes on every cart operation — faster performance
- Cart persists across browser sessions as long as the Django session is active
- Guest users and authenticated users both get a cart automatically
- The cart session key (`session_key`) is deliberately preserved on logout so returning users do not lose their cart

---

## App Structure

```
cart/
├── __init__.py
├── apps.py
├── cart.py                  # Core Cart class — all cart logic lives here
├── views.py                 # cart_summary, cart_add, cart_delete, cart_update
├── urls.py                  # Cart URL routing
├── context_processors.py    # Makes cart available in all templates globally
└── templates/
    └── cart/
        └── cart-summary.html
```

---

## Cart Class

The `Cart` class in `cart/cart.py` is the core of the entire cart system. It wraps the Django session and provides a clean interface for all cart operations.

### Initialisation

```python
class Cart():
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('session_key')
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}
        self.cart = cart
```

On every request, the cart reads from the session. If no cart exists yet (new user or cleared session), an empty dict is created and stored under `session_key`.

### Session Data Structure

Each item in the cart is stored as:

```python
{
    "product_id_string": {
        "price": "59.99",    # stored as string to avoid float precision issues
        "qty": 2
    }
}
```

Product IDs are stored as strings because Django session data is JSON-serialised and JSON keys must be strings.

---

### Methods

#### `add(product, product_qty)`

Adds a product to the cart or updates its quantity if already present:

```python
def add(self, product, product_qty):
    product_id = str(product.id)
    if product_id in self.cart:
        self.cart[product_id]['qty'] = product_qty
    else:
        self.cart[product_id] = {
            'price': str(product.price),
            'qty': product_qty
        }
    self.session.modified = True
```

> **Note:** Setting `self.session.modified = True` is required whenever the session dict is mutated in place — Django only auto-detects modifications to the session dict itself, not nested changes.

#### `delete(product)`

Removes a product from the cart by product ID:

```python
def delete(self, product):
    product_id = str(product)
    if product_id in self.cart:
        del self.cart[product_id]
    self.session.modified = True
```

#### `update(product, qty)`

Updates the quantity of an existing cart item:

```python
def update(self, product, qty):
    product_id = str(product)
    if product_id in self.cart:
        self.cart[product_id]['qty'] = qty
    self.session.modified = True
```

#### `__len__()`

Returns the total number of individual items across all products in the cart (not number of unique products). Used by the navbar cart badge:

```python
def __len__(self):
    return sum(item['qty'] for item in self.cart.values())
```

#### `__iter__()`

Iterates over cart items, fetching full `Product` objects from the database and computing line totals using `Decimal` arithmetic:

```python
def __iter__(self):
    all_product_ids = self.cart.keys()
    products = Product.objects.filter(id__in=all_product_ids)
    cart = self.cart.copy()
    for product in products:
        cart[str(product.id)]['product'] = product
    for item in cart.values():
        item['price'] = Decimal(item['price'])
        item['total'] = item['price'] * item['qty']   # ← line total
        yield item
```

The `item['total']` computed here is used directly in `cart-summary.html` as `{{ item.total|floatformat:2 }}` — this replaced the previous `mathfilters` `|mul:` template tag dependency.

#### `get_total()`

Returns the cart grand total as a `Decimal`:

```python
def get_total(self):
    return sum(
        Decimal(item['price']) * item['qty']
        for item in self.cart.values()
    )
```

Used in both `cart-summary.html` and `checkout.html` for displaying and processing the order total.

---

## Views

### `cart_summary`

Renders the full cart page with all items, stock warnings, quantity selectors, and the proceed to checkout button.

```python
def cart_summary(request):
    cart = Cart(request)
    return render(request, 'cart/cart-summary.html', {'cart': cart})
```

### `cart_add`

AJAX POST endpoint called from the product info page when a user clicks Add to Cart. Validates stock before adding:

```python
def cart_add(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        product = get_object_or_404(Product, id=product_id)

        if not product.can_fulfill_order(product_quantity):
            return JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available.',
                'qty': cart.__len__()
            })

        if not product.is_in_stock():
            return JsonResponse({
                'error': True,
                'message': 'This product is currently out of stock.',
                'qty': cart.__len__()
            })

        cart.add(product=product, product_qty=product_quantity)
        return JsonResponse({
            'error': False,
            'message': 'Product added to cart successfully!',
            'qty': cart.__len__()
        })
```

### `cart_delete`

AJAX POST endpoint called from the cart summary page delete button:

```python
def cart_delete(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        cart.delete(product=product_id)
        return JsonResponse({
            'qty':   cart.__len__(),
            'total': cart.get_total()
        })
```

### `cart_update`

AJAX POST endpoint called from the cart summary page update button. Validates stock availability before updating:

```python
def cart_update(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        product = get_object_or_404(Product, id=product_id)

        if not product.can_fulfill_order(product_quantity):
            return JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available.',
                'qty':   cart.__len__(),
                'total': cart.get_total()
            })

        cart.update(product=product_id, qty=product_quantity)
        return JsonResponse({
            'error': False,
            'qty':   cart.__len__(),
            'total': cart.get_total()
        })
```

---

## URLs

```python
# cart/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('',        views.cart_summary, name='cart-summary'),
    path('add/',    views.cart_add,     name='cart-add'),
    path('delete/', views.cart_delete,  name='cart-delete'),
    path('update/', views.cart_update,  name='cart-update'),
]
```

All cart URLs are prefixed with `cart/` from the root `urls.py`:

```python
path('cart/', include('cart.urls')),
```

| Full URL | View | Name |
|---|---|---|
| `/cart/` | `cart_summary` | `cart-summary` |
| `/cart/add/` | `cart_add` | `cart-add` |
| `/cart/delete/` | `cart_delete` | `cart-delete` |
| `/cart/update/` | `cart_update` | `cart-update` |

---

## Context Processor

`context_processors.py` makes the `cart` object available in every template across the entire site without needing to pass it manually from each view:

```python
# cart/context_processors.py

from .cart import Cart

def cart(request):
    return {'cart': Cart(request)}
```

Registered in `settings.py`:

```python
TEMPLATES = [{
    ...
    'OPTIONS': {
        'context_processors': [
            ...
            'cart.context_processors.cart',
        ],
    },
}]
```

This is what powers the cart quantity badge in the navbar:

```html
{% with qty_amount=cart|length %}
    {% if qty_amount > 0 %}{{ qty_amount }}{% else %}0{% endif %}
{% endwith %}
```

And the cart total in `checkout.html`:

```html
{{ cart.get_total|floatformat:2 }}
```

---

## Templates

### `cart-summary.html`

Displays all items currently in the cart with:

- Product image and title linked to the product detail page
- Per-item stock warnings (out of stock, low stock, quantity exceeds available)
- Line total per item using `{{ item.total|floatformat:2 }}` — computed by `Cart.__iter__()` using native Python `Decimal` multiplication
- Quantity selector limited to available stock (max 4 or stock count, whichever is lower)
- Update button — triggers `cart_update` AJAX call
- Delete button — triggers `cart_delete` AJAX call
- Cart grand total using `{{ cart.get_total|floatformat:2 }}`
- Proceed to Checkout button

**Important:** The cart summary template does not use `{% load mathfilters %}`. All arithmetic is handled in `Cart.__iter__()` in Python, keeping the template clean and dependency-free.

---

## Stock Validation

Stock is validated at two points in the cart flow:

### 1 — On Add (`cart_add`)

Before adding to cart, the view checks:
- `product.is_in_stock()` — quantity > 0
- `product.can_fulfill_order(quantity)` — quantity_available >= requested quantity

If either check fails, a JSON error response is returned and the product is not added.

### 2 — On Display (`cart-summary.html`)

When the cart is rendered, each item is checked against current stock:

```html
{% if product.quantity_available == 0 %}
    <!-- Out of stock warning -->
{% elif item.qty > product.quantity_available %}
    <!-- Quantity exceeds available warning -->
{% elif product.quantity_available < 5 %}
    <!-- Low stock warning -->
{% endif %}
```

This catches edge cases where stock changed after an item was added to the cart (e.g. another customer purchased the last unit).

### 3 — On Checkout (`complete_order` in payment app)

A final stock check runs on all cart items before any order is created or payment processed. If any item has insufficient stock, the entire order is rejected with a detailed error message listing each affected product.

---

## Integration with Checkout

The cart integrates with the payment app at checkout via two mechanisms:

### 1 — Cart total passed to PayPal

In `checkout.html`, the cart total is read into a JavaScript variable:

```javascript
const originalTotal = parseFloat('{{ cart.get_total|floatformat:2 }}');
let total_price = originalTotal.toFixed(2);
```

After rewards are applied, `total_price` is reduced and passed to PayPal's `createOrder` as the charge amount.

### 2 — Cart cleared after payment

In `payment_success` view, the cart session is cleared:

```python
def payment_success(request):
    for key in list(request.session.keys()):
        if key == 'session_key':
            del request.session[key]
    return render(request, 'payment/payment-success.html')
```

Only `session_key` is deleted — all other session data (authentication, messages) is preserved.

---

## AJAX Operations

All cart mutations (add, delete, update) use jQuery AJAX calls with CSRF token protection. Responses update the UI without a full page reload.

### Add to Cart (from `product-info.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-add" %}',
    data: {
        product_id:       $('#add-button').val(),
        product_quantity: $('#select option:selected').text(),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        if (json.error) {
            // Show error alert
        } else {
            document.getElementById('cart-qty').textContent = json.qty;
            // Show success alert
        }
    }
});
```

### Delete from Cart (from `cart-summary.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-delete" %}',
    data: {
        product_id: $(this).data('index'),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        location.reload();
        document.getElementById('cart-qty').textContent  = json.qty;
        document.getElementById('total').textContent = json.total;
    }
});
```

### Update Quantity (from `cart-summary.html`)

```javascript
$.ajax({
    type: 'POST',
    url:  '{% url "cart-update" %}',
    data: {
        product_id:       $(this).data('index'),
        product_quantity: $('#select' + theproductid + ' option:selected').text(),
        csrfmiddlewaretoken: "{{ csrf_token }}",
        action: 'post'
    },
    success: function(json) {
        if (json.error) {
            // Show stock error message inline
        } else {
            location.reload();
        }
    }
});
```

---

## Setup and Installation

### 1 — Register the app

```python
# ecom_store/settings.py
INSTALLED_APPS = [
    ...
    'cart',
    ...
]
```

### 2 — Register the context processor

```python
# ecom_store/settings.py
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            ...
            'cart.context_processors.cart',
        ],
    },
}]
```

### 3 — Include URLs

```python
# ecom_store/urls.py
path('cart/', include('cart.urls')),
```

### 4 — Session configuration

The cart relies on Django's session framework which is included by default. Confirm these are present:

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django.contrib.sessions',
    ...
]

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    ...
]
```

No additional migrations are needed — the cart has no database models.

---

## Dependencies

| Package | Purpose |
|---|---|
| `django.contrib.sessions` | Session framework for storing cart data |
| `decimal` | Python standard library — precise monetary arithmetic |
| `store.models.Product` | Fetched during cart iteration for titles, prices, images |

The cart app has **no third-party package dependencies** beyond Django itself.

---

## Notes

- **No `mathfilters` dependency** — line totals (`price × qty`) are computed in `Cart.__iter__()` using Python's `Decimal` and exposed as `item['total']`. The template uses `{{ item.total|floatformat:2 }}` with Django's built-in filter only.
- **Decimal precision** — prices are stored as strings in the session and converted to `Decimal` on iteration to avoid floating point rounding errors in financial calculations.
- **Guest cart persistence** — the cart works for both authenticated and unauthenticated users. It is tied to the Django session, not the user account, so it is not transferable between devices.
- **Session key preservation** — the logout view in `account/views.py` deliberately skips deleting `session_key` so the cart survives logout and is available when the user logs back in.
- **Quantity selector** — the cart summary limits the dropdown to a maximum of 4 units or the available stock count, whichever is lower, using a simple `{% for i in "1234" %}` loop with a counter comparison.
- **Disabled states** — both the quantity selector and the Update button are `disabled` when `product.quantity_available == 0`, preventing any interaction with out-of-stock items.stock error message inline
        } else {
            location.reload();
        }
    }
});
```

---

## Setup and Installation

### 1 — Register the app

```python
# ecom_store/settings.py
INSTALLED_APPS = [
    ...
    'cart',
    ...
]
```

### 2 — Register the context processor

```python
# ecom_store/settings.py
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            ...
            'cart.context_processors.cart',
        ],
    },
}]
```

### 3 — Include URLs

```python
# ecom_store/urls.py
path('cart/', include('cart.urls')),
```

### 4 — Session configuration

The cart relies on Django's session framework which is included by default. Confirm these are present:

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django.contrib.sessions',
    ...
]

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    ...
]
```

No additional migrations are needed — the cart has no database models.

---

## Dependencies

| Package | Purpose |
|---|---|
| `django.contrib.sessions` | Session framework for storing cart data |
| `decimal` | Python standard library — precise monetary arithmetic |
| `store.models.Product` | Fetched during cart iteration for titles, prices, images |

The cart app has **no third-party package dependencies** beyond Django itself.

---

## Notes

- **No `mathfilters` dependency** — line totals (`price × qty`) are computed in `Cart.__iter__()` using Python's `Decimal` and exposed as `item['total']`. The template uses `{{ item.total|floatformat:2 }}` with Django's built-in filter only.
- **Decimal precision** — prices are stored as strings in the session and converted to `Decimal` on iteration to avoid floating point rounding errors in financial calculations.
- **Guest cart persistence** — the cart works for both authenticated and unauthenticated users. It is tied to the Django session, not the user account, so it is not transferable between devices.
- **Session key preservation** — the logout view in `account/views.py` deliberately skips deleting `session_key` so the cart survives logout and is available when the user logs back in.
- **Quantity selector** — the cart summary limits the dropdown to a maximum of 4 units or the available stock count, whichever is lower, using a simple `{% for i in "1234" %}` loop with a counter comparison.
- **Disabled states** — both the quantity selector and the Update button are `disabled` when `product.quantity_available == 0`, preventing any interaction with out-of-stock items.