import os
import django
import sys
import random
from datetime import datetime, timedelta, time
from django.utils import timezone

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from django.contrib.auth.models import User
from services.models import Booking, Service, Salon, Staff

def seed_bookings_for_salon(salon_name):
    try:
        salon = Salon.objects.get(name=salon_name)
    except Salon.DoesNotExist:
        print(f"Error: Salon '{salon_name}' does not exist!")
        return

    services = Service.objects.filter(salon=salon, is_active=True)
    staffs = Staff.objects.filter(salon=salon, is_active=True)
    customers = User.objects.filter(userprofile__role='customer')

    if not services.exists():
        print(f"Error: Salon '{salon_name}' has no active Services!")
        return
    if not staffs.exists():
        print(f"Error: Salon '{salon_name}' has no active Staff!")
        return
    if not customers.exists():
        # Fallback: create a dummy customer if none exists
        dummy_user, _ = User.objects.get_or_create(username="test_customer", defaults={'email': 'customer@test.com'})
        if _:
            dummy_user.set_password("password123")
            dummy_user.save()
            from services.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=dummy_user)
            profile.role = 'customer'
            profile.save()
        customers = User.objects.filter(userprofile__role='customer')

    print(f"Generating historical bookings for '{salon_name}'...")
    
    count = 0
    # Generate 150 records
    for i in range(150):
        # Random date in the past 30 days
        days_ago = random.randint(0, 30)
        random_date = timezone.now().date() - timedelta(days=days_ago)
        
        # Simulate peak hours (higher density around lunch/afternoon: 12-14 and 16-18)
        if random.random() > 0.4:
            hour = random.choice([12, 13, 14, 16, 17, 18])
        else:
            hour = random.choice([10, 11, 15, 19])
            
        random_time = time(hour, 0)
        selected_service = random.choice(services)
        selected_staff = random.choice(staffs)
        selected_customer = random.choice(customers)

        # Ensure no duplicate booking for the same staff at the exact same date and time
        exists = Booking.objects.filter(
            staff=selected_staff,
            booking_date=random_date,
            timeslot=random_time
        ).exists()

        if not exists:
            Booking.objects.create(
                salon=salon,
                customer=selected_customer,
                staff=selected_staff,
                service=selected_service,
                booking_date=random_date,
                timeslot=random_time,
                status='completed'
            )
            count += 1

    print(f"Success! {count} historical booking records added to '{salon_name}'.")

if __name__ == '__main__':
    seed_bookings_for_salon("Signature Style Hair Salon")
    seed_bookings_for_salon("Hair Style Salon")
