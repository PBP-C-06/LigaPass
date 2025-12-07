from django.urls import path
from bookings.views import *

app_name = 'bookings'

urlpatterns = [
    path("<uuid:match_id>/", create_booking, name="create_booking"),
    path("payment/<uuid:booking_id>/", payment, name="payment"),
    path("cancel/<uuid:booking_id>/", cancel_booking, name="cancel_booking"),
    path('notification/', midtrans_notification, name='midtrans_notification'),
    path("check_status/<uuid:booking_id>/", check_booking_status, name="check_booking_status"),
    path("flutter-create-booking/<uuid:match_id>/", flutter_create_booking, name="flutter_create_booking"),
    path("flutter-payment/<uuid:booking_id>/", flutter_payment, name="flutter_payment"),
    path("flutter-cancel/<uuid:booking_id>/", flutter_cancel_booking, name="flutter_cancel_booking"),
    path("flutter-check-status/<uuid:booking_id>/", flutter_check_status, name="flutter_check_status"),
    path("flutter-ticket-prices/<uuid:match_id>/", flutter_get_ticket_prices, name="flutter_ticket_prices"),
    path('flutter-user-tickets/', flutter_get_user_tickets, name='flutter_user_tickets'),
    path('flutter-get-tickets/<uuid:booking_id>/', flutter_get_booking_tickets, name='flutter_get_booking_tickets'),
    path('flutter-sync-status/<uuid:booking_id>/', flutter_sync_status, name='flutter_sync_status'),
]