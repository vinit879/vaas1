from .forms import UserRegisterForm
import requests
import xmltodict
import logging
from django.shortcuts import render, redirect
from requests.auth import HTTPDigestAuth
import cv2
from django.http import StreamingHttpResponse
from django.views.decorators import gzip
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
import asyncio
from asgiref.sync import sync_to_async
from HM1.models import Site
from HM1.views import fetch_all_sites
from django.contrib.auth import logout

logger = logging.getLogger(__name__)

@login_required
def charts(request):
    # Define the context variable
    context = {}
    return render(request, 'info/charts.html', context)

@login_required
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'info/register.html', {'form': form})

@login_required
def profile(request):
    # Your logic for the profile view
    return render(request, 'profile.html')


def dashboard(request):
    context = {
        'company_name': 'VC TECH',
        'description': 'We provide innovative tech solutions to modern problems.',
    }
    return render(request, 'info/dashboard.html', context)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')  # Redirect to login page after logout

# Charts
import asyncio
from django.shortcuts import render
from django.db.models import Count, Q, DateField
from django.db.models.functions import TruncDate
from asgiref.sync import sync_to_async
from HM1.models import Alert, Site

@sync_to_async
def get_filtered_sites(selected_client):
    if selected_client == 'all':
        return list(Site.objects.all())  # Convert queryset to list for async compatibility
    else:
        return list(Site.objects.filter(client=selected_client))  # Filter by client and convert to list

@sync_to_async
def get_alert_counts():
    alert_counts = Alert.objects.values('alert_type').annotate(count=Count('id'))
    alert_labels = [Alert.ALERT_TYPE_CHOICES_DICT[alert['alert_type']] for alert in alert_counts]
    alert_data = [alert['count'] for alert in alert_counts]
    return alert_labels, alert_data

@sync_to_async
def get_alerts_over_time():
    # Group alerts by date and calculate counts
    alerts_by_date = Alert.objects.annotate(date=TruncDate('created_at')).values('date').annotate(
        total_alerts=Count('id'),
        resolved_alerts=Count('id', filter=Q(is_resolved=True)),
        dismissed_alerts=Count('id', filter=Q(is_dismissed=True)),
    ).order_by('date')

    dates = [alert['date'].strftime('%Y-%m-%d') for alert in alerts_by_date]
    total_alerts = [alert['total_alerts'] for alert in alerts_by_date]
    resolved_alerts = [alert['resolved_alerts'] for alert in alerts_by_date]
    dismissed_alerts = [alert['dismissed_alerts'] for alert in alerts_by_date]
    unresolved_alerts = [
        alert['total_alerts'] - alert['resolved_alerts'] - alert['dismissed_alerts']
        for alert in alerts_by_date
    ]

    return dates, total_alerts, resolved_alerts, unresolved_alerts, dismissed_alerts

async def fetch_dashboard_data(selected_client):
    filtered_sites = await get_filtered_sites(selected_client)
    contexts = await fetch_all_sites(filtered_sites)

    total_cameras = sum(context['total_cameras_count'] for context in contexts)
    total_online_cameras = 0
    total_offline_cameras = 0

    for context in contexts:
        total_online_cameras += context.get('online_cameras_count', 0)
        total_offline_cameras += context.get('offline_cameras_count', 0)
        total_online_cameras = total_cameras - total_offline_cameras

    total_dvrs = sum(1 for context in contexts if context['type'] == 'dvr')
    total_nvrs = sum(1 for context in contexts if context['type'] == 'nvr')
    total_sites = len(filtered_sites)
    total_offline_sites = sum(1 for context in contexts if context['nvr_status'] == 'offline')

    # Fetch and process alert data
    alert_labels, alert_data = await get_alert_counts()

    # Fetch and process alerts over time data for the line chart
    dates, total_alerts, resolved_alerts, unresolved_alerts, dismissed_alerts = await get_alerts_over_time()

    return {
        'contexts': contexts,
        'total_cameras': total_cameras,
        'total_online_cameras': total_online_cameras,
        'total_offline_cameras': total_offline_cameras,
        'dvr_count': total_dvrs,
        'nvr_count': total_nvrs,
        'total_sites': total_sites,
        'total_offline_sites': total_offline_sites,
        'total_online_sites': total_sites - total_offline_sites,
        'alert_labels': alert_labels,
        'alert_data': alert_data,
        'dates': dates,
        'total_alerts': total_alerts,
        'resolved_alerts': resolved_alerts,
        'unresolved_alerts': unresolved_alerts,
        'dismissed_alerts': dismissed_alerts,
    }

def dashboard_view(request):
    selected_client = request.GET.get('client', 'all')

    data = asyncio.run(fetch_dashboard_data(selected_client))

    return render(request, 'info/charts.html', {
        'contexts': data['contexts'],
        'total_cameras': data['total_cameras'],
        'total_online_cameras': data['total_online_cameras'],
        'total_offline_cameras': data['total_offline_cameras'],
        'dvr_count': data['dvr_count'],
        'nvr_count': data['nvr_count'],
        'total_sites': data['total_sites'],
        'total_online_sites': data['total_online_sites'],
        'total_offline_sites': data['total_offline_sites'],
        'alert_labels': data['alert_labels'],
        'alert_data': data['alert_data'],
        'dates': data['dates'],
        'total_alerts': data['total_alerts'],
        'resolved_alerts': data['resolved_alerts'],
        'unresolved_alerts': data['unresolved_alerts'],
        'dismissed_alerts': data['dismissed_alerts'],
        'selected_client': selected_client,
        'clients': ['all', 'StarUnion', 'Mcdonald']
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('/info/dashboard/')