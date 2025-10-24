from django.urls import path, reverse_lazy,include
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView

app_name = 'store'  

urlpatterns = [
    path('', views.store, name='store'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),

    path('update_item/', views.updateItem, name='update_item'),
    path('process_order/', views.processOrder, name="process_order"),

    path('paymenthandler/', views.paymenthandler, name="paymenthandler"),
    path('paymentsuccess/', views.paymentsuccess, name="paymentsuccess"),
    path('paymentfail/', views.paymentfail, name="paymentfail"),

    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),

    path('apply_coupon/', views.apply_coupon, name='apply_coupon'),

    # path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('logout/', LogoutView.as_view(next_page=reverse_lazy('store:store')), name='logout'),
    # path('logout/', auth_views.LogoutView.as_view(next_page=reverse_lazy('store:store')), name='logout'),
    # path('logout/', LogoutView.as_view(next_page='store'), name='logout'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
]
