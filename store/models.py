from django.db import models
from django.urls import reverse
from django.utils import timezone
from cloudinary.models import CloudinaryField

class Topic(models.Model):
    name = models.CharField(max_length=250, db_index=True)
    slug = models.SlugField(max_length=250, unique=True)

    class Meta:
        verbose_name_plural = 'topics'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('list-topic', args=[self.slug])


class Category(models.Model):
    topic = models.ForeignKey(
        Topic,
        related_name='categories',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The topic this category belongs to (e.g. Video Games)"
    )
    name = models.CharField(max_length=250, db_index=True)
    slug = models.SlugField(max_length=250, unique=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('list-category', args=[self.slug])

class Product(models.Model):
    #FK 
    category = models.ForeignKey(Category, related_name='product', on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=250)
    brand = models.CharField(max_length=250, default='un-branded')
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255)
    price = models.DecimalField(max_digits=4, decimal_places=2)
    #image = models.ImageField(upload_to='images/')
    image = CloudinaryField('image', folder='gamestore/products/')
    # Inventory and Sales Tracking Fields
    date_uploaded = models.DateTimeField(auto_now_add=True, help_text="Date when product was first added")
    quantity_available = models.IntegerField(default=0, help_text="Current stock available")
    quantity_sold = models.IntegerField(default=0, help_text="Total quantity sold")
    total_price_sold = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total revenue from this product")
    last_sold_date = models.DateTimeField(null=True, blank=True, help_text="Last date this product was sold")
    payment_successful = models.BooleanField(default=False, help_text="Has this product been successfully sold at least once")

    class Meta:
        verbose_name_plural = 'products'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('product-info', args=[self.slug])
    
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.quantity_available > 0
    
    def can_fulfill_order(self, requested_quantity):
        """Check if there's enough stock to fulfill an order"""
        return self.quantity_available >= requested_quantity
    
    def process_sale(self, quantity, total_amount):
        """Update product after a successful sale"""
        if self.can_fulfill_order(quantity):
            self.quantity_available -= quantity
            self.quantity_sold += quantity
            self.total_price_sold += total_amount
            self.last_sold_date = timezone.now()
            self.payment_successful = True
            self.save()
            return True
        return False

