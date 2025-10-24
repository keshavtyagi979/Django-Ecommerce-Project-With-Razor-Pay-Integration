from django.shortcuts import render, redirect
from django.http import JsonResponse
import json
import datetime
from .models import * 
from .utils import cookieCart, cartData, guestOrder
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST
from decimal import Decimal


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
    if not request.user.is_authenticated:
        return redirect('/login/')
    
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    
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
            return render(request, 'store/paymentsuccess.html')
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

def processOrder(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required to place order'}, status=403)
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
    response = JsonResponse('Payment submitted..', safe=False)
    return response

def paymentsuccess(request):
    return render(request, 'store/paymentsuccess.html')

def paymentfail(request):
    return render(request, 'store/paymentfail.html')

def login_view(request):
    message = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('checkout')
        else:
            message = 'Invalid username or password'
    return render(request, 'store/login.html', {'message': message})

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

