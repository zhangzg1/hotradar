"""
视频音频转录服务

优先提取原生字幕（秒级完成），无字幕时回退到 Qwen ASR 转录

支持 B站、YouTube、抖音等视频平台
"""
import os
import re
import uuid
import json
import asyncio
import subprocess
import aiohttp
import requests
from pathlib import Path
from typing import Optional, Tuple

import yt_dlp
import dashscope
from bilibili_api import video

from backend.common.logger import logger
from llm.utils import QWEN_ASR_BASE_URL, QWEN_API_KEY


PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMP_DIR = PROJECT_ROOT / ".video"  # 音频暂存目录

# Qwen ASR 配置
dashscope.base_http_api_url = QWEN_ASR_BASE_URL

# Qwen ASR 最大支持时长（秒）- 每个片段设置4分钟更稳健
MAX_AUDIO_DURATION = 240  # 4分钟


def extract_bvid(url: str) -> Optional[str]:
    """从B站URL中提取BV号"""
    patterns = [
        r"bilibili\.com/video/(BV[a-zA-Z0-9]+)",
        r"bilibili\.com/video/(bv[a-zA-Z0-9]+)",
        r"BV([a-zA-Z0-9]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            bvid = match.group(1) if "BV" in pattern or "bv" in pattern else f"BV{match.group(1)}"
            if bvid.startswith("bv"):
                bvid = "BV" + bvid[2:]
            return bvid

    return None


def detect_platform(url: str) -> str:
    """检测视频平台"""
    if "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "douyin.com" in url:
        return "douyin"
    else:
        return "other"


class SubtitleExtractor:
    """原生字幕提取器"""

    def _extract_youtube_video_id(self, url: str) -> Optional[str]:
        """从 YouTube URL 提取视频 ID"""
        patterns = [
            r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:embed/)([a-zA-Z0-9_-]{11})',
            r'(?:shorts/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def extract_youtube_subtitle(self, url: str) -> Optional[str]:
        """提取 YouTube 原生字幕（使用 youtube-transcript-api）"""
        video_id = self._extract_youtube_video_id(url)
        if not video_id:
            logger.warning("[字幕提取] 无法提取 YouTube 视频 ID")
            return None

        def _extract():
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                ytt_api = YouTubeTranscriptApi()
                transcript = ytt_api.fetch(video_id, languages=['zh-Hans', 'zh-CN', 'zh', 'en'])
                return "\n".join(entry.text for entry in transcript)
            except Exception as e:
                logger.warning(f"[字幕提取] YouTube 字幕提取失败: {e}")
                return None

        return await asyncio.to_thread(_extract)

    async def extract_bilibili_subtitle(self, url: str) -> Optional[str]:
        """提取 B站原生字幕"""
        bvid = extract_bvid(url)
        if not bvid:
            return None

        try:
            # 获取视频信息（包含cid）
            info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'https://www.bilibili.com/video/{bvid}'
            }

            resp = requests.get(info_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get('code') != 0:
                return None

            cid = data.get('data', {}).get('cid')
            if not cid:
                return None

            # 通过Player V2 API获取字幕信息
            player_url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
            resp2 = requests.get(player_url, headers=headers, timeout=10)
            if resp2.status_code != 200:
                return None

            player_data = resp2.json()
            subtitles = player_data.get('data', {}).get('subtitle', {}).get('subtitles', [])

            if not subtitles:
                return None

            first_sub = subtitles[0]
            sub_url = first_sub.get('subtitle_url')
            if not sub_url:
                return None

            if not sub_url.startswith('http'):
                sub_url = 'https://' + sub_url

            resp3 = requests.get(sub_url, headers=headers, timeout=10)
            if resp3.status_code != 200:
                return None

            sub_data = resp3.json()
            lines = [item.get('content', '') for item in sub_data.get('body', [])]
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"[字幕提取] B站字幕提取失败: {e}")
            return None

    def _parse_subtitle_content(self, content: str, ext: str) -> str:
        """解析字幕文件内容为纯文本"""
        lines = []

        if ext in ['srt', 'vtt']:
            for line in content.split('\n'):
                line = line.strip()
                if line.isdigit() or '-->' in line or line.startswith('WEBVTT') or not line:
                    continue
                line = re.sub(r'<[^>]+>', '', line)
                lines.append(line)

        elif ext in ['json3', 'srv3']:
            try:
                data = json.loads(content)
                for event in data.get('events', []):
                    if 'segs' not in event:
                        continue
                    text_parts = [seg.get('utf8', '') for seg in event.get('segs', []) if seg.get('utf8', '').strip()]
                    if text_parts:
                        lines.append(''.join(text_parts).strip())
            except json.JSONDecodeError:
                pass

        elif ext == 'json':
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    lines = [item.get('content', '') for item in data]
                elif isinstance(data, dict):
                    for event in data.get('events', []):
                        text = ''.join([s.get('utf8', '') for s in event.get('segs', [])])
                        if text.strip():
                            lines.append(text.strip())
            except json.JSONDecodeError:
                pass

        else:
            for line in content.split('\n'):
                line = line.strip()
                if line and '-->' not in line and not line.isdigit():
                    lines.append(line)

        return "\n".join(lines)

    async def extract(self, url: str) -> Optional[str]:
        """根据平台提取原生字幕"""
        platform = detect_platform(url)
        if platform == "youtube":
            return await self.extract_youtube_subtitle(url)
        elif platform == "bilibili":
            return await self.extract_bilibili_subtitle(url)
        return None


