from django.urls import path, include
from . import views

urlpatterns = [
    # 账号相关
    path('register/', views.register, name='register'),
    path('onboarding/', views.onboarding_choice, name='onboarding_choice'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', views.salon_dashboard, name='dashboard'),
    path('add-staff/', views.add_staff, name='add_staff'),
    path('add-service/', views.add_service, name='add_service'),
    path('manage-services/', views.manage_services, name='manage_services'),
    path('service/<int:service_id>/toggle/', views.toggle_service_status, name='toggle_service_status'),
    path('salon/<int:salon_id>/book/', views.create_booking, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking, name='reject_booking'),
    path('my-schedule/', views.staff_schedule, name='staff_schedule'),
    path('create-salon/', views.create_salon, name='create_salon'),
    path('salons/', views.salon_list, name='salon_list'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    path('staff/<int:staff_id>/toggle/', views.toggle_staff_status, name='toggle_staff_status'),
]