#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import os
import re
import json
import requests
import threading

# ===================== AYARLAR =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = os.getenv("STREAM_KEY") or "maxdizi"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

M3U_URL = os.getenv("M3U_URL") or "https://raw.githubusercontent.com/UzunMuhalefet/Legal-IPTV/refs/heads/main/lists/video/sources/www-kanald-com-tr/arsiv-diziler.m3u"
LOGO_URL = os.getenv("LOGO_URL") or "https://raw.githubusercontent.com/ino8090/0101/refs/heads/main/1791047356035.png"

STATE_FILE_NAME = os.getenv("STATE_FILE_NAME", "maxdizi.json")
GITHUB_STEP_SUMMARY = os.getenv("GITHUB_STEP_SUMMARY")

STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
STREAM_REFERER = "https://vidmody.com/"

LOGO_OPACITY = float(os.getenv("LOGO_OPACITY", "1.0"))
TEXT_OPACITY = float(os.getenv("TEXT_OPACITY", "1.0"))
BOLD_FONT_PATH = os.getenv("BOLD_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

FIFO_PIPE = "stream_fifo.ts"


def format_hms(total_seconds):
    total_seconds = max(0, int(total_seconds))
    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def get_highest_quality_hls_link(url):
    if not url.endswith('.m3u8') and '.m3u8?' not in url:
        return url
    try:
        headers = {'User-Agent': STREAM_USER_AGENT, 'Referer': STREAM_REFERER}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200 and '#EXTM3U' in res.text:
            lines = res.text.splitlines()
            best_url = None
            max_bandwidth = 0
            base_url = url.rsplit('/', 1)[0] + '/'
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    bw = int(bw_match.group(1)) if bw_match else 0
                    if i + 1 < len(lines):
                        sub_url = lines[i + 1].strip()
                        if not sub_url.startswith('http'):
                            sub_url = base_url + sub_url
                        if bw > max_bandwidth:
                            max_bandwidth = bw
                            best_url = sub_url
            if best_url:
                return best_url
    except Exception as e:
        print(f"⚠️ HLS Kalite ayrıştırma hatası: {e}")
    return url


def get_local_state():
    if os.path.exists(STATE_FILE_NAME) and os.path.getsize(STATE_FILE_NAME) > 0:
        try:
            with open(STATE_FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_index", 0), data.get("last_seconds", 0)
        except Exception:
            pass
    return 0, 0


def update_local_state(index, seconds):
    try:
        data = {"last_index": int(index), "last_seconds": int(seconds)}
        with open(STATE_FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ State hatası: {e}")


def get_m3u_playlist(m3u_url):
    try:
        headers = {'User-Agent': STREAM_USER_AGENT, 'Referer': STREAM_REFERER}
        res = requests.get(m3u_url, headers=headers, timeout=10)
        if res.status_code == 200:
            playlist = []
            pending_title = None
            for line in res.text.splitlines():
                line = line.strip()
                if line.startswith('#EXTINF'):
                    match = re.search(r',(.+)$', line)
                    pending_title = match.group(1).strip() if match else None
                elif line and not line.startswith('#') and line.startswith('http'):
                    title = pending_title or os.path.basename(line.split('?')[0])
                    playlist.append({"url": line, "title": title})
                    pending_title = None
            return playlist
    except Exception as e:
        print(f"⚠️ M3U Alma Hatası: {e}")
    return []


def create_fifo():
    if os.path.exists(FIFO_PIPE):
        os.remove(FIFO_PIPE)
    os.mkfifo(FIFO_PIPE)


def start_master_encoder():
    """
    OBS MANTIĞI: Bu FFmpeg işlemi M3U8 videoları bitse dahi ASLA kapanmaz.
    Girdiyi Named Pipe (FIFO) üzerinden okur ve RTMP sunucusuna kesintisiz aktarır.
    """
    has_logo = os.path.exists('logo.png') and os.path.getsize('logo.png') > 0
    title_drawtext = f"drawtext=textfile='title.txt':reload=1:fontfile='{BOLD_FONT_PATH}':fontcolor=white@{TEXT_OPACITY}:fontsize=19:x=w-tw-20:y=h-th-20"
    time_drawtext = f"drawtext=textfile='time.txt':reload=1:fontfile='{BOLD_FONT_PATH}':fontcolor=white@{TEXT_OPACITY}:fontsize=18:x=20:y=h-th-20"

    if has_logo:
        filter_str = (
            '[0:v]scale=1920:1080:flags=bicubic,setdar=16/9,fps=25[main];'
            f'[1:v]scale=-2:85,format=rgba,colorchannelmixer=aa={LOGO_OPACITY}[logo];'
            '[main][logo]overlay=50:50[tmp1];'
            f'[tmp1]{title_drawtext}[tmp2];'
            f'[tmp2]{time_drawtext}[v]'
        )
        logo_input = ['-i', 'logo.png']
    else:
        filter_str = (
            '[0:v]scale=1920:1080:flags=bicubic,setdar=16/9,fps=25[main];'
            f'[main]{title_drawtext}[tmp2];'
            f'[tmp2]{time_drawtext}[v]'
        )
        logo_input = []

    cmd = [
        'ffmpeg',
        '-re',
        '-i', FIFO_PIPE
    ] + logo_input + [
        '-filter_complex', filter_str,
        '-map', '[v]',
        '-map', '0:a:0?',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-pix_fmt', 'yuv420p',
        '-r', '25',
        '-b:v', '2500k',
        '-maxrate', '2500k',
        '-bufsize', '3500k',
        '-g', '50',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ac', '2',
        '-ar', '44100',
        '-f', 'flv',
        RTMP_SERVER
    ]
    return subprocess.Popen(cmd)


def feeder_loop():
    """
    Videoları tek tek indirip dönüştürerek FIFO borusuna basar.
    Bir film bittiğinde diğeri anında borunun içine yazılmaya başlar.
    """
    current_index, last_seconds = get_local_state()

    while True:
        playlist = get_m3u_playlist(M3U_URL)
        if not playlist:
            time.sleep(5)
            continue

        if current_index >= len(playlist):
            current_index = 0
            last_seconds = 0

        item = playlist[current_index]
        target_url = get_highest_quality_hls_link(item["url"])
        title = item["title"]

        with open('title.txt', 'w', encoding='utf-8') as f:
            f.write(title)

        print(f"\n🎬 Boruya Beslenen Video ({current_index + 1}/{len(playlist)}): {title}")

        headers_arg = f"User-Agent: {STREAM_USER_AGENT}\r\nReferer: https://vidmody.com/\r\n"
        seek_args = ['-ss', str(last_seconds)] if last_seconds > 0 else []

        # Videoyu MPEG-TS formatına çevirip boruya (FIFO) yazan FFmpeg
        feed_cmd = [
            'ffmpeg',
            '-headers', headers_arg,
            '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
            '-reconnect', '1', '-reconnect_at_eof', '1', '-reconnect_streamed', '1',
        ] + seek_args + [
            '-i', target_url,
            '-c:v', 'copy',      # En yüksek hız için kodlama yapmadan ham taşıma
            '-c:a', 'aac',
            '-f', 'mpegts',
            '-y',
            FIFO_PIPE
        ]

        proc = subprocess.Popen(feed_cmd)
        proc.wait()

        # Video bittiğinde bir sonraki videoya geç
        current_index += 1
        last_seconds = 0
        update_local_state(current_index, 0)
        print("⚡ Video bitti. Arka plandaki yayın kopmadan sıradaki videoya geçiliyor...")


def main():
    create_fifo()

    # 1. Ana Yayın İşlemcisini Başlat (OBS Gibi Kesintisiz)
    print("🚀 Ana RTMP Yayın İşlemcisi Başlatılıyor...")
    master_proc = start_master_encoder()

    # 2. Besleyiciyi Ayrı Bir Thread Üzerinde Çalıştır
    feeder_thread = threading.Thread(target=feeder_loop, daemon=True)
    feeder_thread.start()

    # Ana yayın işlemcisini izle
    master_proc.wait()


if __name__ == "__main__":
    main()
