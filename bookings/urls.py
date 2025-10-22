from django.urls import path
from bookings.views import *

app_name = 'bookings'

urlpatterns = [
    path("<uuid:match_id>/", create_booking, name="create_booking"),
    path("payment/<uuid:booking_id>/", payment, name="payment"),
    path("cancel/<uuid:booking_id>/", cancel_booking, name="cancel_booking"),
    path('notification/', midtrans_notification, name='midtrans_notification'),
    path("check_status/<uuid:booking_id>/", check_booking_status, name="check_booking_status"),
]