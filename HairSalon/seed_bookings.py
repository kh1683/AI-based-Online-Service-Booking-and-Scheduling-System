import os
import django
import sys

# 设置 Django 的 settings 模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HairSalon.settings')
django.setup()

import random
from datetime import datetime, timedelta
from django.utils import timezone
from services.models import Booking, Service, Salon, User, Staff

def run_seed():
    # 1. 配置参数
    SALON_NAME = "GG" # 或者是你 Michael 账号名下的店名
    try:
        target_salon = Salon.objects.get(name=SALON_NAME)
    except Salon.DoesNotExist:
        print(f"找不到名为 '{SALON_NAME}' 的沙龙，尝试使用第一个可用的沙龙...")
        target_salon = Salon.objects.first()
        if not target_salon:
            print("错误：数据库中没有任何沙龙！")
            sys.exit(1)
        print(f"Salon not found, using first available salon: {target_salon.name}")

    services = Service.objects.filter(salon=target_salon)
    customers = User.objects.filter(userprofile__role='customer')
    staffs = Staff.objects.filter(salon=target_salon)

    if not services.exists():
        print(f"Error: Salon '{target_salon.name}' has no Services!")
        sys.exit(1)
    if not customers.exists():
        print("Error: No Users with role 'customer' found!")
        sys.exit(1)
    if not staffs.exists():
        print(f"Error: Salon '{target_salon.name}' has no Staff!")
        sys.exit(1)

    print(f"Generating historical data for {target_salon.name}...")
    
    count = 0
    # 2. 生成过去 30 天的数据
    for i in range(300): # 生成 300 条记录
        # 随机日期：过去 30 天
        days_ago = random.randint(0, 30)
        random_date = timezone.now().date() - timedelta(days=days_ago)
        
        # 模拟高峰期逻辑：下午 2-4 点预约概率更高
        if random.random() > 0.5:
            hour = random.randint(14, 16)
        else:
            hour = random.randint(10, 19)
            
        random_time = datetime.strptime(f"{hour}:00", "%H:%M").time()

        Booking.objects.create(
            salon=target_salon,
            customer=random.choice(customers),
            staff=random.choice(staffs),
            service=random.choice(services),
            booking_date=random_date,
            timeslot=random_time,
            status='completed' 
        )
        count += 1

    print(f"Success! {count} historical booking records added.")

if __name__ == '__main__':
    run_seed()
