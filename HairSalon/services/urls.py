from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.salon_dashboard, name='dashboard'),
    path('add-staff/', views.add_staff, name='add_staff'),
]