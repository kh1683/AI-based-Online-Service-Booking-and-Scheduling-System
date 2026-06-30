from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from .models import Salon, Staff, Service, Booking, UserProfile, SalonReview
import json

class BookingRecommendationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='customer', password='password')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = 'customer'
        profile.save()
        
        self.merchant = User.objects.create_user(username='merchant', password='password')
        m_profile, _ = UserProfile.objects.get_or_create(user=self.merchant)
        m_profile.role = 'merchant'
        m_profile.save()
        
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
        other_profile, _ = UserProfile.objects.get_or_create(user=other_user)
        other_profile.role = 'customer'
        other_profile.save()
        self.client.login(username='other_customer', password='password')
        response2 = self.client.get(f'/services/booking/{booking.id}/')
        self.assertEqual(response2.status_code, 302)


class LoginRedirectTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
    def test_login_redirect_role_none(self):
        # Create user with role='none'
        user = User.objects.create_user(username='none_user', password='password')
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'none'
        profile.save()
        
        # Log in and check redirect
        response = self.client.post('/services/accounts/login/', {
            'username': 'none_user',
            'password': 'password'
        }, follow=False)
        # Should redirect to onboarding choice
        self.assertRedirects(response, '/services/onboarding/')

    def test_login_redirect_role_customer(self):
        # Create user with role='customer'
        user = User.objects.create_user(username='customer_user', password='password')
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'customer'
        profile.save()
        
        # Log in and check redirect
        response = self.client.post('/services/accounts/login/', {
            'username': 'customer_user',
            'password': 'password'
        }, follow=False)
        # Should redirect to salon list
        self.assertRedirects(response, '/services/salon_list/')

    def test_login_redirect_role_merchant_no_salon(self):
        # Create merchant without a salon
        user = User.objects.create_user(username='merchant_user_no_salon', password='password')
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'merchant'
        profile.has_setup_salon = False
        profile.save()
        
        # Log in and check redirect
        response = self.client.post('/services/accounts/login/', {
            'username': 'merchant_user_no_salon',
            'password': 'password'
        }, follow=False)
        # Should redirect to create salon
        self.assertRedirects(response, '/services/create-salon/')

    def test_login_redirect_role_merchant_with_salon(self):
        # Create merchant with a salon
        user = User.objects.create_user(username='merchant_user_with_salon', password='password')
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.role = 'merchant'
        profile.has_setup_salon = True
        profile.save()
        
        # Create the salon associated with merchant
        Salon.objects.create(
            owner=user,
            name="Merchant Salon",
            location="Location"
        )
        
        # Log in and check redirect
        response = self.client.post('/services/accounts/login/', {
            'username': 'merchant_user_with_salon',
            'password': 'password'
        }, follow=False)
        # Should redirect to merchant dashboard
        self.assertRedirects(response, '/services/dashboard/')


class RoleAccessControlTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # User with no role selected
        self.none_user = User.objects.create_user(username='none_user', password='password')
        # UserProfile defaults to role='none'
        
        # User with customer role
        self.customer_user = User.objects.create_user(username='customer_user', password='password')
        self.customer_profile, _ = UserProfile.objects.get_or_create(user=self.customer_user)
        self.customer_profile.role = 'customer'
        self.customer_profile.save()

        # Create a test salon and service for booking test
        self.merchant = User.objects.create_user(username='merchant', password='password')
        self.merchant_profile, _ = UserProfile.objects.get_or_create(user=self.merchant)
        self.merchant_profile.role = 'merchant'
        self.merchant_profile.has_setup_salon = True
        self.merchant_profile.save()
        
        self.salon = Salon.objects.create(
            owner=self.merchant,
            name="Test Salon",
            location="Test Location"
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Classic Haircut",
            min_price=35.00,
            max_price=35.00,
            duration_minutes=30
        )

    def test_unauthenticated_user_access(self):
        # Unauthenticated users can access login, register
        response = self.client.get('/services/accounts/login/')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get('/services/register/')
        self.assertEqual(response.status_code, 200)
        
        # Unauthenticated user accessing a protected page gets redirected to login (login_required check)
        response = self.client.get('/services/dashboard/')
        self.assertRedirects(response, '/services/register/?next=/services/dashboard/')

    def test_authenticated_no_role_redirected_to_onboarding(self):
        self.client.login(username='none_user', password='password')
        
        # Try accessing salon list (protected page)
        response = self.client.get('/services/salon_list/')
        self.assertRedirects(response, '/services/onboarding/')
        
        # Try accessing booking detail page (protected page)
        response = self.client.get('/services/booking/1/')
        self.assertRedirects(response, '/services/onboarding/')
        
        # Try accessing salon dashboard (protected page)
        response = self.client.get('/services/dashboard/')
        self.assertRedirects(response, '/services/onboarding/')
        
        # Try accessing book now URL (protected page)
        response = self.client.get(f'/services/salon/{self.salon.id}/book/')
        self.assertRedirects(response, '/services/onboarding/')

    def test_authenticated_no_role_can_access_onboarding_and_logout(self):
        self.client.login(username='none_user', password='password')
        
        # Can access onboarding selection
        response = self.client.get('/services/onboarding/')
        self.assertEqual(response.status_code, 200)
        
        # Can choose a role
        response = self.client.get('/services/choose-role/customer/')
        # Redirects to salon list after choosing customer role
        self.assertRedirects(response, '/services/salon_list/')

    def test_authenticated_with_role_can_access_protected_pages(self):
        self.client.login(username='customer_user', password='password')
        
        # Can access salon list
        response = self.client.get('/services/salon_list/')
        self.assertEqual(response.status_code, 200)


class SalonSortingTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(username='customer', password='password')
        self.merchant1 = User.objects.create_user(username='merchant1', password='password')
        self.merchant2 = User.objects.create_user(username='merchant2', password='password')
        
        # Create Salons
        self.salon1 = Salon.objects.create(
            owner=self.merchant1,
            name="Salon A",
            location="Location A"
        )
        self.salon2 = Salon.objects.create(
            owner=self.merchant2,
            name="Salon B",
            location="Location B"
        )
        
        # Create Reviews
        SalonReview.objects.create(
            salon=self.salon1,
            customer=self.customer,
            rating=5,
            comment="Excellent salon!"
        )
        SalonReview.objects.create(
            salon=self.salon2,
            customer=self.customer,
            rating=3,
            comment="Average salon."
        )

        # Create Staff & Services for Bookings
        self.staff1 = Staff.objects.create(salon=self.salon1, name="Stylist A", role="Stylist", is_active=True)
        self.staff2 = Staff.objects.create(salon=self.salon2, name="Stylist B", role="Stylist", is_active=True)
        
        self.service1 = Service.objects.create(salon=self.salon1, name="Haircut", min_price=50, max_price=100, duration_minutes=30)
        self.service2 = Service.objects.create(salon=self.salon2, name="Haircut", min_price=50, max_price=100, duration_minutes=30)
        
        # Create Bookings for Salon A (1 pending, 2 completed)
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(10, 0), status='pending'
        )
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(11, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(12, 0), status='completed'
        )
        
        # Create Bookings for Salon B (3 completed)
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(10, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(11, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(12, 0), status='completed'
        )
        
    def test_reviews_retained_across_all_sorting_options(self):
        # 1. Default/Rating Sort
        response = self.client.get('/services/salon_list/', {'sort': 'rating'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salon A")
        self.assertContains(response, "Salon B")
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # Verify rating sort order (Salon A before Salon B)
        html = response.content.decode()
        self.assertLess(html.index("Salon A"), html.index("Salon B"))
        
        # 2. Newest Sort
        response = self.client.get('/services/salon_list/', {'sort': 'newest'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # 3. Popular Sort (Sorted by completed booking count, so Salon B with 3 completed bookings before Salon A with 2)
        response = self.client.get('/services/salon_list/', {'sort': 'popular'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # Verify bookings count badges
        self.assertContains(response, "2 Bookings")
        self.assertContains(response, "3 Bookings")
        
        # Verify popular sort order (Salon B before Salon A)
        html_pop = response.content.decode()
        self.assertLess(html_pop.index("Salon B"), html_pop.index("Salon A"))


class AIForecastFallbackTestCase(TestCase):
    def test_forecast_fallback_when_data_is_sparse(self):
        from .ai_logic import get_ai_forecast
        
        # Test with salon ID that has zero booking records (data is sparse/insufficient)
        labels, values = get_ai_forecast(9999)
        
        # Should return the specific fallback demo dataset
        expected_labels = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"]
        expected_values = [0.7, 1.1, 1.4, 1.2, 1.0, 0.9, 1.1, 1.5, 1.4, 0.8]
        
        self.assertEqual(labels, expected_labels)
        self.assertEqual(values, expected_values)


class AIDashboardForecastSummaryTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant = User.objects.create_user(username='merchant_dashboard_user', password='password')
        profile, _ = UserProfile.objects.get_or_create(user=self.merchant)
        profile.role = 'merchant'
        profile.has_setup_salon = True
        profile.save()
        
        self.salon = Salon.objects.create(
            owner=self.merchant,
            name="Merchant Salon A",
            location="Location A"
        )
        self.client.login(username='merchant_dashboard_user', password='password')
        
    def test_dynamic_forecast_summary_rendering(self):
        response = self.client.get('/services/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Verify the dynamically generated forecast summary context exists
        self.assertIn('forecast_peak_hour', response.context)
        self.assertIn('forecast_demand_level', response.context)
        self.assertIn('forecast_recommended_action', response.context)
        
        # Verify the HTML contains the expected summary values derived from fallback data (since no bookings exist)
        # Fallback values peak at 17:00 (5:00 PM) with 1.5 expected customers -> Peak Hour: 5:00 PM - 6:00 PM, Demand: Medium
        self.assertEqual(response.context['forecast_peak_hour'], "5:00 PM - 6:00 PM")
        self.assertEqual(response.context['forecast_demand_level'], "Medium")
        self.assertEqual(response.context['forecast_recommended_action'], "Monitor bookings during peak periods.")
        
        self.assertContains(response, "5:00 PM - 6:00 PM")
        self.assertContains(response, "Medium")
        self.assertContains(response, "Monitor bookings during peak periods.")


class DynamicServiceFiltersTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant1 = User.objects.create_user(username='merchant1_df', password='password')
        self.merchant2 = User.objects.create_user(username='merchant2_df', password='password')
        
        self.salon1 = Salon.objects.create(owner=self.merchant1, name="Salon Alpha", location="Alpha Location")
        self.salon2 = Salon.objects.create(owner=self.merchant2, name="Salon Beta", location="Beta Location")
        
        # Only setup a haircut service for salon1, and coloring service for salon2
        self.service1 = Service.objects.create(
            salon=self.salon1,
            name="Classic Haircut",
            min_price=40,
            max_price=80,
            duration_minutes=30,
            is_active=True
        )
        self.service2 = Service.objects.create(
            salon=self.salon2,
            name="Premium Coloring",
            min_price=150,
            max_price=250,
            duration_minutes=90,
            is_active=True
        )
        
    def test_dynamic_service_filters_list_and_filtering(self):
        response = self.client.get('/services/salon_list/')
        self.assertEqual(response.status_code, 200)
        
        # Assert that ONLY categories with active matching services in the database are returned in filters
        # Haircut (via self.service1) and Hair Coloring (via self.service2) should exist
        # Treatment, Wash, and Grooming should NOT exist since no active services match them
        filter_values = [f["value"] for f in response.context["dynamic_service_filters"]]
        self.assertIn("haircut", filter_values)
        self.assertIn("coloring", filter_values)
        self.assertNotIn("treatment", filter_values)
        self.assertNotIn("wash", filter_values)
        self.assertNotIn("grooming", filter_values)
        
        # Verify All Services shows both salons
        self.assertContains(response, "Salon Alpha")
        self.assertContains(response, "Salon Beta")
        
        # Verify filtering by Haircut shows Salon Alpha but NOT Salon Beta
        response_haircut = self.client.get('/services/salon_list/', {'service': 'haircut'})
        self.assertEqual(response_haircut.status_code, 200)
        self.assertContains(response_haircut, "Salon Alpha")
        self.assertNotContains(response_haircut, "Salon Beta")
        
        # Verify filtering by Coloring shows Salon Beta but NOT Salon Alpha
        response_coloring = self.client.get('/services/salon_list/', {'service': 'coloring'})
        self.assertEqual(response_coloring.status_code, 200)
        self.assertContains(response_coloring, "Salon Beta")
        self.assertNotContains(response_coloring, "Salon Alpha")


class DynamicAIRecommendationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant = User.objects.create_user(username='merchant_rec', password='password')
        self.salon = Salon.objects.create(owner=self.merchant, name="Salon Recommendation", location="Location Rec")

    def test_recommended_slots_dynamic_evaluation(self):
        response = self.client.get('/services/salon_list/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('recommended_slots', response.context)
        
        # Recommendation slots should have exactly 3 slots
        slots = response.context['recommended_slots']
        self.assertEqual(len(slots), 3)
        
        self.service1 = Service.objects.create(salon=self.salon1, name="Haircut", min_price=50, max_price=100, duration_minutes=30)
        self.service2 = Service.objects.create(salon=self.salon2, name="Haircut", min_price=50, max_price=100, duration_minutes=30)
        
        # Create Bookings for Salon A (1 pending, 2 completed)
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(10, 0), status='pending'
        )
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(11, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon1, customer=self.customer, staff=self.staff1, service=self.service1,
            booking_date=date.today(), timeslot=time(12, 0), status='completed'
        )
        
        # Create Bookings for Salon B (3 completed)
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(10, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(11, 0), status='completed'
        )
        Booking.objects.create(
            salon=self.salon2, customer=self.customer, staff=self.staff2, service=self.service2,
            booking_date=date.today(), timeslot=time(12, 0), status='completed'
        )
        
    def test_reviews_retained_across_all_sorting_options(self):
        # 1. Default/Rating Sort
        response = self.client.get('/services/salon_list/', {'sort': 'rating'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salon A")
        self.assertContains(response, "Salon B")
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # Verify rating sort order (Salon A before Salon B)
        html = response.content.decode()
        self.assertLess(html.index("Salon A"), html.index("Salon B"))
        
        # 2. Newest Sort
        response = self.client.get('/services/salon_list/', {'sort': 'newest'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # 3. Popular Sort (Sorted by completed booking count, so Salon B with 3 completed bookings before Salon A with 2)
        response = self.client.get('/services/salon_list/', {'sort': 'popular'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent salon!")
        self.assertContains(response, "Average salon.")
        self.assertContains(response, "5.0")
        self.assertContains(response, "3.0")
        
        # Verify bookings count badges
        self.assertContains(response, "2 Bookings")
        self.assertContains(response, "3 Bookings")
        
        # Verify popular sort order (Salon B before Salon A)
        html_pop = response.content.decode()
        self.assertLess(html_pop.index("Salon B"), html_pop.index("Salon A"))


class AIForecastFallbackTestCase(TestCase):
    def test_forecast_fallback_when_data_is_sparse(self):
        from .ai_logic import get_ai_forecast
        
        # Test with salon ID that has zero booking records (data is sparse/insufficient)
        labels, values = get_ai_forecast(9999)
        
        # Should return the specific fallback demo dataset
        expected_labels = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"]
        expected_values = [0.7, 1.1, 1.4, 1.2, 1.0, 0.9, 1.1, 1.5, 1.4, 0.8]
        
        self.assertEqual(labels, expected_labels)
        self.assertEqual(values, expected_values)


class AIDashboardForecastSummaryTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant = User.objects.create_user(username='merchant_dashboard_user', password='password')
        profile, _ = UserProfile.objects.get_or_create(user=self.merchant)
        profile.role = 'merchant'
        profile.has_setup_salon = True
        profile.save()
        
        self.salon = Salon.objects.create(
            owner=self.merchant,
            name="Merchant Salon A",
            location="Location A"
        )
        self.client.login(username='merchant_dashboard_user', password='password')
        
    def test_dynamic_forecast_summary_rendering(self):
        response = self.client.get('/services/dashboard/')
        self.assertEqual(response.status_code, 200)
        
        # Verify the dynamically generated forecast summary context exists
        self.assertIn('forecast_peak_hour', response.context)
        self.assertIn('forecast_demand_level', response.context)
        self.assertIn('forecast_recommended_action', response.context)
        
        # Verify the HTML contains the expected summary values derived from fallback data (since no bookings exist)
        # Fallback values peak at 17:00 (5:00 PM) with 1.5 expected customers -> Peak Hour: 5:00 PM - 6:00 PM, Demand: Medium
        self.assertEqual(response.context['forecast_peak_hour'], "5:00 PM - 6:00 PM")
        self.assertEqual(response.context['forecast_demand_level'], "Medium")
        self.assertEqual(response.context['forecast_recommended_action'], "Monitor bookings during peak periods.")
        
        self.assertContains(response, "5:00 PM - 6:00 PM")
        self.assertContains(response, "Medium")
        self.assertContains(response, "Monitor bookings during peak periods.")


class DynamicServiceFiltersTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant1 = User.objects.create_user(username='merchant1_df', password='password')
        self.merchant2 = User.objects.create_user(username='merchant2_df', password='password')
        
        self.salon1 = Salon.objects.create(owner=self.merchant1, name="Salon Alpha", location="Alpha Location")
        self.salon2 = Salon.objects.create(owner=self.merchant2, name="Salon Beta", location="Beta Location")
        
        # Only setup a haircut service for salon1, and coloring service for salon2
        self.service1 = Service.objects.create(
            salon=self.salon1,
            name="Classic Haircut",
            min_price=40,
            max_price=80,
            duration_minutes=30,
            is_active=True
        )
        self.service2 = Service.objects.create(
            salon=self.salon2,
            name="Premium Coloring",
            min_price=150,
            max_price=250,
            duration_minutes=90,
            is_active=True
        )
        
    def test_dynamic_service_filters_list_and_filtering(self):
        response = self.client.get('/services/salon_list/')
        self.assertEqual(response.status_code, 200)
        
        # Assert that ONLY categories with active matching services in the database are returned in filters
        # Haircut (via self.service1) and Hair Coloring (via self.service2) should exist
        # Treatment, Wash, and Grooming should NOT exist since no active services match them
        filter_values = [f["value"] for f in response.context["dynamic_service_filters"]]
        self.assertIn("haircut", filter_values)
        self.assertIn("coloring", filter_values)
        self.assertNotIn("treatment", filter_values)
        self.assertNotIn("wash", filter_values)
        self.assertNotIn("grooming", filter_values)
        
        # Verify All Services shows both salons
        self.assertContains(response, "Salon Alpha")
        self.assertContains(response, "Salon Beta")
        
        # Verify filtering by Haircut shows Salon Alpha but NOT Salon Beta
        response_haircut = self.client.get('/services/salon_list/', {'service': 'haircut'})
        self.assertEqual(response_haircut.status_code, 200)
        self.assertContains(response_haircut, "Salon Alpha")
        self.assertNotContains(response_haircut, "Salon Beta")
        
        # Verify filtering by Coloring shows Salon Beta but NOT Salon Alpha
        response_coloring = self.client.get('/services/salon_list/', {'service': 'coloring'})
        self.assertEqual(response_coloring.status_code, 200)
        self.assertContains(response_coloring, "Salon Beta")
        self.assertNotContains(response_coloring, "Salon Alpha")


class DynamicAIRecommendationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant = User.objects.create_user(username='merchant_rec', password='password')
        self.salon = Salon.objects.create(owner=self.merchant, name="Salon Recommendation", location="Location Rec")

    def test_recommended_slots_dynamic_evaluation(self):
        response = self.client.get('/services/salon_list/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('recommended_slots', response.context)
        
        # Recommendation slots should have exactly 3 slots
        slots = response.context['recommended_slots']
        self.assertEqual(len(slots), 3)
        
        # Verify that all slots are in AM/PM format
        for slot in slots:
            self.assertTrue("AM" in slot or "PM" in slot)


class SalonContactNumberValidationTestCase(TestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='merchant_test', password='password')
        self.merchant2 = User.objects.create_user(username='merchant_test2', password='password')

    def test_valid_contact_numbers(self):
        # 11 digits
        salon = Salon(owner=self.merchant, name="S1", location="L1", contact_number="12345678901")
        salon.full_clean()  # should not raise
        salon.save()

        # 12 digits
        salon2 = Salon(owner=self.merchant2, name="S2", location="L2", contact_number="123456789012")
        salon2.full_clean()  # should not raise
        salon2.save()

    def test_invalid_contact_numbers(self):
        from django.core.exceptions import ValidationError
        
        # Less than 11 digits (10 digits)
        salon = Salon(owner=self.merchant, name="S1", location="L1", contact_number="1234567890")
        with self.assertRaises(ValidationError):
            salon.full_clean()

        # More than 12 digits (13 digits)
        salon = Salon(owner=self.merchant, name="S1", location="L1", contact_number="1234567890123")
        with self.assertRaises(ValidationError):
            salon.full_clean()

        # Non-digits
        salon = Salon(owner=self.merchant, name="S1", location="L1", contact_number="1234567890a")
        with self.assertRaises(ValidationError):
            salon.full_clean()

    def test_form_validation(self):
        from services.forms import SalonForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Valid form data
        data_valid = {
            'name': 'Valid Salon',
            'location': 'Address',
            'contact_number': '12345678901',
            'business_hours': '10:00 AM - 07:00 PM',
            'description': 'Desc',
        }
        # 1x1 or 100x100 valid PNG bytes
        valid_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d\x00\x00\x00d\x08\x02\x00\x00\x00\xff\x80\x02\x03\x00\x00\x004IDATx\x9c\xed\xc1\x01\r\x00\x00\x00\xc2\xa0\xf7Om\x0e7\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xba1u\x94\x00\x01{\x98\xd2\xac\x00\x00\x00\x00IEND\xaeB`\x82'
        test_image = SimpleUploadedFile("salon.png", valid_png_bytes, content_type="image/png")
        files = {'image': test_image}

        form = SalonForm(data=data_valid, files=files)
        self.assertTrue(form.is_valid(), form.errors)

        # Invalid form data: too short
        data_invalid = data_valid.copy()
        data_invalid['contact_number'] = '1234567890'
        form = SalonForm(data=data_invalid, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('contact_number', form.errors)

        # Invalid form data: too long
        data_invalid['contact_number'] = '1234567890123'
        form = SalonForm(data=data_invalid, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn('contact_number', form.errors)
