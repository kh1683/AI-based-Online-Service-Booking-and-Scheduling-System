from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Salon, Staff, Service, Booking, UserProfile
from .forms import StaffForm, ServiceForm, BookingForm, SalonForm, UserForm, UserProfileForm
from datetime import date, timedelta
from django.db.models import Count
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import login, update_session_auth_hash
from django import forms
from django.utils import timezone
from django.contrib import messages
from datetime import datetime,time
import random
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from .ai_logic import get_ai_forecast

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
        
        'staff_count': staff_count,
        'service_count': service_count,
        'pending_bookings': pending_bookings_list,  
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
    salon = Salon.objects.get(id=salon_id)
    
    if request.method == 'POST':
        date_str = request.POST.get('booking_date') 
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        form = BookingForm(request.POST, salon=salon)
        if form.is_valid():
            booking = form.save(commit=False)
            
            now = timezone.now() 
            today = now.date()
            # 🚩 Validation 1: Check if date is in the past
            if booking.booking_date < timezone.now().date():
                messages.error(request, "You cannot book a date in the past!")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})
            
            # 🚩 2. Operating hours interception：10:00 - 19:00 (7 p.m.)
            start_time = time(10, 0) # 10:00 AM
            end_time = time(19, 0)   # 07:00 PM
            
            if not (start_time <= booking.timeslot <= end_time):
                messages.error(request, f"❌ Booking failed! Salon operating hours are 10:00 AM - 07:00 PM.")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})

            # 🚩 3. If today, check if time has passed
            if booking.booking_date == today and booking.timeslot < now.time():
                messages.error(request, "❌ This time has already passed. Please select a later time.")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})
            
            booking.salon = salon
            booking.customer = request.user 

            
            if not getattr(booking, 'staff_id', None):
                active_staffs = Staff.objects.filter(salon=salon, is_active=True)
                available_staff = None
                
                for staff in active_staffs:
                    conflict = Booking.objects.filter(
                        staff=staff,
                        booking_date=booking.booking_date,
                        timeslot=booking.timeslot,
                        status__in=['pending', 'confirmed']
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
                    messages.error(request, "❌ Sorry, no stylists are available at this time. Please choose another time.")
                    form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                    form.fields['service'].queryset = Service.objects.filter(salon=salon)
                    return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})

            else:
                
                conflict = Booking.objects.filter(
                    staff=booking.staff,
                    booking_date=booking.booking_date,
                    timeslot=booking.timeslot,
                    status='confirmed'
                ).exists()
                
                if not conflict:
                    
                    booking.status = 'confirmed'
                    messages.success(request, 'Appointment booked successfully! We look forward to seeing you.')
                else:
                    
                    # Save as pending, let owner manage
                    booking.status = 'pending'
                    messages.warning(request, 'This time slot is busy. Your booking is pending for merchant approval.')
                
                booking.save()
                return redirect('my_bookings')
            
           
    else:
        selected_service_id = request.GET.get('service')
        form = BookingForm(salon=salon, initial={'service': selected_service_id})
        form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True) 
        form.fields['service'].queryset = Service.objects.filter(salon=salon)
    return render(request, 'services/create_booking.html', {
        'form': form,
        'salon': salon
    })
    
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
    salons = Salon.objects.all()
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
    
    bookings = Booking.objects.filter(customer=request.user).order_by('-booking_date', '-timeslot')
    
    return render(request, 'services/my_bookings.html', {
        'bookings': bookings
    })
    
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
    
def salon_detail(request, salon_id):
    
    salon = get_object_or_404(Salon, id=salon_id)
    
    
    services = Service.objects.filter(salon=salon, is_active=True)
    
    return render(request, 'services/salon_detail.html', {
        'salon': salon,
        'services': services
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
        
    return render(request, 'services/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_profile': user_profile
    })

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
