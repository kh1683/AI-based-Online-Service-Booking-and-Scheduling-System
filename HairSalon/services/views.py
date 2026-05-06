from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Salon, Staff, Service
from .forms import StaffForm

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
    
    return render(request, 'services/dashboard.html', {
        'salon': salon,
        'staffs': staffs,
        'services': services
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