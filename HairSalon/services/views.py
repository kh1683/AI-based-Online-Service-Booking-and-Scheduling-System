from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Salon, Staff, Service, Booking, UserProfile
from .forms import StaffForm, ServiceForm, BookingForm, SalonForm, UserForm, UserProfileForm, SalonLocationForm, SalonImageForm
from datetime import date, timedelta
from django.db.models import Count, Q, Avg
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import login, update_session_auth_hash
from django import forms
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages

from datetime import datetime,time
import random
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from .ai_logic import get_ai_forecast, get_optimal_time_slots

@login_required
def salon_dashboard(request):
    
    
    if hasattr(request.user, 'staff_profile'):
        return redirect('staff_schedule') 

    
    try:
        salon = Salon.objects.get(owner=request.user)
    except Salon.DoesNotExist:
        return redirect('')  


    salon = get_object_or_404(Salon, owner=request.user)
    staff_count = Staff.objects.filter(salon=salon, is_active=True).count()
    service_count = Service.objects.filter(salon=salon, is_active=True).count()
    
    pending_bookings_list = Booking.objects.filter(salon=salon, status='pending')
    
    
    pending_count = pending_bookings_list.count()
    
    
    staffs = salon.staffs.all()
    services = salon.services.all()
    
    forecast_data = get_ai_forecast(salon.id)
    if forecast_data:
        forecast_labels, forecast_values = forecast_data
    else:
        forecast_labels, forecast_values = [], []
    
    # 2. 新增：统计最受欢迎的服务类型 (Popular Service Types)
    service_counts = Booking.objects.filter(service__salon=salon)\
        .values('service__name')\
        .annotate(count=Count('id'))\
        .order_by('-count')

    service_labels = [item['service__name'] for item in service_counts]
    service_data = [item['count'] for item in service_counts]

    # 3. 新增：基本 KPIs 计数器
    total_bookings = Booking.objects.filter(service__salon=salon).count()
    pending_bookings_count = Booking.objects.filter(service__salon=salon, status='pending').count()
    
    today = date.today()
    hourly_stats = salon.bookings.filter(booking_date=today, status='confirmed') \
                    .values('timeslot') \
                    .annotate(count=Count('id')) \
                    .order_by('timeslot')
    busy_slots = [item['timeslot'].strftime('%H:%M') for item in hourly_stats if item['count'] >= 2]
    
    pending_bookings = salon.bookings.filter(status='pending').order_by('booking_date', 'timeslot')
    confirmed_bookings = salon.bookings.filter(status='confirmed').order_by('booking_date', 'timeslot')
    
    for b in pending_bookings:
        is_conflicted = salon.bookings.filter(
            staff=b.staff,
            booking_date=b.booking_date,
            timeslot=b.timeslot,
            status='confirmed' 
        ).exists()
        
        b.is_real_conflict = is_conflicted
    
    return render(request, 'services/dashboard.html', {
        'salon': salon,
        'staffs': staffs,
        'services': services,
        'pending_bookings': pending_bookings,  
        'confirmed_bookings': confirmed_bookings, 
        'busy_slots': busy_slots,
        'hourly_stats': hourly_stats,
        
        'forecast_labels': forecast_labels,
        'forecast_values': forecast_values,
        'service_labels': service_labels,
        'service_data': service_data,
        'total_bookings': total_bookings,
        'pending_bookings_count': pending_bookings_count,
        
        'staff_count': staff_count,
        'service_count': service_count,
        'pending_bookings_list': pending_bookings_list,  
        'pending_count': pending_count,
    })
    
# @login_required
# def add_staff(request):
#     salon = Salon.objects.get(owner=request.user)
#     if request.method == 'POST':
#         form = StaffForm(request.POST)
#         if form.is_valid():
#             staff = form.save(commit=False)

#             staff.save()
#             return redirect('dashboard')
#     else:
#         form = StaffForm()
#     return render(request, 'services/add_staff.html', {'form': form})


# @login_required
# def add_service(request):
#     salon = Salon.objects.get(owner=request.user)
#     if request.method == 'POST':
#         form = ServiceForm(request.POST)
#         if form.is_valid():
#             service = form.save(commit=False)

#             service.save()
#             return redirect('dashboard')
#     else:
#         form = ServiceForm()
#     return render(request, 'services/add_service.html', {'form': form})



