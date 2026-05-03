from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from .models import ShippingAddress, Order, OrderItem, RefundRequest, RefundItem

admin.site.register(ShippingAddress)
admin.site.register(Order)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_link',
        'customer_name',
        'username',
        'product',
        'quantity',
        'unit_price_display',
        'line_total_display',
        'date_sold',
    ]
    list_filter = ['order__date_ordered', 'product']
    search_fields = [
        'order__id',
        'order__full_name',
        'user__username',
        'product__title',
    ]
    readonly_fields = ['order', 'product', 'quantity', 'price', 'user']
    ordering = ['-order__date_ordered']

    def order_link(self, obj):
        return f'Order #{obj.order.id}'
    order_link.short_description = 'Order'
    order_link.admin_order_field = 'order__id'

    def customer_name(self, obj):
        return obj.order.full_name
    customer_name.short_description = 'Customer Name'
    customer_name.admin_order_field = 'order__full_name'

    def username(self, obj):
        if obj.user:
            return obj.user.username
        return 'Guest'
    username.short_description = 'Username'
    username.admin_order_field = 'user__username'

    def unit_price_display(self, obj):
        return f'${float(obj.price):.2f}'
    unit_price_display.short_description = 'Unit Price'
    unit_price_display.admin_order_field = 'price'

    def line_total_display(self, obj):
        return f'${float(obj.price * obj.quantity):.2f}'
    line_total_display.short_description = 'Line Total'

    def date_sold(self, obj):
        return obj.order.date_ordered
    date_sold.short_description = 'Date Sold'
    date_sold.admin_order_field = 'order__date_ordered'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'product', 'user'
        )

# Refund Admin

