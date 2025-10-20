"""
Moduł do zarządzania konfiguracją aplikacji.

Odpowiada za wczytywanie i zapisywanie ustawień do pliku config.json.
"""

import json
import os

def load_settings(config_path):
    """Wczytuje ustawienia z pliku JSON."""
    default_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    default_settings = {
        "last_tab": "YouTube",
        "last_path": default_path,
        "video_quality": "1080p (Full HD)",
        "audio_format": "mp3",
        "auto_download": 0,
        "show_advanced": 0,
        "start_time": "",
        "end_time": "",
        "subtitles_option": "Brak",
        "rate_limit": "",
        "use_part_files": 0,
        "download_history": []
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Upewnij się, że wszystkie klucze istnieją
                for key, value in default_settings.items():
                    settings.setdefault(key, value)
                return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return default_settings # Zwróć domyślne w razie błędu

    return default_settings

def save_settings(config_path, settings):
    """Zapisuje ustawienia do pliku JSON."""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Nie udało się zapisać ustawień: {e}")