@login_required
def create_booking(request, salon_id):
    # Block merchants from making bookings
    user_profile = getattr(request.user, 'userprofile', None)
    if user_profile and user_profile.role == 'merchant':
        messages.error(request, 'Merchants cannot make bookings. Please use a customer account.')
        return redirect('salon_list')

    salon = Salon.objects.get(id=salon_id)
    
    # Calculate Cancel URL dynamically
    from django.urls import reverse
    selected_staff_id = request.GET.get('staff') or request.POST.get('staff')
    cancel_to = request.GET.get('cancel_to') or request.POST.get('cancel_to')
    
    if cancel_to == 'staff' and selected_staff_id:
        cancel_url = reverse('staff_detail', kwargs={'staff_id': selected_staff_id})
    else:
        cancel_url = reverse('salon_detail', kwargs={'salon_id': salon.id})
        
    context = {
        'salon': salon,
        'cancel_url': cancel_url
    }
    
    if request.method == 'POST':
        date_str = request.POST.get('booking_date') 
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        form = BookingForm(request.POST, salon=salon)
        if form.is_valid():
            booking = form.save(commit=False)
            
            now_local = timezone.localtime(timezone.now())
            today = now_local.date()
            # 🚩 Validation 1: Check if date is in the past
            if booking.booking_date < today:
                messages.error(request, "You cannot book a date in the past!")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {**context, 'form': form})
            
            # 🚩 2. Operating hours interception：10:00 - 19:00 (7 p.m.)
            start_time = time(10, 0) # 10:00 AM
            end_time = time(19, 0)   # 07:00 PM
            
            if not (start_time <= booking.timeslot <= end_time):
                messages.error(request, f"❌ Booking failed! Salon operating hours are 10:00 AM - 07:00 PM.")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {**context, 'form': form})

            # 🚩 3. If today, check if time has passed
            if booking.booking_date == today and booking.timeslot < now_local.time():
                messages.error(request, "❌ This time has already passed. Please select a later time.")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {**context, 'form': form})

            
            booking.salon = salon
            booking.customer = request.user 
            # Calculate new booking's expected end time
            new_start_dt = datetime.combine(date.today(), booking.timeslot)
            new_end_dt = new_start_dt + timedelta(minutes=booking.service.duration_minutes)
            new_end_time = new_end_dt.time()

            if not getattr(booking, 'staff_id', None):
                active_staffs = Staff.objects.filter(salon=salon, is_active=True)
                available_staff = None
                
                for staff in active_staffs:
                    # Overlap logic: (existing_start < new_end) AND (existing_end > new_start)
                    conflict = Booking.objects.filter(
                        staff=staff,
                        booking_date=booking.booking_date,
                        status__in=['pending', 'confirmed']
                    ).filter(
                        timeslot__lt=new_end_time,
                        end_time__gt=booking.timeslot
                    ).exists()
                    
                    if not conflict:
                        available_staff = staff
                        break
                
                if available_staff:
                    booking.staff = available_staff
                    booking.status = 'confirmed'
                    messages.success(request, f'Appointment booked! You have been auto-assigned to {available_staff.name}.')
                    booking.save()
                    return redirect('my_bookings')
                else:
                    messages.error(request, "❌ Sorry, no stylists are available at this time due to overlapping appointments. Please choose another time.")
                    form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                    form.fields['service'].queryset = Service.objects.filter(salon=salon)
                    return render(request, 'services/create_booking.html', {**context, 'form': form})

            else:
                # Specific staff check with overlap logic
                conflict = Booking.objects.filter(
                    staff=booking.staff,
                    booking_date=booking.booking_date,
                    status__in=['pending', 'confirmed']
                ).filter(
                    timeslot__lt=new_end_time,
                    end_time__gt=booking.timeslot
                ).exists()
                if conflict:
                    messages.error(request, f"❌ Sorry, {booking.staff.name} is busy during this time (including service cooling time). Please choose another time or stylist.")
                    form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                    form.fields['service'].queryset = Service.objects.filter(salon=salon)
                    return render(request, 'services/create_booking.html', {**context, 'form': form})
                
                booking.status = 'confirmed'
                booking.save()
                messages.success(request, f'Appointment confirmed with {booking.staff.name}!')
                return redirect('my_bookings')
            
           
    else:
        selected_service_id = request.GET.get('service')
        selected_staff_id = request.GET.get('staff')
        selected_date = request.GET.get('date')
        selected_time = request.GET.get('time')
        initial_data = {}
        if selected_service_id:
            initial_data['service'] = selected_service_id
        if selected_staff_id:
            initial_data['staff'] = selected_staff_id
        if selected_date:
            initial_data['booking_date'] = selected_date
        if selected_time:
            initial_data['timeslot'] = selected_time
        form = BookingForm(salon=salon, initial=initial_data)
        form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True) 
        form.fields['service'].queryset = Service.objects.filter(salon=salon)
    return render(request, 'services/create_booking.html', {**context, 'form': form})
    
