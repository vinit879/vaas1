# Generated by Django 5.0.6 on 2024-07-23 11:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('HM1', '0004_alert_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='dismissed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='alert',
            name='is_dismissed',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='alert',
            name='source',
            field=models.CharField(max_length=100),
        ),
    ]
