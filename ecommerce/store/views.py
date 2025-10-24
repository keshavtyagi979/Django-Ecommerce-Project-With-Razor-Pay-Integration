from django.shortcuts import render, redirect
from django.http import JsonResponse
import json
import datetime
from .models import * 
from .utils import cookieCart, cartData, guestOrder
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages  

razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def store(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']
    products = Product.objects.all()
    context = {'products':products, 'cartItems':cartItems}
    return render(request, 'store/store.html', context)

def cart(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']
    context = {'items':items, 'order':order, 'cartItems':cartItems}
    return render(request, 'store/cart.html', context)

def checkout(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    if request.user.is_authenticated and not hasattr(request.user, 'customer'):
        Customer.objects.create(user=request.user, name=request.user.username, email=request.user.email)

    final_total = order.get_cart_total
    applied_coupon = request.session.get("applied_coupon", None)
    if applied_coupon:
        try:
            coupon = Coupon.objects.get(code=applied_coupon, active=True)
            discount_amount = (Decimal(coupon.discount) / Decimal('100')) * final_total
            final_total -= discount_amount
        except Coupon.DoesNotExist:
            pass

    amount = int(final_total * 100)
    razorpay_order = razorpay_client.order.create(dict(
        amount=amount,
        currency="INR",
        payment_capture='1'
    ))
    razorpay_order_id = razorpay_order['id']
    callback_url = '/paymenthandler/'

    context = {
        'items': items,
        'order': order,
        'cartItems': cartItems,
        'razorpay_order_id': razorpay_order_id,
        'razorpay_merchant_key': settings.RAZORPAY_KEY_ID,
        'razorpay_amount': amount,
        'currency': 'INR',
        'callback_url': callback_url,
        'applied_coupon': applied_coupon
    }
    return render(request, 'store/checkout.html', context)

# @csrf_exempt
# def paymenthandler(request):
#     if request.method == "POST":
#         try:
#             payment_id = request.POST.get('razorpay_payment_id', '')
#             razorpay_order_id = request.POST.get('razorpay_order_id', '')
#             signature = request.POST.get('razorpay_signature', '')
#             params_dict = {
#                 'razorpay_order_id': razorpay_order_id,
#                 'razorpay_payment_id': payment_id,
#                 'razorpay_signature': signature
#             }
#             razorpay_client.utility.verify_payment_signature(params_dict)

           
#             if request.user.is_authenticated and hasattr(request.user, 'customer'):
#                 customer = request.user.customer
#                 order = Order.objects.filter(customer=customer, complete=False).first()
#                 if order:
#                     order.complete = True
#                     order.save()
#                     order.orderitem_set.all().delete()  

            
#             response = render(request, 'store/paymentsuccess.html')
#             response.delete_cookie('cart')
#             return response

#         except Exception as e:
#             print("Payment verification failed:", str(e))
#             return render(request, 'store/paymentfail.html')

#     return JsonResponse({'error': 'Invalid request'}, status=400)
@csrf_exempt
def paymenthandler(request):
    if request.method == "POST":
        try:
            payment_id = request.POST.get('razorpay_payment_id', '')
            razorpay_order_id = request.POST.get('razorpay_order_id', '')
            signature = request.POST.get('razorpay_signature', '')
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

            
            if request.user.is_authenticated and hasattr(request.user, 'customer'):
                customer = request.user.customer
                order = Order.objects.filter(customer=customer, complete=False).first()
                if order:
                    order.complete = True
                    order.save()

           
            request.session['cart_merged'] = False
            response = render(request, 'store/paymentsuccess.html')
            response.delete_cookie('cart')
            return response

        except Exception as e:
            print("Payment verification failed:", str(e))
            return render(request, 'store/paymentfail.html')

    return JsonResponse({'error': 'Invalid request'}, status=400)

def updateItem(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']
    product = Product.objects.get(id=productId)

    if request.user.is_authenticated:
        if not hasattr(request.user, 'customer'):
            Customer.objects.create(user=request.user, name=request.user.username, email=request.user.email)
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
    else:
        return JsonResponse({'error': 'Login required to modify cart'}, status=403)

    if action == 'add':
        orderItem.quantity += 1
    elif action == 'remove':
        orderItem.quantity -= 1
    orderItem.save()
    if orderItem.quantity <= 0:
        orderItem.delete()
    return JsonResponse('Item was added', safe=False)

# def processOrder(request):
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Login required to place order'}, status=403)

#     if not hasattr(request.user, 'customer'):
#         Customer.objects.create(user=request.user, name=request.user.username, email=request.user.email)

#     transaction_id = datetime.datetime.now().timestamp()
#     data = json.loads(request.body)
#     customer = request.user.customer
#     order, created = Order.objects.get_or_create(customer=customer, complete=False)
#     total = float(data['form']['total'])
#     order.transaction_id = transaction_id
#     if total == order.get_cart_total:
#         order.complete = True
#     order.save()
#     if order.shipping == True:
#         ShippingAddress.objects.create(
#             customer=customer,
#             order=order,
#             address=data['shipping']['address'],
#             city=data['shipping']['city'],
#             state=data['shipping']['state'],
#             zipcode=data['shipping']['zipcode'],
#         )

#     response = JsonResponse('Payment submitted..', safe=False)
    
#     response.delete_cookie('cart')
#     return response
def processOrder(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required to place order'}, status=403)

    if not hasattr(request.user, 'customer'):
        Customer.objects.create(user=request.user, name=request.user.username, email=request.user.email)

    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)
    customer = request.user.customer
    order, created = Order.objects.get_or_create(customer=customer, complete=False)
    total = float(data['form']['total'])
    order.transaction_id = transaction_id
    if total == order.get_cart_total:
        order.complete = True
    order.save()

    if order.shipping == True:
        ShippingAddress.objects.create(
            customer=customer,
            order=order,
            address=data['shipping']['address'],
            city=data['shipping']['city'],
            state=data['shipping']['state'],
            zipcode=data['shipping']['zipcode'],
        )

   
    request.session['cart_merged'] = False
    response = JsonResponse('Payment submitted..', safe=False)
    response.delete_cookie('cart')
    return response


def paymentsuccess(request):
    return render(request, 'store/paymentsuccess.html')

def paymentfail(request):
    return render(request, 'store/paymentfail.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('store:store')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('store:login')
    return render(request, 'store/login.html')


def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Customer.objects.create(user=user, name=user.username, email=user.email)
            login(request, user)
            return redirect('store:checkout')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserCreationForm()
    return render(request, 'store/signup.html', {'form': form})

def logout_view(request):
    logout(request)
    request.session['cart_merged'] = False  
    return redirect('store:store')

@require_POST
def apply_coupon(request):
    data = json.loads(request.body)
    code = data.get("code", "").strip()
    try:
        coupon = Coupon.objects.get(code=code, active=True)
        cart_data = cartData(request)
        order = cart_data['order']
        total = order.get_cart_total
        discount_percent = Decimal(coupon.discount)
        discount_amount = (discount_percent / Decimal('100')) * total
        new_total = total - discount_amount

        razorpay_amount = int(new_total * 100)
        razorpay_order = razorpay_client.order.create(dict(
            amount=razorpay_amount,
            currency="INR",
            payment_capture='1'
        ))
        razorpay_order_id = razorpay_order['id']

        request.session["applied_coupon"] = coupon.code

        return JsonResponse({
            "valid": True,
            "discount": float(discount_percent),
            "new_total": float(new_total),
            "razorpay_order_id": razorpay_order_id,
            "razorpay_amount": razorpay_amount
        })
    except Coupon.DoesNotExist:
        return JsonResponse({"valid": False})
from django.contrib.auth.decorators import login_required

@login_required
def order_history(request):
    
    customer = request.user.customer
    orders = Order.objects.filter(customer=customer, complete=True).order_by('-date_ordered')

    context = {
        'orders': orders
    }
    return render(request, 'store/order_history.html', context)
@login_required
def order_detail(request, order_id):
    customer = request.user.customer
    order = Order.objects.filter(id=order_id, customer=customer, complete=True).first()
    if not order:
        return redirect('store:order_history')

    items = order.orderitem_set.all()
    context = {
        'order': order,
        'items': items
    }
    return render(request, 'store/order_detail.html', context)
