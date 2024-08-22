import logging
from threading import Lock, Thread, Timer
from queue import Queue, Empty
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseServerError
from django.shortcuts import render
import time
from subprocess import Popen, PIPE
import psutil  # To set process priority

# Configure logging for detailed output
logging.basicConfig(level=logging.WARNING)  # Set to WARNING by default
logger = logging.getLogger(__name__)

# Global dictionary to store camera instances
cameras = {}

class VideoCamera:
    def __init__(self, source):
        self.source = source
        self.is_running = True
        self.frame_queue = Queue(maxsize=100)  # Larger queue to hold more frames
        self.error_count = 0  # Counter for consecutive errors
        self.max_errors = 3  # Maximum allowed consecutive errors before termination
        self.start_ffmpeg()
        self.capture_thread = Thread(target=self.update, daemon=True)
        self.capture_thread.start()
        self.timer = Timer(120, self.stop)  # 120 seconds = 2 minutes
        self.timer.start()
        logger.info(f"Camera initialized and started for source: {self.source}")

    def start_ffmpeg(self):
        ffmpeg_path = 'C:\\ffmpeg\\ffmpeg.exe'  # Changed for Ubuntu
        ffmpeg_command = [
            ffmpeg_path,
            '-rtsp_transport', 'tcp',  # Use TCP for RTSP to improve stability
            '-i', self.source,
            '-f', 'image2pipe',
            '-vf', 'scale=1280:720,fps=30',  # Higher frame rate and resolution for better quality
            '-vcodec', 'mjpeg',
            '-q:v', '2',  # Higher quality
            'pipe:1'
        ]
        self.ffmpeg_process = Popen(ffmpeg_command, stdout=PIPE, stderr=PIPE, bufsize=10**8)
        Thread(target=self.monitor_ffmpeg_output, daemon=True).start()

    def monitor_ffmpeg_output(self):
        try:
            for line in self.ffmpeg_process.stderr:
                line = line.decode(errors='ignore').strip()
                if line:
                    if "error" in line.lower() or "warning" in line.lower():
                        logger.warning(f"FFmpeg warning/error: {line}")
        except Exception as e:
            logger.error(f"Error reading FFmpeg output: {e}")

    def stop(self):
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process.wait()
            self.ffmpeg_process = None
        self.is_running = False
        logger.info("Camera stopped and FFmpeg process terminated successfully.")
        if self.timer:
            self.timer.cancel()

    
    def update(self):
        # Set thread priority to high
        p = psutil.Process()
        try:
            p.nice(-20)  # Attempt to set the highest priority
        except psutil.AccessDenied:
            logger.warning("Insufficient permissions to set high priority. Running with normal priority.")

        
        
        
        while self.is_running:
            try:
                frame = self.get_frame()
                if frame:
                    self.error_count = 0  # Reset error count on successful frame retrieval
                    self.frame_queue.put_nowait(frame)
                else:
                    self.error_count += 1
                    logger.warning(f"No complete frame found in buffer. Consecutive errors: {self.error_count}")
                    if self.error_count >= self.max_errors:
                        logger.error("Max consecutive errors reached. Terminating process.")
                        self.stop()
                        break
            except Exception as e:
                logger.error(f"Error in update thread: {e}")
                self.stop()

    def get_frame(self):
        start_marker = b'\xff\xd8'
        end_marker = b'\xff\xd9'
        buffer = bytearray()
        while self.is_running:
            try:
                data = self.ffmpeg_process.stdout.read(4096)  # Adjust buffer read size for optimal performance
                if not data:
                    break
                buffer += data
                start = buffer.find(start_marker)
                end = buffer.find(end_marker, start + 2)
                if start != -1 and end != -1:
                    frame = buffer[start:end + 2]
                    buffer = buffer[end + 2:]
                    return frame
                if len(buffer) > 10**8:  # Increased buffer size limit
                    logger.warning("Buffer overflow, resetting buffer.")
                    buffer = bytearray()
            except Exception as e:
                logger.error(f"Error reading frame: {e}")
                break
        return None

    def get_current_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None

