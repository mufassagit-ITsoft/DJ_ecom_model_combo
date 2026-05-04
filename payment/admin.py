from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from .models import (
    ShippingAddress, Order, OrderItem,
    RefundRequest, RefundItem,
    send_refund_status_email,
    restock_refunded_items,
    process_rewards_refund,
    restore_used_rewards,
    issue_paypal_refund,
)

@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'username', 'email', 'city', 'state', 'zipcode']
    search_fields = ['full_name', 'email', 'city', 'state', 'zipcode', 'user__username']
    list_filter = ['state', 'city']
    readonly_fields = ['full_name', 'email', 'address1', 'address2', 'city', 'state', 'zipcode', 'user']

    fieldsets = (
        ('Customer', {'fields': ('user', 'full_name', 'email')}),
        ('Address',  {'fields': ('address1', 'address2', 'city', 'state', 'zipcode')}),
    )

    def username(self, obj):
        return obj.user.username if obj.user else 'Guest'
    username.short_description = 'Username'
    username.admin_order_field = 'user__username'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price', 'line_total', 'user']
    fields = ['product', 'quantity', 'price', 'line_total', 'user']
    can_delete = False

    def line_total(self, obj):
        return f'${float(obj.price * obj.quantity):.2f}'
    line_total.short_description = 'Line Total'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'customer_name', 'username',
        'amount_paid_display', 'item_count',
        'has_paypal_id', 'date_ordered', 'refund_status',
    ]
    list_filter = ['date_ordered', 'user']
    search_fields = ['id', 'full_name', 'email', 'user__username', 'paypal_transaction_id']
    readonly_fields = [
        'full_name', 'email', 'shipping_address',
        'amount_paid', 'date_ordered', 'user', 'paypal_transaction_id',
    ]
    date_hierarchy = 'date_ordered'
    ordering = ['-date_ordered']
    inlines = [OrderItemInline]

    fieldsets = (
        ('Order Information', {
            'fields': ('user', 'date_ordered')
        }),
        ('Customer Details', {
            'fields': ('full_name', 'email')
        }),
        ('Payment', {
            'fields': ('amount_paid', 'paypal_transaction_id')
        }),
        ('Shipping Address', {
            'fields': ('shipping_address',),
            'classes': ('collapse',)
        }),
    )

    def customer_name(self, obj):
        return obj.full_name
    customer_name.short_description = 'Customer Name'
    customer_name.admin_order_field = 'full_name'

    def username(self, obj):
        return obj.user.username if obj.user else 'Guest'
    username.short_description = 'Username'
    username.admin_order_field = 'user__username'

    def amount_paid_display(self, obj):
        return f'${float(obj.amount_paid):.2f}'
    amount_paid_display.short_description = 'Amount Paid'
    amount_paid_display.admin_order_field = 'amount_paid'

    def item_count(self, obj):
        return f'{obj.orderitem_set.count()} item(s)'
    item_count.short_description = 'Items'

    def has_paypal_id(self, obj):
        """Shows whether a PayPal transaction ID was stored — required for programmatic refunds"""
        if obj.paypal_transaction_id:
            return '✓ Yes'
        return '✗ No'
    has_paypal_id.short_description = 'PayPal ID Stored'

    def refund_status(self, obj):
        refund = obj.refund_requests.filter(
            status__in=['PENDING_RETURN', 'PRODUCT_RECEIVED', 'PROCESSING_REFUND']
        ).first()
        if refund:
            return refund.get_status_display()
        completed = obj.refund_requests.filter(status='COMPLETED').first()
        if completed:
            return 'Refund Completed'
        return 'No Refund'
    refund_status.short_description = 'Refund Status'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related(
            'orderitem_set', 'refund_requests'
        )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_link', 'customer_name', 'username',
        'product', 'quantity', 'unit_price_display',
        'line_total_display', 'date_sold',
    ]
    list_filter = ['order__date_ordered', 'product']
    search_fields = ['order__id', 'order__full_name', 'user__username', 'product__title']
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
        return obj.user.username if obj.user else 'Guest'
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
        return super().get_queryset(request).select_related('order', 'product', 'user')