class BilibiliDownloader:
    """B站音频下载器"""

    HEADERS = {
        'Referer': 'https://www.bilibili.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    async def download_audio(self, url: str) -> Tuple[str, str]:
        """下载B站视频音频"""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())[:8]

        bvid = extract_bvid(url)
        if not bvid:
            raise ValueError(f"无法从URL提取BV号: {url}")

        v = video.Video(bvid=bvid)
        info = await v.get_info()
        title = info.get('title', 'unknown')

        download_info = await v.get_download_url(0)
        dash = download_info.get('dash', {})

        # B站 DASH 格式：视频和音频分离，直接下载音频流
        if 'audio' not in dash or not dash['audio']:
            raise ValueError("未找到音频流")

        audio_streams = dash['audio']
        best_audio = max(audio_streams, key=lambda x: x.get('bandwidth', 0))
        audio_url = best_audio.get('baseUrl') or best_audio.get('base_url')

        if not audio_url:
            raise ValueError("无法获取音频下载链接")

        audio_file = str(TEMP_DIR / f"audio_{unique_id}.m4a")

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            async with session.get(audio_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"下载失败: HTTP {resp.status}")
                with open(audio_file, 'wb') as f:
                    f.write(await resp.read())

        return audio_file, title


class DouyinDownloader:
    """抖音音频下载器"""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
        'Referer': 'https://www.douyin.com/',
    }

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'douyin\.com/video/(\d+)',
            r'iesdouyin\.com/share/video/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _resolve_short_url(self, url: str) -> Tuple[str, str]:
        resp = requests.get(url, headers=self.HEADERS, allow_redirects=True, timeout=10)
        return resp.url, self._extract_video_id(resp.url)

    def _parse_router_data(self, html: str) -> dict:
        match = re.search(r'_ROUTER_DATA\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return {}

    async def download_audio(self, url: str) -> Tuple[str, str]:
        """下载抖音视频音频"""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())[:8]

        real_url, video_id = await asyncio.to_thread(self._resolve_short_url, url)
        if not video_id:
            raise ValueError(f"无法从URL提取视频ID: {url}")

        share_url = f"https://www.iesdouyin.com/share/video/{video_id}"
        resp = await asyncio.to_thread(requests.get, share_url, headers=self.HEADERS, timeout=10)

        router_data = self._parse_router_data(resp.text)
        if not router_data:
            raise ValueError("无法解析页面数据")

        try:
            video_info = router_data['loaderData']['video_(id)/page']['videoInfoRes']['item_list'][0]
        except (KeyError, IndexError):
            raise ValueError("页面数据结构异常")

        title = video_info.get('desc', 'unknown')
        play_addr = video_info.get('video', {}).get('play_addr', {}).get('url_list', [])
        if not play_addr:
            raise ValueError("未找到播放地址")

        video_url = play_addr[0]
        video_file = str(TEMP_DIR / f"video_{unique_id}.mp4")
        audio_file = str(TEMP_DIR / f"audio_{unique_id}.m4a")

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            async with session.get(video_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"下载失败: HTTP {resp.status}")
                with open(video_file, 'wb') as f:
                    f.write(await resp.read())

        def _extract_audio():
            import subprocess
            subprocess.run([
                'ffmpeg', '-y', '-i', video_file,
                '-vn', '-acodec', 'aac', '-b:a', '128k',
                '-ac', '1', '-ar', '16000', audio_file
            ], capture_output=True, check=True)
            os.remove(video_file)

        await asyncio.to_thread(_extract_audio)
        return audio_file, title