@login_required
def approve_booking(request, booking_id):
    
    booking = get_object_or_404(Booking, id=booking_id, salon__owner=request.user)
    booking.status = 'confirmed'
    booking.save()
    return redirect('dashboard')

@login_required
def reject_booking(request, booking_id):
    
    booking = get_object_or_404(Booking, id=booking_id, salon__owner=request.user)
    
    
    
    booking.status = 'cancelled'
    booking.save()
    
    return redirect('dashboard')

@login_required
def staff_schedule(request):
    
    try:
        staff_profile = request.user.staff_profile
    except Staff.DoesNotExist:
        
        return render(request, 'services/error.html', {'message': 'You are not a registered staff, cannot view schedule'})

    
    my_tasks = Booking.objects.filter(
        staff=staff_profile, 
        status='confirmed'
    ).order_by('booking_date', 'timeslot')

    return render(request, 'services/staff_schedule.html', {
        'staff': staff_profile,
        'tasks': my_tasks
    })
    
    
    

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Please enter your email address")

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please use a different email or log in.")
        return email
        
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('onboarding_choice') 
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def onboarding_choice(request):
    
    
    if hasattr(request.user, 'salon'):
        return redirect('dashboard')
    return render(request, 'services/onboarding_choice.html')    
    
def create_salon(request):
    
    profile = request.user.userprofile
    if profile.role != 'merchant':
        return redirect('home')

    
    
    existing_salon = Salon.objects.filter(owner=request.user).first()

    if request.method == 'POST':
        
        if existing_salon:
            return redirect('dashboard')
        form = SalonForm(request.POST, request.FILES) 
        if form.is_valid():
            salon = form.save(commit=False)
            salon.owner = request.user 
            salon.save()
            
            
            profile.has_setup_salon = True
            profile.save()
            
            messages.success(request, "Salon created successfully! Welcome to your dashboard.")
            return redirect('dashboard')
    else:
        
        if existing_salon:
            messages.info(request, "You already have a salon.")
            return redirect('dashboard')
        form = SalonForm()
    return render(request, 'services/create_salon.html', {'form': form})

def salon_list(request):
    from .models import Salon
    from django.db.models import Avg
    salons = Salon.objects.all()
    for s in salons:
        s_reviews = s.reviews.all().order_by('-created_at')
        s_avg = s_reviews.aggregate(Avg('rating'))['rating__avg']
        s.avg_rating = round(s_avg, 1) if s_avg is not None else None
        s.reviews_count = s_reviews.count()
        s.latest_review = s_reviews.first()
    return render(request, 'services/salon_list.html', {'salons': salons})  

@login_required
def merchant_dashboard(request):
    salon = getattr(request.user, 'salon', None)
    if not salon:
        return redirect('create_salon')

    # 调用 AI 逻辑
    forecast_data = get_ai_forecast(salon.id)
    
    if forecast_data:
        labels, values = forecast_data
    else:
        # 数据不足时的保底数据
        labels, values = [], []

    return render(request, 'services/dashboard.html', {
        'forecast_labels': labels,
        'forecast_values': values,
    })

@login_required
def my_bookings(request):
    """View list of bookings for the logged-in customer with pagination."""
    bookings_list = Booking.objects.filter(customer=request.user).order_by('-booking_date', '-timeslot')
    
    paginator = Paginator(bookings_list, 10) # Show 10 bookings per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get elided page range (available in Django 3.2+)
    elided_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
    
    return render(request, 'services/my_bookings.html', {
        'page_obj': page_obj,
        'elided_page_range': elided_page_range
    })


