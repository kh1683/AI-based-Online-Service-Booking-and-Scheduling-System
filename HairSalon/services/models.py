
# Create your models here.
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Salon(models.Model):
    # 核心：将店铺与创建它的用户（店主）绑定
    # 这就是 SaaS 多租户架构的基础：每个租户拥有自己的数据实体
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salon')
    
    # 店铺基本信息
    name = models.CharField(max_length=100, verbose_name="店铺名称")
    location = models.CharField(max_length=200, verbose_name="店铺地址")
    description = models.TextField(blank=True, null=True, verbose_name="店铺简介")
    
    # 扩展：支持上传店铺的照片
    image = models.ImageField(upload_to='salons/', blank=True, null=True, verbose_name="店铺图片")
    
    # 记录创建时间，有助于后续的分析（如查看哪家店入驻最早）
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (Owner: {self.owner.username})"
    
# 将第 25 行到第 46 行的内容替换为这一个类
class Staff(models.Model):
    # 1. 关联到店铺
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='staffs', verbose_name="所属店铺")
    
    # 2. 关联到用户账号 (可选，如果员工也要登录系统的话)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_profile')
    
    # 3. 基本信息
    name = models.CharField(max_length=100, verbose_name="姓名")
    role = models.CharField(max_length=100, blank=True, null=True, default='General Stylist') # 🚩 保留这个字段
    specialty = models.CharField(max_length=200, blank=True, null=True, verbose_name="专业技能")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="联系电话")
    is_active = models.BooleanField(default=True, verbose_name="是否在职") # 🚩 默认为在职  
    def __str__(self):
        # 统一返回格式
        return f"{self.name} ({self.role})"
    
    
class Service(models.Model):
    # 同样通过 ForeignKey 锁定在该店的业务范围
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services', verbose_name="所属店铺")
    name = models.CharField(max_length=100, verbose_name="Services")
    min_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # 🚩 增加一个给顾客看的提示词
    price_note = models.CharField(
        max_length=200, 
        blank=True, 
        default="Price varies by age and hair length/style."
    )
    duration_minutes = models.IntegerField(default=30, help_text="平均所需分钟数")
    is_active = models.BooleanField(default=True)    
    def __str__(self):
        return f"{self.name} (RM {self.min_price} - {self.max_price})"
    
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('confirmed', '已确认'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='bookings')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='my_bookings')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='bookings')
    
    booking_date = models.DateField() # 预约日期
    timeslot = models.TimeField()     # 预约时间点
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.username} - {self.service.name} - {self.booking_date}"
    
    
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('none', 'None'),
        ('customer', 'Customer'),
        ('merchant', 'Merchant'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='none')
    # 如果是商家，可以预留一个字段判断是否填了店名
    has_setup_salon = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)