from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from . models import ShippingAddress, Order, OrderItem, RefundRequest, RefundItem
from cart.cart import Cart
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from store.models import Product
from decimal import Decimal
from account.models import award_points_for_order, RewardAccount, RewardTransaction
from django.contrib import messages

def checkout(request):
    # Checkout view with rewards integration
    cart = Cart(request)
    cart_total = cart.get_total()
    context = {
        'cart': cart,
        'cart_total': cart_total,
    }
    
    # Add reward account for authenticated users
    if request.user.is_authenticated:
        try:
            reward_account = RewardAccount.objects.get(user=request.user)
        except RewardAccount.DoesNotExist:
            reward_account = RewardAccount.objects.create(
                user=request.user,
                total_points=Decimal('0.00'),
                lifetime_points=Decimal('0.00')
            )
        context['reward_account'] = reward_account
    return render(request, 'payment/checkout.html', context)


def complete_order(request):
    if request.POST.get('action') == 'post':
        name = request.POST.get('name')
        email = request.POST.get('email')
        address1 = request.POST.get('address1')
        address2 = request.POST.get('address2')
        city = request.POST.get('city')
        state = request.POST.get('state')
        zipcode = request.POST.get('zipcode')

        # Get rewards redemption amount sent from checkout.html JS
        rewards_to_apply = Decimal(request.POST.get('rewards_applied', '0'))

        # All-in-one shipping address
        shipping_address = (address1 + "\n" + address2 + "\n" +
        city + "\n" + state + "\n" + zipcode)

        # BUG FIX 1: cart and original_total were commented out — restored here.
        # Without these, every variable below (original_total, cart iteration,
        # total_cost, etc.) would throw a NameError and crash the entire view.
        cart = Cart(request)
        original_total = cart.get_total()

        # Calculate final total after rewards redemption
        rewards_redeemed = Decimal('0.00')

        if request.user.is_authenticated and rewards_to_apply > 0:
            try:
                reward_account = RewardAccount.objects.get(user=request.user)

                # Validate: cannot redeem more than available balance
                if rewards_to_apply > reward_account.total_points:
                    return JsonResponse({
                        'success': False,
                        'error': f'You only have ${reward_account.total_points} in rewards available.'
                    })

                # Validate: cannot redeem more than order total
                if rewards_to_apply > original_total:
                    return JsonResponse({
                        'success': False,
                        'error': f'Rewards cannot exceed order total of ${original_total}.'
                    })

                rewards_redeemed = rewards_to_apply

            except RewardAccount.DoesNotExist:
                rewards_redeemed = Decimal('0.00')

        # Calculate final charge after applying rewards
        total_cost = original_total - rewards_redeemed

        # Ensure total doesn't go negative
        if total_cost < Decimal('0.00'):
            total_cost = Decimal('0.00')

        # Initialize product list and stock validation
        product_list = []
        insufficient_stock = []

        # STEP 1: Validate stock for ALL items before processing anything
        for item in cart:
            product = item['product']
            quantity = item['qty']

            if not product.can_fulfill_order(quantity):
                insufficient_stock.append({
                    'product': product.title,
                    'requested': quantity,
                    'available': product.quantity_available
                })

        if insufficient_stock:
            error_message = "Unable to complete order. Insufficient stock for: "
            error_details = ", ".join([
                f"{item['product']} (requested: {item['requested']}, available: {item['available']})"
                for item in insufficient_stock
            ])
            return JsonResponse({
                'success': False,
                'error': error_message + error_details
            })

        # STEP 2: Create order and order items
        rewards_earned = 0

        if request.user.is_authenticated:
            order = Order.objects.create(
                full_name=name,
                email=email,
                shipping_address=shipping_address,
                amount_paid=total_cost,
                user=request.user
            )
            order_id = order.pk

            for item in cart:
                product = item['product']
                quantity = item['qty']
                price = item['price']

                OrderItem.objects.create(
                    order_id=order_id,
                    product=product,
                    quantity=quantity,
                    price=price,
                    user=request.user
                )

                total_item_price = Decimal(str(price)) * quantity
                product.process_sale(quantity, total_item_price)
                product_list.append(product.title)

            # STEP 3: Process rewards
            try:
                # Deduct redeemed rewards from account balance
                if rewards_redeemed > 0:
                    reward_account = RewardAccount.objects.get(user=request.user)
                    reward_account.total_points -= rewards_redeemed
                    reward_account.save()

                    RewardTransaction.objects.create(
                        user=request.user,
                        order=order,
                        order_total=original_total,
                        points_earned=-rewards_redeemed,  # Negative = deduction
                        transaction_type='REDEEMED',
                        description=f'Rewards redeemed on order #{order.id}'
                    )
                    print(f"✓ Rewards redeemed: ${rewards_redeemed} from {request.user.username}")

                # Award new rewards based on final amount paid
                if total_cost > 0:
                    reward_transaction = award_points_for_order(
                        user=request.user,
                        order=order,
                        order_total=total_cost
                    )
                    print(f"✓ New rewards awarded: ${reward_transaction.points_earned} to {request.user.username}")
                    rewards_earned = float(reward_transaction.points_earned)
                else:
                    # Order fully covered by rewards — no new points awarded
                    rewards_earned = 0

            except Exception as e:
                print(f"✗ Error processing rewards: {e}")
                rewards_earned = 0

        else:
            # Guest user — no rewards, full price charged
            order = Order.objects.create(
                full_name=name,
                email=email,
                shipping_address=shipping_address,
                amount_paid=original_total
            )
            order_id = order.pk

            for item in cart:
                product = item['product']
                quantity = item['qty']
                price = item['price']

                OrderItem.objects.create(
                    order_id=order_id,
                    product=product,
                    quantity=quantity,
                    price=price
                )

                total_item_price = Decimal(str(price)) * quantity
                product.process_sale(quantity, total_item_price)
                product_list.append(product.title)

            rewards_earned = 0
            rewards_redeemed = Decimal('0.00')

        # Send confirmation email
        try:
            email_body = (
                'Hi! \n\n'
                'Thank you for placing your order\n\n'
                'Please see your order below: \n\n' +
                str(product_list) + '\n\n'
            )

            if rewards_redeemed > 0:
                email_body += (
                    f'Original Total: ${original_total}\n'
                    f'Rewards Applied: -${rewards_redeemed}\n'
                    f'Final Total Paid: ${total_cost}\n\n'
                )
            else:
                email_body += f'Total paid: ${total_cost}\n\n'

            if request.user.is_authenticated and rewards_earned > 0:
                email_body += (
                    f'\n🎁 REWARDS EARNED: ${rewards_earned:.2f}\n'
                    'Check your dashboard to see your rewards balance!'
                )

            send_mail(
                'Order received',
                email_body,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
            )
        except Exception as e:
            print(f"Email sending failed: {e}")

        # Build response
        response_data = {
            'success': True,
            'order_id': order_id,
            'original_total': float(original_total),
            'final_total': float(total_cost)
        }

        if rewards_redeemed > 0:
            response_data['rewards_redeemed'] = float(rewards_redeemed)
            response_data['savings_message'] = f'You saved ${rewards_redeemed:.2f} with rewards!'

        if request.user.is_authenticated and rewards_earned > 0:
            response_data['rewards_earned'] = rewards_earned
            response_data['rewards_message'] = f'You earned ${rewards_earned:.2f} in new rewards!'

        return JsonResponse(response_data)


