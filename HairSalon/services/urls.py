from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.salon_dashboard, name='dashboard'),
    path('add-staff/', views.add_staff, name='add_staff'),
    path('add-service/', views.add_service, name='add_service'),
    path('salon/<int:salon_id>/book/', views.create_booking, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking, name='reject_booking'),
    path('my-schedule/', views.staff_schedule, name='staff_schedule'),
]