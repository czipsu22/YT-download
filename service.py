"""
Moduł usługi działającej w tle.

Odpowiada za uruchamianie się w trybie bez UI,
monitorowanie subskrybowanych kanałów w pętli
i pobieranie nowych filmów przy użyciu modułu Downloader.
"""

import sys
import os
import time
import subprocess
import settings_manager
# === POPRAWKA BŁĘDU IMPORTU ===
from downloader import YtdlpDownloader
# === KONIEC POPRAWKI ===

# Ustalanie ścieżek (musimy to zrobić na nowo, bo działamy jako osobny proces)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    ffmpeg_base_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_base_path = application_path

yt_dlp_path = os.path.join(application_path, "yt-dlp.exe")
config_path = os.path.join(application_path, "config.json")
archive_path = os.path.join(application_path, "download_archive.txt")

def start_service():
    """Główna pętla usługi."""
    
    # Sprawdzenie, czy kluczowe pliki istnieją
    if not os.path.exists(yt_dlp_path):
        # W razie błędu nie możemy nawet pokazać okna, więc logujemy do pliku
        with open(os.path.join(application_path, "service_error.log"), "a") as f:
            f.write(f"{time.ctime()}: Błąd krytyczny: Nie znaleziono yt-dlp.exe\n")
        return

    # === POPRAWKA BŁĘDU IMPORTU ===
    downloader = YtdlpDownloader(yt_dlp_path, ffmpeg_base_path, archive_path)
    # === KONIEC POPRAWKI ===
    
    while True:
        settings = settings_manager.load_settings(config_path)
        
        # === POPRAWKA BŁĘDNEJ LOGIKI ===
        # Usługa nie powinna sprawdzać, czy jest "zainstalowana" (to tylko dla UI).
        # Powinna sprawdzać TYLKO, czy monitorowanie jest włączone.
        if not settings.get("monitoring_enabled", False):
            # Jeśli monitorowanie jest wyłączone w configu, po prostu śpij
            time.sleep(300) # Sprawdź ponownie za 5 minut
            continue
        # === KONIEC POPRAWKI ===

        subscriptions = settings.get("subscriptions", [])
        if subscriptions:
            
            # Tworzymy listę "entries" dla downloadera
            # Musimy podać 'webpage_url', bo z tego korzysta downloader
            entries_to_check = [{"webpage_url": url, "title": f"Subskrypcja: {url}"} for url in subscriptions]
            
            # Używamy tych samych opcji co UI, ale bez folderu playlisty
            download_options = {
                "last_path": settings["last_path"],
                "video_quality": settings["video_quality"],
                "audio_format": settings["audio_format"],
                "subtitles_option": settings["subtitles_option"],
                "use_part_files": settings["use_part_files"],
                "cookies_path": settings["cookies_path"],
                "rate_limit": settings.get("rate_limit", ""), # Upewnij się, że klucz istnieje
                "create_playlist_folder": False # Nigdy nie twórz folderów dla subskrypcji
            }

            try:
                # Uruchamiamy pobieranie BEZ callbacków (bo nie mamy UI)
                # Downloader sprawdzi archiwum i pobierze tylko nowe filmy
                downloader.download(
                    entries_to_check,
                    download_options,
                    on_progress=None,
                    on_complete=None,
                    on_error=None # Błędy będą po prostu ignorowane w tle
                )
            except Exception as e:
                # Logowanie błędów do pliku
                with open(os.path.join(application_path, "service_error.log"), "a") as f:
                    f.write(f"{time.ctime()}: Błąd podczas pętli pobierania: {e}\n")

        # Czekamy na następne sprawdzenie
        interval_minutes = settings.get("monitoring_interval", 30)
        time.sleep(interval_minutes * 60)

