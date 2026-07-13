from django.shortcuts import render
from django.conf import settings
from . models import Category, Product, Topic
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
import requests


def store(request):
    all_products = Product.objects.all()
    context = {'my_products':all_products}
    return render(request, 'store/store.html', context)

def categories(request):
    all_categories = Category.objects.all()
    return {'all_categories': all_categories}

def brands(request):
    all_topics = Topic.objects.all().order_by('name')

    all_topics_with_categories = []
    for topic in all_topics:
        topic_categories = Category.objects.filter(topic=topic).order_by('name')
        all_topics_with_categories.append({
            'topic': topic,
            'categories': topic_categories,
        })

    return {'all_topics_with_categories': all_topics_with_categories}

def list_topics(request, topic_slug=None):
    topic = get_object_or_404(Topic, slug=topic_slug)
    categories = Category.objects.filter(topic=topic)
    products = Product.objects.filter(category__in=categories)
    context = {
        'topic': topic,
        'products': products,
        'product_count': products.count(),
    }
    return render(request, 'store/list-topic.html', context)

def list_category(request, category_slug=None):
    category = get_object_or_404(Category, slug=category_slug)
    products = Product.objects.filter(category=category)
    return render(request, 'store/list-category.html', {'category':category, 'products':products})

def list_brand(request, brand_name=None):
    """Display all products from a specific brand"""
    brand_name = brand_name.replace('-', ' ')
    products = Product.objects.filter(brand__iexact=brand_name)
    
    if not products.exists():
        products = Product.objects.filter(brand__icontains=brand_name)
    
    context = {
        'brand': brand_name,
        'products': products,
        'product_count': products.count()
    }
    return render(request, 'store/brand.html', context)

def product_info(request, product_slug):
    product = get_object_or_404(Product, slug=product_slug)
    context = {'product': product}
    return render(request, 'store/product-info.html', context)

def search_products(request):
    query = request.GET.get('q', '')
    is_ajax = request.GET.get('ajax', '') == '1'
    if query:
        products = Product.objects.filter(
            Q(title__icontains=query) | 
            Q(brand__icontains=query) | 
            Q(description__icontains=query)
        ).distinct()[:10]
    else:
        products = Product.objects.none()
    if is_ajax:
        html = render_to_string('store/search-suggestions.html', {'products': products, 'query': query})
        return HttpResponse(html)
    context = {
        'products': products,
        'query': query,
        'product_count': products.count()
    }
    return render(request, 'store/search-results.html', context)

def barcode_lookup(request):
    """
    Look up a UPC code against:
    1. Local database first (existing products)
    2. UPCitemdb public API as fallback (pre-fills new product forms)

    Returns JSON with product data or an error message.
    Free tier: 100 lookups/day — sufficient for admin use.
    """
    upc = request.GET.get('upc', '').strip()

    if not upc:
        return JsonResponse({'error': 'No UPC code provided.'}, status=400)

    # Step 1 — check local database
    try:
        product = Product.objects.get(upc_code=upc)
        return JsonResponse({
            'source': 'local',
            'found_locally': True,
            'product': {
                'id':          product.id,
                'title':       product.title,
                'brand':       product.brand,
                'price':       str(product.price),
                'description': product.description,
                'upc_code':    product.upc_code,
                'slug':        product.slug,
                'url':         product.get_absolute_url(),
                'in_stock':    product.is_in_stock(),
                'quantity':    product.quantity_available,
            }
        })
    except Product.DoesNotExist:
        pass

    # Step 2 — UPCitemdb API lookupB

    api_url = settings.UPCITEMDB_API_URL
    timeout = settings.UPCITEMDB_TIMEOUT

    try:
        response = requests.get(
            f'{api_url}?upc={upc}',
            headers={'Accept': 'application/json'},
            timeout=5
        )
        data = response.json()

        if data.get('code') == 'OK' and data.get('items'):
            item = data['items'][0]
            price = ''
            offers = item.get('offers', [])
            if offers:
                prices = [
                    float(o['price']) for o in offers
                    if o.get('price') and float(o['price']) > 0
                ]
                if prices:
                    price = str(round(min(prices), 2))
            images = item.get('images', [])
            return JsonResponse({
                'source':        'upcitemdb',
                'found_locally': False,
                'product': {
                    'title':       item.get('title', ''),
                    'brand':       item.get('brand', ''),
                    'description': item.get('description', ''),
                    'price':       price,
                    'upc_code':    upc,
                    'image_url':   images[0] if images else '',
                    'model':       item.get('model', ''),
                }
            })
        else:
            return JsonResponse({
                'source':        'upcitemdb',
                'found_locally': False,
                'product':       None,
                'message':       f'UPC {upc} not found in registry. Enter details manually.'
            })

    except requests.exceptions.Timeout:
        return JsonResponse({
            'error': 'External UPC lookup timed out. Enter product details manually.'
        }, status=504)
    except Exception as e:
        return JsonResponse({'error': f'UPC lookup failed: {str(e)}'}, status=500)


def barcode_scanner_page(request):
    """Standalone barcode scanner page for customers."""
    return render(request, 'store/barcode-scanner.html')


def upc_product_search(request):
    """
    AJAX endpoint: find a product by exact UPC match.
    Used by the storefront scanner to redirect to the product page.
    """
    upc = request.GET.get('upc', '').strip()
    if not upc:
        return JsonResponse({'found': False, 'message': 'No UPC provided.'})
    try:
        product = Product.objects.get(upc_code=upc)
        return JsonResponse({
            'found':    True,
            'url':      product.get_absolute_url(),
            'title':    product.title,
            'brand':    product.brand,
            'price':    str(product.price),
            'in_stock': product.is_in_stock(),
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'found':   False,
            'message': f'No product found for UPC: {upc}'
        })