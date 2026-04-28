from django.urls import path
from . import views

urlpatterns = [
    # Store main page
    path('', views.store, name='store'),
    # Individual product
    path('product/<slug:product_slug>/', views.product_info, name='product-info'),
    # Individual category
    path('search/<slug:category_slug>/', views.list_category, name='list-category'),
    #Topic page
    path('topic/<slug:topic_slug>/', views.list_topics, name='list-topic'),
    # Brand page
    path('brand/<str:brand_name>/', views.list_brand, name='list-brand'),
    # Search products
    path('search-products/', views.search_products, name='search-products'),
]