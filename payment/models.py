from django.db import models
from django.contrib.auth.models import User

class ShippingAddress(models.Model):
    full_name = models.CharField(max_length=300)
    email = models.EmailField(max_length=255)
    address1 = models.CharField(max_length=300)
    # Address 2 is optional and the rest are required
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

# Refund Models
class RefundRequest(models.Model):
    """
    Tracks refund requests for orders
    
    Process:
    1. PENDING_RETURN - Customer requested refund, waiting for product return
    2. PRODUCT_RECEIVED - Admin confirmed product received
    3. PROCESSING_REFUND - Admin is processing PayPal refund
    4. COMPLETED - Refund completed
    5. REJECTED - Refund rejected by admin
    6. CANCELLED - Customer cancelled the request
    """
    
    STATUS_CHOICES = [
        ('PENDING_RETURN', 'Pending Product Return'),
        ('PRODUCT_RECEIVED', 'Product Received - Processing Refund'),
        ('PROCESSING_REFUND', 'Processing PayPal Refund'),
        ('COMPLETED', 'Refund Completed'),
        ('REJECTED', 'Refund Rejected'),
        ('CANCELLED', 'Cancelled by Customer'),
    ]
    
    REASON_CHOICES = [
        ('DEFECTIVE', 'Product is defective'),
        ('WRONG_ITEM', 'Wrong item received'),
        ('NOT_AS_DESCRIBED', 'Not as described'),
        ('CHANGED_MIND', 'Changed my mind'),
        ('OTHER', 'Other reason'),
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
    reason_details = models.TextField(blank=True, help_text="Additional details about the refund reason")
    
    # Refund amount
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount to refund via PayPal (order.amount_paid - what customer actually paid in cash)")
    rewards_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Rewards used in original purchase. NOT automatically restored - admin must manually approve via 'Restore rewards as goodwill' action")
    
    # Tracking
    tracking_number = models.CharField(max_length=200, blank=True, help_text="Customer's return tracking number")
    
    # Admin verification — must be set before any payment processing action can proceed
    admin_verified = models.BooleanField(
        default=False,
        help_text=(
            "Administrator has reviewed and verified this refund request. "
            "REQUIRED before 'Mark as processing PayPal refund' or 'Complete refund' actions can run. "
            "Use the 'Verify & approve refund requests' action to set this flag."
        )
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_refunds',
        help_text="Admin user who verified this refund request"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the refund was verified by an admin"
    )

    # Admin notes
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admin")
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if applicable")
    
    # PayPal transaction
    paypal_refund_id = models.CharField(max_length=200, blank=True, help_text="PayPal refund transaction ID")
    
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
        """Check if customer can cancel this refund request"""
        return self.status in ['PENDING_RETURN']
    
    def can_process_refund(self):
        """Check if admin can process PayPal refund"""
        return self.status == 'PRODUCT_RECEIVED'
    
    def get_status_color(self):
        """Return Bootstrap color class for status"""
        colors = {
            'PENDING_RETURN': 'warning',
            'PRODUCT_RECEIVED': 'info',
            'PROCESSING_REFUND': 'primary',
            'COMPLETED': 'success',
            'REJECTED': 'danger',
            'CANCELLED': 'secondary',
        }
        return colors.get(self.status, 'secondary')

class RefundItem(models.Model):
    """
    Individual items being refunded within a refund request
    """
    refund_request = models.ForeignKey(RefundRequest, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    
    quantity_to_refund = models.PositiveIntegerField(help_text="Number of items being returned")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Refund amount for this item")
    
    # Product condition on return
    condition_acceptable = models.BooleanField(default=False, help_text="Product in acceptable condition")
    condition_notes = models.TextField(blank=True, help_text="Notes about product condition")
    
    # Restocking
    restocked = models.BooleanField(default=False, help_text="Product added back to inventory")
    
    class Meta:
        verbose_name = 'Refund Item'
        verbose_name_plural = 'Refund Items'
    
    def __str__(self):
        return f"Refund Item - {self.order_item.product.title} x{self.quantity_to_refund}"

# Helper functions below
def process_rewards_refund(refund_request):
    """
    Adjust rewards when processing a refund for registered users
    
    IMPORTANT: This function ONLY deducts earned rewards, it does NOT restore used rewards.
    Used rewards are only restored if an admin manually approves it via admin action.
    
    Actions:
    1. Deduct rewards points that were earned from the purchase
    
    Note: Rewards used during purchase are NOT automatically restored because:
    - Customer is already getting cash refund for amount_paid
    - Restoring rewards would give double value
    - Admin can manually restore rewards as goodwill gesture if approved
    """
    from account.models import RewardAccount, RewardTransaction
    from decimal import Decimal
    
    # Only process if user is registered
    if not refund_request.user:
        return
    
    try:
        reward_account = RewardAccount.objects.get(user=refund_request.user)
        
        # ONLY ACTION: Deduct rewards that were earned from this purchase
        try:
            earned_transaction = RewardTransaction.objects.get(
                user=refund_request.user,
                order=refund_request.order,
                transaction_type='PURCHASE'
            )
            
            # Deduct the earned points
            reward_account.total_points -= earned_transaction.points_earned
            reward_account.save()
            
            # Create deduction transaction record
            RewardTransaction.objects.create(
                user=refund_request.user,
                order=refund_request.order,
                order_total=refund_request.order.amount_paid,
                points_earned=-earned_transaction.points_earned,  # Negative - removing points
                transaction_type='ADJUSTMENT',
                description=f'Rewards deducted due to refund of order #{refund_request.order.id}'
            )
            
        except RewardTransaction.DoesNotExist:
            # No rewards were earned from this order
            pass
            
    except RewardAccount.DoesNotExist:
        # User doesn't have a reward account
        pass


def restock_refunded_items(refund_request):
    """
    Add refunded items back to inventory
    """
    for refund_item in refund_request.items.all():
        if refund_item.condition_acceptable and not refund_item.restocked:
            # Add quantity back to product
            product = refund_item.order_item.product
            product.quantity += refund_item.quantity_to_refund
            product.save()
            
            # Mark as restocked
            refund_item.restocked = True
            refund_item.save()

def restore_used_rewards(refund_request):
    """
    Manually restore rewards that were used in the original purchase.
    
    This is an ADMIN-ONLY action for goodwill gestures or special cases.
    Should only be used when customer deserves both cash refund AND reward restoration.
    
    Example use cases:
    - Defective product (not customer's fault)
    - Company error (sent wrong item)
    - Goodwill gesture for valued customer
    
    DO NOT use for:
    - Changed mind refunds
    - Buyer's remorse
    - Normal return situations
    """
    from account.models import RewardAccount, RewardTransaction
    from decimal import Decimal
    
    # Only process if user is registered and rewards were used
    if not refund_request.user or refund_request.rewards_used <= 0:
        return False
    
    try:
        reward_account = RewardAccount.objects.get(user=refund_request.user)
        
        # Check if rewards were already restored
        existing_restoration = RewardTransaction.objects.filter(
            user=refund_request.user,
            order=refund_request.order,
            transaction_type='ADMIN_ADJUSTMENT',
            description__icontains='Rewards restored by admin'
        ).exists()
        
        if existing_restoration:
            return False  # Already restored
        
        # Restore the rewards
        reward_account.total_points += refund_request.rewards_used
        reward_account.save()
        
        # Create transaction record
        RewardTransaction.objects.create(
            user=refund_request.user,
            order=refund_request.order,
            order_total=refund_request.order.amount_paid,
            points_earned=refund_request.rewards_used,  # Positive - restoring points
            transaction_type='ADMIN_ADJUSTMENT',
            description=f'Rewards restored by admin as goodwill gesture for refund #{refund_request.id}'
        )
        
        return True
        
    except RewardAccount.DoesNotExist:
        return False
