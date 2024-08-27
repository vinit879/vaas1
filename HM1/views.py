from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
import requests
import logging
import xmltodict
from requests.auth import HTTPDigestAuth
from .models import Alert, Site
from django.views.decorators.http import require_POST
from django.utils import timezone
import xml.parsers.expat
import asyncio
from django.core.cache import cache
from asgiref.sync import sync_to_async
import datetime
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

def get_channel_count(model):
    if "04CH" in model or "4CH" in model or '04' in model:
        return "4 CH"
    elif "08CH" in model or "8CH" in model or '08' in model:
        return "8 CH"
    elif "16CH" in model or '16' in model:
        return "16 CH"
    elif "32CH" in model or '32' in model:
        return "32 CH"
    elif "64CH" in model or '64' in model:
        return "64 CH"
    else:
        return "Unknown"

# Asynchronous function to fetch data
async def fetch_data(url, auth):
    try:
        response = await asyncio.to_thread(requests.get, url, auth=auth, timeout=20)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Request exception for URL {url}: {e}")
        return None

# Asynchronous function to create an alert
async def create_alert(alert_type, message, source):
    if alert_type not in ['ports', 'client']:
        existing_alert = await sync_to_async(Alert.objects.filter)(
            alert_type=alert_type,
            message=message,
            source=source,
            is_resolved=False,
            is_dismissed=False
        )
        if not await sync_to_async(existing_alert.exists)():
            await sync_to_async(Alert.objects.create)(alert_type=alert_type, message=message, source=source)

