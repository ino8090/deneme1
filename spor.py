#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import time
import os
import re
from collections import deque
import requests

# ===================== YAYIN AYARLARI =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = os.getenv("STREAM_KEY") or "b1"
RTMP_SERVER = f"{RTMP_URL}/{STREAM_KEY}"

PAGE_URL = os.getenv("STREAM_URL") or "https://vuvuu.enesgonullu2009-356.workers.dev/?url=https%3A%2F%2Fkool.to%2Fkool-iptv%2Fplay%2F5934938605e361d7e0ff0"
STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"

# ===================== LOGO AYARLARI =====================
LOGO_URL = os.getenv("LOGO_URL") or "https://raw.githubusercontent.com/ino8090/0101/refs/heads/main/1788625175420.png"
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

LOGO_WIDTH = 213     # Piksel genişliği
LOGO_X = 1620       # Konum X
LOGO_Y = 30          # Konum Y
LOGO_OPACITY = 1.0   # Saydamlık


def ensure_logo_downloaded():
    """Logoyu indirir ve kaydeder."""
    if os.path.exists(LOGO_PATH) and os.path.getsize(LOGO_PATH) > 0:
        return True
    try:
        print(f"⬇️ Logo indiriliyor: {LOGO_URL}")
        resp = requests.get(LOGO_URL, headers={"User-Agent": STREAM_USER_AGENT}, timeout=15)
        resp.raise_for_status()
        with open(LOGO_PATH, "wb") as f:
            f.write(resp.content)
        print(f"✅ Logo indirildi: {LOGO_PATH}")
        return True
    except Exception as e:
        print(f"⚠️ Logo indirilemedi: {e}")
        return False


def extract_m3u8(page_url):
    """M3u8 linkini çözer."""
    if page_url.endswith(".m3u8"):
        return page_url

    headers = {
        "User-Agent": STREAM_USER_AGENT, 
        "Referer": "https://kool.to/"
    }
    try:
        response = requests.get(page_url, headers=headers, timeout=10)
        matches = re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', response.text)
        if matches:
            return matches[0]
    except Exception as e:
        print(f"⚠️ Link çıkarma hatası: {e}")

    return page_url


def start_live_relay():
    logo_available = ensure_logo_downloaded()

    while True:
        stream_target = extract_m3u8(PAGE_URL)

        print("\n" + "=" * 50)
        print(f"📡 Yayın Başlatılıyor...")
        print(f"🎯 Kaynak Stream: {stream_target}")
        print(f"📍 Logo Konumu: X={LOGO_X}px, Y={LOGO_Y}px | Genişlik: {LOGO_WIDTH}px")
        print("=" * 50)

        # FFmpeg Filtre Zinciri
        if logo_available:
            filter_complex = (
                f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[bg];"
                f"[1:v]scale={LOGO_WIDTH}:-1,format=rgba,colorchannelmixer=aa={LOGO_OPACITY}[logo];"
                f"[bg][logo]overlay={LOGO_X}:{LOGO_Y},fps=25[v]"
            )
        else:
            filter_complex = (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=25[v]"
            )

        command = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-user_agent', STREAM_USER_AGENT,
            '-headers', 'Referer: https://kool.to/\r\n',
            
            # Kaynak (m3u8) Kararlılık Ayarları
            '-reconnect', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-i', stream_target
        ]

        if logo_available:
            command += ['-loop', '1', '-i', LOGO_PATH]

        command += [
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '0:a?',
            
            # Video Kodlama (Bitrate: 2000k olarak ayarlandı)
            '-c:v', 'libx264',
            '-preset', 'superfast',
            '-pix_fmt', 'yuv420p',
            '-r', '25',
            '-b:v', '2000k',
            '-maxrate', '2000k',
            '-bufsize', '4000k',
            '-g', '50',
            
            # Ses Kodlama
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            
            # RTMP Sunucu Kopma Engelleyici Bayraklar
            '-flvflags', 'no_duration_filesize',
            '-rtmp_live', 'live',
            '-f', 'flv',
            RTMP_SERVER
        ]

        stderr_tail = deque(maxlen=20)

        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )

        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                stderr_tail.append(line.rstrip())

        print(f"⚠️ Yayın koptu/sunucu bağlantıyı kesti (Return Code: {process.returncode}).")
        if stderr_tail:
            print("🧾 Son Loglar:")
            for tail_line in stderr_tail:
                print(f"   {tail_line}")

        # Beklemeden hızlıca tekrar bağlan (5 Saniye)
        print("🔄 5 saniye içinde tekrar bağlanılıyor...")
        time.sleep(5)


if __name__ == "__main__":
    start_live_relay()
