from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User

class Alert(models.Model):
    ALERT_TYPE_CHOICES = [
        ('camera', 'Camera Offline'),
        ('nvr_dvr', 'NVR/DVR Offline'),
        ('hdd', 'HDD Abnormal'),
        ('time_mismatch', 'Time Mismatch'),
        ('recording', 'Less Recording'),
    ]

    ALERT_TYPE_CHOICES_DICT = dict(ALERT_TYPE_CHOICES)

    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES)
    message = models.TextField()
    source = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    def resolve(self):
        self.is_resolved = True
        self.save()

    def dismiss(self):
        self.is_dismissed = True
        self.save()


class Site(models.Model):
    name = models.CharField(max_length=255)
    device_url = models.URLField()
    storage_url = models.URLField()
    camera_url = models.URLField()
    ports_url = models.URLField()
    recording_url = models.URLField()
    site_type = models.CharField(max_length=50, choices=[('dvr', 'DVR'), ('nvr', 'NVR')])
    client = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sites', null=True, blank=True)
    region = models.CharField(max_length=50)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)





    def __str__(self):
        return self.name