# Asynchronous function to fetch data for a specific site
async def fetch_site_data(site):
    cache_key = f"site_data_{site.name}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Using cached data for site {site.name}")
        return cached_data
    auth = HTTPDigestAuth(site.username, site.password)
    logger.info(f"Fetching data for site {site.name}")

    # Extract IP address and HTTP port directly from the site.device_url
    ip_port = site.device_url.split('/')[2]
    ip_address = ip_port.split(':')[0]
    http = ip_port.split(':')[1] if ':' in ip_port else '80'

    # Add logging to verify the extracted values
    logger.debug(f"Site: {site.name} - IP Address: {ip_address}, HTTP Port: {http}")

    context = {
        'name': site.name,
        'type': site.site_type,
        'offline_cameras': [],
        'total_cameras_count': 0,
        'offline_cameras_count': 0,
        'hdd_status': '0/0',
        'hdd_status_color': '#ff3131',
        'nvr_status': 'offline',
        'recordings_days': 0,
        'device': {
            'ip_address': ip_address,
            'http_port': http,
            'ports': {}
        }
    }

    offline_cameras = []
    total_cameras_count = 0
    nvr_status = 'offline'
    recordings_days = 0
    cameras = []

    # Fetch ports information
    ports_response = await fetch_data(site.ports_url, auth)
    if ports_response:
        try:
            ports_data = xmltodict.parse(ports_response)
            context['device']['ports'] = {
                'http': next((p['portNo'] for p in ports_data['AdminAccessProtocolList']['AdminAccessProtocol'] if p['protocol'] == 'HTTP'), 'N/A'),
                'rtsp': next((p['portNo'] for p in ports_data['AdminAccessProtocolList']['AdminAccessProtocol'] if p['protocol'] == 'RTSP'), 'N/A'),
                'server': next((p['portNo'] for p in ports_data['AdminAccessProtocolList']['AdminAccessProtocol'] if p['protocol'] == 'DEV_MANAGE'), 'N/A')
            }
            logger.debug(f"Ports for {site.name}: {context['device']['ports']}")
        except Exception as e:
            logger.error(f"Error parsing ports data for site {site.name}: {e}")

    # Fetch recording data
    recording_url = site.recording_url
    if recording_url:
        search_body = """
        <?xml version="1.0" encoding="UTF-8"?>
        <CMSearchDescription version="1.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
            <searchID>{A1B2C3D4-5678-90AB-CDEF-1234567890AB}</searchID>
            <trackIDList>
                <trackID>101</trackID> <!-- Channel ID to search -->
            </trackIDList>
            <timeSpanList>
                <timeSpan>
                    <startTime>2023-05-08T00:00:00Z</startTime>
                    <endTime>2028-08-10T23:59:59Z</endTime>
                </timeSpan>
            </timeSpanList>
            <searchResultPosition>0</searchResultPosition>
            <maxResults>1</maxResults>
            <metadataList>
                <metadataDescriptor>recordType.meta.hikvision.com/timing</metadataDescriptor>
            </metadataList>
        </CMSearchDescription>
        """

        try:
            search_response = await asyncio.to_thread(
                requests.post,
                recording_url,
                auth=auth,
                data=search_body,
                headers={'Content-Type': 'application/xml'},
                timeout=20  # Increased timeout to 20 seconds
            )

            if search_response.status_code == 200:
                try:
                    search_data = xmltodict.parse(search_response.text)
                    match_list = search_data.get('CMSearchResult', {}).get('matchList', {})
                    if match_list:
                        # Extract the startTime from the first match item
                        start_time_str = match_list['searchMatchItem']['timeSpan']['startTime']
                        if start_time_str:
                            # Convert startTime to datetime object
                            start_time = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).date()
                            today = datetime.datetime.now(datetime.timezone.utc).date()
                            recordings_days = (today - start_time).days

                            # Update context with calculated days
                            context['recordings_days'] = recordings_days

                            # Alert if recordings are less than 45 days
                            if recordings_days <= 45:
                                await create_alert('recording', 'Recording is less than 45 days', site.name)
                        else:
                            logger.warning(f"No start time found for recordings in site {site.name}")
                    else:
                        logger.warning(f"No match list found in recording data for site {site.name}")
                except Exception as e:
                    logger.error(f"Error parsing recording data for site {site.name}: {e}")
            else:
                logger.error(f"Failed to fetch recording data for site {site.name}: {search_response.status_code}")
        except requests.exceptions.ConnectTimeout:
            logger.error(f"Connection timed out while trying to reach {recording_url} for site {site.name}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception for {recording_url} on site {site.name}: {e}")

    # Fetch device info
    device_url = site.device_url
    if device_url:
        device_response = await fetch_data(device_url, auth)
        if device_response:
            device_data = xmltodict.parse(device_response)
            device_info = device_data.get('DeviceInfo', {})
            context['device'] = device_info
            if device_info.get('serialNumber'):
                nvr_status = 'online'
                context['device']['channel_count'] = get_channel_count(device_info.get('model', 'Unknown'))
                context['device']['ip_address'] = site.device_url.split('/')[2].split(':')[0]
            else:
                await create_alert('nvr_dvr', 'NVR/DVR status is offline', site.name)
                context['device']['ip_address'] = site.device_url.split('/')[2].split(':')[0]

    # Fetch storage info (HDD status)
    storage_url = site.storage_url
    if storage_url:
        storage_response = await fetch_data(storage_url, auth)
        if storage_response:
            try:
                storage_data = xmltodict.parse(storage_response)
                hdd_list = storage_data.get('hddList', {}).get('hdd', [])
                if isinstance(hdd_list, dict):
                    hdd_list = [hdd_list]
                total_hdd = len(hdd_list)
                abnormal_hdd = 0
                if hdd_list:
                    for hdd in hdd_list:
                        status = hdd.get('status', '').lower()
                        capacity_mb = int(hdd.get('capacity', 0))
                        free_space_mb = int(hdd.get('freeSpace', 0))

                        hdd['capacity_tb'] = capacity_mb / (1024 ** 2)
                        hdd['free_space_tb'] = free_space_mb / (1024 ** 2)

                        if status != 'ok':
                            abnormal_hdd += 1
                    if abnormal_hdd > 0:
                        await create_alert('hdd', 'HDD is abnormal', site.name)
                context['hdd_status'] = f"{abnormal_hdd}/{total_hdd}" if total_hdd > 0 else '0/0'
                context['hdd_status_color'] = "#7ed957" if abnormal_hdd == 0 else "#ff914d" if abnormal_hdd < total_hdd else "#ff3131"
                context['storage'] = hdd_list  # Store HDD list in the context

                logger.debug(f"Fetched HDD data for {site.name}: {context['storage']}")

            except Exception as e:
                logger.error(f"Error processing storage data for site {site.name}): {e}")
                context['storage'] = []
        else:
            logger.warning(f"No storage information available for site {site.name}")
            context['storage'] = []

    # Fetch camera info
    camera_url = site.camera_url
    if camera_url:
        camera_response = await fetch_data(camera_url, auth)
        if camera_response:
            camera_data = xmltodict.parse(camera_response)
            if site.site_type == 'dvr':
                camera_list = camera_data.get('VideoInput', {}).get('VideoInputChannelList', {}).get('VideoInputChannel', [])
            else:
                camera_list = camera_data.get('InputProxyChannelStatusList', {}).get('InputProxyChannelStatus', [])
            if isinstance(camera_list, dict):
                camera_list = [camera_list]
            context['total_cameras_count'] = len(camera_list)
            for camera in camera_list:
                if site.site_type == 'dvr':
                    if camera.get('resDesc', '').strip() in ['', 'NO VIDEO']:
                        offline_cameras.append(camera)
                        await create_alert('camera', f'Camera {camera.get("id", "unknown")} status is offline', site.name)
                elif site.site_type == 'nvr':
                    if camera.get('online', '').lower() != 'true':
                        offline_cameras.append(camera)
                        await create_alert('camera', f'Camera {camera.get("id", "unknown")} status is offline', site.name)
            context['offline_cameras_count'] = len(offline_cameras)
            context['offline_cameras'] = offline_cameras

    context['nvr_status'] = nvr_status

    cache.set(cache_key, context, timeout=12000)
    return context

