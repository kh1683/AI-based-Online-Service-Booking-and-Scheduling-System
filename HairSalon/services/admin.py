from django.contrib import admin
from .models import Salon, Staff, Service, Booking
# Register your models here.
admin.site.register(Salon)
admin.site.register(Staff)
admin.site.register(Service)
admin.site.register(Booking)