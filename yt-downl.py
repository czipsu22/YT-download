# Importowanie potrzebnych bibliotek
import customtkinter as ctk
import tkinter
from tkinter import messagebox
import os
import sys
import threading
import subprocess
import re
import requests
from PIL import Image
from io import BytesIO
import json
from datetime import datetime
import webbrowser
from packaging.version import parse as parse_version

# --- Okno dialogowe aktualizacji ---
class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, current_version, new_version):
        super().__init__()

        self.title("Dostępna aktualizacja!")
        self.geometry("400x180")
        self.resizable(False, False)
        self.transient()
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        main_frame.grid_columnconfigure((0, 1), weight=1)

        message = (f"Dostępna jest nowa wersja yt-dlp: {new_version}\n"
                   f"(Zainstalowana wersja: {current_version})\n\n"
                   "Aktualizacja jest zalecana, aby zapewnić\n"
                   "prawidłowe działanie aplikacji.")
        
        label = ctk.CTkLabel(main_frame, text=message, justify="left")
        label.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        github_button = ctk.CTkButton(main_frame, text="Otwórz stronę pobierania", command=self.open_github)
        github_button.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        close_button = ctk.CTkButton(main_frame, text="Zamknij", command=self.destroy, fg_color="gray")
        close_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

    def open_github(self):
        webbrowser.open("https://github.com/yt-dlp/yt-dlp/releases/latest")
        self.destroy()

