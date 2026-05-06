
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