from django.shortcuts import render
from django.http import JsonResponse
import json
import datetime
from .models import * 
from .utils import cookieCart, cartData, guestOrder
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

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

	if not request.user.is_authenticated:
		class OrderWrapper:
			def __init__(self, order_dict):
				self.get_cart_total = order_dict['get_cart_total']
				self.get_cart_items = order_dict['get_cart_items']
				self.shipping = order_dict['shipping']
		order = OrderWrapper(order)


	amount = int(order.get_cart_total * 100)

	razorpay_order = razorpay_client.order.create(dict(
        amount=amount,
        currency="INR",
        payment_capture='1'
    ))

	razorpay_order_id=razorpay_order['id']
	callback_url = '/paymenthandler/'

	context = {
        'items': items,
        'order': order,
        'cartItems': data['cartItems'],
        'razorpay_order_id': razorpay_order_id,
        'razorpay_merchant_key': settings.RAZORPAY_KEY_ID,
        'razorpay_amount': amount,
        'currency': 'INR',
        'callback_url': callback_url
    }

	# context = {'items':items, 'order':order, 'cartItems':cartItems}
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

    #         result = razorpay_client.utility.verify_payment_signature(params_dict)

    #         if result is None:
    #             
    #             amount = request.POST.get('razorpay_amount', 0)
    #            
    #             # razorpay_client.payment.capture(payment_id, amount)

    #             return render(request, 'store/paymentsuccess.html')
    #         else:
    #             return render(request, 'store/paymentfail.html')

    #     except:
    #         return render(request, 'store/paymentfail.html')
    # else:
    #     return JsonResponse({'error': 'Invalid request'}, status=400)



def updateItem(request):
	data = json.loads(request.body)
	productId = data['productId']
	action = data['action']
	print('Action:', action)
	print('Product:', productId)
	
	product = Product.objects.get(id=productId)

	if request.user.is_authenticated:
		customer = request.user.customer
		order, created = Order.objects.get_or_create(customer=customer, complete=False)
		orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
		# orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
	else:
		try:
			cart = json.loads(request.COOKIES.get('cart', '{}'))
		except:
			cart = {}
		if str(productId) in cart:
			if action == 'add':
				cart[str(productId)]['quantity'] += 1
			elif action == 'remove':
				cart[str(productId)]['quantity'] -= 1
				if cart[str(productId)]['quantity'] <= 0:
					del cart[str(productId)]
		else:
			if action == 'add':
				cart[str(productId)] = {'quantity': 1}
		response = JsonResponse('Item was added', safe=False)
		response.set_cookie('cart', json.dumps(cart))
		return response
		
	#product = Product.objects.get(id=productId)
    #orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)
	# customer = request.user.customer
	# order, created = Order.objects.get_or_create(customer=customer, complete=False)

	# product = Product.objects.get(id=productId)
	# orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

	if action == 'add':
		orderItem.quantity = (orderItem.quantity + 1)
	elif action == 'remove':
		orderItem.quantity = (orderItem.quantity - 1)

	orderItem.save()

	if orderItem.quantity <= 0:
		orderItem.delete()

	return JsonResponse('Item was added', safe=False)

def processOrder(request):
	transaction_id = datetime.datetime.now().timestamp()
	data = json.loads(request.body)

	if request.user.is_authenticated:
		customer = request.user.customer
		order, created = Order.objects.get_or_create(customer=customer, complete=False)
	else:
		customer, order = guestOrder(request, data)

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
	if not request.user.is_authenticated:
		 response.delete_cookie('cart')

	return response

	# return JsonResponse('Payment submitted..', safe=False)
def paymentsuccess(request):
    return render(request, 'store/paymentsuccess.html')

def paymentfail(request):

    return render(request, 'store/paymentfail.html')
