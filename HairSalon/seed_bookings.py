import os
import django
import sys
import random
from datetime import datetime, timedelta, time
from django.utils import timezone

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from services.models import Booking, Service, Salon, User, Staff

def run_seed():
    # 1. Configuration parameters
    SALON_NAME = "Hair Style Salon"
    try:
        target_salon = Salon.objects.get(name=SALON_NAME)
    except Salon.DoesNotExist:
        print(f"Cannot find salon named '{SALON_NAME}', trying to use the first available salon...")
        target_salon = Salon.objects.first()
        if not target_salon:
            print("Error: No salons in the database!")
            sys.exit(1)
        print(f"Salon not found, using first available salon: {target_salon.name}")

    services = Service.objects.filter(salon=target_salon)
    customers = User.objects.filter(userprofile__role='customer')
    staffs = Staff.objects.filter(salon=target_salon)

    if not services.exists():
        print(f"Error: Salon '{target_salon.name}' has no Services!")
        sys.exit(1)
    if not customers.exists():
        print("Error: No Users with role 'customer' found!")
        sys.exit(1)
    if not staffs.exists():
        print(f"Error: Salon '{target_salon.name}' has no Staff!")
        sys.exit(1)

    print(f"Clearing existing bookings for {target_salon.name} to avoid duplicate conflicts and stale flat trends...")
    deleted_count = Booking.objects.filter(salon=target_salon).delete()[0]
    print(f"Deleted {deleted_count} existing bookings.")

    print(f"Generating dense historical booking data for {target_salon.name} with realistic peak hours...")
    
    count = 0
    # Generate 600 records to create a strong dataset
    # This averages ~20 bookings/day, or ~2 bookings/hour on average, with distinct peaks.
    attempts = 0
    while count < 600 and attempts < 1500:
        attempts += 1
        # Random date: past 30 days
        days_ago = random.randint(0, 30)
        random_date = timezone.now().date() - timedelta(days=days_ago)
        
        # Simulate peak hours:
        # 45% chance of Lunch Rush (12:00 PM - 02:00 PM)
        # 45% chance of Evening Rush (05:00 PM - 07:00 PM)
        # 10% chance of Off-Peak hours (10:00 AM, 11:00 AM, 03:00 PM, 04:00 PM)
        r = random.random()
        if r < 0.45:
            hour = random.choice([12, 13, 14])
        elif r < 0.90:
            hour = random.choice([17, 18, 19])
        else:
            hour = random.choice([10, 11, 15, 16])
            
        random_time = time(hour, 0)
        selected_staff = random.choice(staffs)
        selected_service = random.choice(services)
        selected_customer = random.choice(customers)

        # Check for overlap: each stylist can only do one job at a time
        overlap = Booking.objects.filter(
            staff=selected_staff,
            booking_date=random_date,
            timeslot=random_time
        ).exists()

        if not overlap:
            Booking.objects.create(
                salon=target_salon,
                customer=selected_customer,
                staff=selected_staff,
                service=selected_service,
                booking_date=random_date,
                timeslot=random_time,
                status='completed' 
            )
            count += 1

    print(f"Success! {count} historical booking records added to '{target_salon.name}'.")

if __name__ == '__main__':
    run_seed()
