from django.db import models
from django.contrib.auth.models import User


class ShippingAddress(models.Model):
    full_name = models.CharField(max_length=300)
    email = models.EmailField(max_length=255)
    address1 = models.CharField(max_length=300)
    address2 = models.CharField(max_length=300, null=True, blank=True)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zipcode = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Shipping Address'

    def __str__(self):
        return 'Shipping Address - ' + str(self.id)


class Order(models.Model):
    full_name = models.CharField(max_length=300)
    email = models.EmailField(max_length=255)
    shipping_address = models.TextField(max_length=10000)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2)
    date_ordered = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # ── GAP 1 FIX: Store the PayPal capture ID at checkout ──────────────
    # This is the ID returned by PayPal's onApprove → actions.order.capture()
    # Required to call PayPal's refund API programmatically from admin.
    # Field is blank/null for orders placed before this fix was deployed.
    paypal_transaction_id = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="PayPal capture/transaction ID — required for programmatic refunds"
    )

    def __str__(self):
        return 'Order - #' + str(self.id)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey('store.Product', on_delete=models.CASCADE, null=True)
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return 'Order Item - #' + str(self.id)

class RefundRequest(models.Model):
    """
    Tracks refund requests for orders.

    Workflow:
    1. PENDING_RETURN    — Customer requested refund, waiting for product return
    2. PRODUCT_RECEIVED  — Admin confirmed product received, inventory restocked
    3. PROCESSING_REFUND — Admin triggered PayPal refund via admin action
    4. COMPLETED         — PayPal refund confirmed, customer notified by email
    5. REJECTED          — Refund rejected by admin
    6. CANCELLED         — Customer cancelled the request
    """

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

    # Related order
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refund_requests')

    # Customer info
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=300)

    # Refund details
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_RETURN')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_details = models.TextField(blank=True)

    # Refund amount
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Amount to refund via PayPal (what customer actually paid in cash)"
    )
    rewards_used = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Rewards used in original purchase"
    )

    # Tracking
    tracking_number = models.CharField(max_length=200, blank=True)

    # Admin verification gate
    admin_verified = models.BooleanField(
        default=False,
        help_text=(
            "Must be set before PayPal refund or completion actions can run. "
            "Use 'Verify & approve refund requests' action."
        )
    )
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_refunds'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Admin notes
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # PayPal refund transaction ID (filled after refund is issued)
    paypal_refund_id = models.CharField(max_length=200, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    product_received_at = models.DateTimeField(null=True, blank=True)
    refund_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Refund Request'
        verbose_name_plural = 'Refund Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund #{self.id} - Order #{self.order.id} - {self.status}"

    def can_cancel(self):
        return self.status in ['PENDING_RETURN']

    def can_process_refund(self):
        return self.status == 'PRODUCT_RECEIVED'

    def get_status_color(self):
        colors = {
            'PENDING_RETURN':    'warning',
            'PRODUCT_RECEIVED':  'info',
            'PROCESSING_REFUND': 'primary',
            'COMPLETED':         'success',
            'REJECTED':          'danger',
            'CANCELLED':         'secondary',
        }
        return colors.get(self.status, 'secondary')


class RefundItem(models.Model):
    refund_request = models.ForeignKey(RefundRequest, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity_to_refund = models.PositiveIntegerField()
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    condition_acceptable = models.BooleanField(default=False)
    condition_notes = models.TextField(blank=True)
    restocked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Refund Item'
        verbose_name_plural = 'Refund Items'

    def __str__(self):
        return f"Refund Item - {self.order_item.product.title} x{self.quantity_to_refund}"

def send_refund_status_email(refund, subject, body):
    """
    Central email sender for all refund status notifications.
    Called at each stage transition so the customer always knows what's happening.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[refund.customer_email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"✗ Refund email failed for refund #{refund.id}: {e}")


def process_rewards_refund(refund_request):
    """
    Deduct rewards that were earned from the original purchase.
    Does NOT restore used rewards — that requires admin goodwill action.

    BUG FIX: transaction_type was 'ADMIN_ADJUSTMENT' which is not a valid
    choice. Corrected to 'ADJUSTMENT' which is defined in RewardTransaction.
    """
    from account.models import RewardAccount, RewardTransaction
    from decimal import Decimal

    if not refund_request.user:
        return

    try:
        reward_account = RewardAccount.objects.get(user=refund_request.user)

        try:
            earned_transaction = RewardTransaction.objects.get(
                user=refund_request.user,
                order=refund_request.order,
                transaction_type='PURCHASE'
            )

            reward_account.total_points -= earned_transaction.points_earned
            reward_account.save()

            RewardTransaction.objects.create(
                user=refund_request.user,
                order=refund_request.order,
                order_total=refund_request.order.amount_paid,
                points_earned=-earned_transaction.points_earned,
                transaction_type='ADMIN_ADJUSTMENT',
                description=f'Rewards deducted due to refund of order #{refund_request.order.id}'
            )

        except RewardTransaction.DoesNotExist:
            pass

    except RewardAccount.DoesNotExist:
        pass


def restock_refunded_items(refund_request):
    """
    Add refunded items back to inventory when condition is acceptable.
    """
    for refund_item in refund_request.items.all():
        if refund_item.condition_acceptable and not refund_item.restocked:
            product = refund_item.order_item.product

            product.quantity += refund_item.quantity_to_refund
            product.save()

            refund_item.restocked = True
            refund_item.save()


def restore_used_rewards(refund_request):
    """
    Admin-only goodwill action: restore rewards used in the original purchase.
    Only for defective products, company errors, or special goodwill cases.
    """
    from account.models import RewardAccount, RewardTransaction

    if not refund_request.user or refund_request.rewards_used <= 0:
        return False

    try:
        reward_account = RewardAccount.objects.get(user=refund_request.user)

        existing = RewardTransaction.objects.filter(
            user=refund_request.user,
            order=refund_request.order,
            transaction_type='ADJUSTMENT',
            description__icontains='Rewards restored by admin'
        ).exists()

        if existing:
            return False

        reward_account.total_points += refund_request.rewards_used
        reward_account.save()

        RewardTransaction.objects.create(
            user=refund_request.user,
            order=refund_request.order,
            order_total=refund_request.order.amount_paid,
            points_earned=refund_request.rewards_used,
            transaction_type='ADJUSTMENT',
            description=f'Rewards restored by admin as goodwill gesture for refund #{refund_request.id}'
        )

        return True

    except RewardAccount.DoesNotExist:
        return False


def issue_paypal_refund(refund_request):
    """
    Call PayPal REST API to issue a refund programmatically.

    Requires:
    - PAYPAL_CLIENT_ID and PAYPAL_SECRET in settings/env vars
    - order.paypal_transaction_id was saved at checkout (complete_order view)

    Returns: (success: bool, paypal_refund_id: str, error_message: str)
    """
    import requests
    from django.conf import settings

    client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
    secret = getattr(settings, 'PAYPAL_SECRET', '')

    if not client_id or not secret:
        return False, '', 'PAYPAL_SECRET not configured in environment variables.'

    transaction_id = refund_request.order.paypal_transaction_id
    if not transaction_id:
        return False, '', (
            f'No PayPal transaction ID on Order #{refund_request.order.id}. '
            'This order was placed before transaction IDs were stored. '
            'Process this refund manually in your PayPal dashboard.'
        )

    # Step 1 — Get access token
    try:
        token_response = requests.post(
            'https://api-m.paypal.com/v1/oauth2/token',
            auth=(client_id, secret),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        token_data = token_response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            return False, '', f'PayPal auth failed: {token_data.get("error_description", "Unknown error")}'

    except Exception as e:
        return False, '', f'PayPal auth request failed: {e}'

    # Step 2 — Issue refund against the capture ID
    try:
        refund_response = requests.post(
            f'https://api-m.paypal.com/v2/payments/captures/{transaction_id}/refund',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
            },
            json={
                'amount': {
                    'value': str(refund_request.refund_amount),
                    'currency_code': 'USD'
                },
                'note_to_payer': f'Refund for Order #{refund_request.order.id} - Refund Request #{refund_request.id}'
            },
            timeout=15
        )

        refund_data = refund_response.json()

        if refund_response.status_code in [200, 201]:
            paypal_refund_id = refund_data.get('id', '')
            return True, paypal_refund_id, ''
        else:
            error_msg = refund_data.get('message', refund_data.get('error_description', 'Unknown PayPal error'))
            return False, '', f'PayPal refund failed: {error_msg}'

    except Exception as e:
        return False, '', f'PayPal refund request failed: {e}'