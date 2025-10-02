"""
Media Processing Service for multi-platform video downloads.
Implements yt-dlp integration with progress tracking and platform detection.
"""

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
import logging
import yt_dlp
from urllib.parse import urlparse

from models import (
    VideoSource, VideoMetadata, MediaDownloadResult, 
    VideoProcessingJob, ProcessingStatus
)
from config import settings


logger = logging.getLogger(__name__)


class VideoDownloader:
    """
    Multi-platform video downloader using yt-dlp.
    Supports YouTube, Facebook, Instagram with progress tracking.
    """
    
    def __init__(self):
        self.download_dir = settings.media.download_dir
        self.temp_dir = settings.media.temp_dir
        self._active_downloads: Dict[str, asyncio.Task] = {}
        self._loop = asyncio.get_event_loop() # Store the event loop
    
    async def download_video(self, job: VideoProcessingJob, 
                           progress_callback: Optional[Callable] = None) -> MediaDownloadResult:
        """
        Download video from URL with progress tracking.
        """
        start_time = time.time()
        
        try:
            # Detect platform
            platform = self._detect_platform(job.video_url)
            job.platform = platform
            
            # Create unique filename
            safe_job_id = re.sub(r'[^\w\-_.]', '_', job.job_id)
            
            # Configure yt-dlp options
            video_path = self.download_dir / f"{safe_job_id}.mp4"
            audio_path = self.download_dir / f"{safe_job_id}_audio.mp3"
            
            ydl_opts = self._get_ytdl_options(
                video_path, audio_path, progress_callback, job, platform
            )
            
            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = await self._extract_info(ydl, job.video_url)
                if not info:
                    return MediaDownloadResult(
                        success=False,
                        error_message="Failed to extract video information"
                    )
                
                # Create metadata
                metadata = self._create_metadata(info, platform, job.job_id)
                
                # Check file size and duration limits
                if not self._validate_video_limits(metadata):
                    return MediaDownloadResult(
                        success=False,
                        error_message="Video exceeds size or duration limits"
                    )
                
                # Download the video
                await self._download_with_ytdl(ydl, job.video_url, job.job_id)
                
                # Verify files exist
                if not video_path.exists():
                    # Try to find the actual downloaded file
                    video_path = self._find_downloaded_file(safe_job_id, self.download_dir)
                
                if not audio_path.exists():
                    audio_path = self._find_downloaded_audio_file(safe_job_id, self.download_dir)
                
                download_time = time.time() - start_time
                
                return MediaDownloadResult(
                    success=True,
                    video_path=video_path,
                    audio_path=audio_path,
                    metadata=metadata,
                    download_time=download_time
                )
        
        except yt_dlp.DownloadError as e:
            error_msg = f"Download error: {str(e)}"
            logger.error(f"yt-dlp download error for {job.job_id}: {error_msg}")
            return MediaDownloadResult(
                success=False,
                error_message=error_msg,
                download_time=time.time() - start_time
            )
        
        except Exception as e:
            error_msg = f"Unexpected error during download: {str(e)}"
            logger.error(f"Download error for {job.job_id}: {error_msg}")
            return MediaDownloadResult(
                success=False,
                error_message=error_msg,
                download_time=time.time() - start_time
            )
    
    def _detect_platform(self, url: str) -> VideoSource:
        """Detect video platform from URL."""
        url_lower = url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return VideoSource.YOUTUBE
        elif "facebook.com" in url_lower or "fb.com" in url_lower:
            return VideoSource.FACEBOOK
        elif "instagram.com" in url_lower:
            return VideoSource.INSTAGRAM
        else:
            return VideoSource.UNKNOWN
    
    def _get_ytdl_options(self, video_path: Path, audio_path: Path,
                          progress_callback: Optional[Callable], job: VideoProcessingJob,
                          platform: VideoSource) -> Dict:
        """Get yt-dlp configuration options."""
        
        job_id = job.job_id
        job_type = getattr(job, 'job_type', 'audio')

        def progress_hook(d):
            if progress_callback and d['status'] == 'downloading':
                try:
                    if 'total_bytes' in d and d['total_bytes']:
                        percentage = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
                        # Schedule the coroutine on the main event loop
                        asyncio.run_coroutine_threadsafe(
                            progress_callback(job_id, percentage, f"Downloading: {percentage:.1f}%"),
                            self._loop
                        )
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
        
        options = {
            'outtmpl': str(video_path).replace('.mp4', '.%(ext)s'),
            'progress_hooks': [progress_hook] if progress_callback else [],
            'socket_timeout': settings.media.download_timeout,
        }

        # Platform-specific configurations
        if platform == VideoSource.YOUTUBE:
            if job_type == 'video':
                options['format'] = 'bestvideo+bestaudio/best'
            else:  # audio job
                options['format'] = 'bestaudio/best'
                # Use FFmpegExtractAudio for better audio extraction on YouTube
                options['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': settings.media.audio_format,
                    'preferredquality': settings.media.audio_quality,
                }]
                options['add_metadata'] = True

        elif platform == VideoSource.FACEBOOK or platform == VideoSource.INSTAGRAM:
            # Enhanced metadata extraction for Facebook/Instagram
            options['writeinfojson'] = True  # Write metadata to JSON file
            options['writedescription'] = True  # Write description to separate file
            options['cookiefile'] = 'cookies-facebook.txt' if platform == VideoSource.FACEBOOK else 'cookies-instagram.txt'

            if job_type == 'video':
                options['format'] = 'bestvideo+bestaudio/best'
                options['extractaudio'] = False
            else:  # audio job
                options['format'] = 'm4a'
                options['extractaudio'] = settings.media.extract_audio
                options['audioformat'] = settings.media.audio_format
                options['audioquality'] = settings.media.audio_quality
                options['keepvideo'] = False

        else:  # Other platforms (fallback)
            if job_type == 'video':
                options['format'] = 'bestvideo+bestaudio/best'
                options['extractaudio'] = False
            else:  # audio job
                options['format'] = 'bestaudio/best'
                options['extractaudio'] = settings.media.extract_audio
                options['audioformat'] = settings.media.audio_format
                options['audioquality'] = settings.media.audio_quality
                options['keepvideo'] = False
            
        return options
    
    async def _extract_info(self, ydl: yt_dlp.YoutubeDL, url: str) -> Optional[Dict]:
        """Extract video information."""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )
            return info
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            return None
    
    async def _download_with_ytdl(self, ydl: yt_dlp.YoutubeDL, url: str, job_id: str) -> None:
        """Download video using yt-dlp."""
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(None, ydl.download, [url])
        
        # Store active download for potential cancellation
        self._active_downloads[job_id] = task
        
        try:
            await asyncio.wait_for(task, timeout=settings.media.download_timeout)
        except asyncio.TimeoutError:
            task.cancel()
            raise yt_dlp.DownloadError("Download timeout")
        finally:
            self._active_downloads.pop(job_id, None)
    
    def _create_metadata(self, info: Dict, platform: VideoSource, job_id: str = None) -> VideoMetadata:
        """Create VideoMetadata from yt-dlp info."""
        description = info.get('description', None)

        # Enhanced description extraction for Facebook/Instagram
        if platform in [VideoSource.FACEBOOK, VideoSource.INSTAGRAM] and job_id:
            description = self._extract_enhanced_description(info, job_id, description)

        return VideoMetadata(
            title=info.get('title', 'Unknown'),
            duration=float(info.get('duration', 0)),
            resolution=f"{info.get('width', 0)}x{info.get('height', 0)}",
            file_size=info.get('filesize', 0) or info.get('filesize_approx', 0),
            format=info.get('ext', 'unknown'),
            platform=platform,
            author=info.get('uploader', None),
            upload_date=self._parse_upload_date(info.get('upload_date')),
            view_count=info.get('view_count', None),
            description=description
        )

    def _extract_enhanced_description(self, info: Dict, job_id: str, fallback_description: Optional[str]) -> Optional[str]:
        """Enhanced description extraction for Facebook/Instagram."""
        try:
            # For Facebook/Instagram, the full description is often in the title field
            # Check title first as it contains the complete content
            title = info.get('title', '')
            fulltitle = info.get('fulltitle', '')

            # Facebook often puts the full description in the title field
            # Look for title that seems to contain description content (long text)
            if title and len(title) > 100:  # Likely contains description content
                logger.info(f"Using title field as description for Facebook/Instagram: {job_id}")
                return title.strip()

            if fulltitle and len(fulltitle) > 100:  # Try fulltitle if title is short
                logger.info(f"Using fulltitle field as description for Facebook/Instagram: {job_id}")
                return fulltitle.strip()

            # Try the standard description from info
            description = info.get('description')
            if description and description.strip():
                logger.debug(f"Using standard description for {job_id}")
                return description.strip()

            # For Facebook/Instagram, we need to re-extract metadata without downloading
            # because the download process sometimes loses description data
            logger.info(f"Re-extracting metadata for better description: {job_id}")
            try:
                ydl_opts = {
                    'skip_download': True,
                    'extract_flat': False,
                    'socket_timeout': 30,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    fresh_info = ydl.extract_info(info.get('webpage_url') or info.get('original_url'), download=False)

                    # Check title/fulltitle first in fresh extraction
                    fresh_title = fresh_info.get('title', '')
                    fresh_fulltitle = fresh_info.get('fulltitle', '')

                    if fresh_title and len(fresh_title) > 100:
                        logger.info(f"Successfully extracted description from fresh title for {job_id}")
                        return fresh_title.strip()

                    if fresh_fulltitle and len(fresh_fulltitle) > 100:
                        logger.info(f"Successfully extracted description from fresh fulltitle for {job_id}")
                        return fresh_fulltitle.strip()

                    # Fallback to description field
                    fresh_description = fresh_info.get('description')
                    if fresh_description and fresh_description.strip():
                        logger.info(f"Successfully extracted description via re-extraction for {job_id}")
                        return fresh_description.strip()
            except Exception as e:
                logger.warning(f"Re-extraction failed for {job_id}: {e}")

            # Try to read from .description file
            safe_job_id = re.sub(r'[^\w\-_.]', '_', job_id)
            description_file = self.download_dir / f"{safe_job_id}.description"

            if description_file.exists():
                try:
                    with open(description_file, 'r', encoding='utf-8') as f:
                        file_description = f.read().strip()
                        if file_description:
                            logger.debug(f"Using description file for {job_id}")
                            return file_description
                except Exception as e:
                    logger.warning(f"Error reading description file for {job_id}: {e}")

            # Try to read from .info.json file and check title/fulltitle there too
            info_file = self.download_dir / f"{safe_job_id}.info.json"
            if info_file.exists():
                try:
                    import json
                    with open(info_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)

                        # Check title/fulltitle in JSON first
                        json_title = json_data.get('title', '')
                        json_fulltitle = json_data.get('fulltitle', '')

                        if json_title and len(json_title) > 100:
                            logger.debug(f"Using JSON title as description for {job_id}")
                            return json_title.strip()

                        if json_fulltitle and len(json_fulltitle) > 100:
                            logger.debug(f"Using JSON fulltitle as description for {job_id}")
                            return json_fulltitle.strip()

                        # Fallback to description field in JSON
                        json_description = json_data.get('description')
                        if json_description and json_description.strip():
                            logger.debug(f"Using JSON description for {job_id}")
                            return json_description.strip()
                except Exception as e:
                    logger.warning(f"Error reading info JSON file for {job_id}: {e}")

            # Fallback to uploader field if it contains meaningful content
            uploader = info.get('uploader', '')
            if uploader and len(uploader) > 50:  # Likely contains description
                logger.debug(f"Using uploader field as description for {job_id}")
                return uploader.strip()

            logger.warning(f"No description found for Facebook/Instagram video: {job_id}")
            return fallback_description

        except Exception as e:
            logger.error(f"Error in enhanced description extraction for {job_id}: {e}")
            return fallback_description

    def _parse_upload_date(self, upload_date_str: Optional[str]) -> Optional[datetime]:
        """Parse upload date string to datetime."""
        if not upload_date_str:
            return None
        
        try:
            # yt-dlp format: YYYYMMDD
            return datetime.strptime(upload_date_str, '%Y%m%d')
        except (ValueError, TypeError):
            return None
    
    def _validate_video_limits(self, metadata: VideoMetadata) -> bool:
        """Validate video against size and duration limits."""
        if metadata.duration and metadata.duration > settings.ai.max_video_duration:
            logger.warning(f"Video duration {metadata.duration}s exceeds limit")
            return False
        
        if metadata.file_size and metadata.file_size > settings.ai.max_file_size:
            logger.warning(f"Video size {metadata.file_size} exceeds limit")
            return False
        
        return True
    
    def _find_downloaded_file(self, safe_job_id: str, directory: Path) -> Optional[Path]:
        """Find the actual downloaded video file."""
        patterns = [
            f"{safe_job_id}.mp4",
            f"{safe_job_id}.mkv",
            f"{safe_job_id}.webm",
            f"{safe_job_id}.avi",
            f"{safe_job_id}.mov",
            f"{safe_job_id}.flv"
        ]
        
        for pattern in patterns:
            file_path = directory / pattern
            if file_path.exists():
                return file_path
        
        return None
    
    def _find_downloaded_audio_file(self, safe_job_id: str, directory: Path) -> Optional[Path]:
        """Find the actual downloaded audio file."""
        patterns = [
            f"{safe_job_id}.mp3", 
            f"{safe_job_id}.m4a", 
            f"{safe_job_id}.wav", 
            f"{safe_job_id}.opus", 
            f"{safe_job_id}_audio.mp3",
            f"{safe_job_id}_audio.m4a",
            f"{safe_job_id}_audio.wav",
            f"{safe_job_id}_audio.opus"
        ]
        
        for pattern in patterns:
            file_path = directory / pattern
            if file_path.exists():
                return file_path
        
        return None
    
    async def cancel_download(self, job_id: str) -> bool:
        """Cancel active download."""
        task = self._active_downloads.get(job_id)
        if task:
            task.cancel()
            self._active_downloads.pop(job_id, None)
            logger.info(f"Cancelled download for job {job_id}")
            return True
        return False
    
    async def cleanup_files(self, job_id: str) -> None:
        """Clean up downloaded files for a job."""
        try:
            safe_job_id = re.sub(r'[^\w\-_.]', '_', job_id)
            
            # Remove video and audio files
            for pattern in [f"{safe_job_id}.*", f"{safe_job_id}_audio.*"]:
                for file_path in self.download_dir.glob(pattern):
                    file_path.unlink()
                    logger.debug(f"Cleaned up file: {file_path}")
            
            # Remove info files
            for pattern in [f"{safe_job_id}.*.info.json"]:
                for file_path in self.download_dir.glob(pattern):
                    file_path.unlink()
                    logger.debug(f"Cleaned up info file: {file_path}")
        
        except Exception as e:
            logger.error(f"Error cleaning up files for {job_id}: {e}")
    
    async def get_download_status(self) -> Dict[str, int]:
        """Get current download statistics."""
        return {
            "active_downloads": len(self._active_downloads),
            "max_concurrent": settings.media.max_concurrent_downloads,
            "download_dir_files": len(list(self.download_dir.iterdir())),
            "temp_dir_files": len(list(self.temp_dir.iterdir())),
        }


class URLValidator:
    """Utility class for URL validation."""
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid and supported."""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ('http', 'https'))
        except Exception:
            return False
    
    @staticmethod
    def is_supported_platform(url: str) -> Tuple[bool, VideoSource]:
        """Check if URL is from a supported platform."""
        url_lower = url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return True, VideoSource.YOUTUBE
        elif "facebook.com" in url_lower or "fb.com" in url_lower:
            return True, VideoSource.FACEBOOK
        elif "instagram.com" in url_lower:
            return True, VideoSource.INSTAGRAM
        else:
            return False, VideoSource.UNKNOWN
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Clean and normalize URL."""
        # Remove tracking parameters and normalize
        url = url.strip()
        
        # Convert youtu.be to youtube.com
        if "youtu.be" in url:
            video_id = url.split("/")[-1].split("?")[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
        
        return url