def gen(camera):
    while camera.is_running:
        frame = camera.get_current_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        else:
            time.sleep(0.001)  # Reduce sleep to ensure timely updates

def video_feed(request, site, stream_id):
    stream_map = {
        
        'unnatwadi': {str(i): f"rtsp://admin:vct280620@10.11.12.122:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 15)},
        
        'hesargatta': {str(i): f"rtsp://admin:vct280620@10.11.12.93:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 16)},
        'jio_world_bake_module': {str(i): f"rtsp://admin:vct280620@10.11.12.30:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 8)},
        'Florence_House': {str(i): f"rtsp://admin:vct280620@203.122.53.116:8081/Streaming/Channels/{100 * i + 2}" for i in range(1, 17)},
        'Pune': {str(i): f"rtsp://admin:vct280620@10.11.16.203:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 9)},
        'Thane': {str(i): f"rtsp://admin:vct280620@10.11.16.206:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Andheri': {str(i): f"rtsp://admin:vct280620@10.11.16.210:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 9)},
        'Vijayawada': {str(i): f"rtsp://admin:vct280620@10.11.16.211:1024/Streaming/Channels/{100 * i +2}" for i in range(1, 4)},
        'Nashik': {str(i): f"rtsp://admin:vct280620@10.11.16.213:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 9)},
        'Anna Nagar': {str(i): f"rtsp://admin:vct280620@10.11.16.215:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 4)},
        'Akola': {str(i): f"rtsp://admin:vct280620@10.11.16.207:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Ludhiana': {str(i): f"rtsp://admin:vct280620@10.11.16.214:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Kolhapur': {str(i): f"rtsp://admin:vct280620@10.11.16.201:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'MG Road': {str(i): f"rtsp://admin:SUD@2806@10.11.16.218:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Rajaji Nagar': {str(i): f"rtsp://admin:vct280620@10.11.16.204:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'jayanagar': {str(i): f"rtsp://admin:vct280620@10.11.16.209:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Malda': {str(i): f"rtsp://admin:vct280620@10.11.16.216:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Lucknow': {str(i): f"rtsp://admin:vct280620@10.11.16.220:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Patto Goa': {str(i): f"rtsp://admin:vct280620@10.11.16.221:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 8)},
        'Warangal': {str(i): f"rtsp://admin:vct280620@10.11.16.223:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'Latur': {str(i): f"rtsp://admin:vct280620@10.11.16.222:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 4)},
        'Amritsar': {str(i): f"rtsp://admin:vct280620@10.11.16.212:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 4)},
        'Guntur': {str(i): f"rtsp://admin:vct280620@10.11.16.225:1024/Streaming/Channels/{100 * i + 2}" for i in range(1, 5)},
        'KielHouse': {str(i): f"rtsp://admin:vct280620@180.151.29.23:8081/Streaming/Channels/{100 * i + 2}" for i in range(1, 17)},

    }
    if site not in stream_map:
        logger.error(f"Invalid site: {site}")
        return HttpResponseServerError("Invalid site")

    source = stream_map[site].get(str(stream_id))
    if not source:
        logger.error(f"Invalid stream_id: {stream_id} for site: {site}")
        return HttpResponseServerError("Invalid stream_id")

    camera_key = f"{site}_{stream_id}"
    if camera_key not in cameras:
        try:
            cameras[camera_key] = VideoCamera(source)
            logger.info(f"Camera created for stream ID: {stream_id} at site: {site}")
        except Exception as e:
            logger.error(f"Failed to initialize camera for stream {stream_id} at site {site}: {e}")
            return HttpResponseServerError(str(e))

    camera = cameras[camera_key]
    return StreamingHttpResponse(gen(camera), content_type='multipart/x-mixed-replace; boundary=frame')

def control_stream(request, site, stream_id, action):
    logger.debug(f"Received control request: site={site}, stream_id={stream_id}, action={action}")
    camera_key = f"{site}_{stream_id}"
    camera = cameras.get(camera_key)
    if not camera:
        logger.error(f"Camera not found for stream_id: {stream_id} at site: {site}")
        return JsonResponse({'status': 'error', 'message': 'Invalid stream_id'}, status=400)

    if action not in ['pause', 'play']:
        logger.error(f"Invalid action attempted: {action}")
        return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

    if action == 'pause':
        camera.is_running = False
        logger.info(f"Camera {stream_id} at site {site} paused")
    elif action == 'play':
        camera.is_running = True
        logger.info(f"Camera {stream_id} at site {site} resumed")

    return JsonResponse({'status': 'success', 'action': action, 'stream_id': stream_id})

def stop_all_streams(request):
    for camera_key in list(cameras.keys()):
        camera = cameras.pop(camera_key, None)
        if camera:
            camera.stop()
            logger.info(f"Camera {camera_key} stopped")
    return JsonResponse({'status': 'success'})

def stop_site_streams(request, site):
    keys_to_stop = [key for key in cameras.keys() if key.startswith(site)]
    for camera_key in keys_to_stop:
        camera = cameras.pop(camera_key, None)
        if camera:
            camera.stop()
            logger.info(f"Camera {camera_key} stopped")
    return JsonResponse({'status': 'success'})

def live_stream1(request):
    clients = {
        'mac_donald': [
            { 'value': "unnatwadi", 'text': "Unnatwadi", 'cameraCount': 14 },
            { 'value': "hesargatta", 'text': "Hesargatta", 'cameraCount': 15 }
        ],
        'stanza': [
            { 'value': "Florence_House", 'text': "Florence House", 'cameraCount': 16 },
            { 'value': "KielHouse", 'text': "KielHouse", 'cameraCount': 16 },

        ],
        'jioworld': [
            { 'value': "jio_world_bake_module", 'text': "Jio World Bake Module", 'cameraCount': 7 }
        ],
        'StarUnion':[
            { 'value': "Pune", 'text': "Pune", 'cameraCount': 8 },
            { 'value': "Thane", 'text': "Thane", 'cameraCount': 4 },
            { 'value': "Andheri", 'text': "Andheri", 'cameraCount': 8 },
            { 'value': "Vijayawada", 'text': "Vijayawada", 'cameraCount': 3 },
            { 'value': "Nashik", 'text': "Nashik", 'cameraCount': 8 },
            { 'value': "Anna Nagar", 'text': "Anna Nagar", 'cameraCount': 3 },
            { 'value': "Akola", 'text': "Akola", 'cameraCount': 4 },
            { 'value': "Ludhiana", 'text': "Ludhiana", 'cameraCount': 4 },
            { 'value': "Kolhapur", 'text': "Kolhapur", 'cameraCount': 4 },
            { 'value': "MG Road", 'text': "MG Road", 'cameraCount': 4 },
            { 'value': "Rajagi Nagar", 'text': "Rajagi Nagar", 'cameraCount': 4 },
            { 'value': "Jayanagar", 'text': "Jayanagar", 'cameraCount': 4 },
            { 'value': "Malda", 'text': "Malda", 'cameraCount': 4 },
            { 'value': "Lucknow", 'text': "Lucknow", 'cameraCount': 4 },
            { 'value': "Patto Goa", 'text': "Patto Goa", 'cameraCount': 7 },
            { 'value': "Warangal", 'text': "Warangal", 'cameraCount': 4 },
            { 'value': "Latur", 'text': "Latur", 'cameraCount': 3 },
            { 'value': "Amritsar", 'text': "Amritsar", 'cameraCount': 3 },
            { 'value': "Guntur", 'text': "Guntur", 'cameraCount': 4 },

        ]
    }
    return render(request, 'live_preview/live_preview.html', {'clients': clients})