def payment_success(request):
    # BUG FIX 2: Cart session deletion logic was inverted.
    # Original code deleted 'session_key' when it matched,
    # keeping everything else — the opposite of intended behavior.
    # Corrected to match the same safe pattern used in account/views.py user_logout.
    for key in list(request.session.keys()):
        if key == 'session_key':
            del request.session[key]

    # BUG FIX 3: payment_success was calling award_points_for_order() again
    # with missing required arguments (order, order_total were commented out).
    # This caused a crash AND would have double-awarded rewards since
    # complete_order already awards them correctly. Removed entirely.

    return render(request, 'payment/payment-success.html')


def paypal_client_id(request):
    """
    Context processor to make PayPal client-id available in all templates
    """
    return {
        'paypal_client_id': settings.PAYPAL_CLIENT_ID
    }


def payment_failed(request):
    return render(request, 'payment/payment-failed.html')


# Refund Views

def refund_landing(request):
    return render(request, 'payment/refund-landing.html')


@login_required(login_url='my-login')
def request_refund(request, order_id):
    """
    Allow registered customer to request a refund for an order
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Check if active refund already exists
    existing_refund = RefundRequest.objects.filter(
        order=order,
        status__in=['PENDING_RETURN', 'PRODUCT_RECEIVED', 'PROCESSING_REFUND']
    ).first()

    if existing_refund:
        messages.warning(request, 'A refund request already exists for this order.')
        return redirect('refund-status', refund_id=existing_refund.id)

    order_items = OrderItem.objects.filter(order=order)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        reason_details = request.POST.get('reason_details', '')
        tracking_number = request.POST.get('tracking_number', '')

        if not reason:
            messages.error(request, 'Please select a reason for the refund.')
            return redirect('request-refund', order_id=order_id)

        refund_amount = order.amount_paid

        # Check if rewards were redeemed on this order
        rewards_used = Decimal('0.00')
        try:
            redemption = RewardTransaction.objects.get(
                user=request.user,
                order=order,
                transaction_type='REDEEMED'
            )
            rewards_used = abs(redemption.points_earned)
        except RewardTransaction.DoesNotExist:
            pass

        refund_request = RefundRequest.objects.create(
            order=order,
            user=request.user,
            customer_email=request.user.email,
            customer_name=request.user.username,
            status='PENDING_RETURN',
            reason=reason,
            reason_details=reason_details,
            refund_amount=refund_amount,
            rewards_used=rewards_used,
            tracking_number=tracking_number
        )

        for order_item in order_items:
            RefundItem.objects.create(
                refund_request=refund_request,
                order_item=order_item,
                quantity_to_refund=order_item.quantity,
                refund_amount=order_item.price * order_item.quantity
            )

        messages.success(
            request,
            f'Refund request #{refund_request.id} submitted successfully! Please ship the product(s) back to us.'
        )
        return redirect('refund-status', refund_id=refund_request.id)

    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'payment/request-refund.html', context)


@login_required(login_url='my-login')
def refund_status(request, refund_id):
    """
    Display refund request status to registered customer
    """
    refund = get_object_or_404(RefundRequest, id=refund_id, user=request.user)
    can_cancel = refund.can_cancel()

    if request.method == 'POST' and 'cancel_refund' in request.POST:
        if can_cancel:
            refund.status = 'CANCELLED'
            refund.save()
            messages.success(request, 'Refund request cancelled.')
            return redirect('track-orders')
        else:
            messages.error(request, 'This refund request cannot be cancelled at this stage.')

    refund_items = refund.items.all()

    context = {
        'refund': refund,
        'refund_items': refund_items,
        'can_cancel': can_cancel,
    }
    return render(request, 'payment/refund-status.html', context)


def guest_refund_request(request):
    """
    Allow guest users to request refunds
    """
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        email = request.POST.get('email')
        reason = request.POST.get('reason')
        reason_details = request.POST.get('reason_details', '')
        tracking_number = request.POST.get('tracking_number', '')

        if not order_id or not email or not reason:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('guest-refund-request')

        try:
            order = Order.objects.get(id=order_id, email=email, user__isnull=True)

            existing_refund = RefundRequest.objects.filter(
                order=order,
                status__in=['PENDING_RETURN', 'PRODUCT_RECEIVED', 'PROCESSING_REFUND']
            ).first()

            if existing_refund:
                messages.warning(
                    request,
                    f'A refund request already exists for this order. Your Refund Request ID is #{existing_refund.id}'
                )
                return redirect('guest-refund-status', refund_id=existing_refund.id)

            refund_request = RefundRequest.objects.create(
                order=order,
                user=None,
                customer_email=email,
                customer_name=order.full_name,
                status='PENDING_RETURN',
                reason=reason,
                reason_details=reason_details,
                refund_amount=order.amount_paid,
                rewards_used=Decimal('0.00'),
                tracking_number=tracking_number
            )

            order_items = OrderItem.objects.filter(order=order)
            for order_item in order_items:
                RefundItem.objects.create(
                    refund_request=refund_request,
                    order_item=order_item,
                    quantity_to_refund=order_item.quantity,
                    refund_amount=order_item.price * order_item.quantity
                )

            messages.success(
                request,
                f'Refund request submitted successfully! Your Refund Request ID is #{refund_request.id}. Please save this number!'
            )
            return redirect('guest-refund-status', refund_id=refund_request.id)

        except Order.DoesNotExist:
            messages.error(request, 'Order not found. Please check your Order ID and email address.')
            return redirect('guest-refund-request')

    return render(request, 'payment/guest-refund-request.html')


def guest_refund_status(request, refund_id):
    """
    Display refund status for guest users
    """
    refund = get_object_or_404(RefundRequest, id=refund_id, user__isnull=True)
    refund_items = refund.items.all()

    context = {
        'refund': refund,
        'refund_items': refund_items,
    }
    return render(request, 'payment/guest-refund-status.html', context)