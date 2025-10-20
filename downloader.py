"""
Moduł zawierający logikę komunikacji z yt-dlp.

Odpowiada za pobieranie informacji o filmach oraz za sam proces pobierania.
Działa w osobnym wątku i komunikuje się z głównym oknem za pomocą callbacków.
"""

import subprocess
import threading
import re
import json
import os
import requests
from packaging.version import parse as parse_version

def clean_ansi_codes(text):
    """Usuwa kody formatujące ANSI z tekstu."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class Downloader:
    """Klasa zarządzająca operacjami yt-dlp."""
    def __init__(self, yt_dlp_path, ffmpeg_base_path):
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_base_path = ffmpeg_base_path
        self.process = None
        self.cancel_requested = False

    def fetch_info(self, url, on_success, on_error):
        """Pobiera informacje o wideo lub playliście (JSON) w osobnym wątku."""
        def task():
            try:
                command = [self.yt_dlp_path, "--dump-single-json", "--yes-playlist", "--flat-playlist", url]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    on_error("Nie udało się wczytać podglądu. Błędny link lub film niedostępny.")
                    return
                
                data = json.loads(stdout)
                on_success(data)

            except Exception as e:
                on_error(f"Błąd wczytywania podglądu: {e}")
        
        threading.Thread(target=task, daemon=True).start()

    def fetch_thumbnail_for_playlist(self, entries, on_success, on_error):
        """Pobiera dane pierwszego wideo z playlisty, aby uzyskać miniaturkę."""
        def task():
            try:
                if not entries:
                    on_error("Playlista jest pusta.")
                    return
                
                first_video_url = entries[0].get('url')
                if not first_video_url:
                    on_error("Brak URL dla pierwszego wideo.")
                    return

                command = [self.yt_dlp_path, "--dump-single-json", first_video_url]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    video_data = json.loads(stdout)
                    thumbnail_url = video_data.get('thumbnail')
                    on_success(thumbnail_url)
                else:
                    on_error("Nie udało się pobrać danych o miniaturce.")

            except Exception as e:
                on_error(f"Błąd pobierania miniaturki: {e}")

        threading.Thread(target=task, daemon=True).start()

    def download(self, entries, options, on_progress, on_complete, on_error):
        """Rozpoczyna pobieranie plików w osobnym wątku."""
        def task():
            self.cancel_requested = False
            completed_count = 0
            total_files = len(entries)
            
            save_path = options['last_path']
            if options.get('create_playlist_folder', False) and len(entries) > 1:
                playlist_title = options.get('playlist_title', 'Playlista')
                sanitized_title = re.sub(r'[\\/*?:"<>|]', "", playlist_title)
                new_save_path = os.path.join(save_path, sanitized_title)
                os.makedirs(new_save_path, exist_ok=True)
                save_path = new_save_path 
            
            try:
                for i, entry in enumerate(entries):
                    if self.cancel_requested:
                        break
                    
                    url = entry.get('webpage_url', entry.get('url'))
                    on_progress({"type": "preview", "data": (entry, i + 1, total_files)})
                    on_progress({"type": "status", "data": f"Rozpoczynanie pobierania {i+1} z {total_files}..."})
                    
                    final_filepath = None
                    video_title = "Nieznany tytuł"
                    all_output = []

                    try:
                        command = self._build_command(url, save_path, options)
                        
                        self.process = subprocess.Popen(
                            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW, text=True,
                            encoding='utf-8', errors='ignore'
                        )

                        for line in iter(self.process.stdout.readline, ''):
                            if self.cancel_requested:
                                break
                            
                            clean_line = clean_ansi_codes(line.strip())
                            if not clean_line:
                                continue
                            
                            all_output.append(clean_line)
                            on_progress({"type": "status", "data": clean_line})
                            
                            dest_match = re.search(r"\[download\] Destination: (.+)", clean_line)
                            if dest_match:
                                final_filepath = dest_match.group(1)
                                video_title = os.path.splitext(os.path.basename(final_filepath))[0]
                            
                            merge_match = re.search(r"Merging formats into \"(.+)\"", clean_line)
                            if merge_match:
                                final_filepath = merge_match.group(1)
                                video_title = os.path.splitext(os.path.basename(final_filepath))[0]

                        self.process.stdout.close()
                        return_code = self.process.wait()

                        if not self.cancel_requested and return_code == 0:
                            completed_count += 1
                            history_entry = self._create_history_entry(video_title, url, save_path, options, final_filepath)
                            on_progress({"type": "history", "data": history_entry})
                        elif not self.cancel_requested and return_code != 0:
                            error_log = "\n".join(all_output[-5:])
                            on_error(f"Błąd yt-dlp (plik {i+1}, kod: {return_code}):\n{error_log}")

                    except Exception as e:
                        if not self.cancel_requested:
                            on_error(f"Błąd krytyczny (plik {i+1}):\n{e}")

            finally:
                self.process = None
                if not self.cancel_requested:
                    on_complete(f"Zakończono. Pobrano {completed_count}/{total_files} plików.")
        
        threading.Thread(target=task, daemon=True).start()

    def _build_command(self, url, save_path, options):
        """Tworzy listę argumentów dla polecenia yt-dlp."""
        output_template = os.path.join(save_path, "%(title)s.%(ext)s")
        # === POCZĄTEK ZMIAN: Dodanie flag do osadzania metadanych ===
        command = [
            self.yt_dlp_path, "--no-colors", "--progress", "--newline",
            "--embed-thumbnail", "--add-metadata",
            "--ffmpeg-location", self.ffmpeg_base_path,
            "-o", output_template
        ]
        # === KONIEC ZMIAN ===
        
        cookies_path = options.get("cookies_path", "")
        if cookies_path and os.path.exists(cookies_path):
            command.extend(["--cookies", cookies_path])

        if not options.get("use_part_files", False):
            command.append("--no-part")

        video_quality = options.get("video_quality", "Brak")
        audio_format = options.get("audio_format", "Brak")

        format_string = ""
        if video_quality != "Brak":
            command.extend(["--merge-output-format", "mp4"])
            if video_quality == "Najlepsza":
                format_string += "bestvideo+bestaudio/best"
            else:
                height = video_quality.split('p')[0]
                format_string += f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        
        if audio_format != "Brak" and video_quality == "Brak":
            command.extend(["-f", "bestaudio"])

        if format_string:
            command.extend(["-f", format_string])
        
        if audio_format != "Brak" and audio_format != "m4a (najlepsza)":
            command.extend(["-x", "--audio-format", audio_format.split(" ")[0]])
        
        subtitles_choice = options.get("subtitles_option", "Brak")
        if subtitles_choice == "Osadź w pliku":
            command.extend(["--embed-subs", "--all-subs"])
        elif subtitles_choice == "Osobny plik":
            command.extend(["--write-subs", "--all-subs"])

        start_time = options.get("start_time", "")
        end_time = options.get("end_time", "")
        if start_time or end_time:
            time_range = (start_time or "00:00") + "-" + (end_time or "")
            command.extend(["--download-sections", f"*{time_range}"])

        rate_limit = options.get("rate_limit", "")
        if rate_limit:
            command.extend(["--limit-rate", rate_limit])

        command.append(url)
        return command

    def _create_history_entry(self, title, url, save_path, options, filepath):
        """Tworzy wpis do historii pobierania."""
        from datetime import datetime
        return {
            "timestamp": datetime.now().isoformat(), "title": title, "url": url,
            "type": f"Wideo: {options.get('video_quality', 'N/A')}, Audio: {options.get('audio_format', 'N/A')}",
            "subtitles": options.get('subtitles_option', 'Brak'), 
            "path": filepath if filepath else save_path
        }

    def cancel_download(self):
        """Anuluje bieżące pobieranie."""
        self.cancel_requested = True
        if self.process:
            try:
                self.process.terminate()
            except Exception as e:
                print(f"Nie udało się zakończyć procesu: {e}")

    def check_for_updates(self, on_update_available):
        """Sprawdza dostępność aktualizacji yt-dlp w osobnym wątku."""
        def task():
            try:
                process = subprocess.Popen([self.yt_dlp_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                local_version_str, _ = process.communicate()
                if not local_version_str: return

                response = requests.get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", timeout=5)
                response.raise_for_status()
                latest_version_str = response.json()["tag_name"]

                if parse_version(latest_version_str) > parse_version(local_version_str.strip()):
                    on_update_available(latest_version_str, local_version_str.strip())
            except Exception as e:
                print(f"Nie udało się sprawdzić aktualizacji yt-dlp: {e}")

        threading.Thread(target=task, daemon=True).start()