class VideoDownloader:
    """通用视频下载器"""

    YDL_OPTS = {
        'format': 'bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a', 'preferredquality': '192'}],
        'postprocessor_args': ['-ac', '1', '-ar', '16000'],
        'prefer_ffmpeg': True,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    async def download_audio(self, url: str) -> Tuple[str, str]:
        """下载视频音频"""
        platform = detect_platform(url)

        if platform == "bilibili":
            return await BilibiliDownloader().download_audio(url)

        if platform == "douyin":
            return await DouyinDownloader().download_audio(url)

        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        unique_id = str(uuid.uuid4())[:8]
        output_template = str(TEMP_DIR / f"audio_{unique_id}.%(ext)s")

        ydl_opts = self.YDL_OPTS.copy()
        ydl_opts['outtmpl'] = output_template

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info.get('title', 'unknown')
            except Exception as e:
                raise RuntimeError(f"YouTube 音频下载失败: {e}") from e

        title = await asyncio.to_thread(_download)

        audio_file = str(TEMP_DIR / f"audio_{unique_id}.m4a")
        if not os.path.exists(audio_file):
            for ext in ['webm', 'mp4', 'mp3', 'opus']:
                alt_file = str(TEMP_DIR / f"audio_{unique_id}.{ext}")
                if os.path.exists(alt_file):
                    audio_file = alt_file
                    break

        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"音频文件未找到: {audio_file}")

        return audio_file, title


def convert_to_mp3(m4a_path: str) -> str:
    """将 m4a 转换为 mp3（Qwen ASR 需要）"""
    mp3_path = m4a_path.replace(".m4a", ".mp3")

    if os.path.exists(mp3_path):
        return mp3_path

    command = [
        "ffmpeg", "-y", "-i", m4a_path,
        "-ac", "1", "-ar", "16000",
        "-codec:a", "libmp3lame", mp3_path
    ]

    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return mp3_path


def get_audio_duration(audio_path: str) -> float:
    """获取音频时长（秒）"""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip() or 0)


def split_audio(audio_path: str, segment_duration: int = MAX_AUDIO_DURATION) -> list[str]:
    """将音频切分成多个片段"""
    base_path = audio_path.rsplit('.', 1)[0]
    ext = audio_path.rsplit('.', 1)[1]
    segments = []

    duration = get_audio_duration(audio_path)
    if duration <= segment_duration:
        return [audio_path]

    num_segments = int(duration / segment_duration) + 1
    logger.info(f"[转录] 音频时长 {duration:.1f}s，将切分为 {num_segments} 个片段")

    for i in range(num_segments):
        start_time = i * segment_duration
        segment_path = f"{base_path}_seg{i}.{ext}"

        # 重新编码以确保格式正确
        command = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start_time),
            "-t", str(segment_duration),
            "-ac", "1", "-ar", "16000",
            "-acodec", "aac", "-b:a", "64k",
            segment_path
        ]

        subprocess.run(command, capture_output=True, check=True)
        segments.append(segment_path)

    return segments


