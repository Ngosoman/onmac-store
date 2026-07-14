from django.http import JsonResponse


def health(request):
	return JsonResponse({"app": "cart", "status": "ok"})
