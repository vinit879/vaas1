# Generated by Django 5.0.6 on 2024-07-05 14:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('HM1', '0002_alert_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='alert',
            name='status',
        ),
        migrations.AddField(
            model_name='alert',
            name='is_resolved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='alert',
            name='resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
