from django.shortcuts import render
from .cart import Cart
from store.models import Product
from django.shortcuts import get_object_or_404
from django.http import JsonResponse


def cart_summary(request):
    cart = Cart(request)
    return render(request, 'cart/cart-summary.html', {'cart':cart})


def cart_add(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        product = get_object_or_404(Product, id=product_id)
        
        # Check if enough stock is available
        if not product.can_fulfill_order(product_quantity):
            response = JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available in stock.',
                'qty': cart.__len__()
            })
            return response
        
        # Check if product is in stock at all
        if not product.is_in_stock():
            response = JsonResponse({
                'error': True,
                'message': 'This product is currently out of stock.',
                'qty': cart.__len__()
            })
            return response
        
        cart.add(product=product, product_qty=product_quantity)
        cart_quantity = cart.__len__()
        response = JsonResponse({
            'error': False,
            'message': 'Product added to cart successfully!',
            'qty': cart_quantity
        })
        return response

        
def cart_delete(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        cart.delete(product=product_id)
        cart_quantity = cart.__len__()
        cart_total = cart.get_total()
        response = JsonResponse({'qty':cart_quantity, 'total':cart_total})
        return response


def cart_update(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        product_quantity = int(request.POST.get('product_quantity'))
        
        # Validate stock availability
        product = get_object_or_404(Product, id=product_id)
        if not product.can_fulfill_order(product_quantity):
            response = JsonResponse({
                'error': True,
                'message': f'Sorry, only {product.quantity_available} unit(s) available in stock.',
                'qty': cart.__len__(),
                'total': cart.get_total()
            })
            return response
        
        cart.update(product=product_id, qty=product_quantity)
        cart_quantity = cart.__len__()
        cart_total = cart.get_total()
        response = JsonResponse({
            'error': False,
            'qty': cart_quantity,
            'total': cart_total
        })
        return response