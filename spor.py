import subprocess
import sys
import time

# ===================== SSH101.com AYARLARI =====================
RTMP_URL = "rtmp://ssh101.bozztv.com:1935/ssh101"
STREAM_KEY = "b.1"
rtmp_server = f"{RTMP_URL}/{STREAM_KEY}"

# ===================== YAYIN AYARLARI =====================
VIDEO_URL = "https://vuvuu.enesgonullu2009-356.workers.dev/?url=https%3A%2F%2Fkool.to%2Fkool-iptv%2Fplay%2F24034250314fd9aa349685"
LOGO_URL = "https://raw.githubusercontent.com/ino8090/0101/refs/heads/main/1788625175420.png"

print("=" * 50)
print("📺 SSH101.com Yayın Başlatılıyor")
print("=" * 50)
print(f"🎬 Video: {VIDEO_URL}")
print(f"🎨 Logo: {LOGO_URL}")
print(f"🔑 Stream Key: {STREAM_KEY}")
print(f"📡 RTMP: {rtmp_server}")
print(f"🌐 İzleme: https://ssh101.com/live/{STREAM_KEY}")
print(f"📱 HLS: https://lbgo.bozztv.com/ssh101/ssh101/{STREAM_KEY}/playlist.m3u8")
print("=" * 50)

# FFmpeg komutu - Logo SAĞ ÜSTTE
command = [
    'ffmpeg',
    '-re',
    '-stream_loop', '-1',
    '-i', VIDEO_URL,
    '-i', LOGO_URL,
    '-filter_complex',
    '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black[v0];'
    '[1:v]scale=-1:90[logo];'
    '[v0][logo]overlay=W-w-10:10[v1];'
    '[v1]drawtext=text=:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:boxborderw=5:x=(w-text_w)/2:y=h-text_h-20[v]',
    '-map', '[v]',
    '-map', '0:a?',
    '-c:v', 'libx264',
    '-preset', 'veryfast',
    '-b:v', '4000k',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-f', 'flv',
    rtmp_server
]

print("\n🎥 SSH101.com yayını başlatılıyor...")
print("🖼️  Logo: Sağ üst")
print("📝 Alt yazı: t.me/digitaltivi")
print("⏸️  Durdurmak için: Ctrl + C\n")

try:
    proc = subprocess.Popen(command)
    
    # Yayını canlı tut
    while True:
        time.sleep(60)
        if proc.poll() is not None:
            print("⚠️ Yayın durdu, yeniden başlatılıyor...")
            proc = subprocess.Popen(command)
            
except KeyboardInterrupt:
    print("\n\n⛔ Yayın durduruluyor...")
    proc.terminate()
    print("✅ Yayın sonlandırıldı.")
