from django.db import models

class Device(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('NVR', 'NVR'),
        ('DVR', 'DVR'),
        ('CAMERA', 'Camera')
    ]
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    is_online = models.BooleanField(default=False)
    health_status = models.CharField(max_length=100, default='Unknown')
    last_heartbeat = models.DateTimeField(auto_now_add=True)

class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    is_online = models.BooleanField(default=False)
    last_heartbeat = models.DateTimeField(auto_now_add=True)
    nvr = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='cameras')
