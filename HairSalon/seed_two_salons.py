import os
import shutil
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from django.contrib.auth.models import User
from services.models import Salon, Staff, Service, UserProfile

# Paths
BRAIN_DIR = r"C:\Users\User\Network (Fake Path if applicable) or Local Path"
# Real path: C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739
brain_dir = r"C:\Users\User\AppData\Local\Temp" # fallback or let's detect it
# Let's specify exact paths
SOURCE_IMAGES = {
    'salon1': r"C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739\media__1781108792815.png",
    'salon2': r"C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739\media__1781108793198.png",
    'staff1': r"C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739\media__1781108792648.png",
    'staff2': r"C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739\media__1781108792974.png",
    'staff3': r"C:\Users\User\.gemini\antigravity-ide\brain\66f47d9d-21bf-4b7e-a666-aa611a524739\media__1781108793061.png",
}

DEST_SALONS_DIR = r"media\salons"
DEST_STAFF_DIR = r"media\staff_images"

# Ensure directories exist
os.makedirs(DEST_SALONS_DIR, exist_ok=True)
os.makedirs(DEST_STAFF_DIR, exist_ok=True)

# File names
SALON1_IMG_REL = "salons/signature_style.png"
SALON2_IMG_REL = "salons/hair_style.png"
STAFF1_IMG_REL = "staff_images/marcus_vance.png"
STAFF2_IMG_REL = "staff_images/sophia_lin.png"
STAFF3_IMG_REL = "staff_images/ethan_hunt.png"

# Copy images
shutil.copy(SOURCE_IMAGES['salon1'], os.path.join("media", SALON1_IMG_REL))
shutil.copy(SOURCE_IMAGES['salon2'], os.path.join("media", SALON2_IMG_REL))
shutil.copy(SOURCE_IMAGES['staff1'], os.path.join("media", STAFF1_IMG_REL))
shutil.copy(SOURCE_IMAGES['staff2'], os.path.join("media", STAFF2_IMG_REL))
shutil.copy(SOURCE_IMAGES['staff3'], os.path.join("media", STAFF3_IMG_REL))
print("Images copied successfully!")

# Helper to create user & profile
def create_merchant_user(username, email, password):
    user, created = User.objects.get_or_create(username=username, defaults={'email': email})
    if created or not user.check_password(password):
        user.set_password(password)
        user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = 'merchant'
    profile.has_setup_salon = True
    profile.save()
    return user

# Create merchant users
owner1 = create_merchant_user("sigstyle_owner", "owner1@signaturestyle.com", "password123")
owner2 = create_merchant_user("hairstyle_owner", "owner2@hairstyle.com", "password123")
print("Merchant users created/updated!")

# Create Salons
salon1, created1 = Salon.objects.update_or_create(
    owner=owner1,
    defaults={
        'name': "Signature Style Hair Salon",
        'location': "Level 2, Premium Fashion Block, Midtown Shopping Mall, Kuala Lumpur",
        'contact_number': "60321668822",
        'business_hours': "10:00 AM - 07:00 PM",
        'description': "At Signature Style, we believe your hair is your ultimate accessory. Our top-tier stylists specialize in couture haircuts, precision coloring, and bespoke treatments designed to bring out your unique personality.",
        'image': SALON1_IMG_REL
    }
)
print(f"Salon 1: {salon1.name} (Created: {created1})")

salon2, created2 = Salon.objects.update_or_create(
    owner=owner2,
    defaults={
        'name': "Hair Style Salon",
        'location': "No. 15, Ground Floor, Jalan Telawi 3, Bangsar, Kuala Lumpur",
        'contact_number': "60322849911",
        'business_hours': "10:00 AM - 07:00 PM",
        'description': "Classic cuts, modern styling, and exceptional service. Hair Style Salon is your neighborhood destination for clean trims, fresh styling, and premium hair treatments in a warm, welcoming environment.",
        'image': SALON2_IMG_REL
    }
)
print(f"Salon 2: {salon2.name} (Created: {created2})")

# Create Stylists for Salon 1
staff1, s_created1 = Staff.objects.update_or_create(
    salon=salon1,
    name="Marcus Vance",
    defaults={
        'role': "Senior Stylist & Barber",
        'specialty': "Couture Haircuts & Beard Grooming",
        'phone': "+60 12-345 6789",
        'image': STAFF1_IMG_REL,
        'is_active': True
    }
)
print(f"Stylist Marcus Vance (Created: {s_created1})")

staff2, s_created2 = Staff.objects.update_or_create(
    salon=salon1,
    name="Sophia Lin",
    defaults={
        'role': "Master Colorist",
        'specialty': "Balayage, Pastel Tones & Keratin Treatment",
        'phone': "+60 12-987 6543",
        'image': STAFF2_IMG_REL,
        'is_active': True
    }
)
print(f"Stylist Sophia Lin (Created: {s_created2})")

# Create Stylist for Salon 2
staff3, s_created3 = Staff.objects.update_or_create(
    salon=salon2,
    name="Ethan Hunt",
    defaults={
        'role': "Senior Hair Designer",
        'specialty': "Modern Fades, Textured Crop & Styling",
        'phone': "+60 17-654 3210",
        'image': STAFF3_IMG_REL,
        'is_active': True
    }
)
print(f"Stylist Ethan Hunt (Created: {s_created3})")

# Add default services for Salon 1
services_salon1 = [
    ("Signature Haircut", 60.00, 100.00, "Includes wash, scalp massage, and expert blow style.", 45),
    ("Premium Hair Coloring & Balayage", 250.00, 450.00, "Price varies by hair length and thickness.", 120),
    ("Scalp & Keratin Treatment", 180.00, 300.00, "Deep nourishment and frizz-free repair.", 60),
]
for name, min_p, max_p, note, dur in services_salon1:
    Service.objects.update_or_create(
        salon=salon1,
        name=name,
        defaults={
            'min_price': min_p,
            'max_price': max_p,
            'price_note': note,
            'duration_minutes': dur,
            'is_active': True
        }
    )

# Add default services for Salon 2
services_salon2 = [
    ("Classic Trim & Styling", 45.00, 70.00, "Clean standard haircut with styling gel/pomade.", 30),
    ("Hair Wash & Blow Dry", 30.00, 50.00, "Invigorating wash with premium shampoo and styling.", 30),
    ("Modern Men's Grooming", 50.00, 80.00, "Includes modern skin fade and beard trim/grooming.", 45),
]
for name, min_p, max_p, note, dur in services_salon2:
    Service.objects.update_or_create(
        salon=salon2,
        name=name,
        defaults={
            'min_price': min_p,
            'max_price': max_p,
            'price_note': note,
            'duration_minutes': dur,
            'is_active': True
        }
    )

print("Services created successfully!")
print("All seeding completed!")