# Asynchronous function to fetch data for all sites
async def fetch_all_sites(sites):
    tasks = [fetch_site_data(site) for site in sites]
    return await asyncio.gather(*tasks)

# Dashboard view for your custom dashboard
@login_required
def dashboard_view(request):
    selected_client = request.GET.get('client', 'all')
    selected_region = request.GET.get('region', 'all')
    selected_status = request.GET.get('status', 'all')  # New status filter

    # Fetch sites from the database
    filtered_sites = Site.objects.all()
    if selected_client != 'all':
        filtered_sites = filtered_sites.filter(client=selected_client)
    if selected_region != 'all':
        filtered_sites = filtered_sites.filter(region=selected_region)

    # Fetch and process data for each site
    contexts = asyncio.run(fetch_all_sites(list(filtered_sites)))

    # Filter contexts based on the selected status
    if selected_status == 'online':
        contexts = [context for context in contexts if context['nvr_status'] == 'online']
    elif selected_status == 'offline':
        contexts = [context for context in contexts if context['nvr_status'] == 'offline']

    # Calculate totals
    total_cameras = sum(context['total_cameras_count'] for context in contexts)
    total_dvrs = sum(1 for context in contexts if context['type'] == 'dvr')
    total_nvrs = sum(1 for context in contexts if context['type'] == 'nvr')
    total_sites = len(contexts)
    total_offline_sites = sum(1 for context in contexts if context['nvr_status'] == 'offline')
    total_offline_cameras = sum(context['offline_cameras_count'] for context in contexts)
    total_online_cameras = total_cameras - total_offline_cameras
    total_online_sites = total_sites - total_offline_sites

    # Calculate additional DVR/NVR stats
    total_dvrs_online = sum(1 for context in contexts if context['type'] == 'dvr' and context['nvr_status'] == 'online')
    total_nvrs_online = sum(1 for context in contexts if context['type'] == 'nvr' and context['nvr_status'] == 'online')
    total_dvrs_offline = total_dvrs - total_dvrs_online
    total_nvrs_offline = total_nvrs - total_nvrs_online

    return render(request, 'info/alert_dashboard.html', {
        'contexts': contexts,
        'clients': ['all', 'StarUnion', 'Mcdonald', 'Stanza'],
        'regions': ['all', 'east', 'west', 'north', 'south'],
        'statuses': ['all', 'online', 'offline'],
        'selected_client': selected_client,
        'selected_region': selected_region,
        'selected_status': selected_status,  # Pass the selected status to the template
        'total_cameras': total_cameras,
        'dvr_count': total_dvrs,
        'nvr_count': total_nvrs,
        'total_sites': total_sites,
        'total_offline_sites': total_offline_sites,
        'total_offline_cameras': total_offline_cameras,
        'total_online_cameras': total_online_cameras,
        'total_online_sites': total_online_sites,
        'total_dvrs_online': total_dvrs_online,
        'total_nvrs_online': total_nvrs_online,
        'total_dvrs_offline': total_dvrs_offline,
        'total_nvrs_offline': total_nvrs_offline,
    })


