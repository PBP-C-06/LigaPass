from django.urls import path
from bookings.views import *

app_name = 'bookings'

urlpatterns = [
    path("<int:match_id>/", create_booking, name="create_booking"),
    path("payment/<uuid:booking_id>/", payment, name="payment"),
    path("cancel/<uuid:booking_id>/", cancel_booking, name="cancel_booking"),
]