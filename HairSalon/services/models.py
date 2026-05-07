
# Create your models here.
from django.db import models
from django.conf import settings

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
    
    
    
class Staff(models.Model):
    # 关联到特定的 Salon，实现多租户数据隔离
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='staffs', verbose_name="所属店铺")
    
    name = models.CharField(max_length=100, verbose_name="姓名")
    specialty = models.CharField(max_length=100, verbose_name="专业技能") # 比如：理发、染发、洗头
    phone = models.CharField(max_length=20, verbose_name="联系电话")
    
    def __str__(self):
        return f"{self.name} - {self.salon.name}"
    
    
class Service(models.Model):
    # 同样通过 ForeignKey 锁定在该店的业务范围
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services', verbose_name="所属店铺")
    
    name = models.CharField(max_length=100, verbose_name="服务名称")
    price_range = models.CharField(max_length=50, verbose_name="价格区间")
    duration = models.IntegerField(help_text="预估耗时 (分钟)", verbose_name="耗时")
    
    def __str__(self):
        return f"{self.name} - {self.salon.name}"