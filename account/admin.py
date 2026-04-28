from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from .models import RewardAccount, RewardTransaction


@admin.register(RewardAccount)
class RewardAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_points_display', 'lifetime_points_display', 'transaction_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'lifetime_points']
    
    def total_points_display(self, obj):
        return format_html('<strong>${}</strong>', '{:.2f}'.format(float(obj.total_points)))
    total_points_display.short_description = 'Total Points'
    
    def lifetime_points_display(self, obj):
        return format_html('${}', '{:.2f}'.format(float(obj.lifetime_points)))
    lifetime_points_display.short_description = 'Lifetime Points'
    
    def transaction_count(self, obj):
        count = obj.user.reward_transactions.count()
        return format_html('<span style="color: blue;">{} transactions</span>', count)
    transaction_count.short_description = 'Transactions'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Points Summary', {
            'fields': ('total_points', 'lifetime_points')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RewardTransaction)
class RewardTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'order_link', 'order_total_display', 'points_earned_display', 'transaction_type', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__username', 'user__email', 'order__id', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def order_link(self, obj):
        if obj.order:
            return format_html('<a href="/admin/payment/order/{}/change/">Order #{}</a>', obj.order.id, obj.order.id)
        return '-'
    order_link.short_description = 'Order'
    
    def order_total_display(self, obj):
        return format_html('${}', '{:.2f}'.format(float(obj.order_total)))
    order_total_display.short_description = 'Order Total'
    order_total_display.admin_order_field = 'order_total'
    
    def points_earned_display(self, obj):
        color = 'green' if obj.transaction_type == 'PURCHASE' else 'red'
        formatted_amount = '{:.2f}'.format(float(obj.points_earned))
        return format_html('<strong style="color: {};">${}</strong>', color, formatted_amount)
    points_earned_display.short_description = 'Points Earned'
    points_earned_display.admin_order_field = 'points_earned'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'order', 'transaction_type')
        }),
        ('Financial Information', {
            'fields': ('order_total', 'points_earned')
        }),
        ('Additional Information', {
            'fields': ('description', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'order')


# Create a custom admin action to recalculate points
def recalculate_user_points(modeladmin, request, queryset):
    """Recalculate total points for selected users based on their transactions"""
    for account in queryset:
        total = account.user.reward_transactions.filter(
            transaction_type='PURCHASE'
        ).aggregate(Sum('points_earned'))['points_earned__sum'] or 0
        
        account.total_points = total
        account.save()
    
    modeladmin.message_user(request, f'Successfully recalculated points for {queryset.count()} accounts.')

recalculate_user_points.short_description = 'Recalculate total points'
RewardAccountAdmin.actions = [recalculate_user_points]

