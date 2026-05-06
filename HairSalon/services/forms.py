from django import forms
from .models import Staff

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