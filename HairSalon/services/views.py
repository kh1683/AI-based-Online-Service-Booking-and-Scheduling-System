from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Salon, Staff, Service, Booking, UserProfile
from .forms import StaffForm, ServiceForm, BookingForm
from datetime import date, timedelta
from django.db.models import Count
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django import forms
from django.utils import timezone
from django.contrib import messages
from datetime import datetime,time
import random
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password

@login_required
def salon_dashboard(request):
    # 尝试获取当前店主的店铺，如果没有，跳转到创建页面
    # 1. 首先检查这个用户是不是【理发师/员工】
    if hasattr(request.user, 'staff_profile'):
        return redirect('staff_schedule') # 🚩 员工直接去他的工作表，别来老板的后台

    # 2. 如果不是员工，再检查他是不是【店主/老板】
    try:
        salon = Salon.objects.get(owner=request.user)
    except Salon.DoesNotExist:
        return redirect('')  # 之后我们再补这个创建页面


    salon = get_object_or_404(Salon, owner=request.user)
    staff_count = Staff.objects.filter(salon=salon, is_active=True).count()
    service_count = Service.objects.filter(salon=salon, is_active=True).count()
    # 🚩 1. 获取所有的待处理预约对象（给表格循环用）
    pending_bookings_list = Booking.objects.filter(salon=salon, status='pending')
    
    # 🚩 2. 获取数量（给紫色卡片显示数字用）
    pending_count = pending_bookings_list.count()
    
    # 使用 related_name 轻松获取数据
    staffs = salon.staffs.all()
    services = salon.services.all()
    last_7_days = []
    booking_counts = []
    chart_labels = ['5-03', '5-04', '5-05', '5-06', '5-07', '5-08', '5-09']
    chart_data = [2, 5, 1, 8, 4, 10, 3]
    
    today = date.today()
    hourly_stats = salon.bookings.filter(booking_date=today, status='confirmed') \
                    .values('timeslot') \
                    .annotate(count=Count('id')) \
                    .order_by('timeslot')
    busy_slots = [item['timeslot'].strftime('%H:%M') for item in hourly_stats if item['count'] >= 2]
    # 🚩 获取属于该店的所有预约，按日期排序
    # 我们把待处理和已确认的分开，方便店主操作
    pending_bookings = salon.bookings.filter(status='pending').order_by('booking_date', 'timeslot')
    confirmed_bookings = salon.bookings.filter(status='confirmed').order_by('booking_date', 'timeslot')
    
    for i in range(6, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        count = salon.bookings.filter(booking_date=day).count()
        last_7_days.append(day.strftime('%m-%d'))
        booking_counts.append(count)
    
    
    # 🚩 遍历待处理预约，检查它们是否真的与“已确认”的预约有时间冲突
    for b in pending_bookings:
        is_conflicted = salon.bookings.filter(
            staff=b.staff,
            booking_date=b.booking_date,
            timeslot=b.timeslot,
            status='confirmed' # 只跟已经定死的预约比
        ).exists()
        
        # 给对象动态添加一个属性，只在前端显示用，不存数据库
        b.is_real_conflict = is_conflicted
    
    return render(request, 'services/dashboard.html', {
        'salon': salon,
        'staffs': staffs,
        'services': services,
        'pending_bookings': pending_bookings,  # 🚩 传给前端
        'confirmed_bookings': confirmed_bookings, # 🚩 传给前端
        'busy_slots': busy_slots,
        'hourly_stats': hourly_stats,
        # 🚩 重点：把图表数据传过去
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        #统计
        'staff_count': staff_count,
        'service_count': service_count,
        'pending_bookings': pending_bookings_list,  # 🚩 传列表给表格循环
        'pending_count': pending_count,
    })
    
# @login_required
# def add_staff(request):
#     salon = Salon.objects.get(owner=request.user)
#     if request.method == 'POST':
#         form = StaffForm(request.POST)
#         if form.is_valid():
#             staff = form.save(commit=False)
#             staff.salon = salon  # 🚩 自动将新员工绑定到当前店主的店铺
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
#             service.salon = salon  # 同样自动绑定当前店铺
#             service.save()
#             return redirect('dashboard')
#     else:
#         form = ServiceForm()
#     return render(request, 'services/add_service.html', {'form': form})



@login_required
def create_booking(request, salon_id):
    salon = Salon.objects.get(id=salon_id)
    
    if request.method == 'POST':
        date_str = request.POST.get('booking_date') # 假设你的 input name 是这个
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        form = BookingForm(request.POST, salon=salon)
        if form.is_valid():
            booking = form.save(commit=False)
            # 获取当前大马时间
            now = timezone.now() 
            today = now.date()
            # 🚩 验证 1: 检查日期是否是过去
            if booking.booking_date < timezone.now().date():
                messages.error(request, "You cannot book a date in the past!")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})
            
            # 🚩 2. 营业时间拦截：10:00 - 19:00 (7 p.m.)
            start_time = time(10, 0) # 10:00 AM
            end_time = time(19, 0)   # 07:00 PM
            
            if not (start_time <= booking.timeslot <= end_time):
                messages.error(request, f"❌ 预约失败！该店营业时间为 10:00 AM - 07:00 PM。")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})

            # 🚩 3. 如果是今天，检查时间是否已经过了
            if booking.booking_date == today and booking.timeslot < now.time():
                messages.error(request, "❌ 这个时间点已经过去了，请选晚一点的时间。")
                form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True)
                form.fields['service'].queryset = Service.objects.filter(salon=salon)
                return render(request, 'services/create_booking.html', {'form': form, 'salon': salon})
            
            # 🚩 核心：自动冲突检测逻辑
            # 检查是否有【相同员工】在【相同日期】和【相同时间】已有【已确认】的预约
            conflict = Booking.objects.filter(
                staff=booking.staff,
                booking_date=booking.booking_date,
                timeslot=booking.timeslot,
                status='confirmed'
            ).exists()
            
            booking.salon = salon
            booking.customer = request.user # 绑定当前登录的客户
            
            if not conflict:
                # 如果没有冲突，直接设为“已确认”，实现自动化
                booking.status = 'confirmed'
                # 可以加个成功消息 (需 import messages)
                messages.success(request, 'Appointment booked successfully! We look forward to seeing you.')
            else:
                # 如果有冲突，保持为“等待中”，或者报错给客户
                # 这里我们先让它存为 pending，让店主去协调
                booking.status = 'pending'
                messages.warning(request, 'This time slot is busy. Your booking is pending for merchant approval.')
            booking.save()
            return redirect('my_bookings')
            
           
    else:
        selected_service_id = request.GET.get('service')
        form = BookingForm(salon=salon, initial={'service': selected_service_id})
        form.fields['staff'].queryset = Staff.objects.filter(salon=salon, is_active=True) # 🚩 只显示在职员工
        form.fields['service'].queryset = Service.objects.filter(salon=salon)
    return render(request, 'services/create_booking.html', {
        'form': form,
        'salon': salon
    })
    
