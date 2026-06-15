
# Create your models here.
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, timedelta


class Salon(models.Model):
    # Core: Bind salon to its owner
    # Foundation of SaaS multi-tenancy: each tenant owns their data
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salon')
    
    # Salon basic info
    name = models.CharField(max_length=100, verbose_name="Salon Name")
    location = models.CharField(max_length=200, verbose_name="Location")
    contact_number = models.CharField(max_length=20, verbose_name="Contact Number", default="N/A")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    
    # Extend: support salon images
    image = models.ImageField(upload_to='salons/', blank=True, null=True, verbose_name="Salon Image")
    
    # Business hours
    business_hours = models.CharField(max_length=100, default="10:00 AM - 07:00 PM", verbose_name="Business Hours")
    
    # Track creation time
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"
    
    @property
    def has_valid_image(self):
        return bool(self.image and self.image.storage.exists(self.image.name))

class Staff(models.Model):
    # 1. Link to Salon
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='staffs', verbose_name="Salon")
    
    # 2. Link to user account (optional)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_profile')
    
    # 3. Basic info
    name = models.CharField(max_length=100, verbose_name="Name")
    role = models.CharField(max_length=100, blank=True, null=True, default='General Stylist')
    specialty = models.CharField(max_length=200, blank=True, null=True, verbose_name="Specialty")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Phone Number")
    image = models.ImageField(upload_to='staff_images/', blank=True, null=True, verbose_name="Photo")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    @property
    def has_valid_image(self):
        return bool(self.image and self.image.storage.exists(self.image.name))

    def __str__(self):
    # Uniform return format
        return f"{self.name} ({self.role})"
    
    
class Service(models.Model):
    # Link to Salon
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services', verbose_name="Salon")
    name = models.CharField(max_length=100, verbose_name="Services")
    min_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Note for customers
    price_note = models.CharField(
        max_length=200, 
        blank=True, 
        default="Price varies by age and hair length/style."
    )
    duration_minutes = models.IntegerField(default=30, help_text="Average duration in minutes")
    is_active = models.BooleanField(default=True)    
    def __str__(self):
        return f"{self.name} (RM {self.min_price} - {self.max_price})"
    
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='bookings')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='my_bookings')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='bookings')
    
    booking_date = models.DateField() # Booking Date
    timeslot = models.TimeField()     # Start Time
    end_time = models.TimeField(blank=True, null=True) # Calculated End Time
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.end_time and self.timeslot and self.service:
            # Calculate end_time based on service duration
            start_datetime = datetime.combine(datetime.today(), self.timeslot)
            end_datetime = start_datetime + timedelta(minutes=self.service.duration_minutes)
            self.end_time = end_datetime.time()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.username} - {self.service.name} - {self.booking_date}"
    
    
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('none', 'None'),
        ('customer', 'Customer'),
        ('merchant', 'Merchant'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='none')
    # For merchants, determine if they setup salon
    has_setup_salon = models.BooleanField(default=False)
    # User Avatar
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Profile Picture")


    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

class StaffReview(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_reviews')
    rating = models.IntegerField(default=5, verbose_name="Rating (1-5)")
    comment = models.TextField(blank=True, null=True, verbose_name="Comment")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.username} - {self.staff.name} - {self.rating} Stars"

class SalonReview(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salon_reviews')
    rating = models.IntegerField(default=5, verbose_name="Rating (1-5)")
    comment = models.TextField(blank=True, null=True, verbose_name="Comment")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.username} - {self.salon.name} - {self.rating} Stars"