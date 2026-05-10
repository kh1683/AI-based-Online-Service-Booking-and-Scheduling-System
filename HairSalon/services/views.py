from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Salon, Staff, Service, Booking
from .forms import StaffForm, ServiceForm, BookingForm
from datetime import date, timedelta
from django.db.models import Count
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django import forms
from django.utils import timezone
from django.contrib import messages

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
    })
    
@login_required
def add_staff(request):
    salon = Salon.objects.get(owner=request.user)
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            staff = form.save(commit=False)
            staff.salon = salon  # 🚩 自动将新员工绑定到当前店主的店铺
            staff.save()
            return redirect('dashboard')
    else:
        form = StaffForm()
    return render(request, 'services/add_staff.html', {'form': form})


@login_required
def add_service(request):
    salon = Salon.objects.get(owner=request.user)
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.salon = salon  # 同样自动绑定当前店铺
            service.save()
            return redirect('dashboard')
    else:
        form = ServiceForm()
    return render(request, 'services/add_service.html', {'form': form})



@login_required
def create_booking(request, salon_id):
    salon = Salon.objects.get(id=salon_id)
    
    if request.method == 'POST':
        form = BookingForm(request.POST, salon=salon)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.salon = salon
            booking.customer = request.user
            
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
        form = BookingForm(salon=salon)
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
    
