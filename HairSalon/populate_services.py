import os
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from services.models import Salon, Service
from django.db.models import Q

PREDEFINED_SERVICES = [
    {
        "name": "Classic Haircut",
        "min_price": 35.00,
        "max_price": 60.00,
        "price_note": "Standard cut, does not include wash.",
        "duration_minutes": 30
    },
    {
        "name": "Hair Wash & Blow Dry",
        "min_price": 30.00,
        "max_price": 50.00,
        "price_note": "Invigorating wash and premium styling.",
        "duration_minutes": 30
    },
    {
        "name": "Premium Hair Coloring",
        "min_price": 180.00,
        "max_price": 320.00,
        "price_note": "Full color or highlights. Price varies by length.",
        "duration_minutes": 90
    },
    {
        "name": "Scalp Treatment",
        "min_price": 120.00,
        "max_price": 220.00,
        "price_note": "Deep cleaning and hair root nourishment.",
        "duration_minutes": 45
    },
    {
        "name": "Modern Perm",
        "min_price": 150.00,
        "max_price": 280.00,
        "price_note": "Cold or hot wave perm styling.",
        "duration_minutes": 120
    },
    {
        "name": "Beard Trimming & Grooming",
        "min_price": 25.00,
        "max_price": 45.00,
        "price_note": "Precision beard trim with hot towel treatment.",
        "duration_minutes": 30
    }
]

def populate_salon_services():
    salons = Salon.objects.all()
    print(f"Found {salons.count()} salons in database.")
    
    for salon in salons:
        print(f"\nProcessing salon: {salon.name} (ID: {salon.id})")
        existing_services = salon.services.all()
        existing_names = [s.name.lower() for s in existing_services]
        
        # Rule: check existing services for missing fields and update them
        for existing in existing_services:
            updated = False
            # Find matching predefined service definition
            matching = next((p for p in PREDEFINED_SERVICES if p["name"].lower() == existing.name.lower()), None)
            
            if matching:
                # Update only if fields are missing or empty
                if not existing.min_price or existing.min_price == 0.00:
                    existing.min_price = matching["min_price"]
                    updated = True
                if not existing.max_price or existing.max_price == 0.00:
                    existing.max_price = matching["max_price"]
                    updated = True
                if not existing.duration_minutes or existing.duration_minutes == 0:
                    existing.duration_minutes = matching["duration_minutes"]
                    updated = True
                if not existing.price_note or existing.price_note == "Price varies by age and hair length/style.":
                    existing.price_note = matching["price_note"]
                    updated = True
                    
            if updated:
                existing.save()
                print(f"Updated missing fields for existing service: {existing.name}")
        
        # Rule: add missing predefined services until at least 5 unique services exist
        current_count = salon.services.count()
        if current_count < 5:
            print(f"Current unique services count is {current_count} (less than 5). Adding missing predefined services...")
            for predefined in PREDEFINED_SERVICES:
                if salon.services.count() >= 5:
                    break
                if predefined["name"].lower() not in existing_names:
                    # Create service
                    Service.objects.create(
                        salon=salon,
                        name=predefined["name"],
                        min_price=predefined["min_price"],
                        max_price=predefined["max_price"],
                        price_note=predefined["price_note"],
                        duration_minutes=predefined["duration_minutes"],
                        is_active=True
                    )
                    existing_names.append(predefined["name"].lower())
                    print(f"Created service: {predefined['name']} for salon {salon.name}")
        else:
            print(f"Salon already has {current_count} services. Minimum requirement of 5 met.")

if __name__ == "__main__":
    populate_salon_services()
