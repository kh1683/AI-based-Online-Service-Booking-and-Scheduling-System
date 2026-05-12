from django import forms
from .models import Staff, Service, Booking, Salon

class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        # Note: we exclude salon here because we auto-bind it in the backend
        fields = ['name', 'specialty', 'phone'] 
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Staff Name'}),
            'specialty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Specialty'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
        }
        
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name','min_price', 'max_price', 'price_note', 'duration_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Name'}),
            'min_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min Price'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max Price'}),
            'price_note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Depends on hair length'}),
            'duration_minutes': forms.NumberInput(attrs={'placeholder': 'e.g., 60'}),
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
        salon = kwargs.pop('salon', None) # Salon instance passed from view
        super(BookingForm, self).__init__(*args, **kwargs)
        if salon:
            # Core logic: only show staff and services belonging to this salon
            self.fields['staff'].queryset = Staff.objects.filter(salon=salon)
            self.fields['service'].queryset = Service.objects.filter(salon=salon)
            
            # Make staff selection optional for auto-assignment
            self.fields['staff'].required = False
            self.fields['staff'].empty_label = "Any Available Stylist (Auto Arrange)"
            
        # Beautify all fields
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        
        
class SalonForm(forms.ModelForm):
    class Meta:
        model = Salon
        # Fields to be filled by merchant, must match Salon model fields
        fields = ['name', 'location', 'contact_number', 'description', 'image']
        
        # Add Bootstrap styling for prettier inputs
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Salon Name'}),
            'location': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter Address'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Contact Number'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

from django.contrib.auth.models import User
from .models import UserProfile

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar']
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