class RefundItemInline(admin.TabularInline):
    model = RefundItem
    extra = 0
    readonly_fields = ['order_item', 'quantity_to_refund', 'refund_amount']
    fields = [
        'order_item', 'quantity_to_refund', 'refund_amount',
        'condition_acceptable', 'condition_notes', 'restocked'
    ]

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_id_simple', 'customer_info', 'customer_type',
        'refund_amount_simple', 'status_simple', 'verification_status',
        'reason', 'created_at',
    ]
    list_filter = ['status', 'reason', 'admin_verified', 'created_at']
    search_fields = ['order__id', 'customer_email', 'customer_name', 'user__username']
    date_hierarchy = 'created_at'

    readonly_fields = [
        'order', 'user', 'customer_email', 'customer_name',
        'refund_amount', 'rewards_used',
        'created_at', 'updated_at',
        'product_received_at', 'refund_completed_at',
        'verified_by', 'verified_at',
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
        ('Admin Verification (Required Before Processing)', {
            'fields': ('admin_verified', 'verified_by', 'verified_at'),
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
        'verify_refund_requests',
        'mark_product_received',
        'process_paypal_refund',
        'complete_refund',
        'reject_refund',
        'restore_rewards_goodwill',
    ]

    def order_id_simple(self, obj):
        try:
            return f'Order #{obj.order.id}'
        except Exception:
            return '-'
    order_id_simple.short_description = 'Order'

    def customer_info(self, obj):
        try:
            if obj.user:
                return f'{obj.user.username} ({obj.customer_email})'
            return f'Guest ({obj.customer_email})'
        except Exception:
            return '-'
    customer_info.short_description = 'Customer'

    def customer_type(self, obj):
        return 'Registered' if obj.user else 'Guest'
    customer_type.short_description = 'Type'

    def refund_amount_simple(self, obj):
        amount = f'${float(obj.refund_amount):.2f}'
        if obj.rewards_used > 0:
            amount += f' (Rewards: ${float(obj.rewards_used):.2f})'
        return amount
    refund_amount_simple.short_description = 'Refund Amount'

    def status_simple(self, obj):
        return obj.get_status_display()
    status_simple.short_description = 'Status'

    def verification_status(self, obj):
        if obj.admin_verified:
            by = f' by {obj.verified_by.username}' if obj.verified_by else ''
            return f'VERIFIED{by}'
        return 'NOT VERIFIED'
    verification_status.short_description = 'Admin Verified'

    def verify_refund_requests(self, request, queryset):
        """
        STEP 1 — Verify and approve refund requests.
        Must run before any processing action can proceed.
        """
        already_verified = queryset.filter(admin_verified=True)
        if already_verified.exists():
            self.message_user(
                request,
                f'{already_verified.count()} refund(s) were already verified — skipped.',
                level=messages.WARNING
            )

        updated = 0
        for refund in queryset.filter(admin_verified=False).exclude(
            status__in=['COMPLETED', 'REJECTED', 'CANCELLED']
        ):
            refund.admin_verified = True
            refund.verified_by = request.user
            refund.verified_at = timezone.now()
            refund.save()
            updated += 1

        if updated:
            self.message_user(
                request,
                f'{updated} refund request(s) verified. Proceed with "Mark product received".',
                level=messages.SUCCESS
            )
        else:
            self.message_user(request, 'No eligible refund requests to verify.', level=messages.WARNING)
    verify_refund_requests.short_description = '(1) Verify & approve refund requests'

    def mark_product_received(self, request, queryset):
        """
        STEP 2 — Mark product as received, auto-restock acceptable items,
        and email the customer that their return has arrived.
        """
        unverified = queryset.filter(status='PENDING_RETURN', admin_verified=False)
        if unverified.exists():
            ids = ', '.join(f'#{r.id}' for r in unverified)
            self.message_user(
                request,
                f'Cannot proceed: refund(s) {ids} are not yet verified. Run Step 1 first.',
                level=messages.ERROR
            )
            return

        updated = 0
        for refund in queryset.filter(status='PENDING_RETURN', admin_verified=True):
            refund.status = 'PRODUCT_RECEIVED'
            refund.product_received_at = timezone.now()
            refund.save()

            # Auto-mark items as acceptable and restock
            refund.items.all().update(condition_acceptable=True)
            try:
                restock_refunded_items(refund)
            except Exception as e:
                self.message_user(
                    request,
                    f'Error restocking refund #{refund.id}: {e}',
                    level=messages.ERROR
                )

            # ── GAP 2 FIX: Email customer at this stage ────────────────
            send_refund_status_email(
                refund,
                subject=f'Return Received — Refund #{refund.id} Being Processed',
                body=(
                    f'Hi {refund.customer_name},\n\n'
                    f'Great news! We have received your returned item(s) for '
                    f'Order #{refund.order.id}.\n\n'
                    f'We are now processing your refund of ${refund.refund_amount:.2f}.\n\n'
                    f'You will receive another email once the PayPal refund has been issued. '
                    f'This typically takes 3-5 business days to appear in your account.\n\n'
                    f'Refund Request ID: #{refund.id}'
                )
            )

            updated += 1

        self.message_user(
            request,
            f'{updated} refund(s) marked as product received. Items restocked. Customers notified.',
            level=messages.SUCCESS
        )
    mark_product_received.short_description = '(2) Mark product received & restock'

    def process_paypal_refund(self, request, queryset):
        """
        STEP 3 — Issue the actual PayPal refund via PayPal REST API.

        GAP 1 FIX: Previously just changed the status and told admin to
        go do it manually in PayPal. Now calls the PayPal API directly.

        Requires:
        - PAYPAL_SECRET in environment variables
        - order.paypal_transaction_id was stored at checkout

        Orders without a stored PayPal transaction ID (placed before this
        fix was deployed) will show an error and must be refunded manually
        in the PayPal dashboard.
        """
        unverified = queryset.filter(status='PRODUCT_RECEIVED', admin_verified=False)
        if unverified.exists():
            ids = ', '.join(f'#{r.id}' for r in unverified)
            self.message_user(
                request,
                f'Cannot proceed: refund(s) {ids} are not yet verified. Run Step 1 first.',
                level=messages.ERROR
            )
            return

        success_count = 0
        manual_count  = 0
        error_count   = 0

        for refund in queryset.filter(status='PRODUCT_RECEIVED', admin_verified=True):
            success, paypal_refund_id, error_msg = issue_paypal_refund(refund)

            if success:
                refund.status = 'PROCESSING_REFUND'
                refund.paypal_refund_id = paypal_refund_id
                refund.save()

                # ── Notify customer PayPal refund was issued ───────────
                send_refund_status_email(
                    refund,
                    subject=f'PayPal Refund Issued — Refund #{refund.id}',
                    body=(
                        f'Hi {refund.customer_name},\n\n'
                        f'Your PayPal refund of ${refund.refund_amount:.2f} has been issued '
                        f'for Order #{refund.order.id}.\n\n'
                        f'PayPal Refund ID: {paypal_refund_id}\n\n'
                        f'The refund should appear in your PayPal account within '
                        f'3-5 business days depending on your payment method.\n\n'
                        f'Refund Request ID: #{refund.id}'
                    )
                )
                success_count += 1

            elif 'manually' in error_msg.lower() or 'before this fix' in error_msg.lower():
                # No transaction ID — needs manual PayPal processing
                refund.status = 'PROCESSING_REFUND'
                refund.save()
                self.message_user(
                    request,
                    f'Refund #{refund.id}: {error_msg}',
                    level=messages.WARNING
                )
                manual_count += 1

            else:
                self.message_user(
                    request,
                    f'Refund #{refund.id} PayPal error: {error_msg}',
                    level=messages.ERROR
                )
                error_count += 1

        if success_count:
            self.message_user(
                request,
                f'{success_count} PayPal refund(s) issued successfully. Customers notified.',
                level=messages.SUCCESS
            )
        if manual_count:
            self.message_user(
                request,
                f'{manual_count} refund(s) need manual PayPal processing (no transaction ID stored). '
                f'After processing in PayPal, enter the refund ID and run "Complete refund".',
                level=messages.WARNING
            )
    process_paypal_refund.short_description = '(3) Issue PayPal refund via API'

    def complete_refund(self, request, queryset):
        """
        STEP 4 — Mark refund as completed, deduct earned rewards,
        and send the customer a final confirmation email.
        """
        unverified = queryset.filter(status='PROCESSING_REFUND', admin_verified=False)
        if unverified.exists():
            ids = ', '.join(f'#{r.id}' for r in unverified)
            self.message_user(
                request,
                f'Cannot complete: refund(s) {ids} are not yet verified.',
                level=messages.ERROR
            )
            return

        updated = 0
        for refund in queryset.filter(status='PROCESSING_REFUND', admin_verified=True):
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

            # ── GAP 2 FIX: Final completion email to customer ──────────
            send_refund_status_email(
                refund,
                subject=f'Refund Complete — Refund #{refund.id}',
                body=(
                    f'Hi {refund.customer_name},\n\n'
                    f'Your refund of ${refund.refund_amount:.2f} for '
                    f'Order #{refund.order.id} has been fully processed.\n\n'
                    + (
                        f'PayPal Refund ID: {refund.paypal_refund_id}\n\n'
                        if refund.paypal_refund_id else ''
                    ) +
                    f'The funds should already be available or will appear in your '
                    f'PayPal account within 1-3 business days.\n\n'
                    f'Thank you for shopping with us. We hope to serve you again!'
                )
            )

            updated += 1

        self.message_user(
            request,
            f'{updated} refund(s) completed. Rewards adjusted. Customers notified by email.',
            level=messages.SUCCESS
        )
    complete_refund.short_description = '(4) Complete refund & notify customer'

    def reject_refund(self, request, queryset):
        """Reject selected refund requests and notify the customer."""
        updated = 0
        for refund in queryset.exclude(status__in=['COMPLETED', 'REJECTED', 'CANCELLED']):
            refund.status = 'REJECTED'
            refund.save()

            send_refund_status_email(
                refund,
                subject=f'Refund Request #{refund.id} — Decision',
                body=(
                    f'Hi {refund.customer_name},\n\n'
                    f'After reviewing your refund request #{refund.id} for '
                    f'Order #{refund.order.id}, we are unable to approve this refund.\n\n'
                    + (
                        f'Reason: {refund.rejection_reason}\n\n'
                        if refund.rejection_reason else ''
                    ) +
                    f'If you have questions, please contact our support team and '
                    f'reference Refund Request ID: #{refund.id}.'
                )
            )
            updated += 1

        self.message_user(
            request,
            f'{updated} refund(s) rejected. Customers notified.',
            level=messages.WARNING
        )
    reject_refund.short_description = 'Reject selected refund requests'

    def restore_rewards_goodwill(self, request, queryset):
        """
        Admin-only goodwill action: restore used rewards.
        Only for defective products, company errors, or special cases.
        """
        restored = 0
        skipped  = 0

        for refund in queryset:
            result = restore_used_rewards(refund)
            if result:
                restored += 1

                send_refund_status_email(
                    refund,
                    subject=f'Rewards Restored — Order #{refund.order.id}',
                    body=(
                        f'Hi {refund.customer_name},\n\n'
                        f'As a goodwill gesture, we have restored ${refund.rewards_used:.2f} '
                        f'in rewards points to your account.\n\n'
                        f'These points are now available for use on your next purchase.\n\n'
                        f'Thank you for your patience and understanding.'
                    )
                )
            else:
                skipped += 1

        if restored:
            self.message_user(
                request,
                f'Rewards restored for {restored} customer(s). Customers notified.',
                level=messages.SUCCESS
            )
        if skipped:
            self.message_user(
                request,
                f'{skipped} skipped (already restored, no rewards used, or guest orders).',
                level=messages.WARNING
            )
    restore_rewards_goodwill.short_description = 'Restore rewards as goodwill gesture (admin only)'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 'user', 'verified_by'
        ).prefetch_related('items')

@admin.register(RefundItem)
class RefundItemAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'refund_request', 'product_name',
        'quantity_to_refund', 'refund_amount',
        'condition_acceptable', 'restocked'
    ]
    list_filter = ['condition_acceptable', 'restocked']
    search_fields = ['refund_request__id', 'order_item__product__title']
    readonly_fields = ['refund_request', 'order_item', 'quantity_to_refund', 'refund_amount']

    def product_name(self, obj):
        try:
            return obj.order_item.product.title
        except Exception:
            return '-'
    product_name.short_description = 'Product'