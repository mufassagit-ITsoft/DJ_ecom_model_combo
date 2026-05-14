# Store App — Gamestore Django Project

The `store` app is the product-facing core of the Gamestore website. It manages the product catalogue, hierarchical navigation (topics → categories → brands), real-time search with AJAX suggestions, UPC barcode scanning with external API lookup, and all product-related admin tooling. It serves as the entry point for every customer interaction before checkout.

---

## Table of Contents

- [Overview](#overview)
- [App Structure](#app-structure)
- [Models](#models)
- [Views](#views)
- [URLs](#urls)
- [Admin](#admin)
- [Templates](#templates)
- [Barcode Scanner](#barcode-scanner)
- [Search System](#search-system)
- [Navigation System](#navigation-system)
- [Context Processors](#context-processors)
- [Setup and Installation](#setup-and-installation)
- [Dependencies](#dependencies)
- [Notes](#notes)

---

## Overview

The store app provides the complete customer-facing product experience:

- A hierarchical catalogue organised by **Topics** (e.g. Video Games) → **Categories** (e.g. Nintendo Switch) → **Brands** (e.g. Nintendo)
- Real-time product search with AJAX-powered suggestions appearing as the customer types
- UPC barcode scanning supporting camera, USB/Bluetooth hand scanner, and manual entry — with automatic product data lookup from the UPCitemdb API
- Inline barcode scanner widget directly inside the Django admin product form for rapid product entry
- Full inventory and sales tracking on every product — quantity available, quantity sold, total revenue, last sold date

---

## App Structure

```
store/
├── __init__.py
├── apps.py
├── models.py                  # Topic, Category, Product
├── views.py                   # All store views + barcode lookup views
├── urls.py                    # All store routes including barcode endpoints
├── admin.py                   # TopicAdmin, CategoryAdmin, ProductAdmin
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

---

## Models

### `Topic`

The top level of the product hierarchy. Each Topic groups related categories together and appears as a top-level dropdown in the navbar.

```python
class Topic(models.Model):
    name = models.CharField(max_length=250, db_index=True)
    slug = models.SlugField(max_length=250, unique=True)
```

**Example topics:** Video Games, Trading Card Games, Accessories

`get_absolute_url()` returns `/topic/<slug>/`

---

### `Category`

The second level of the hierarchy. Each category belongs to one Topic and appears as a flyout item under its parent topic dropdown.

```python
class Category(models.Model):
    topic = models.ForeignKey(
        Topic, related_name='categories',
        on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=250, db_index=True)
    slug = models.SlugField(max_length=250, unique=True)
```

**Example categories under Video Games:** Nintendo Switch, PlayStation 5, Xbox Series X, Game Boy

`get_absolute_url()` returns `/search/<slug>/`

---

### `Product`

The central model of the entire application. Stores all product data including pricing, imagery, inventory, sales tracking, and the UPC barcode code.

```python
class Product(models.Model):
    category          = models.ForeignKey(Category, related_name='product',
                                          on_delete=models.CASCADE, null=True)
    title             = models.CharField(max_length=250)
    brand             = models.CharField(max_length=250, default='un-branded')
    description       = models.TextField(blank=True)
    slug              = models.SlugField(max_length=255)
    price             = models.DecimalField(max_digits=4, decimal_places=2)
    image             = CloudinaryField('image', folder='gamestore/products/')

    # UPC barcode
    upc_code          = models.CharField(max_length=20, blank=True, null=True,
                                         unique=True, db_index=True)

    # Inventory and sales tracking
    date_uploaded     = models.DateTimeField(auto_now_add=True)
    quantity_available = models.IntegerField(default=0)
    quantity_sold     = models.IntegerField(default=0)
    total_price_sold  = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_sold_date    = models.DateTimeField(null=True, blank=True)
    payment_successful = models.BooleanField(default=False)
```

#### Inventory and Sales Fields

| Field | Description |
|---|---|
| `quantity_available` | Current sellable stock — decremented on each sale |
| `quantity_sold` | Running total of units sold — never decremented |
| `total_price_sold` | Cumulative revenue from this product |
| `last_sold_date` | Timestamp of the most recent sale |
| `payment_successful` | `True` once the product has been sold at least once |

#### UPC Code Field

```python
upc_code = models.CharField(
    max_length=20,
    blank=True, null=True,
    unique=True,
    db_index=True,
    help_text="Universal Product Code (UPC/EAN barcode number)"
)
```

Stored as a string to accommodate UPC-A (12 digits), EAN-13 (13 digits), and UPC-E (8 digits) formats. Indexed for fast lookup during barcode scanning. Unique constraint prevents duplicate products from being entered via scanner.

#### Instance Methods

```python
def is_in_stock(self):
    """Returns True if quantity_available > 0."""
    return self.quantity_available > 0

def can_fulfill_order(self, requested_quantity):
    """Returns True if quantity_available >= requested_quantity."""
    return self.quantity_available >= requested_quantity

def process_sale(self, quantity, total_amount):
    """
    Called from payment/views.py complete_order after PayPal confirms.
    Atomically updates all inventory and sales tracking fields.
    Returns True on success, False if insufficient stock.
    """
    if self.can_fulfill_order(quantity):
        self.quantity_available -= quantity
        self.quantity_sold      += quantity
        self.total_price_sold   += total_amount
        self.last_sold_date      = timezone.now()
        self.payment_successful  = True
        self.save()
        return True
    return False
```

---

## Views

### `store`

Main storefront — fetches all products and renders the store homepage with hero section and product grid.

```python
def store(request):
    all_products = Product.objects.all()
    return render(request, 'store/store.html', {'my_products': all_products})
```

---

### `categories`

Context processor registered in `settings.py`. Returns all categories for use in templates across the entire site.

```python
def categories(request):
    return {'all_categories': Category.objects.all()}
```

---

### `brands`

Context processor registered in `settings.py`. Returns all topics with their associated categories grouped together — powers the hierarchical navbar dropdown.

```python
def brands(request):
    all_topics = Topic.objects.all().order_by('name')
    all_topics_with_categories = []
    for topic in all_topics:
        topic_categories = Category.objects.filter(topic=topic).order_by('name')
        all_topics_with_categories.append({
            'topic':      topic,
            'categories': topic_categories,
        })
    return {'all_topics_with_categories': all_topics_with_categories}
```

---

### `list_topics`

Displays all products belonging to a specific topic by filtering through its categories.

```python
def list_topics(request, topic_slug=None):
    topic      = get_object_or_404(Topic, slug=topic_slug)
    categories = Category.objects.filter(topic=topic)
    products   = Product.objects.filter(category__in=categories)
    context    = {
        'topic':         topic,
        'products':      products,
        'product_count': products.count(),
    }
    return render(request, 'store/list-topic.html', context)
```

---

### `list_category`

Displays all products in a specific category.

```python
def list_category(request, category_slug=None):
    category = get_object_or_404(Category, slug=category_slug)
    products  = Product.objects.filter(category=category)
    return render(request, 'store/list-category.html', {
        'category': category,
        'products': products
    })
```

---

### `list_brand`

Displays all products from a specific brand. Uses case-insensitive exact match with a fallback to a contains search for partial brand name matches.

```python
def list_brand(request, brand_name=None):
    brand_name = brand_name.replace('-', ' ')
    products = Product.objects.filter(brand__iexact=brand_name)
    if not products.exists():
        products = Product.objects.filter(brand__icontains=brand_name)
    context = {
        'brand':         brand_name,
        'products':      products,
        'product_count': products.count()
    }
    return render(request, 'store/brand.html', context)
```

---

### `product_info`

Single product detail page showing image, description, stock status, price, quantity selector, and add-to-cart button.

```python
def product_info(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug)
    return render(request, 'store/product-info.html', {'product': product})
```

---

### `search_products`

Dual-mode search view. In AJAX mode (`?ajax=1`), returns rendered HTML suggestions for the live search dropdown. In standard mode, returns a full search results page.

```python
def search_products(request):
    query   = request.GET.get('q', '')
    is_ajax = request.GET.get('ajax', '') == '1'
    if query:
        products = Product.objects.filter(
            Q(title__icontains=query)       |
            Q(brand__icontains=query)       |
            Q(description__icontains=query) |
            Q(upc_code__icontains=query)    # ← UPC searchable from navbar
        ).distinct()[:10]
    else:
        products = Product.objects.none()
    if is_ajax:
        html = render_to_string(
            'store/search-suggestions.html',
            {'products': products, 'query': query}
        )
        return HttpResponse(html)
    return render(request, 'store/search-results.html', {
        'products':      products,
        'query':         query,
        'product_count': products.count()
    })
```

---

### `barcode_lookup`

AJAX endpoint for UPC barcode lookup. Checks the local database first, then falls back to the UPCitemdb public API. Used by both the admin scanner widget and the storefront barcode scanner page.

```python
def barcode_lookup(request):
    upc = request.GET.get('upc', '').strip()

    # Step 1: Check local database
    try:
        product = Product.objects.get(upc_code=upc)
        return JsonResponse({
            'source':        'local',
            'found_locally': True,
            'product':       { ...product fields... }
        })
    except Product.DoesNotExist:
        pass

    # Step 2: UPCitemdb API lookup
    response = requests.get(
        f'https://api.upcitemdb.com/prod/trial/lookup?upc={upc}',
        timeout=5
    )
    # Returns title, brand, description, price, image_url
```

---

### `barcode_scanner_page`

Renders the customer-facing barcode scanner page at `/barcode/scan/`.

---

### `upc_product_search`

AJAX endpoint used by the storefront scanner to find a product by exact UPC match and return its URL for redirect.

---

## URLs

```python
# store/urls.py

urlpatterns = [
    path('',
         views.store,             name='store'),
    path('product/<slug:product_slug>/',
         views.product_info,      name='product-info'),
    path('search/<slug:category_slug>/',
         views.list_category,     name='list-category'),
    path('topic/<slug:topic_slug>/',
         views.list_topics,       name='list-topic'),
    path('brand/<str:brand_name>/',
         views.list_brand,        name='list-brand'),
    path('search-products/',
         views.search_products,   name='search-products'),

    # Barcode / UPC
    path('barcode/lookup/',
         views.barcode_lookup,        name='barcode-lookup'),
    path('barcode/scan/',
         views.barcode_scanner_page,  name='barcode-scanner'),
    path('barcode/search/',
         views.upc_product_search,    name='upc-product-search'),
]
```

The store app is mounted at the root in `ecom_store/urls.py`:

```python
path('', include('store.urls')),
```

---

## Admin

### `TopicAdmin`

```python
@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
```

Slug auto-populates from the topic name as you type.

---

### `CategoryAdmin`

```python
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
```

Slug auto-populates from the category name as you type.

---

### `ProductAdmin`

The most feature-rich admin class in the project. Key features:

**List display columns:**

| Column | Description |
|---|---|
| `title` | Product name |
| `upc_badge` | Green badge with UPC code, or grey "No UPC" badge |
| `brand` | Brand name |
| `price` | Unit price |
| `quantity_available` | Current stock |
| `quantity_sold` | Total units sold |
| `total_price_sold` | Cumulative revenue |
| `date_uploaded` | When added |
| `last_sold_date` | Most recent sale |
| `payment_successful` | Has ever been sold |
| `stock_status` | ✅ In Stock / ⚠️ Low Stock / ❌ Out of Stock |

**Readonly fields:** `date_uploaded`, `quantity_sold`, `total_price_sold`, `last_sold_date`, `payment_successful`, `barcode_scanner_widget`

**Fieldset organisation:**

```
├── Basic Information
│   └── title, slug, brand, category, description, price, image
├── Barcode / UPC
│   └── barcode_scanner_widget (inline scanner), upc_code
├── Inventory Management
│   └── quantity_available
└── Sales Tracking (Read-Only, collapsed)
    └── date_uploaded, quantity_sold, total_price_sold,
        last_sold_date, payment_successful
```

**Inline Barcode Scanner Widget:**

A `readonly_field` method that renders a full barcode scanner directly inside the product admin form — no separate page needed. Supports all three input methods:

| Input Method | How it works |
|---|---|
| USB/Bluetooth hand scanner | Click the input field, scan — UPC auto-types and triggers lookup |
| Camera scanner | QuaggaJS detects barcode via device camera |
| Manual keyboard entry | Type UPC, press Enter or click Look Up |

On successful lookup, the widget pre-fills the `title`, `brand`, `description`, `price`, and `upc_code` fields automatically. If the product already exists locally it links directly to the existing product record.

---

## Templates

### `base.html`

Global layout template. Includes:
- Bootstrap 5 (Bootswatch Flatly) from CDN
- Font Awesome 4.7 icons
- Press Start 2P pixel font from Google Fonts
- `arcade.css` — Super Mario Bros. NES theme
- jQuery and Bootstrap JS
- Real-time search JavaScript
- Django messages block

### `nav.html`

Included in `base.html`. Contains:
- EvoGames logo icon from Cloudinary CDN
- "Gamestore" brand text
- Hierarchical topic dropdown menus populated from the `brands` context processor
- Dashboard/Login/Logout nav buttons
- Shopping cart badge with live quantity count
- Real-time search bar with AJAX suggestions
- White hamburger toggler for mobile

### `store.html`

Homepage with two sections:
- **Hero section** — controller SVG illustration, GameStore heading, tagline, create account button
- **All products** — responsive product grid (5 columns on desktop)

### `product-info.html`

Single product page with:
- Full-size product image
- Title, brand, description
- Stock status alert (in stock / low stock / out of stock)
- Price display
- Quantity selector limited to available stock
- Add to cart button with AJAX error/success feedback
- Disabled state when out of stock

### `list-category.html` and `list-topic.html`

Category and topic product grids matching the store homepage layout. Topic pages show total product count. Both handle empty states with a friendly message.

### `brand.html`

Products filtered by brand. Uses `brand__iexact` for exact matching with `brand__icontains` fallback. Displays product count and empty state.

### `search-results.html`

Full-page search results with query display and product count. Empty state encourages trying different keywords.

### `search-suggestions.html`

Partial template rendered server-side and injected into the AJAX search dropdown. Shows product image, title, brand, price, and a "View all results" link.

### `barcode-scanner.html`

Customer-facing barcode scanner page styled with the Mario NES theme. Features:
- Camera viewport with animated scan line and corner markers
- Start/Stop camera toggle button
- Manual UPC input field
- Product result card showing title, brand, price, stock status, and a View Product link
- Fallback search link when UPC is not found in store

---

## Barcode Scanner

### Overview

The barcode scanning system operates at two levels:

**Admin level** — for staff adding new products:
- Inline widget in the product add/change form
- Scans barcode → looks up UPCitemdb → pre-fills all product fields
- If product already exists, links to existing record instead of creating duplicate

**Customer level** — for customers finding products:
- Standalone page at `/barcode/scan/`
- Scans barcode → searches local database only
- Redirects to product page if found, offers search fallback if not

### UPCitemdb API

The external API used for product data lookup on new product entry:

```
Endpoint: https://api.upcitemdb.com/prod/trial/lookup?upc={upc}
Free tier: 100 lookups/day
Returns:  title, brand, description, offers (prices), images
```

The lookup is only triggered in the admin when a UPC is not already in the local database. Once a product is saved with its UPC, subsequent scans of the same code return the local record instantly without hitting the API.

### Supported Barcode Formats

| Format | Digits | Examples |
|---|---|---|
| UPC-A | 12 | Standard US retail products |
| EAN-13 | 13 | International products |
| UPC-E | 8 | Compressed short-form UPC |
| EAN-8 | 8 | Small package EAN |
| Code 128 | Variable | Used in logistics and some game packaging |

### QuaggaJS Library

Camera-based scanning uses QuaggaJS loaded from cdnjs:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js"></script>
```

A debounce mechanism prevents duplicate scans within a 3-second window:

```javascript
var lastScanned = '', lastScanTime = 0;
Quagga.onDetected(function(result) {
    var code = result.codeResult.code;
    var now  = Date.now();
    if (code === lastScanned && now - lastScanTime < 3000) return;
    lastScanned = code;
    lastScanTime = now;
    lookupUPC(code);
});
```

---

## Search System

### Real-Time AJAX Search

Triggered after 2+ characters are typed in the navbar search bar with a 300ms debounce:

```javascript
$('#search-input').on('keyup', function() {
    clearTimeout(searchTimeout);
    const query = $(this).val();
    if (query.length >= 2) {
        searchTimeout = setTimeout(function() {
            performSearch(query);
        }, 300);
    } else {
        $('#search-suggestions').hide();
    }
});
```

The AJAX call hits `search_products` with `?ajax=1` and receives rendered HTML suggestions injected into the dropdown.

### Search Fields

Products are searchable across four fields:

```python
Q(title__icontains=query)       |
Q(brand__icontains=query)       |
Q(description__icontains=query) |
Q(upc_code__icontains=query)
```

The `upc_code` field inclusion means customers can type a barcode number into the search bar and find the product directly without using the dedicated scanner page.

### Results Limit

AJAX suggestions are capped at 10 results. Full search results have no cap but are ordered by relevance through Django's query matching.

---

## Navigation System

The navbar uses a two-level hierarchical dropdown:

```
Topic (top level)
    └── All [Topic Name]      ← links to list-topic view
    └── Category A            ← links to list-category view
    └── Category B
    └── Category C
```

Both levels are populated from the `brands` context processor which runs on every request. Adding a new Topic or Category in admin immediately appears in the navbar without any code changes.

Brand-level navigation is handled separately via `list-brand` URLs generated from product brand values — no dedicated Brand model is needed.

---

## Context Processors

Both `categories` and `brands` are registered as context processors in `settings.py`:

```python
'context_processors': [
    ...
    'store.views.categories',
    'store.views.brands',
]
```

This makes `all_categories` and `all_topics_with_categories` available in every template site-wide including the admin pages — which is required for the navbar to render on every page.

---

## Setup and Installation

### 1 — Register the app

```python
# ecom_store/settings.py
INSTALLED_APPS = [
    ...
    'store',
    ...
]
```

### 2 — Register context processors

```python
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            ...
            'store.views.categories',
            'store.views.brands',
        ],
    },
}]
```

### 3 — Include URLs

```python
# ecom_store/urls.py
path('', include('store.urls')),
```

### 4 — Run migrations

```bash
python manage.py makemigrations store
python manage.py migrate
```

### 5 — Configure Cloudinary for product images

```python
# settings.py
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY':    config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}

if all([CLOUDINARY_STORAGE['CLOUD_NAME'], ...]):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
```

### 6 — Collect static files

```bash
python manage.py collectstatic
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `cloudinary` | Cloudinary Python SDK |
| `django-cloudinary-storage` | Django storage backend for Cloudinary media |
| `requests` | HTTP calls to UPCitemdb API for barcode lookup |
| `QuaggaJS` | JavaScript barcode detection library (loaded from CDN) |
| `pillow` | Image processing — required by Django's image handling |
| `django.db.models.Q` | Complex OR queries for search |

---

## Notes

- **`price` field constraint** — `max_digits=4` limits prices to `$99.99` maximum. For products above $99.99, increase to `max_digits=6` and run a migration.
- **Cloudinary folder** — all product images upload to the `gamestore/products/` folder in Cloudinary, keeping them organised separately from logo and other assets.
- **Brand navigation** — brands are not a dedicated model. The `list_brand` view filters `Product.objects.filter(brand__iexact=brand_name)`. Brand links in templates are constructed by slugifying the brand name and passing it to the `list-brand` URL.
- **Slug uniqueness** — `Product.slug` is not marked `unique=True` in the model, meaning two products with the same title would share a slug. If duplicate titles are possible, add `unique=True` to the slug field and run a migration.
- **Search result cap** — AJAX suggestions are limited to 10 results. This is hardcoded in the view with `[:10]`. Adjust as needed.
- **UPC free tier limit** — the UPCitemdb trial API allows 100 lookups per day. For high-volume product entry, upgrade to a paid plan or cache results locally after the first lookup.
- **`mark_safe` in admin widget** — the barcode scanner widget returns `mark_safe(widget_html)` rather than `format_html()` because the entire HTML string is internally constructed. `format_html()` raises `TypeError: args or kwargs must be provided` in Django 4.0+ when called with no escaping arguments.