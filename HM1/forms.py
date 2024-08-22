from django import forms
from .models import Site
from django.contrib.auth.models import User

class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ['name', 'device_url', 'storage_url', 'camera_url', 'ports_url', 'recording_url', 'site_type', 'client', 'region', 'username', 'password', 'user']

    user = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=False), required=True, label="Select User")
