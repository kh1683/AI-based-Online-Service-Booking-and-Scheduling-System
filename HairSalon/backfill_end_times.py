import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

from services.models import Booking

def update_end_times():
    bookings = Booking.objects.filter(end_time__isnull=True)
    count = 0
    for b in bookings:
        if b.timeslot and b.service:
            start_dt = datetime.combine(datetime.today(), b.timeslot)
            end_dt = start_dt + timedelta(minutes=b.service.duration_minutes)
            b.end_time = end_dt.time()
            b.save()
            count += 1
    print(f"Updated {count} bookings with end_time.")

if __name__ == "__main__":
    update_end_times()
