from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.salon_dashboard, name='dashboard'),
]