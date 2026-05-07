from django import forms
from .models import Staff, Service, Booking

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
        
class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['service', 'staff', 'booking_date', 'timeslot']
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'timeslot': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop('salon', None) # 从视图传进来的 salon 实例
        super(BookingForm, self).__init__(*args, **kwargs)
        if salon:
            # 🚩 核心逻辑：只显示属于这家店的员工和服务
            self.fields['staff'].queryset = Staff.objects.filter(salon=salon)
            self.fields['service'].queryset = Service.objects.filter(salon=salon)
            
        # 美化所有字段
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
            
            
            
            