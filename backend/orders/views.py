import json
from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Order, OrderItem


def _parse_json(request):
	try:
		return json.loads(request.body.decode("utf-8") or "{}")
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


def _serialize_order_item(item):
	return {
		"id": item.id,
		"product_id": item.product_id,
		"product_name": item.product_name,
		"quantity": item.quantity,
		"unit_price": str(item.unit_price),
		"subtotal": str(item.subtotal),
		"line_total": str(item.subtotal),
	}


def _serialize_order(order):
	return {
		"id": order.id,
		"reference": str(order.reference),
		"merchant_reference": order.merchant_reference,
		"customer_name": order.customer_name,
		"customer_email": order.customer_email,
		"customer_phone": order.customer_phone,
		"shipping_address": order.shipping_address,
		"payment_method": order.payment_method,
		"pesapal_tracking_id": order.pesapal_tracking_id,
		"currency": order.currency,
		"status": order.status,
		"total_amount": str(order.total_amount),
		"created_at": order.created_at.isoformat(),
		"updated_at": order.updated_at.isoformat(),
		"items": [_serialize_order_item(item) for item in order.items.all()],
	}


def health(request):
	return JsonResponse({"app": "orders", "status": "ok"})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def orders_collection(request):
	if request.method == "GET":
		orders = Order.objects.prefetch_related("items").order_by("-created_at")
		return JsonResponse({"orders": [_serialize_order(order) for order in orders]})

	payload = _parse_json(request)
	if payload is None:
		return JsonResponse({"error": "Invalid JSON payload."}, status=400)

	items = payload.get("items", [])
	if not isinstance(items, list) or len(items) == 0:
		return JsonResponse({"error": "At least one order item is required."}, status=400)

	required = ["customer_name", "customer_email"]
	missing = [field for field in required if not payload.get(field)]
	if missing:
		return JsonResponse({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

	with transaction.atomic():
		order = Order.objects.create(
			customer_name=payload.get("customer_name", "").strip(),
			customer_email=payload.get("customer_email", "").strip(),
			customer_phone=payload.get("customer_phone", "").strip(),
			shipping_address=payload.get("shipping_address", "").strip(),
			payment_method=payload.get("payment_method", "").strip(),
			merchant_reference=payload.get("merchant_reference"),
			pesapal_tracking_id=payload.get("pesapal_tracking_id"),
			currency=payload.get("currency", Order.Currency.KES),
			status=payload.get("status", Order.Status.PENDING),
			total_amount=0,
		)

		total = Decimal("0")
		for raw_item in items:
			product_id = raw_item.get("product_id")
			product_name = str(raw_item.get("product_name", "")).strip()
			quantity = int(raw_item.get("quantity", 1))
			unit_price = Decimal(str(raw_item.get("unit_price", "0")))

			if not product_name:
				transaction.set_rollback(True)
				return JsonResponse({"error": "Each item must include product_name."}, status=400)
			if quantity <= 0 or unit_price < 0:
				transaction.set_rollback(True)
				return JsonResponse({"error": "Item quantity and price must be positive."}, status=400)

			OrderItem.objects.create(
				order=order,
				product_id=product_id,
				product_name=product_name,
				quantity=quantity,
				unit_price=unit_price,
			)
			total += Decimal(str(unit_price)) * quantity

		order.total_amount = total
		order.save(update_fields=["total_amount", "updated_at"])

	order = Order.objects.prefetch_related("items").get(id=order.id)
	return JsonResponse(_serialize_order(order), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def order_detail(request, order_id):
	try:
		order = Order.objects.prefetch_related("items").get(id=order_id)
	except Order.DoesNotExist:
		return JsonResponse({"error": "Order not found."}, status=404)

	if request.method == "GET":
		return JsonResponse(_serialize_order(order))

	payload = _parse_json(request)
	if payload is None:
		return JsonResponse({"error": "Invalid JSON payload."}, status=400)

	update_fields = ["updated_at"]

	next_status = payload.get("status")
	if next_status is not None:
		if next_status not in dict(Order.Status.choices):
			return JsonResponse({"error": "Invalid order status."}, status=400)
		order.status = next_status
		update_fields.append("status")

	if "pesapal_tracking_id" in payload:
		tracking_id = payload.get("pesapal_tracking_id")
		order.pesapal_tracking_id = tracking_id.strip() if isinstance(tracking_id, str) else tracking_id
		update_fields.append("pesapal_tracking_id")

	if "merchant_reference" in payload:
		merchant_reference = payload.get("merchant_reference")
		order.merchant_reference = merchant_reference.strip() if isinstance(merchant_reference, str) else merchant_reference
		update_fields.append("merchant_reference")

	if "currency" in payload:
		currency = payload.get("currency")
		if currency not in dict(Order.Currency.choices):
			return JsonResponse({"error": "Invalid currency. Use KES, USD, or GBP."}, status=400)
		order.currency = currency
		update_fields.append("currency")

	if len(update_fields) == 1:
		return JsonResponse({"error": "No valid fields to update."}, status=400)

	order.save(update_fields=update_fields)
	return JsonResponse(_serialize_order(order))
