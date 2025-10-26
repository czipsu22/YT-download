"""
Moduł do obsługi zapisywania i wczytywania ustawień z pliku config.json.
"""

import json
import os

def get_default_settings():
    """Zwraca słownik z domyślnymi ustawieniami aplikacji."""
    return {
        # POPRAWKA: Zmiana domyślnej zakładki na "Pobieranie" dla spójności
        "last_tab": "Pobieranie",
        "last_path": os.path.join(os.path.expanduser('~'), 'Downloads'),
        "video_quality": "1080p (Full HD)",
        "audio_format": "mp3",
        "auto_download": 0,
        "show_advanced": 0,
        "start_time": "",
        "end_time": "",
        "subtitles_option": "Brak",
        "rate_limit": "",
        "use_part_files": 0,
        "cookies_path": "",
        "download_history": [],
        
        # === POCZĄTEK ZMIAN: Ustawienia Subskrypcji ===
        "subscriptions": [],
        "service_installed": False,
        "monitoring_enabled": True,
        "monitoring_interval": 30 # w minutach
        # === KONIEC ZMIAN ===
    }

def load_settings(config_path):
    """Wczytuje ustawienia z pliku JSON. Jeśli plik nie istnieje, zwraca domyślne."""
    settings = get_default_settings()
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # Uzupełnij brakujące klucze w starym configu
                for key, value in settings.items():
                    if key not in loaded_settings:
                        loaded_settings[key] = value
                return loaded_settings
    except (json.JSONDecodeError, FileNotFoundError):
        pass # W razie błędu zwróci domyślne
    return settings

def save_settings(config_path, settings):
    """Zapisuje podany słownik ustawień do pliku JSON."""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Nie udało się zapisać ustawień: {e}")