# Glowna klasa naszej aplikacji
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Zmienne stanu ---
        self.download_process = None
        self.is_downloading = False
        self.download_history = []

        # --- Konfiguracja sciezek ---
        if getattr(sys, 'frozen', False):
            self.application_path = os.path.dirname(sys.executable)
            self.ffmpeg_base_path = sys._MEIPASS
        else:
            self.application_path = os.path.dirname(os.path.abspath(__file__))
            self.ffmpeg_base_path = self.application_path

        self.yt_dlp_path = os.path.join(self.application_path, "yt-dlp.exe")
        self.ffmpeg_path = os.path.join(self.ffmpeg_base_path, "ffmpeg.exe")
        self.icon_path = os.path.join(self.ffmpeg_base_path, "icon.ico")
        self.config_path = os.path.join(self.application_path, "config.json")
        
        if not os.path.exists(self.yt_dlp_path):
            messagebox.showerror("Błąd krytyczny", "Nie znaleziono pliku yt-dlp.exe!\nUpewnij się, że znajduje się on w tym samym folderze co aplikacja.")
            sys.exit()
        if not os.path.exists(self.ffmpeg_path):
            messagebox.showerror("Błąd krytyczny", "Nie znaleziono pliku ffmpeg.exe!\nTen plik powinien być dołączony do aplikacji.")
            sys.exit()

        # --- Konfiguracja okna ---
        self.title("YT Downloader v2.3")
        self.geometry("900x580")
        if os.path.exists(self.icon_path):
            self.iconbitmap(self.icon_path)
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- Glowny kontener i siatka ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Ramka lewa (kontrolki) ---
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")

        self.url_label = ctk.CTkLabel(self.controls_frame, text="Wklej link do filmu lub playlisty:")
        self.url_label.pack(padx=10, pady=(10, 0), anchor="w")
        self.url_entry = ctk.CTkEntry(self.controls_frame, placeholder_text="https://...")
        self.url_entry.pack(padx=10, pady=(0, 10), fill="x")
        self.url_entry.bind("<KeyRelease>", self.schedule_action_on_url)
        self.action_timer = None

        self.mode_switch = ctk.CTkSegmentedButton(self.controls_frame, values=["Wideo", "Tylko Audio"], command=self.toggle_menus)
        self.mode_switch.pack(padx=10, pady=10, fill="x")
        
        self.options_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.options_frame.pack(padx=10, pady=0, fill="x")
        self.options_frame.grid_columnconfigure(1, weight=1)

        self.quality_label = ctk.CTkLabel(self.options_frame, text="Jakość wideo:")
        self.quality_menu = ctk.CTkOptionMenu(self.options_frame, values=["Najlepsza", "4320p (8K)", "2160p (4K)", "1440p (QHD)", "1080p (Full HD)", "720p (HD)", "480p", "360p", "240p", "144p"], command=lambda _: self.save_settings())
        
        self.audio_format_label = ctk.CTkLabel(self.options_frame, text="Format audio:")
        self.audio_format_menu = ctk.CTkOptionMenu(self.options_frame, values=["mp3", "m4a (najlepsza)", "opus"], command=lambda _: self.save_settings())
        
        self.path_label = ctk.CTkLabel(self.controls_frame, text="Folder zapisu:")
        self.path_label.pack(padx=10, pady=(10, 0), anchor="w")
        
        self.path_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.path_frame.pack(padx=10, pady=(0, 10), fill="x")
        self.path_frame.grid_columnconfigure(0, weight=1)
        
        self.path_entry = ctk.CTkEntry(self.path_frame)
        self.path_entry.grid(row=0, column=0, sticky="ew")

        self.browse_button = ctk.CTkButton(self.path_frame, text="...", width=40, command=self.browse_folder)
        self.browse_button.grid(row=0, column=1, padx=(5, 0))
        
        self.advanced_frame = ctk.CTkFrame(self.controls_frame)
        self.advanced_frame.pack(padx=10, pady=10, fill="x")
        self.advanced_frame.grid_columnconfigure(1, weight=1)

        self.advanced_label = ctk.CTkLabel(self.advanced_frame, text="Opcje zaawansowane", font=ctk.CTkFont(size=12, weight="bold"))
        self.advanced_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="w")
        
        self.time_label = ctk.CTkLabel(self.advanced_frame, text="Pobierz fragment:")
        self.time_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.time_inputs_frame = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        self.time_inputs_frame.grid(row=1, column=1, sticky="ew", padx=(0,10))
        self.time_inputs_frame.grid_columnconfigure((0, 2), weight=1)
        self.start_time_entry = ctk.CTkEntry(self.time_inputs_frame, placeholder_text="00:00")
        self.start_time_entry.grid(row=0, column=0, sticky="ew")
        self.time_separator_label = ctk.CTkLabel(self.time_inputs_frame, text="-", padx=5)
        self.time_separator_label.grid(row=0, column=1)
        self.end_time_entry = ctk.CTkEntry(self.time_inputs_frame, placeholder_text="koniec")
        self.end_time_entry.grid(row=0, column=2, sticky="ew")
        
        self.subtitles_label = ctk.CTkLabel(self.advanced_frame, text="Napisy:")
        self.subtitles_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.subtitles_menu = ctk.CTkOptionMenu(self.advanced_frame, values=["Brak", "Osadź w pliku", "Osobny plik"], command=lambda _: self.save_settings())
        self.subtitles_menu.grid(row=2, column=1, sticky="ew", padx=(0,10), pady=5)


        self.spacer = ctk.CTkLabel(self.controls_frame, text="")
        self.spacer.pack(fill="y", expand=True)

        self.auto_download_checkbox = ctk.CTkCheckBox(self.controls_frame, text="Pobierz automatycznie po wklejeniu linku", command=self.save_settings)
        self.auto_download_checkbox.pack(padx=10, pady=5, anchor="w")

        self.download_button = ctk.CTkButton(self.controls_frame, text="Pobierz", command=self.start_download_thread)
        self.download_button.pack(padx=10, pady=5, fill="x")

        self.status_label = ctk.CTkLabel(self.controls_frame, text="Gotowy")
        self.status_label.pack(padx=10, pady=(10, 2), anchor="w")

        self.progress_bar = ctk.CTkProgressBar(self.controls_frame)
        self.progress_bar.pack(padx=10, pady=(2, 10), fill="x")
        self.progress_bar.set(0)

        # --- Ramka prawa (podglad) ---
        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nswe")
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=0)
        self.preview_frame.grid_rowconfigure(1, weight=0)
        self.preview_frame.grid_rowconfigure(2, weight=1)

        self.placeholder_image = Image.new("RGBA", (320, 180), (0,0,0,0))
        self.thumbnail_ctk_image = ctk.CTkImage(light_image=self.placeholder_image, size=(320, 180))
        self.thumbnail_label = ctk.CTkLabel(self.preview_frame, text="Wklej link, aby zobaczyć podgląd...", height=200, image=self.thumbnail_ctk_image)
        self.thumbnail_label.pack(padx=10, pady=10, fill="x")

        self.title_label = ctk.CTkLabel(self.preview_frame, text="", font=ctk.CTkFont(size=14, weight="bold"), wraplength=350, justify="left")
        self.title_label.pack(padx=10, pady=(0, 5), fill="x", anchor="n")

        self.resolution_label = ctk.CTkLabel(self.preview_frame, text="", font=ctk.CTkFont(size=12), wraplength=350, justify="left")
        self.resolution_label.pack(padx=10, pady=(0, 10), fill="x", anchor="n")
        
        # --- Ramka dolna (stopka) ---
        self.footer_frame = ctk.CTkFrame(self, height=25)
        self.footer_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        self.version_label = ctk.CTkLabel(self.footer_frame, text="YT Downloader v2.3 by czipsu & Gemini", font=ctk.CTkFont(size=10))
        self.version_label.pack(side="left", padx=10)

        # Inicjalizacja stanu interfejsu
        self.load_settings()
        self.start_update_check_thread()


    # --- Funkcje obslugujace zdarzenia ---
    
    def start_update_check_thread(self):
        thread = threading.Thread(target=self.check_for_updates_logic)
        thread.daemon = True
        thread.start()

    def check_for_updates_logic(self):
        try:
            # Sprawdzenie lokalnej wersji
            process = subprocess.Popen([self.yt_dlp_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            local_version_str, _ = process.communicate()
            if not local_version_str: return

            # Sprawdzenie najnowszej wersji na GitHub
            response = requests.get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", timeout=5)
            response.raise_for_status()
            latest_version_str = response.json()["tag_name"]

            # Porownanie wersji
            if parse_version(latest_version_str) > parse_version(local_version_str.strip()):
                self.after(0, self.show_update_notification, latest_version_str, local_version_str.strip())

        except Exception as e:
            print(f"Nie udało się sprawdzić aktualizacji yt-dlp: {e}")

    def show_update_notification(self, new_version, current_version):
        dialog = UpdateDialog(current_version=current_version, new_version=new_version)

    def load_settings(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                last_path = settings.get("last_path")
                if last_path and os.path.isdir(last_path):
                    self.path_entry.insert(0, last_path)
                else:
                    self.path_entry.insert(0, os.path.join(os.path.expanduser('~'), 'Downloads'))
                
                self.mode_switch.set(settings.get("download_mode", "Wideo"))
                self.quality_menu.set(settings.get("video_quality", "1440p (QHD)"))
                self.audio_format_menu.set(settings.get("audio_format", "mp3"))
                self.subtitles_menu.set(settings.get("subtitles_option", "Brak"))
                if settings.get("auto_download", 0) == 1:
                    self.auto_download_checkbox.select()

                self.download_history = settings.get("download_history", [])
                
                self.toggle_menus(self.mode_switch.get())
                return

        except (json.JSONDecodeError, FileNotFoundError):
            pass 
        
        self.path_entry.insert(0, os.path.join(os.path.expanduser('~'), 'Downloads'))
        self.mode_switch.set("Wideo")
        self.quality_menu.set("1440p (QHD)")
        self.audio_format_menu.set("mp3")
        self.subtitles_menu.set("Brak")
        self.toggle_menus("Wideo")

    def save_settings(self):
        settings = {
            "last_path": self.path_entry.get(),
            "download_mode": self.mode_switch.get(),
            "video_quality": self.quality_menu.get(),
            "audio_format": self.audio_format_menu.get(),
            "subtitles_option": self.subtitles_menu.get(),
            "auto_download": self.auto_download_checkbox.get(),
            "download_history": self.download_history
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Nie udalo sie zapisac ustawien: {e}")

    def schedule_action_on_url(self, event=None):
        if self.action_timer:
            self.after_cancel(self.action_timer)
        self.action_timer = self.after(750, self.start_action_thread)

    def start_action_thread(self):
        if self.auto_download_checkbox.get() == 1:
            if self.url_entry.get() and not self.is_downloading:
                self.start_download_thread()
        else:
            self.start_fetch_info_thread()

    def start_fetch_info_thread(self):
        thread = threading.Thread(target=self.fetch_info_logic)
        thread.daemon = True
        thread.start()

    def fetch_info_logic(self):
        url = self.url_entry.get()
        if not url:
            self.after(0, self.clear_preview)
            return

        try:
            self.after(0, lambda: self.status_label.configure(text="Pobieranie informacji..."))
            command = [self.yt_dlp_path, "--dump-single-json", url]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                self.after(0, lambda: self.clear_preview(error=True))
                return
            
            data = json.loads(stdout)
            
            is_playlist = data.get('_type') == 'playlist'

            if is_playlist:
                title = data.get('title', 'Brak tytułu playlisty')
                video_info = data.get('entries', [{}])[0]
                if not video_info: # Pusta playlista
                    self.after(0, self.update_preview, title, None, "Playlista jest pusta")
                    self.after(0, lambda: self.status_label.configure(text="Gotowy"))
                    return
            else:
                title = data.get('title', 'Brak tytułu')
                video_info = data
            
            thumbnail_url = video_info.get('thumbnail')
            
            max_height = 0
            if 'formats' in video_info:
                for f in video_info['formats']:
                    if f.get('height') is not None:
                        if f['height'] > max_height:
                            max_height = f['height']
            
            resolution_text = f"Maks. rozdzielczość: {max_height}p" if max_height > 0 else ""

            img_data = None
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url)
                    response.raise_for_status()
                    img_data = response.content
                except requests.RequestException:
                    img_data = None
            
            self.after(0, self.update_preview, title, img_data, resolution_text)
            self.after(0, lambda: self.status_label.configure(text="Gotowy"))

        except Exception:
            self.after(0, lambda: self.clear_preview(error=True))

    def update_preview(self, title, img_data, resolution):
        self.title_label.configure(text=title)
        self.resolution_label.configure(text=resolution)
        
        new_pil_image = self.placeholder_image
        text_to_show = ""
        
        if img_data:
            try:
                new_pil_image = Image.open(BytesIO(img_data))
            except Exception as e:
                print(f"Błąd podczas tworzenia obrazu: {e}")
                text_to_show = "Nie można załadować miniaturki"
        else:
            text_to_show = "Brak miniaturki"

        self.thumbnail_ctk_image = ctk.CTkImage(light_image=new_pil_image, dark_image=new_pil_image, size=(320, 180))
        self.thumbnail_label.configure(image=self.thumbnail_ctk_image, text=text_to_show)


    def clear_preview(self, error=False):
        self.thumbnail_ctk_image = ctk.CTkImage(light_image=self.placeholder_image, dark_image=self.placeholder_image, size=(320, 180))
        self.thumbnail_label.configure(image=self.thumbnail_ctk_image, text="Wklej link, aby zobaczyć podgląd..." if not error else "Błędny link lub film niedostępny")
        self.title_label.configure(text="")
        self.resolution_label.configure(text="")
        if error:
            self.status_label.configure(text="Błąd pobierania informacji")

    def reset_for_next_download(self):
        self.url_entry.delete(0, "end")
        self.clear_preview()

    def clean_ansi_codes(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def toggle_menus(self, choice):
        self.save_settings()
        if choice == "Wideo":
            self.audio_format_label.grid_forget()
            self.audio_format_menu.grid_forget()
            self.quality_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
            self.quality_menu.grid(row=0, column=1, sticky="ew")
        else:
            self.quality_label.grid_forget()
            self.quality_menu.grid_forget()
            self.audio_format_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
            self.audio_format_menu.grid(row=0, column=1, sticky="ew")

    def browse_folder(self):
        folder_path = tkinter.filedialog.askdirectory()
        if folder_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder_path)
            self.save_settings()

    def start_download_thread(self):
        if self.is_downloading:
            self.cancel_download()
        else:
            thread = threading.Thread(target=self.download_logic)
            thread.daemon = True
            thread.start()

    def cancel_download(self):
        if self.download_process:
            self.is_downloading = False
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.download_process.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
            self.status_label.configure(text="Anulowano pobieranie.")

    def download_logic(self):
        self.is_downloading = True
        self.download_button.configure(text="Anuluj", fg_color="red", hover_color="#C00000")
        self.progress_bar.set(0)
        self.status_label.configure(text="Rozpoczynam...")
        
        was_auto_download_enabled = self.auto_download_checkbox.get() == 1
        final_filepath = None
        video_title = "Nieznany tytuł"

        try:
            url = self.url_entry.get()
            if not url:
                raise ValueError("Musisz wkleić link!")

            save_path = self.path_entry.get()
            
            output_template = os.path.join(save_path, "%(title)s.%(ext)s")

            mode = self.mode_switch.get()

            command = [self.yt_dlp_path, "--ffmpeg-location", self.ffmpeg_base_path, "-o", output_template]

            if mode == "Wideo":
                quality = self.quality_menu.get()
                if quality == "Najlepsza":
                    command.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
                else:
                    height = quality.split('p')[0]
                    command.extend(["-f", f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
            else:
                audio_format = self.audio_format_menu.get().split(' ')[0]
                if audio_format == "m4a":
                    command.extend(["-f", "bestaudio[ext=m4a]"])
                else:
                    command.extend(["-x", "--audio-format", audio_format])
            
            subtitles_choice = self.subtitles_menu.get()
            if subtitles_choice == "Osadź w pliku":
                command.extend(["--embed-subs", "--all-subs"])
            elif subtitles_choice == "Osobny plik":
                command.extend(["--write-subs", "--all-subs"])
            
            start_time = self.start_time_entry.get()
            end_time = self.end_time_entry.get()
            if start_time or end_time:
                time_range = (start_time or "00:00") + "-" + (end_time or "")
                command.extend(["--download-sections", f"*{time_range}"])

            command.append(url)

            self.download_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)

            for line in iter(self.download_process.stdout.readline, ''):
                if not self.is_downloading:
                    break
                clean_line = self.clean_ansi_codes(line.strip())
                
                match = re.search(r"\[download\]\s+([\d\.]+)%", clean_line)
                if match:
                    percentage = float(match.group(1)) / 100
                    self.progress_bar.set(percentage)
                    self.status_label.configure(text=f"Pobieranie... {match.group(1)}%")
                elif "merging" in clean_line.lower():
                    self.status_label.configure(text="Scalanie plików...")
                elif "extracting" in clean_line.lower():
                    self.status_label.configure(text="Konwertowanie audio...")

                dest_match = re.search(r"\[download\] Destination: (.+)", clean_line)
                merge_match = re.search(r"Merging formats into \"(.+)\"", clean_line)
                
                if dest_match:
                    final_filepath = dest_match.group(1)
                    video_title = os.path.splitext(os.path.basename(final_filepath))[0]

                if merge_match:
                    final_filepath = merge_match.group(1)
                    video_title = os.path.splitext(os.path.basename(final_filepath))[0]

            self.download_process.stdout.close()
            return_code = self.download_process.wait()

            if self.is_downloading:
                if return_code == 0:
                    self.status_label.configure(text="Gotowe! Plik zapisany.")
                    self.progress_bar.set(1)
                    
                    history_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "title": video_title,
                        "url": url,
                        "type": mode,
                        "quality_format": self.quality_menu.get() if mode == "Wideo" else self.audio_format_menu.get(),
                        "subtitles": subtitles_choice,
                        "path": final_filepath if final_filepath else save_path
                    }
                    self.add_to_history(history_entry)

                    if was_auto_download_enabled:
                        self.after(500, self.reset_for_next_download)
                else:
                    self.status_label.configure(text=f"Wystąpił błąd (kod: {return_code})")

        except ValueError as ve:
            self.status_label.configure(text=f"Błąd: {str(ve)}")
        except Exception as e:
            self.status_label.configure(text=f"Wystąpił krytyczny błąd.")
        finally:
            self.is_downloading = False
            self.download_process = None
            self.download_button.configure(text="Pobierz", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])

    def add_to_history(self, entry):
        self.download_history.insert(0, entry)
        self.save_settings()


# Uruchomienie aplikacji
if __name__ == "__main__":
    app = App()
    app.mainloop()


