from django import forms
from .models import Staff, Service

class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        # 注意：这里排除 salon，因为我们会在后端自动绑定
        fields = ['name', 'specialty', 'phone'] 
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '员工姓名'}),
            'specialty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '专业技能'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '联系电话'}),
        }
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'price_range', 'duration']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '服务名称'}),
            'price_range': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例如: 50-100'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '分钟'}),
        }