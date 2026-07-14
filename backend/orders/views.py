from django.http import JsonResponse


def health(request):
	return JsonResponse({"app": "orders", "status": "ok"})