class QwenASRTranscriber:
    """Qwen ASR 转录器"""

    def _transcribe_segment(self, audio_path: str) -> str:
        """转录单个音频片段"""
        mp3_path = convert_to_mp3(audio_path)
        audio_file_url = f"file:///{mp3_path}"

        messages = [
            {
                "role": "user",
                "content": [{"audio": audio_file_url}]
            }
        ]

        try:
            response = dashscope.MultiModalConversation.call(
                api_key=QWEN_API_KEY,
                model="qwen3-asr-flash",
                messages=messages,
                result_format="message",
                asr_options={"enable_itn": False}
            )

            if response.status_code == 200:
                output = response.output
                if hasattr(output, 'choices') and output.choices:
                    content = output.choices[0].message.content
                    if content and isinstance(content, list) and len(content) > 0:
                        return content[0].get('text', '')
                if hasattr(output, 'text'):
                    return output.text
            else:
                logger.warning(f"[转录] Qwen ASR 错误: {response.code} - {response.message}")
                return ""

        except Exception as e:
            logger.warning(f"[转录] Qwen ASR 失败: {e}")
            return ""

        return ""

    def transcribe(self, audio_path: str) -> str:
        """转录音频为文字（支持分段处理长音频）"""
        duration = get_audio_duration(audio_path)

        # 如果音频不超过最大时长，直接处理
        if duration <= MAX_AUDIO_DURATION:
            return self._transcribe_segment(audio_path)

        # 长音频需要分段处理
        logger.info(f"[转录] 音频时长 {duration:.1f}s > {MAX_AUDIO_DURATION}s，启用分段处理")
        segments = split_audio(audio_path)

        results = []
        for i, seg_path in enumerate(segments):
            logger.info(f"[转录] 处理片段 {i+1}/{len(segments)}")
            text = self._transcribe_segment(seg_path)
            if text:
                results.append(text)
            # 清理临时片段文件
            mp3_seg = seg_path.replace(".m4a", ".mp3")
            for path in [seg_path, mp3_seg]:
                if path != audio_path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass

        return "\n".join(results)


# 转录超时（秒）
TRANSCRIBE_TIMEOUT_SUBTITLE = 10
TRANSCRIBE_TIMEOUT_DOWNLOAD = 30
TRANSCRIBE_TIMEOUT_ASR = 60


async def transcribe_video(url: str) -> Optional[str]:
    """
    转录视频为文字

    优先提取原生字幕，无字幕时回退到 Qwen ASR 转录
    每个阶段有独立超时，超时则返回 None
    """
    # 尝试提取原生字幕（限时）
    logger.info(f"[转录] 尝试提取原生字幕: {url}")
    try:
        subtitle_text = await asyncio.wait_for(
            SubtitleExtractor().extract(url),
            timeout=TRANSCRIBE_TIMEOUT_SUBTITLE,
        )
        if subtitle_text:
            logger.info(f"[转录] 字幕提取成功，文本长度: {len(subtitle_text)}")
            return subtitle_text
    except asyncio.TimeoutError:
        logger.warning(f"[转录] 字幕提取超时({TRANSCRIBE_TIMEOUT_SUBTITLE}s)，跳过")
    except Exception as e:
        logger.warning(f"[转录] 字幕提取失败: {e}")

    # 无字幕时，下载音频并用 Qwen ASR 转录（限时）
    logger.info(f"[转录] 无原生字幕，尝试 Qwen ASR 转录")
    audio_path = None
    mp3_path = None
    try:
        try:
            logger.info(f"[转录] 开始下载音频: {url}")
            audio_path, title = await asyncio.wait_for(
                VideoDownloader().download_audio(url),
                timeout=TRANSCRIBE_TIMEOUT_DOWNLOAD,
            )
            logger.info(f"[转录] 音频下载完成，开始转录: {audio_path}")

            def _transcribe():
                return QwenASRTranscriber().transcribe(audio_path)

            text = await asyncio.wait_for(
                asyncio.to_thread(_transcribe),
                timeout=TRANSCRIBE_TIMEOUT_ASR,
            )
            logger.info(f"[转录] 转录完成，文本长度: {len(text) if text else 0}")
            return text
        except asyncio.TimeoutError:
            logger.warning(f"[转录] ASR 转录超时，终止")
            return None
    except Exception as e:
        logger.warning(f"[转录] Qwen ASR 转录失败: {e}")
        return None
    finally:
        # 删除临时音频文件
        mp3_path = audio_path.replace(".m4a", ".mp3") if audio_path else None
        for path in [audio_path, mp3_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


async def fetch_video_content(url: str, fallback_content: str = "") -> str:
    """获取视频内容，失败时使用备用内容"""
    text = await transcribe_video(url)
    return text if text else fallback_content


async def fetch_bilibili_subtitle(url: str, fallback_content: str = "") -> str:
    """获取B站视频内容（兼容旧接口）"""
    text = await transcribe_video(url)
    return text if text else fallback_content