@login_required
def approve_booking(request, booking_id):
    # 确保只有该店的店主能确认这个预约 (Security Check)
    booking = get_object_or_404(Booking, id=booking_id, salon__owner=request.user)
    booking.status = 'confirmed'
    booking.save()
    return redirect('dashboard')

@login_required
def reject_booking(request, booking_id):
    # 同样要确保安全：只能拒绝属于自己店铺的预约
    booking = get_object_or_404(Booking, id=booking_id, salon__owner=request.user)
    
    # 我们可以直接删除，或者将其状态改为 'cancelled'
    # 为了保留数据记录（方便以后 AI 分析客户流失），建议改为 cancelled
    booking.status = 'cancelled'
    booking.save()
    
    return redirect('dashboard')

@login_required
def staff_schedule(request):
    # 1. 尝试获取当前登录用户的员工档案
    try:
        staff_profile = request.user.staff_profile
    except Staff.DoesNotExist:
        # 如果不是员工，跳转回首页或报错
        return render(request, 'services/error.html', {'message': '您不是注册员工，无法查看工作表'})

    # 2. 获取属于该员工的所有【已确认】预约
    my_tasks = Booking.objects.filter(
        staff=staff_profile, 
        status='confirmed'
    ).order_by('booking_date', 'timeslot')

    return render(request, 'services/staff_schedule.html', {
        'staff': staff_profile,
        'tasks': my_tasks
    })
    
    
    
# 自定义表单，强制加上 email
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="请输入您的 Gmail 地址")

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)
        
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('onboarding_choice') # 注册完去选身份
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def onboarding_choice(request):
    # 如果已经开过店了，直接去 dashboard
    # 检查用户是否已经是店主（为了防止重复开店）
    if hasattr(request.user, 'salon'):
        return redirect('dashboard')
    return render(request, 'services/onboarding_choice.html')    
    
