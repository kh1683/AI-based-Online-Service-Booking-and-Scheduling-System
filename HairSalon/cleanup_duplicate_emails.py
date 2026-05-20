"""
One-time script to remove duplicate accounts sharing the same email.
Keeps the OLDEST account (earliest date_joined) for each email.
Run with: python manage.py shell < cleanup_duplicate_emails.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from django.contrib.auth.models import User
from django.db.models import Count, Min

# Find emails used by more than one account
dupes = (
    User.objects.values('email')
    .annotate(cnt=Count('id'), oldest=Min('id'))
    .filter(cnt__gt=1)
    .exclude(email='')  # skip blank emails
)

total_deleted = 0
for entry in dupes:
    email = entry['email']
    oldest_id = entry['oldest']
    to_delete = User.objects.filter(email=email).exclude(id=oldest_id)
    names = list(to_delete.values_list('username', flat=True))
    count = to_delete.count()
    print(f"Email: {email} — keeping id={oldest_id}, deleting {count} duplicate(s): {names}")
    to_delete.delete()
    total_deleted += count

if total_deleted == 0:
    print("No duplicate emails found. Database is clean!")
else:
    print(f"\nDone! Deleted {total_deleted} duplicate account(s).")
