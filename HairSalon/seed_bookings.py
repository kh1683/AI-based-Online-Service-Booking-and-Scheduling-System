import os
import django
import sys

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

import random
from datetime import datetime, timedelta
from django.utils import timezone
from services.models import Booking, Service, Salon, User, Staff

def run_seed():
    # 1. Configuration parameters
    SALON_NAME = "GG" # Or the salon name under your Michael account
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

    print(f"Generating historical data for {target_salon.name}...")
    
    count = 0
    # 2. Generate data for the past 30 days
    for i in range(300): # Generate 300 records
        # Random date: past 30 days
        days_ago = random.randint(0, 30)
        random_date = timezone.now().date() - timedelta(days=days_ago)
        
        # Simulate peak hours logic: booking probability is higher between 2 PM and 4 PM
        if random.random() > 0.5:
            hour = random.randint(14, 16)
        else:
            hour = random.randint(10, 19)
            
        random_time = datetime.strptime(f"{hour}:00", "%H:%M").time()

        Booking.objects.create(
            salon=target_salon,
            customer=random.choice(customers),
            staff=random.choice(staffs),
            service=random.choice(services),
            booking_date=random_date,
            timeslot=random_time,
            status='completed' 
        )
        count += 1

    print(f"Success! {count} historical booking records added.")

if __name__ == '__main__':
    run_seed()
