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
from datetime import datetime # Dodano dla historii

def clean_ansi_codes(text):
    """Usuwa kody formatujące ANSI z tekstu."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# === POCZĄTEK POPRAWKI: Zmiana nazwy klasy ===
class YtdlpDownloader:
# === KONIEC POPRAWKI ===
    """Klasa zarządzająca operacjami yt-dlp."""
    # === POCZĄTEK POPRAWKI: Dodanie archive_path ===
    def __init__(self, yt_dlp_path, ffmpeg_base_path, archive_path):
    # === KONIEC POPRAWKI ===
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_base_path = ffmpeg_base_path
        # === POCZĄTEK POPRAWKI: Dodanie archive_path ===
        self.archive_path = archive_path
        # === KONIEC POPRAWKI ===
        self.process = None
        self.cancel_requested = False
        self.current_filepath = None # Do śledzenia ścieżki przy konwersji

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

    # === POCZĄTEK POPRAWKI: Opcjonalne callbacki ===
    def download(self, entries, options, on_progress=None, on_complete=None, on_error=None):
    # === KONIEC POPRAWKI ===
        """Rozpoczyna pobieranie plików w osobnym wątku."""
        def task():
            self.cancel_requested = False
            completed_count = 0
            total_files = len(entries)
            self.current_filepath = None # Resetuj ścieżkę

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
                    # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                    if on_progress:
                        on_progress({"type": "preview", "data": (entry, i + 1, total_files)})
                        on_progress({"type": "status", "data": f"Rozpoczynanie pobierania {i+1} z {total_files}..."})
                    else:
                        print(f"INFO (Service): Rozpoczynanie pobierania {i+1}/{total_files}: {entry.get('title', url)}")
                    # === KONIEC POPRAWKI ===

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
                            # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                            if on_progress:
                                on_progress({"type": "status", "data": clean_line})
                            # === KONIEC POPRAWKI ===

                            dest_match = re.search(r"\[download\] Destination: (.+)", clean_line)
                            if dest_match:
                                self.current_filepath = dest_match.group(1) # Zapisz oryginalną ścieżkę
                                video_title = os.path.splitext(os.path.basename(self.current_filepath))[0]

                            merge_match = re.search(r"Merging formats into \"(.+)\"", clean_line)
                            if merge_match:
                                self.current_filepath = merge_match.group(1) # Nadpisz ścieżkę po scaleniu
                                video_title = os.path.splitext(os.path.basename(self.current_filepath))[0]

                            # Sprawdź komunikat o usuwaniu oryginalnego pliku po konwersji
                            delete_match = re.search(r"\[ffmpeg\] Deleting original file .+", clean_line)
                            if delete_match and self.current_filepath:
                                # Spróbuj odgadnąć nową nazwę (często zmiana kontenera)
                                base, _ = os.path.splitext(self.current_filepath)
                                potential_new_path = base + ".mp4" # Zakładamy mp4 po konwersji
                                if os.path.exists(potential_new_path):
                                     self.current_filepath = potential_new_path


                        self.process.stdout.close()
                        return_code = self.process.wait()
                        final_filepath = self.current_filepath # Użyj ostatniej znanej ścieżki

                        if not self.cancel_requested and return_code == 0:
                            completed_count += 1
                            history_entry = self._create_history_entry(video_title, url, save_path, options, final_filepath)
                            # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                            if on_progress:
                                on_progress({"type": "history", "data": history_entry})
                            # === KONIEC POPRAWKI ===
                        elif not self.cancel_requested and return_code != 0:
                            error_log = "\n".join(all_output[-5:])
                            # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                            if on_error:
                                on_error(f"Błąd yt-dlp (plik {i+1}, kod: {return_code}):\n{error_log}")
                            else:
                                print(f"ERROR (Service): Błąd yt-dlp (plik {i+1}, kod: {return_code}):\n{error_log}")
                            # === KONIEC POPRAWKI ===

                    except Exception as e:
                        if not self.cancel_requested:
                             # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                            if on_error:
                                on_error(f"Błąd krytyczny (plik {i+1}):\n{e}")
                            else:
                                print(f"ERROR (Service): Błąd krytyczny (plik {i+1}):\n{e}")
                             # === KONIEC POPRAWKI ===

            finally:
                self.process = None
                if not self.cancel_requested:
                    # === POCZĄTEK POPRAWKI: Sprawdzenie, czy callback istnieje ===
                    if on_complete:
                        on_complete(f"Zakończono. Pobrano {completed_count}/{total_files} plików.")
                    else:
                        print(f"INFO (Service): Zakończono sprawdzanie/pobieranie. Pobrano {completed_count}/{total_files} nowych plików.")
                    # === KONIEC POPRAWKI ===

        threading.Thread(target=task, daemon=True).start()

    def _build_command(self, url, save_path, options):
        """Tworzy listę argumentów dla polecenia yt-dlp."""
        output_template = os.path.join(save_path, "%(title)s.%(ext)s")
        command = [
            self.yt_dlp_path, "--no-colors", "--progress", "--newline",
            # === POCZĄTEK POPRAWKI: Wymuszenie konwersji miniatur ===
            "--embed-thumbnail", # Zostaje, na Twoją prośbę
            "--convert-thumbnails", "jpg", # NOWA FLAGA: Rozwiązuje problem z .webp
            "--add-metadata",
            # "--force-delete-tempfiles", # Usunięto - powodowało błędy scalania
            # === KONIEC POPRAWKI ===
            "--ffmpeg-location", self.ffmpeg_base_path,
            # === POCZĄTEK POPRAWKI: Dodanie archiwum ===
            "--download-archive", self.archive_path,
            # === KONIEC POPRAWKI ===
            "-o", output_template
        ]

        cookies_path = options.get("cookies_path", "")
        if cookies_path and os.path.exists(cookies_path):
            command.extend(["--cookies", cookies_path])

        if not options.get("use_part_files", False):
            command.append("--no-part")

        video_quality = options.get("video_quality", "Brak")
        audio_format = options.get("audio_format", "Brak")

        format_string = ""

        if video_quality != "Brak" and audio_format != "Brak":
            # SCENARIUSZ 1: Wideo + Audio
            command.extend(["--merge-output-format", "mp4"])
            if video_quality == "Najlepsza":
                format_string = "bestvideo+bestaudio/best"
            else:
                height = video_quality.split('p')[0]
                format_string = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

        elif video_quality != "Brak" and audio_format == "Brak":
            # SCENARIUSZ 2: Tylko Wideo (z post-processingiem ffmpeg)
            command.extend(["--merge-output-format", "mp4"]) # Upewnij się, że końcowy plik to mp4
            if video_quality == "Najlepsza":
                format_string = "bestvideo/best" # Pobierz najlepsze wideo
            else:
                height = video_quality.split('p')[0]
                format_string = f"bestvideo[height<={height}]/best[height<={height}]" # Pobierz wideo o określonej wysokości
            # Dodaj post-processor ffmpeg do usunięcia audio
            command.extend(["--postprocessor-args", "ffmpeg:-an"])

        elif video_quality == "Brak" and audio_format != "Brak":
            # SCENARIUSZ 3: Tylko Audio
            format_string = "bestaudio"


        if format_string:
            command.extend(["-f", format_string])

        # Logika re-enkodowania audio (działa tylko gdy wybrano format audio)
        if audio_format != "Brak" and audio_format != "m4a (najlepsza)":
             # Upewnij się, że -x jest dodawane tylko, gdy pobieramy *jakieś* audio
            if video_quality == "Brak" or audio_format != "Brak":
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
                # Zakończ proces yt-dlp i jego procesy potomne (ffmpeg)
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                               check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                 print(f"INFO: Nie udało się zakończyć procesu yt-dlp (może już zakończony?): {e}")
            except Exception as e:
                print(f"BŁĄD: Nieoczekiwany błąd podczas próby zakończenia procesu: {e}")
            finally:
                self.process = None # Ustaw proces na None po próbie zakończenia


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