@login_required
def cancel_booking(request, booking_id):
    """Let customers cancel their own bookings, or salon owners cancel their salon's bookings."""
    booking = get_object_or_404(Booking, id=booking_id)
    
    is_customer = (booking.customer == request.user)
    is_owner = (booking.salon.owner == request.user)
    
    if not (is_customer or is_owner):
        messages.error(request, 'You do not have permission to cancel this booking.')
        return redirect('home')
        
    if booking.status in ['pending', 'confirmed']:
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, f'The booking for {booking.service.name} on {booking.booking_date} has been cancelled.')
    else:
        messages.error(request, 'This booking cannot be cancelled.')
    
    if is_owner:
        return redirect('dashboard')
    return redirect('my_bookings')

    
@login_required
def manage_staff(request):
    
    salon = get_object_or_404(Salon, owner=request.user)
    staff_members = Staff.objects.filter(salon=salon)
    
    if request.method == 'POST':
        
        name = request.POST.get('name')
        role = request.POST.get('role')
        specialty = request.POST.get('specialty')
        image = request.FILES.get('image')
        print(f"DEBUG: name={name}, role={role}, specialty={specialty}, image={image}")
        if name:
            Staff.objects.create(salon=salon, name=name, role=role, specialty=specialty, image=image)
            messages.success(request, f'Staff {name} added successfully!')
            return redirect('manage_staff')
        else:
            messages.error(request, 'Please provide a staff name.')
            
    return render(request, 'services/manage_staff.html', {
        'staff_members': staff_members,
        'salon': salon
    })
    
@login_required
def toggle_staff_status(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id, salon__owner=request.user)
    
    staff.is_active = not staff.is_active
    staff.save()
    
    status_text = "Active" if staff.is_active else "Inactive"
    messages.info(request, f"Staff {staff.name} status updated to {status_text}.")
    return redirect('manage_staff')


@login_required
def edit_staff(request, staff_id):
    """Edit an existing staff member."""
    staff = get_object_or_404(Staff, id=staff_id, salon__owner=request.user)
    
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, f'Staff "{staff.name}" updated successfully!')
        else:
            messages.error(request, 'Please correct the errors and try again.')
    return redirect('manage_staff')




@login_required
def manage_services(request):
    salon = get_object_or_404(Salon, owner=request.user)
    services = Service.objects.filter(salon=salon)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST) 
        if form.is_valid():
            new_service = form.save(commit=False)
            new_service.salon = salon
            new_service.save()
            messages.success(request, "Service successfully added!")
            return redirect('manage_services')
        else:
            messages.error(request, 'Please correct the errors and try again.')
    else:
        form = ServiceForm()
        
        
    return render(request, 'services/manage_services.html', {
        'services': services,
        'form': form,
        'salon': salon
    })
    
@login_required
def toggle_service_status(request, service_id):
    
    service = get_object_or_404(Service, id=service_id, salon__owner=request.user)
    
    
    service.is_active = not service.is_active
    service.save()
    
    
    status_text = "Active" if service.is_active else "Inactive"
    messages.info(request, f"Service '{service.name}' is now {status_text}.")
    
    
    return redirect('manage_services')


@login_required
def edit_service(request, service_id):
    """Edit an existing service."""
    service = get_object_or_404(Service, id=service_id, salon__owner=request.user)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f'Service "{service.name}" updated successfully!')
        else:
            messages.error(request, 'Please correct the errors and try again.')
    return redirect('manage_services')


