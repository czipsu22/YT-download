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

# Glowna klasa naszej aplikacji
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Zmienne stanu ---
        self.download_process = None
        self.is_downloading = False

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
        self.title("YT-downloader v2.0")
        self.geometry("900x520")
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
        self.url_entry.bind("<KeyRelease>", self.schedule_fetch_info)
        self.fetch_timer = None

        self.mode_switch = ctk.CTkSegmentedButton(self.controls_frame, values=["Wideo", "Tylko Audio"], command=self.toggle_menus)
        self.mode_switch.pack(padx=10, pady=5, fill="x")
        
        # --- Pojemnik na dynamiczne menu ---
        self.options_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.options_frame.pack(padx=10, pady=5, fill="x")

        self.quality_menu = ctk.CTkOptionMenu(self.options_frame, values=["Najlepsza", "4320p (8K)", "2160p (4K)", "1440p (QHD)", "1080p (Full HD)", "720p (HD)", "480p", "360p", "240p", "144p"], command=lambda _: self.save_settings())
        self.quality_menu.pack(fill="x")
        
        self.audio_format_menu = ctk.CTkOptionMenu(self.options_frame, values=["mp3", "m4a (najlepsza)", "opus"], command=lambda _: self.save_settings())
        
        self.path_label = ctk.CTkLabel(self.controls_frame, text="Folder zapisu:")
        self.path_label.pack(padx=10, pady=(5, 0), anchor="w")
        
        self.path_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.path_frame.pack(padx=10, pady=(0, 5), fill="x")
        self.path_frame.grid_columnconfigure(0, weight=1)
        
        self.path_entry = ctk.CTkEntry(self.path_frame)
        self.path_entry.grid(row=0, column=0, sticky="ew")

        self.browse_button = ctk.CTkButton(self.path_frame, text="...", width=40, command=self.browse_folder)
        self.browse_button.grid(row=0, column=1, padx=(5, 0))
        
        self.time_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.time_frame.pack(padx=10, pady=5, fill="x")
        self.time_frame.grid_columnconfigure((1, 3), weight=1)

        self.time_label = ctk.CTkLabel(self.time_frame, text="Pobierz fragment:")
        self.time_label.grid(row=0, column=0, padx=(0,10))
        self.start_time_entry = ctk.CTkEntry(self.time_frame, placeholder_text="00:00")
        self.start_time_entry.grid(row=0, column=1, sticky="ew")
        self.time_separator_label = ctk.CTkLabel(self.time_frame, text="-")
        self.time_separator_label.grid(row=0, column=2, padx=5)
        self.end_time_entry = ctk.CTkEntry(self.time_frame, placeholder_text="koniec")
        self.end_time_entry.grid(row=0, column=3, sticky="ew")

        self.subtitles_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.subtitles_frame.pack(padx=10, pady=5, fill="x")
        self.subtitles_label = ctk.CTkLabel(self.subtitles_frame, text="Napisy:")
        self.subtitles_label.pack(side="left", padx=(0, 10))
        self.subtitles_menu = ctk.CTkOptionMenu(self.subtitles_frame, values=["Brak", "Osadź w pliku", "Osobny plik"], command=lambda _: self.save_settings())
        self.subtitles_menu.pack(side="left", fill="x", expand=True)

        self.download_button = ctk.CTkButton(self.controls_frame, text="Pobierz", command=self.start_download_thread)
        self.download_button.pack(padx=10, pady=5, fill="x")

        self.progress_bar = ctk.CTkProgressBar(self.controls_frame)
        self.progress_bar.pack(padx=10, pady=5, fill="x")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self.controls_frame, text="Gotowy")
        self.status_label.pack(padx=10, pady=(0, 10), anchor="w")

        # --- Ramka prawa (podglad) ---
        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nswe")
        self.preview_frame.grid_rowconfigure(1, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        self.thumbnail_label = ctk.CTkLabel(self.preview_frame, text="Wklej link, aby zobaczyć podgląd...", height=200)
        self.thumbnail_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.title_label = ctk.CTkLabel(self.preview_frame, text="Tytuł", font=ctk.CTkFont(size=14, weight="bold"), wraplength=380)
        self.title_label.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # --- Ramka dolna (stopka) ---
        self.footer_frame = ctk.CTkFrame(self, height=25)
        self.footer_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        self.version_label = ctk.CTkLabel(self.footer_frame, text="YT-downloader v2.0 based on yt-dlp", font=ctk.CTkFont(size=10))
        self.version_label.pack(side="left", padx=10)

        self.devs_label = ctk.CTkLabel(self.footer_frame, text="devs: czipsu & gemini", font=ctk.CTkFont(size=10))
        self.devs_label.pack(side="right", padx=10)

        # Inicjalizacja stanu interfejsu
        self.load_settings()


    # --- Funkcje obslugujace zdarzenia ---

    def load_settings(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
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
                
                self.toggle_menus(self.mode_switch.get())
                return

        except (json.JSONDecodeError, FileNotFoundError):
            pass 
        
        # Ustawienia domyslne, jesli plik config nie istnieje lub jest uszkodzony
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
            "subtitles_option": self.subtitles_menu.get()
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Nie udalo sie zapisac ustawien: {e}")


    def schedule_fetch_info(self, event=None):
        if self.fetch_timer:
            self.after_cancel(self.fetch_timer)
        self.fetch_timer = self.after(750, self.start_fetch_info_thread)

    def start_fetch_info_thread(self):
        thread = threading.Thread(target=self.fetch_info_logic)
        thread.start()

    def fetch_info_logic(self):
        url = self.url_entry.get()
        if not url:
            self.clear_preview()
            return

        try:
            self.status_label.configure(text="Pobieranie informacji...")
            command = [self.yt_dlp_path, "--dump-single-json", "--playlist-items", "1", url]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                self.clear_preview(error=True)
                return
            
            data = json.loads(stdout)
            
            is_playlist = data.get('_type') == 'playlist'

            if is_playlist:
                title = data.get('title', 'Brak tytułu playlisty')
                if 'entries' in data and data['entries']:
                    thumbnail_url = data['entries'][0].get('thumbnail')
                else:
                    thumbnail_url = None
            else:
                title = data.get('title', 'Brak tytułu')
                thumbnail_url = data.get('thumbnail')

            self.update_preview(title, thumbnail_url)
            self.status_label.configure(text="Gotowy")

        except Exception as e:
            self.clear_preview(error=True)

    def update_preview(self, title, thumbnail_url):
        self.title_label.configure(text=title)
        
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url)
                response.raise_for_status()
                img_data = response.content
                img = Image.open(BytesIO(img_data))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(320, 180))
                self.thumbnail_label.configure(image=ctk_img, text="")
            except Exception:
                self.thumbnail_label.configure(image=None, text="Nie można załadować miniaturki")
        else:
            self.thumbnail_label.configure(image=None, text="Brak miniaturki")

    def clear_preview(self, error=False):
        self.thumbnail_label.configure(image=None, text="Wklej link, aby zobaczyć podgląd..." if not error else "Błędny link lub film niedostępny")
        self.title_label.configure(text="Tytuł")
        if error:
            self.status_label.configure(text="Błąd pobierania informacji")

    def clean_ansi_codes(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def toggle_menus(self, choice):
        self.save_settings()
        if choice == "Wideo":
            self.audio_format_menu.pack_forget()
            self.quality_menu.pack(fill="x")
        else:
            self.quality_menu.pack_forget()
            self.audio_format_menu.pack(fill="x")

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

        try:
            url = self.url_entry.get()
            if not url:
                raise ValueError("Musisz wkleić link!")

            save_path = self.path_entry.get()
            mode = self.mode_switch.get()

            command = [self.yt_dlp_path, "--ffmpeg-location", self.ffmpeg_base_path, "-o", os.path.join(save_path, "%(title)s.%(ext)s")]

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

            self.download_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)

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

            self.download_process.stdout.close()
            return_code = self.download_process.wait()

            if self.is_downloading:
                if return_code == 0:
                    self.status_label.configure(text="Gotowe! Plik zapisany.")
                    self.progress_bar.set(1)
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


# Uruchomienie aplikacji
if __name__ == "__main__":
    app = App()
    app.mainloop()
