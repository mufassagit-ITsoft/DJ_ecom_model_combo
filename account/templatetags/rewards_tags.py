"""
Custom Template Tags for Rewards System

"""

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get item from dictionary by key
    Usage: {{ my_dict|get_item:my_key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def multiply(value, arg):
    """
    Multiply the value by the argument
    Usage: {{ value|multiply:2 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def currency(value):
    """
    Format a number as currency
    Usage: {{ value|currency }}
    """
    try:
        return f"${float(value):.2f}"
    except (ValueError, TypeError):
        return "$0.00"


@register.simple_tag
def calculate_total_rewards(transactions):
    """
    Calculate total rewards from a queryset of transactions
    Usage: {% calculate_total_rewards user.reward_transactions.all %}
    """
    from decimal import Decimal
    total = Decimal('0.00')
    for transaction in transactions:
        if transaction.transaction_type == 'PURCHASE':
            total += transaction.points_earned
    return total