def salon_detail(request, salon_id):
    salon = get_object_or_404(Salon, id=salon_id)
    services = Service.objects.filter(salon=salon, is_active=True)
    
    # Fetch active stylists and their average rating and latest feedback
    staff_members = Staff.objects.filter(salon=salon, is_active=True)
    for s in staff_members:
        s_reviews = s.reviews.all().order_by('-created_at')
        s_avg = s_reviews.aggregate(Avg('rating'))['rating__avg']
        s.avg_rating = round(s_avg, 1) if s_avg is not None else None
        s.reviews_count = s_reviews.count()
        s.latest_review = s_reviews.first()

    # Fetch salon reviews and statistics
    salon_reviews = salon.reviews.all().order_by('-created_at')
    salon_avg = salon_reviews.aggregate(Avg('rating'))['rating__avg']
    salon.avg_rating = round(salon_avg, 1) if salon_avg is not None else None
    salon.reviews_count = salon_reviews.count()
    salon.latest_review = salon_reviews.first()
    
    user_salon_review = None
    if request.user.is_authenticated:
        user_salon_review = salon_reviews.filter(customer=request.user).first()
        
    return render(request, 'services/salon_detail.html', {
        'salon': salon,
        'services': services,
        'staff_members': staff_members,
        'salon_reviews': salon_reviews,
        'user_salon_review': user_salon_review
    })
    
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            
            otp = str(random.randint(100000, 999999))
            
            
            request.session['reset_otp'] = otp
            request.session['reset_email'] = email
            
            
            subject = 'Your Password Reset OTP'
            message = f'Your OTP for password reset is: {otp}. It will expire soon.'
            from_email = 'your-email@gmail.com'
            
            try:
                send_mail(subject, message, from_email, [email])
                messages.success(request, "OTP has been sent to your email.")
                return redirect('verify_otp') 
            except Exception as e:
                messages.error(request, "Failed to send email. Please try again.")
        else:
            messages.error(request, "No account found with this email.")
            
    return render(request, 'registration/forgot_password.html')   

def verify_otp(request):
    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        new_password = request.POST.get('new_password')
        session_otp = request.session.get('reset_otp')
        email = request.session.get('reset_email')
        
        if user_otp == session_otp:
            
            user = User.objects.get(email=email)
            if check_password(new_password, user.password):
                messages.error(request, "Your new password cannot be the same as your old one. Please choose a different one.")
                return render(request, 'registration/verify_otp.html') 
            user.set_password(new_password)
            user.save()
            
            
            del request.session['reset_otp']
            del request.session['reset_email']
            
            messages.success(request, "Password reset successful! Please login.")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            
    return render(request, 'registration/verify_otp.html')


@login_required
def choose_role(request, role_choice):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if role_choice == 'customer':
        profile.role = 'customer'
        profile.save()
        return redirect('salon_list') 
    
    elif role_choice == 'merchant':
        profile.role = 'merchant'
        profile.save()
        return redirect('create_salon') 
    
    return redirect('onboarding_page')



@login_required
def home_router(request):
    
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    
    if profile.role == 'none':
        return render(request, 'services/onboarding.html')

    
    if profile.role == 'customer':
        return redirect('salon_list')
        
    elif profile.role == 'merchant':
        if not profile.has_setup_salon:
            return redirect('create_salon')
        return redirect('dashboard')
    
    
    return render(request, 'services/onboarding.html')

@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)

    # Pass salon and location form for merchants
    salon = None
    location_form = None
    salon_image_form = None
    if user_profile.role == 'merchant':
        salon = getattr(request.user, 'salon', None)
        if salon:
            location_form = SalonLocationForm(instance=salon)
            salon_image_form = SalonImageForm(instance=salon)

    return render(request, 'services/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_profile': user_profile,
        'salon': salon,
        'location_form': location_form,
        'salon_image_form': salon_image_form,
    })


@login_required
def edit_salon_location(request):
    """Handle merchant salon location update."""
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or user_profile.role != 'merchant':
        messages.error(request, 'Only merchants can edit salon location.')
        return redirect('profile')

    salon = getattr(request.user, 'salon', None)
    if not salon:
        messages.error(request, 'You have not created a salon yet.')
        return redirect('profile')

    if request.method == 'POST':
        location_form = SalonLocationForm(request.POST, instance=salon)
        if location_form.is_valid():
            location_form.save()
            messages.success(request, 'Salon location updated successfully!')
        else:
            messages.error(request, 'Please enter a valid location.')
    return redirect('profile')


@login_required
def edit_salon_image(request):
    """Handle merchant salon image update."""
    user_profile = getattr(request.user, 'userprofile', None)
    if not user_profile or user_profile.role != 'merchant':
        messages.error(request, 'Only merchants can edit salon image.')
        return redirect('profile')

    salon = getattr(request.user, 'salon', None)
    if not salon:
        messages.error(request, 'You have not created a salon yet.')
        return redirect('profile')

    if request.method == 'POST':
        salon_image_form = SalonImageForm(request.POST, request.FILES, instance=salon)
        if salon_image_form.is_valid():
            salon_image_form.save()
            messages.success(request, 'Salon image updated successfully!')
        else:
            messages.error(request, 'Please upload a valid image.')
    return redirect('profile')