def create_salon(request):
    return render(request, 'services/create_salon.html') # 之后再写逻辑

def salon_list(request):
    # 先返回一个最简单的内容，以后我们再写“搜索店铺”的逻辑
    from .models import Salon
    salons = Salon.objects.all()
    return render(request, 'services/salon_list.html', {'salons': salons})  



@login_required
def my_bookings(request):
    # 获取当前用户的所有预约，按日期和时间排序
    bookings = Booking.objects.filter(customer=request.user).order_by('-booking_date', '-timeslot')
    
    return render(request, 'services/my_bookings.html', {
        'bookings': bookings
    })
    
@login_required
def manage_staff(request):
    # 确保只看到自己店里的员工
    salon = get_object_or_404(Salon, owner=request.user)
    staff_members = Staff.objects.filter(salon=salon)
    
    if request.method == 'POST':
        # 这里简化处理，直接获取名字添加
        name = request.POST.get('name')
        role = request.POST.get('role')
        print(f"DEBUG: name={name}, role={role}")
        if name:
            Staff.objects.create(salon=salon, name=name, role=role)
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
    # 🚩 切换状态：如果是 True 就变 False，反之亦然
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
        form = ServiceForm(request.POST) # 使用 ModelForm 会自动处理字段对应
        if form.is_valid():
            new_service = form.save(commit=False)
            new_service.salon = salon
            new_service.save()
            messages.success(request, "服务已成功添加！")
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
    # 🚩 1. 获取对应的 Service 对象，同时确保这个服务属于当前登录的店主
    service = get_object_or_404(Service, id=service_id, salon__owner=request.user)
    
    # 🚩 2. 反转状态：True 变 False，False 变 True
    service.is_active = not service.is_active
    service.save()
    
    # 🚩 3. 准备提示信息
    status_text = "Active" if service.is_active else "Inactive"
    messages.info(request, f"Service '{service.name}' is now {status_text}.")
    
    # 🚩 4. 跳回管理页面
    return redirect('manage_services')
    
def salon_detail(request, salon_id):
    # 1. 找到这家店，找不到就报404
    salon = get_object_or_404(Salon, id=salon_id)
    
    # 2. 核心逻辑：只获取属于这家店 (salon=salon) 且 正在营业 (is_active=True) 的服务
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
            # 1. 生成 6 位随机数
            otp = str(random.randint(100000, 999999))
            
            # 2. 将 OTP 和 Email 存入 Session (有效期默认是浏览器关闭)
            request.session['reset_otp'] = otp
            request.session['reset_email'] = email
            
            # 3. 发送邮件
            subject = 'Your Password Reset OTP'
            message = f'Your OTP for password reset is: {otp}. It will expire soon.'
            from_email = 'your-email@gmail.com'
            
            try:
                send_mail(subject, message, from_email, [email])
                messages.success(request, "OTP has been sent to your email.")
                return redirect('verify_otp') # 跳转到输入验证码的页面
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
            # 验证成功，修改密码
            user = User.objects.get(email=email)
            if check_password(new_password, user.password):
                messages.error(request, "Your new password cannot be the same as your old one. Please choose a different one.")
                return render(request, 'registration/verify_otp.html') # 拦截，不让保存
            user.set_password(new_password)
            user.save()
            
            # 清除 Session 防止重复使用
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
        return redirect('salon_list') # 客户直接去看店
    
    elif role_choice == 'merchant':
        profile.role = 'merchant'
        profile.save()
        return redirect('create_salon') # 商家去填店名资料
    
    return redirect('onboarding_page')



@login_required
def home_router(request):
    # 🚩 改用 get_or_create，防止 DoesNotExist 报错
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # 如果角色还是 none，才显示 onboarding 页面
    if profile.role == 'none':
        return render(request, 'services/onboarding.html')

    # 根据记录的角色分流
    if profile.role == 'customer':
        return redirect('salon_list')
        
    elif profile.role == 'merchant':
        if not profile.has_setup_salon:
            return redirect('create_salon')
        return redirect('merchant_dashboard')
    
    # 兜底：如果出了意外，依然回选择页
    return render(request, 'services/onboarding.html')