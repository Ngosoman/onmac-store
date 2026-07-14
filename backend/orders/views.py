import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Order
from .serializers import OrderSerializer
from .services import OrderService


def health(request):
	return JsonResponse({"app": "orders", "status": "ok"})


def _parse_json(request):
	try:
		return json.loads(request.body.decode("utf-8") or "{}")
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def orders_collection(request):
	if request.method == "GET":
		orders = Order.objects.prefetch_related("items").order_by("-created_at")
		serializer = OrderSerializer(orders, many=True)
		return JsonResponse({"orders": serializer.data})

	payload = _parse_json(request)
	if payload is None:
		return JsonResponse({"error": "Invalid JSON payload."}, status=400)

	serializer = OrderSerializer(data=payload)
	if not serializer.is_valid():
		return JsonResponse(serializer.errors, status=400)

	order = OrderService.create_order(serializer.validated_data)
	return JsonResponse(OrderSerializer(order).data, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def order_detail(request, order_id):
	try:
		order = Order.objects.prefetch_related("items").get(id=order_id)
	except Order.DoesNotExist:
		return JsonResponse({"error": "Order not found."}, status=404)

	if request.method == "GET":
		return JsonResponse(OrderSerializer(order).data)

	payload = _parse_json(request)
	if payload is None:
		return JsonResponse({"error": "Invalid JSON payload."}, status=400)

	serializer = OrderSerializer(order, data=payload, partial=True)
	if not serializer.is_valid():
		return JsonResponse(serializer.errors, status=400)

	order = OrderService.update_order(order, serializer.validated_data)
	return JsonResponse(OrderSerializer(order).data)
