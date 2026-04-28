from django.db import models
from django.contrib.auth.models import User
from payment.models import Order
from decimal import Decimal


class RewardAccount(models.Model):
    """
    Stores the total rewards points for each user
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reward_account')
    total_points = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    lifetime_points = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Total points ever earned
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - ${self.total_points}"

    class Meta:
        verbose_name = 'Reward Account'
        verbose_name_plural = 'Reward Accounts'


class RewardTransaction(models.Model):
    """
    Records each rewards transaction tied to an order
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reward_transactions')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='reward_transaction', null=True, blank=True)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    points_earned = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=[
        ('PURCHASE', 'Purchase Reward'),
        ('REDEEMED', 'Points Redeemed'),
        ('ADJUSTMENT', 'Manual Adjustment'),
    ], default='PURCHASE')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Order #{self.order.id if self.order else 'N/A'} - ${self.points_earned}"

    class Meta:
        verbose_name = 'Reward Transaction'
        verbose_name_plural = 'Reward Transactions'
        ordering = ['-created_at']


def calculate_reward_points(order_total):
    """
    Calculate reward points based on order total
    
    Reward Structure:
    $0 - $10: $1.00 reward
    $11 - $20: $2.00 reward
    $21 - $30: $3.00 reward
    $31 - $40: $4.00 reward
    $41 - $100: $5.00 reward
    $101 - $200: $10.00 reward
    $201+: $10.00 + $5.00 for each additional $100 bracket
    
    Args:
        order_total (Decimal or float): The total order amount
        
    Returns:
        Decimal: The reward points to be awarded
    """
    total = Decimal(str(order_total))
    
    if total <= 0:
        return Decimal('0.00')
    elif total <= Decimal('10.00'):
        return Decimal('1.00')
    elif total <= Decimal('20.00'):
        return Decimal('2.00')
    elif total <= Decimal('30.00'):
        return Decimal('3.00')
    elif total <= Decimal('40.00'):
        return Decimal('4.00')
    elif total <= Decimal('100.00'):
        return Decimal('5.00')
    elif total <= Decimal('200.00'):
        return Decimal('10.00')
    else:
        # For amounts $201+
        # Base reward for $101-$200
        base_reward = Decimal('10.00')
        
        # Calculate additional $100 brackets beyond $200
        amount_over_200 = total - Decimal('200.00')
        additional_brackets = int(amount_over_200 / Decimal('100.00'))
        
        # Add $5.00 for each additional $100 bracket
        additional_reward = Decimal(str(additional_brackets)) * Decimal('5.00')
        
        # If there's a partial bracket (e.g., $250 has $50 extra), add $5 for that too
        if amount_over_200 % Decimal('100.00') > Decimal('0.00'):
            additional_reward += Decimal('5.00')
        
        return base_reward + additional_reward


def award_points_for_order(user, order, order_total):
    """
    Award reward points to a user for a successful order
    
    Args:
        user: User object
        order: Order object
        order_total: Decimal or float representing the order total
        
    Returns:
        RewardTransaction: The created transaction object
    """
    # Calculate points
    points = calculate_reward_points(order_total)
    
    # Get or create reward account
    reward_account, created = RewardAccount.objects.get_or_create(user=user)
    
    # Update account totals
    reward_account.total_points += points
    reward_account.lifetime_points += points
    reward_account.save()
    
    # Create transaction record
    transaction = RewardTransaction.objects.create(
        user=user,
        order=order,
        order_total=Decimal(str(order_total)),
        points_earned=points,
        transaction_type='PURCHASE',
        description=f'Reward points earned from order #{order.id if order else "N/A"}'
    )
    
    return transaction
