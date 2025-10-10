from django.conf import settings

def google_client_context(request):
    return {"GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID}