# Alert Dashboard view for the alert dashboard
@login_required
def alert_dashboard(request):
    selected_client = request.GET.get('client', 'all')
    selected_region = request.GET.get('region', 'all')
    selected_status = request.GET.get('status', 'all')  # New status filter

    # Fetch sites from the database
    filtered_sites = Site.objects.all()

    if selected_client != 'all':
        filtered_sites = filtered_sites.filter(client=selected_client)
    if selected_region != 'all':
        filtered_sites = filtered_sites.filter(region=selected_region)

    filtered_sites = list(filtered_sites)

    contexts = asyncio.run(fetch_all_sites(filtered_sites))

    # Debugging: Log the context being sent to the template
    for context in contexts:
        logger.debug(f"Context for site {context['name']}: {context}")

    # Filter contexts based on the selected status
    if selected_status == 'online':
        contexts = [context for context in contexts if context['nvr_status'] == 'online']
    elif selected_status == 'offline':
        contexts = [context for context in contexts if context['nvr_status'] == 'offline']

    # Calculate totals
    total_cameras = sum(context['total_cameras_count'] for context in contexts)
    total_dvrs = sum(1 for context in contexts if context['type'] == 'dvr')
    total_nvrs = sum(1 for context in contexts if context['type'] == 'nvr')
    total_sites = len(filtered_sites)
    total_offline_sites = sum(1 for context in contexts if context['nvr_status'] == 'offline')
    total_offline_cameras = sum(context['offline_cameras_count'] for context in contexts)
    total_online_cameras = total_cameras - total_offline_cameras
    total_online_sites = total_sites - total_offline_sites

    total_dvrs_online = sum(1 for context in contexts if context['type'] == 'dvr' and context['nvr_status'] == 'online')
    total_nvrs_online = sum(1 for context in contexts if context['type'] == 'nvr' and context['nvr_status'] == 'online')
    total_dvrs_offline = total_dvrs - total_dvrs_online
    total_nvrs_offline = total_nvrs - total_nvrs_online

    return render(request, 'info/alert_dashboard.html', {
        'contexts': contexts,
        'clients': ['all', 'StarUnion', 'Mcdonald', 'Jio','Stanza'],
        'regions': ['all', 'east', 'west', 'north', 'south'],
        'statuses': ['all', 'online', 'offline'],  # Add status filter to the template
        'selected_client': selected_client,
        'selected_region': selected_region,
        'selected_status': selected_status,
        'total_cameras': total_cameras,
        'dvr_count': total_dvrs,
        'nvr_count': total_nvrs,
        'total_sites': total_sites,
        'total_offline_sites': total_offline_sites,
        'total_offline_cameras': total_offline_cameras,
        'total_online_cameras': total_online_cameras,
        'total_online_sites': total_online_sites,
        'total_dvrs_online': total_dvrs_online,
        'total_nvrs_online': total_nvrs_online,
        'total_dvrs_offline': total_dvrs_offline,
        'total_nvrs_offline': total_nvrs_offline,
    })

# Display alerts view
def display_alerts(request):
    alerts = Alert.objects.filter(is_resolved=False, is_dismissed=False).exclude(alert_type__in=['storage', 'device']).order_by('-created_at')
    total_alerts = alerts.count()  # Calculate the total number of alerts
    return render(request, 'HM1/display_alerts.html', {'alerts': alerts, 'total_alerts': total_alerts})

# System alerts view
def system_alerts(request):
    alerts = Alert.objects.all()
    return render(request, 'system_alerts.html', {'alerts': alerts})

# Resolve alert view
def resolve_alert(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id)
    alert.resolve()
    return redirect('display_alerts')

# Dismiss alert view
def dismiss_alert(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id)
    alert.dismiss()
    return redirect('display_alerts')

# Resolved alerts view
def resolved_alerts(request):
    alerts = Alert.objects.filter(is_resolved=True)
    return render(request, 'HM1/resolved_alerts.html', {'alerts': alerts})

# Dismissed alerts view
def dismissed_alerts(request):
    alerts = Alert.objects.filter(is_dismissed=True)
    return render(request, 'HM1/dismissed_alerts.html', {'alerts': alerts})

# Create alert view
def create_alert_view(request):
    if request.method == 'POST':
        alert_type = request.POST.get('alert_type')
        message = request.POST.get('message')
        source = request.POST.get('source')
        
        if alert_type and message and source:
            Alert.objects.create(
                alert_type=alert_type,
                message=message,
                source=source,
            )
            return redirect('display_alerts')
    return render(request, 'HM1/create_alert.html')

# Update alert view
def update_alert_view(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    if request.method == 'POST':
        alert.alert_type = request.POST.get('alert_type')
        alert.message = request.POST.get('message')
        alert.source = request.POST.get('source')
        alert.save()
        return redirect('display_alerts')
    return render(request, 'HM1/update_alert.html', {'alert': alert})

# Add site view
@login_required
def add_site(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        device_url = request.POST.get('device_url')
        storage_url = request.POST.get('storage_url')
        camera_url = request.POST.get('camera_url')
        ports_url = request.POST.get('ports_url')
        recording_url = request.POST.get('recording_url')
        site_type = request.POST.get('site_type')
        client = request.POST.get('client')
        region = request.POST.get('region')
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_id = request.POST.get('user')

        user = User.objects.get(id=user_id)

        site = Site(
            name=name,
            device_url=device_url,
            storage_url=storage_url,
            camera_url=camera_url,
            ports_url=ports_url,
            recording_url=recording_url,
            site_type=site_type,
            client=client,
            region=region,
            username=username,
            password=password,
            user=user  # Associate the selected user with the site
        )
        site.save()
        # Optionally, you can clear the form fields after saving
        return render(request, 'HM1/add_site.html', {'users': User.objects.filter(is_staff=False), 'success': True})

    users = User.objects.filter(is_staff=False)
    return render(request, 'HM1/add_site.html', {'users': users})

# List sites view
def list_sites(request):
    sites = Site.objects.all()
    return render(request, 'HM1/list_sites.html', {'sites': sites})

# Success page view
def success_page(request):
    return render(request, 'HM1/success_page.html')