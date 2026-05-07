from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Salon, Staff, Service, Booking
from .forms import StaffForm, ServiceForm, BookingForm


@login_required
def salon_dashboard(request):
    # 尝试获取当前店主的店铺，如果没有，跳转到创建页面
    try:
        salon = Salon.objects.get(owner=request.user)
    except Salon.DoesNotExist:
        return redirect('create_salon')  # 之后我们再补这个创建页面

    # 使用 related_name 轻松获取数据
    staffs = salon.staffs.all()
    services = salon.services.all()
    
    # 🚩 获取属于该店的所有预约，按日期排序
    # 我们把待处理和已确认的分开，方便店主操作
    pending_bookings = salon.bookings.filter(status='pending').order_by('booking_date', 'timeslot')
    confirmed_bookings = salon.bookings.filter(status='confirmed').order_by('booking_date', 'timeslot')
    
    return render(request, 'services/dashboard.html', {
        'salon': salon,
        'staffs': staffs,
        'services': services,
        'pending_bookings': pending_bookings,  # 🚩 传给前端
        'confirmed_bookings': confirmed_bookings # 🚩 传给前端
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
                booking.save()
                # 可以加个成功消息 (需 import messages)
                return redirect('dashboard') 
            else:
                # 如果有冲突，保持为“等待中”，或者报错给客户
                # 这里我们先让它存为 pending，让店主去协调
                booking.status = 'pending'
                booking.save()
                return redirect('dashboard')
            
           
    else:
        form = BookingForm(salon=salon)
    
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