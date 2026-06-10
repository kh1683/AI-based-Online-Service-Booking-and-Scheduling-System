from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from . import views

urlpatterns = [
    
    path('', views.salon_list, name='home'),
    
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('onboarding/', views.onboarding_choice, name='onboarding_choice'),
    path('change-password/', views.custom_password_change, name='custom_password_change'),
    path('edit-salon-location/', views.edit_salon_location, name='edit_salon_location'),
    path('edit-salon-image/', views.edit_salon_image, name='edit_salon_image'),
    path('accounts/login/', auth_views.LoginView.as_view(extra_context={'google_client_id': settings.GOOGLE_CLIENT_ID}), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', views.salon_dashboard, name='dashboard'),
    path('dashboard/history/', views.merchant_booking_history, name='merchant_booking_history'),
    path('booking/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),
    # path('add-staff/', views.add_staff, name='add_staff'),
    # path('add-service/', views.add_service, name='add_service'),
    path('manage-services/', views.manage_services, name='manage_services'),
    path('service/<int:service_id>/toggle/', views.toggle_service_status, name='toggle_service_status'),
    path('service/<int:service_id>/edit/', views.edit_service, name='edit_service'),
    path('service/<int:service_id>/delete/', views.delete_service, name='delete_service'),
    path('salon/<int:salon_id>/book/', views.create_booking, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking, name='reject_booking'),
    path('my-schedule/', views.staff_schedule, name='staff_schedule'),
    path('create-salon/', views.create_salon, name='create_salon'),
    path('salon_list/', views.salon_list, name='salon_list'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    path('staff/<int:staff_id>/toggle/', views.toggle_staff_status, name='toggle_staff_status'),
    path('staff/<int:staff_id>/edit/', views.edit_staff, name='edit_staff'),
    path('salon/<int:salon_id>/', views.salon_detail, name='salon_detail'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('salon/<int:salon_id>/review/', views.submit_salon_review, name='submit_salon_review'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    # path('select-role/<str:role_choice>/', views.select_role, name='select_role'),
    path('choose-role/<str:role_choice>/', views.choose_role, name='choose_role'),
    path('', views.home_router, name='home'),
    path('api/ai-recommendations/', views.get_ai_recommendations, name='ai_recommendations'),
]