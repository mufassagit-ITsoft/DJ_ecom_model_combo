from django.urls import path
from . import views


urlpatterns = [

    path('checkout', views.checkout, name='checkout'),
    path('complete-order', views.complete_order, name='complete-order'),
    path('payment-success', views.payment_success, name='payment-success'),
    path('payment-failed', views.payment_failed, name='payment-failed'),
    path('refunds/', views.refund_landing, name='refund-landing'),
    path('request-refund/<int:order_id>/', views.request_refund, name='request-refund'),
    path('refund-status/<int:refund_id>/', views.refund_status, name='refund-status'),
    path('guest-refund/', views.guest_refund_request, name='guest-refund-request'),
    path('guest-refund-status/<int:refund_id>/', views.guest_refund_status, name='guest-refund-status'),
    
]