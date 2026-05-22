from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from .models import Salon, Staff, Service, Booking
import json

class BookingRecommendationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='customer', password='password')
        self.merchant = User.objects.create_user(username='merchant', password='password')
        self.salon = Salon.objects.create(
            owner=self.merchant,
            name="Test Salon",
            location="Test Location"
        )
        self.staff1 = Staff.objects.create(
            salon=self.salon,
            name="Stylist 1",
            role="Stylist",
            is_active=True
        )
        self.staff2 = Staff.objects.create(
            salon=self.salon,
            name="Stylist 2",
            role="Stylist",
            is_active=True
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Haircut",
            min_price=50.00,
            max_price=100.00,
            duration_minutes=60
        )
        self.client.login(username='customer', password='password')

    def test_past_slots_removed_for_today(self):
        # Determine today's date
        now_local = timezone.localtime(timezone.now())
        today_str = now_local.strftime('%Y-%m-%d')
        
        response = self.client.get(
            '/services/api/ai-recommendations/',
            {
                'salon_id': self.salon.id,
                'date': today_str,
                'service_id': self.service.id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        # Ensure all returned slots are in the future relative to now
        current_time = now_local.time()
        for slot in data['recommended_slots']:
            slot_time = datetime.strptime(slot, '%H:%M').time()
            self.assertGreater(slot_time, current_time)

    def test_booked_slots_excluded(self):
        # Test for tomorrow to avoid current time restrictions
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Book staff1 and staff2 at 11:00 AM tomorrow
        Booking.objects.create(
            salon=self.salon,
            customer=self.user,
            staff=self.staff1,
            service=self.service,
            booking_date=tomorrow,
            timeslot=time(11, 0),
            status='confirmed'
        )
        Booking.objects.create(
            salon=self.salon,
            customer=self.user,
            staff=self.staff2,
            service=self.service,
            booking_date=tomorrow,
            timeslot=time(11, 0),
            status='confirmed'
        )
        
        # Request recommendations for Auto Arrange
        response = self.client.get(
            '/services/api/ai-recommendations/',
            {
                'salon_id': self.salon.id,
                'date': tomorrow_str,
                'service_id': self.service.id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 11:00 should not be available because both stylists are booked!
        self.assertNotIn('11:00', data['recommended_slots'])

    def test_specific_stylist_slots(self):
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Book staff1 at 11:00 AM tomorrow
        Booking.objects.create(
            salon=self.salon,
            customer=self.user,
            staff=self.staff1,
            service=self.service,
            booking_date=tomorrow,
            timeslot=time(11, 0),
            status='confirmed'
        )
        
        # Query for staff1 specifically
        response = self.client.get(
            '/services/api/ai-recommendations/',
            {
                'salon_id': self.salon.id,
                'date': tomorrow_str,
                'service_id': self.service.id,
                'staff_id': self.staff1.id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_optimal'])
        self.assertNotIn('11:00', data['recommended_slots'])
        # staff1 should still have other slots available (e.g. 10:00, 12:00, etc.)
        self.assertIn('10:00', data['recommended_slots'])
        self.assertIn('12:00', data['recommended_slots'])
        
        # Query for staff2 specifically (who is free at 11:00 AM)
        response2 = self.client.get(
            '/services/api/ai-recommendations/',
            {
                'salon_id': self.salon.id,
                'date': tomorrow_str,
                'service_id': self.service.id,
                'staff_id': self.staff2.id
            }
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertIn('11:00', data2['recommended_slots'])

    def test_booking_detail_view_permissions(self):
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.user,
            staff=self.staff1,
            service=self.service,
            booking_date=tomorrow,
            timeslot=time(14, 0),
            status='confirmed'
        )

        # Access by authorized customer
        response = self.client.get(f'/services/booking/{booking.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Booking Details")
        self.assertContains(response, "Test Salon")

        # Access by another customer (unauthorized) -> Redirects to home
        other_user = User.objects.create_user(username='other_customer', password='password')
        self.client.login(username='other_customer', password='password')
        response2 = self.client.get(f'/services/booking/{booking.id}/')
        self.assertEqual(response2.status_code, 302)