class RefundItemInline(admin.TabularInline):
    model = RefundItem
    extra = 0
    readonly_fields = ['order_item', 'quantity_to_refund', 'refund_amount']
    fields = ['order_item', 'quantity_to_refund', 'refund_amount', 
              'condition_acceptable', 'condition_notes', 'restocked']
    
    def has_add_permission(self, request, obj=None):
        return False  # Items are added when refund request is created
    
    class Meta:
        help_text = "Note: Items are automatically marked as 'condition acceptable' when you use the 'Mark product received & restock' action. Uncheck any items that are damaged or not acceptable before processing."


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'order_id_simple',
        'customer_info',
        'customer_type',       # Guest vs Registered
        'refund_amount_simple',
        'status_simple',
        'verification_status', # Admin-verified gate
        'reason',
        'created_at',
    ]
    
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['order__id', 'customer_email', 'customer_name', 'user__username']
    date_hierarchy = 'created_at'
    
    readonly_fields = [
        'order',
        'user',
        'customer_email',
        'customer_name',
        'refund_amount',
        'rewards_used',
        'created_at',
        'updated_at',
        'product_received_at',
        'refund_completed_at',
        'verified_by',
        'verified_at',
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'user', 'customer_name', 'customer_email')
        }),
        ('Refund Details', {
            'fields': ('status', 'reason', 'reason_details', 'refund_amount', 'rewards_used')
        }),
        ('Return Tracking', {
            'fields': ('tracking_number', 'product_received_at')
        }),
        ('PayPal Refund', {
            'fields': ('paypal_refund_id', 'refund_completed_at')
        }),
        ('⚠ Admin Verification (Required Before Processing)', {
            'fields': ('admin_verified', 'verified_by', 'verified_at'),
            'description': (
                'The administrator MUST verify this refund request before any payment processing actions '
                'can proceed. Use the "Verify & approve refund requests" action from the list view, '
                'or check the box below. Applies to both guest and registered-user orders.'
            ),
        }),
        ('Admin Management', {
            'fields': ('admin_notes', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [RefundItemInline]
    
    actions = [
        'verify_refund_requests',   # Must run FIRST before processing actions
        'mark_product_received',
        'manual_restock_items',
        'process_paypal_refund',
        'complete_refund',
        'restore_rewards_goodwill',
        'reject_refund'
    ]
    
    # SIMPLIFIED METHODS - NO FORMAT_HTML AT ALL

    def customer_type(self, obj):
        """Indicate whether this is a guest or registered-user refund"""
        try:
            return "Registered" if obj.user else "Guest"
        except Exception as e:
            return f"Error: {e}"
    customer_type.short_description = 'Customer Type'

    def verification_status(self, obj):
        """Show whether the admin has verified this refund request"""
        try:
            if obj.admin_verified:
                verified_by = f" by {obj.verified_by.username}" if obj.verified_by else ""
                return f"VERIFIED{verified_by}"
            return "NOT VERIFIED"
        except Exception as e:
            return f"Error: {e}"
    verification_status.short_description = 'Admin Verified'
    
    def order_id_simple(self, obj):
        """Simple order ID - plain text, no formatting"""
        try:
            if obj and obj.order and obj.order.id:
                return f"Order #{obj.order.id}"
            return "-"
        except Exception as e:
            return f"Error: {e}"
    order_id_simple.short_description = 'Order'
    
    def customer_info(self, obj):
        """Display customer information"""
        try:
            if obj.user:
                return f"{obj.user.username} ({obj.customer_email})"
            return f"Guest ({obj.customer_email})"
        except Exception as e:
            return f"Error: {e}"
    customer_info.short_description = 'Customer'
    
    def refund_amount_simple(self, obj):
        """Simple refund amount display"""
        try:
            amount = f"${float(obj.refund_amount):.2f}"
            if obj.rewards_used > 0:
                amount += f" (Rewards: ${float(obj.rewards_used):.2f})"
            return amount
        except Exception as e:
            return f"Error: {e}"
    refund_amount_simple.short_description = 'Refund Amount'
    
    def status_simple(self, obj):
        """Simple status display"""
        try:
            return obj.get_status_display()
        except Exception as e:
            return f"Error: {e}"
    status_simple.short_description = 'Status'
    
    # ═══════════════════════════════════════════════════════════════════
    # ADMIN ACTIONS
    # ═══════════════════════════════════════════════════════════════════

    def verify_refund_requests(self, request, queryset):
        """
        Step 0: Admin explicitly verifies and approves refund requests.

        This MUST be done before 'process_paypal_refund' or 'complete_refund'
        can run. Applies to both guest and registered-user orders.

        What to check before verifying:
          - Order ID and customer email match
          - Refund reason is valid and items are listed correctly
          - Guest orders: confirm email matches the original order record
          - Registered orders: confirm the order belongs to the user account
        """
        already_verified = queryset.filter(admin_verified=True)
        to_verify = queryset.filter(admin_verified=False)

        if already_verified.exists():
            self.message_user(
                request,
                f'{already_verified.count()} refund(s) were already verified — skipped.',
                level=messages.WARNING
            )

        updated = 0
        for refund in to_verify.exclude(status__in=['COMPLETED', 'REJECTED', 'CANCELLED']):
            refund.admin_verified = True
            refund.verified_by = request.user
            refund.verified_at = timezone.now()
            refund.save()
            updated += 1

        if updated:
            self.message_user(
                request,
                f'{updated} refund request(s) verified by {request.user.username}. '
                f'You may now proceed with "Mark product received" → "Mark as processing" → "Complete refund".',
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'No eligible refund requests to verify.',
                level=messages.WARNING
            )
    verify_refund_requests.short_description = '✔ Verify & approve refund requests (run FIRST)'

    def mark_product_received(self, request, queryset):
        """Mark selected refunds as product received"""
        from .models import restock_refunded_items
        
        updated = 0
        for refund in queryset.filter(status='PENDING_RETURN'):
            refund.status = 'PRODUCT_RECEIVED'
            refund.product_received_at = timezone.now()
            refund.save()
            
            # Automatically mark all items as acceptable condition (admin can manually change later if needed)
            refund.items.all().update(condition_acceptable=True)
            
            # Restock items if condition acceptable
            try:
                restock_refunded_items(refund)
            except Exception as e:
                self.message_user(
                    request,
                    f'Error restocking items for refund #{refund.id}: {e}',
                    level=messages.ERROR
                )
            
            updated += 1
        
        self.message_user(
            request,
            f'{updated} refund(s) marked as product received and items restocked.',
            level=messages.SUCCESS
        )
    mark_product_received.short_description = '✓ Mark product received & restock'
    
    def manual_restock_items(self, request, queryset):
        """Manually restock items for refunds where products have been received"""
        from .models import restock_refunded_items
        
        restocked_count = 0
        for refund in queryset.filter(status__in=['PRODUCT_RECEIVED', 'PROCESSING_REFUND', 'COMPLETED']):
            try:
                # This will restock any items marked as condition_acceptable that haven't been restocked yet
                restock_refunded_items(refund)
                restocked_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Error restocking items for refund #{refund.id}: {e}',
                    level=messages.ERROR
                )
        
        if restocked_count > 0:
            self.message_user(
                request,
                f'Manually restocked items for {restocked_count} refund(s).',
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'No items were restocked. Items may already be restocked or not marked as acceptable condition.',
                level=messages.WARNING
            )
    manual_restock_items.short_description = '🔄 Manually restock acceptable items'
    
    def process_paypal_refund(self, request, queryset):
        """Process PayPal refund (manual - admin must do this in PayPal)"""

        # ── Verification gate ──────────────────────────────────────────
        unverified = queryset.filter(status='PRODUCT_RECEIVED', admin_verified=False)
        if unverified.exists():
            ids = ', '.join(f'#{r.id}' for r in unverified)
            self.message_user(
                request,
                f'Cannot process: refund(s) {ids} have NOT been admin-verified. '
                f'Run "Verify & approve refund requests" first.',
                level=messages.ERROR
            )
            return
        # ──────────────────────────────────────────────────────────────

        updated = 0
        for refund in queryset.filter(status='PRODUCT_RECEIVED', admin_verified=True):
            refund.status = 'PROCESSING_REFUND'
            refund.save()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} refund(s) marked as processing. Please process refunds in PayPal dashboard and enter transaction IDs.',
            level=messages.WARNING
        )
    process_paypal_refund.short_description = '→ Mark as processing PayPal refund'
    
    def complete_refund(self, request, queryset):
        """Complete the refund process"""
        from .models import process_rewards_refund

        # ── Verification gate ──────────────────────────────────────────
        unverified = queryset.filter(status='PROCESSING_REFUND', admin_verified=False)
        if unverified.exists():
            ids = ', '.join(f'#{r.id}' for r in unverified)
            self.message_user(
                request,
                f'Cannot complete: refund(s) {ids} have NOT been admin-verified. '
                f'Run "Verify & approve refund requests" first.',
                level=messages.ERROR
            )
            return
        # ──────────────────────────────────────────────────────────────

        updated = 0
        for refund in queryset.filter(status='PROCESSING_REFUND', admin_verified=True):
            # Process rewards adjustments for registered users
            # NOTE: This ONLY deducts earned rewards, does NOT restore used rewards
            if refund.user:
                try:
                    process_rewards_refund(refund)
                except Exception as e:
                    self.message_user(
                        request,
                        f'Error processing rewards for refund #{refund.id}: {e}',
                        level=messages.ERROR
                    )
                    continue
            
            refund.status = 'COMPLETED'
            refund.refund_completed_at = timezone.now()
            refund.save()
            updated += 1
        
        self.message_user(
            request,
            f'{updated} refund(s) completed successfully. Earned rewards have been deducted. '
            f'Used rewards were NOT restored (use "Restore rewards as goodwill" if approved).',
            level=messages.SUCCESS
        )
    complete_refund.short_description = '✓ Complete refund & adjust rewards'
    
    def reject_refund(self, request, queryset):
        """Reject selected refund requests"""
        updated = queryset.exclude(status__in=['COMPLETED', 'REJECTED']).update(
            status='REJECTED'
        )
        
        self.message_user(
            request,
            f'{updated} refund(s) rejected. Please add rejection reason in admin notes.',
            level=messages.WARNING
        )
    reject_refund.short_description = '✗ Reject refund request'
    
    def restore_rewards_goodwill(self, request, queryset):
        """
        Manually restore used rewards as a goodwill gesture (ADMIN APPROVAL REQUIRED)
        
        Use this ONLY for special cases:
        - Defective products (not customer's fault)
        - Company errors (wrong item sent)
        - Goodwill gestures for valued customers
        
        DO NOT use for normal returns or changed mind refunds.
        """
        from .models import restore_used_rewards
        
        restored_count = 0
        no_rewards_count = 0
        already_restored_count = 0
        guest_count = 0
        
        for refund in queryset:
            # Check if this is a guest order
            if not refund.user:
                guest_count += 1
                continue
            
            # Check if rewards were used
            if refund.rewards_used <= 0:
                no_rewards_count += 1
                continue
            
            # Try to restore rewards
            success = restore_used_rewards(refund)
            if success:
                restored_count += 1
            else:
                already_restored_count += 1
        
        # Build message
        messages_list = []
        if restored_count > 0:
            messages_list.append(f'{restored_count} customer(s) had ${sum([r.rewards_used for r in queryset if r.user and r.rewards_used > 0]):.2f} in rewards restored')
        if already_restored_count > 0:
            messages_list.append(f'{already_restored_count} already had rewards restored')
        if no_rewards_count > 0:
            messages_list.append(f'{no_rewards_count} had no rewards used in original purchase')
        if guest_count > 0:
            messages_list.append(f'{guest_count} were guest orders (no rewards to restore)')
        
        if restored_count > 0:
            self.message_user(
                request,
                'Rewards restored as goodwill gesture: ' + ', '.join(messages_list),
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'No rewards restored: ' + ', '.join(messages_list),
                level=messages.WARNING
            )
    restore_rewards_goodwill.short_description = '💝 Restore used rewards as goodwill (ADMIN APPROVAL)'


@admin.register(RefundItem)
class RefundItemAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'refund_request',
        'product_name',
        'quantity_to_refund',
        'refund_amount',
        'condition_acceptable',
        'restocked'
    ]
    
    list_filter = ['condition_acceptable', 'restocked']
    search_fields = ['refund_request__id', 'order_item__product__title']
    
    readonly_fields = ['refund_request', 'order_item', 'quantity_to_refund', 'refund_amount']
    
    def product_name(self, obj):
        """Display product name"""
        try:
            return obj.order_item.product.title
        except Exception as e:
            return f"Error: {e}"
    product_name.short_description = 'Product'
