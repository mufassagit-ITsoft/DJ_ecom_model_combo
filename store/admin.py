from django.contrib import admin
from . models import Category, Product, Topic

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    
    # Display these fields in the product list view
    list_display = [
        'title',
        'brand',
        'price',
        'quantity_available',
        'quantity_sold',
        'total_price_sold',
        'date_uploaded',
        'last_sold_date',
        'payment_successful',
        'stock_status'
    ]
    
    # Add filters for easy navigation
    list_filter = [
        'payment_successful',
        'category',
        'brand',
        'date_uploaded',
        'last_sold_date'
    ]
    
    # Add search functionality
    search_fields = ['title', 'brand', 'description']
    
    # Make these fields read-only (auto-calculated)
    readonly_fields = [
        'date_uploaded',
        'quantity_sold',
        'total_price_sold',
        'last_sold_date',
        'payment_successful'
    ]
    
    # Organize fields in the edit form
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'brand', 'category', 'description', 'price', 'image')
        }),
        ('Inventory Management', {
            'fields': ('quantity_available',),
            'description': 'Set the available stock quantity for this product'
        }),
        ('Sales Tracking (Read-Only)', {
            'fields': ('date_uploaded', 'quantity_sold', 'total_price_sold', 'last_sold_date', 'payment_successful'),
            'description': 'These fields are automatically updated when sales occur'
        }),
    )
    
    # Custom method to display stock status
    def stock_status(self, obj):
        if obj.quantity_available > 10:
            return f"✅ In Stock ({obj.quantity_available})"
        elif obj.quantity_available > 0:
            return f"⚠️ Low Stock ({obj.quantity_available})"
        else:
            return "❌ Out of Stock"
    
    stock_status.short_description = 'Stock Status'
    
    # Order by most recently added by default
    ordering = ['-date_uploaded']