@login_required
def custom_password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keeps the user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'services/password_change.html', {
        'form': form
    })

def get_ai_recommendations(request):
    salon_id = request.GET.get('salon_id')
    date_str = request.GET.get('date') # 格式：2026-05-20
    
    if salon_id and date_str:
        # 🚩 调用 AI 推荐引擎
        recommendations = get_optimal_time_slots(salon_id, date_str)
        return JsonResponse({'status': 'success', 'recommended_slots': recommendations})
        
    return JsonResponse({'status': 'error', 'message': 'Missing parameters'})


def staff_detail(request, staff_id):
    from .models import StaffReview, Staff, Booking
    from django.db.models import Avg
    from datetime import date, timedelta
    
    staff = get_object_or_404(Staff, id=staff_id, is_active=True)
    reviews = staff.reviews.all().order_by('-created_at')
    
    # Handle Staff Review submission
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to submit feedback.")
            return redirect('login')
            
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        
        if rating:
            try:
                rating = int(rating)
                if 1 <= rating <= 5:
                    review, created = StaffReview.objects.update_or_create(
                        staff=staff,
                        customer=request.user,
                        defaults={'rating': rating, 'comment': comment if comment else None}
                    )
                    if created:
                        messages.success(request, f"Feedback submitted successfully for {staff.name}!")
                    else:
                        messages.success(request, f"Your feedback for {staff.name} has been updated!")
                else:
                    messages.error(request, "Rating must be between 1 and 5.")
            except ValueError:
                messages.error(request, "Invalid rating.")
        else:
            messages.error(request, "Rating is required.")
        return redirect('staff_detail', staff_id=staff.id)

    # Average rating calculations
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    if avg_rating is not None:
        avg_rating = round(avg_rating, 1)
        full_stars = range(int(avg_rating))
        half_star = 1 if (avg_rating - int(avg_rating)) >= 0.5 else 0
        empty_stars = range(5 - int(avg_rating) - half_star)
    else:
        avg_rating = "No ratings yet"
        full_stars = []
        half_star = 0
        empty_stars = range(5)

    # 7-Day occupancies
    today = date.today()
    schedule_days = []
    
    # Generate list of slots from 10:00 to 19:00
    from datetime import time as python_time, datetime as python_datetime
    working_hours = [python_time(hour, 0) for hour in range(10, 20)]
    
    for i in range(7):
        day = today + timedelta(days=i)
        day_bookings = Booking.objects.filter(
            staff=staff,
            booking_date=day,
            status__in=['pending', 'confirmed']
        )
        
        slots_info = []
        for slot_time in working_hours:
            is_booked = False
            for booking in day_bookings:
                booking_end = booking.end_time if booking.end_time else (python_datetime.combine(date.today(), booking.timeslot) + timedelta(minutes=booking.service.duration_minutes)).time()
                if booking.timeslot <= slot_time < booking_end:
                    is_booked = True
                    break
            slots_info.append({
                'time': slot_time,
                'is_booked': is_booked
            })
            
        schedule_days.append({
            'date': day,
            'slots': slots_info,
            'has_bookings': day_bookings.exists()
        })

    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(customer=request.user).first()

    return render(request, 'services/staff_detail.html', {
        'staff': staff,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'full_stars': full_stars,
        'half_star': half_star,
        'empty_stars': empty_stars,
        'schedule_days': schedule_days,
        'user_review': user_review
    })


@login_required
def submit_salon_review(request, salon_id):
    from .models import SalonReview, Salon
    salon = get_object_or_404(Salon, id=salon_id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        
        if rating:
            try:
                rating = int(rating)
                if 1 <= rating <= 5:
                    review, created = SalonReview.objects.update_or_create(
                        salon=salon,
                        customer=request.user,
                        defaults={'rating': rating, 'comment': comment if comment else None}
                    )
                    if created:
                        messages.success(request, f"Thank you for reviewing {salon.name}!")
                    else:
                        messages.success(request, f"Your review for {salon.name} has been updated!")
                else:
                    messages.error(request, "Rating must be between 1 and 5.")
            except ValueError:
                messages.error(request, "Invalid rating.")
        else:
            messages.error(request, "Rating is required.")
            
    return redirect('salon_detail', salon_id=salon.id)


