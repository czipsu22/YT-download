"""
Główny moduł aplikacji zawierający klasę App.

Odpowiada za tworzenie interfejsu graficznego, obsługę zdarzeń
oraz komunikację z innymi modułami (downloader, settings_manager).
"""

import customtkinter as ctk
import tkinter
from tkinter import messagebox, filedialog
import os
import sys
import requests
import threading
from PIL import Image
from io import BytesIO

# Importowanie modułów z naszego projektu
import settings_manager
from ui_components import UpdateDialog, PlaylistDialog
from downloader import Downloader

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Podstawowa konfiguracja ---
        self._setup_paths()
        self.settings = settings_manager.load_settings(self.config_path)

        # Inicjalizacja "mózgu" aplikacji
        self.downloader = Downloader(self.yt_dlp_path, self.ffmpeg_base_path)

        # --- Zmienne stanu ---
        self.is_downloading = False
        self.current_playlist_entries = []
        self.is_playlist = False
        self.selected_entries_for_download = None
        self.current_item_info = None 
        self.action_timer = None
        self.create_playlist_folder = False
        
        # --- Konfiguracja okna ---
        # === POCZĄTEK ZMIAN: Aktualizacja wersji ===
        self.title("YT Downloader v3.0")
        # === KONIEC ZMIAN ===
        self.expanded_height = 750 
        self.compact_height = 490
        self.geometry(f"900x{self.compact_height}")

        if os.path.exists(self.icon_path):
            self.iconbitmap(self.icon_path)
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # --- Tworzenie interfejsu ---
        self._create_widgets()
        self._apply_settings()
        
        # --- Startowe zadania ---
        self.downloader.check_for_updates(
            on_update_available=lambda new, current: self.after(0, self.show_update_notification, new, current)
        )

    def _setup_paths(self):
        """Konfiguruje ścieżki do plików wykonywalnych i konfiguracyjnych."""
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
            messagebox.showerror("Błąd krytyczny", "Nie znaleziono pliku yt-dlp.exe!")
            sys.exit()
        if not os.path.exists(self.ffmpeg_path):
            messagebox.showerror("Błąd krytyczny", "Nie znaleziono pliku ffmpeg.exe!")
            sys.exit()

    def _create_widgets(self):
        """Tworzy i rozmieszcza wszystkie elementy interfejsu."""
        # --- Główny kontener i siatka ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Ramka lewa (kontrolki) ---
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_view = ctk.CTkTabview(self.controls_frame, command=self.on_tab_change, height=1)
        self.tab_view.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.tab_view.add("YouTube")
        self.tab_view.add("SoundCloud")
        self.tab_view.add("Inne")

        self.auto_download_checkbox = ctk.CTkCheckBox(self.controls_frame, text="Pobierz automatycznie po wklejeniu linku", command=self.save_settings)
        self.auto_download_checkbox.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        
        self.url_entry = ctk.CTkEntry(self.controls_frame, placeholder_text="Wklej link tutaj...")
        self.url_entry.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.url_entry.bind("<KeyRelease>", self.schedule_action_on_url)
        
        # --- Opcje jakości ---
        quality_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        quality_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        quality_frame.grid_columnconfigure((1, 3), weight=1)
        
        ctk.CTkLabel(quality_frame, text="Jakość wideo:").grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.video_quality_menu = ctk.CTkOptionMenu(quality_frame, values=["Brak", "Najlepsza", "4320p (8K)", "2160p (4K)", "1440p (QHD)", "1080p (Full HD)", "720p (HD)", "480p", "360p", "240p", "144p"], command=lambda _: self.save_settings())
        self.video_quality_menu.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")

        ctk.CTkLabel(quality_frame, text="Format audio:").grid(row=0, column=2, padx=(10,5), pady=5, sticky="w")
        self.audio_quality_menu = ctk.CTkOptionMenu(quality_frame, values=["Brak", "mp3", "m4a (najlepsza)", "opus"], command=lambda _: self.save_settings())
        self.audio_quality_menu.grid(row=0, column=3, pady=5, sticky="ew")
        
        # --- Ścieżka zapisu ---
        path_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        path_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        path_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(path_frame, text="Wybierz folder zapisu", command=self.browse_folder).grid(row=0, column=0, padx=(0, 10))
        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="Ścieżka zapisu...")
        self.path_entry.grid(row=0, column=1, sticky="ew")
        
        # --- Opcje zaawansowane ---
        self.adv_checkbox = ctk.CTkCheckBox(self.controls_frame, text="Pokaż opcje zaawansowane", command=self.toggle_advanced_options)
        self.adv_checkbox.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        
        self.advanced_frame = ctk.CTkFrame(self.controls_frame)
        self.advanced_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.advanced_frame, text="Pobierz fragment:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        time_inputs_frame = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        time_inputs_frame.grid(row=1, column=1, sticky="ew", padx=(0,10))
        time_inputs_frame.grid_columnconfigure((0, 2), weight=1)
        self.start_time_entry = ctk.CTkEntry(time_inputs_frame, placeholder_text="00:00")
        self.start_time_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(time_inputs_frame, text="-", padx=5).grid(row=0, column=1)
        self.end_time_entry = ctk.CTkEntry(time_inputs_frame, placeholder_text="koniec")
        self.end_time_entry.grid(row=0, column=2, sticky="ew")
        
        ctk.CTkLabel(self.advanced_frame, text="Napisy:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.subtitles_menu = ctk.CTkOptionMenu(self.advanced_frame, values=["Brak", "Osadź w pliku", "Osobny plik"], command=lambda _: self.save_settings())
        self.subtitles_menu.grid(row=2, column=1, sticky="ew", padx=(0,10), pady=5)
        
        ctk.CTkLabel(self.advanced_frame, text="Ogranicz prędkość:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.rate_limit_entry = ctk.CTkEntry(self.advanced_frame, placeholder_text="np. 2M, 500K")
        self.rate_limit_entry.grid(row=3, column=1, sticky="ew", padx=(0,10), pady=5)
        self.rate_limit_entry.bind("<KeyRelease>", lambda _: self.save_settings())

        self.part_files_checkbox = ctk.CTkCheckBox(self.advanced_frame, text="Użyj plików tymczasowych (.part)", command=self.save_settings)
        self.part_files_checkbox.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        
        ctk.CTkLabel(self.advanced_frame, text="Plik cookies:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
        cookies_frame = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        cookies_frame.grid(row=5, column=1, sticky="ew", padx=(0,10))
        cookies_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(cookies_frame, text="Wybierz...", command=self.browse_cookies).grid(row=0, column=0, padx=(0, 10))
        self.cookies_path_label = ctk.CTkLabel(cookies_frame, text="Brak", anchor="w")
        self.cookies_path_label.grid(row=0, column=1, sticky="ew")

        # --- Status i przycisk ---
        self.controls_frame.grid_rowconfigure(7, weight=1) # Spacer
        ctk.CTkLabel(self.controls_frame, text="").grid(row=7, column=0)

        self.status_textbox = ctk.CTkTextbox(self.controls_frame, height=100, 
            font=ctk.CTkFont(family="Courier New", size=11), 
            wrap="word", activate_scrollbars=True)
        self.status_textbox.grid(row=8, column=0, padx=10, pady=10, sticky="ew")
        self.status_textbox.insert("1.0", "Gotowy")
        self.status_textbox.configure(state="disabled")

        self.download_button = ctk.CTkButton(self.controls_frame, text="Pobierz", command=self.start_download, state="disabled")
        self.download_button.grid(row=9, column=0, padx=10, pady=5, sticky="ew")

        # --- Ramka prawa (podgląd) ---
        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nswe")
        self.preview_frame.grid_columnconfigure(0, weight=1)
        
        self.placeholder_image = Image.new("RGBA", (320, 180), (0,0,0,0))
        self.thumbnail_ctk_image = ctk.CTkImage(light_image=self.placeholder_image, size=(320, 180))
        self.thumbnail_label = ctk.CTkLabel(self.preview_frame, text="Wklej link, aby zobaczyć podgląd...", height=200, image=self.thumbnail_ctk_image)
        self.thumbnail_label.pack(padx=10, pady=10, fill="x")

        self.title_label = ctk.CTkLabel(self.preview_frame, text="", font=ctk.CTkFont(size=14, weight="bold"), wraplength=350, justify="left")
        self.title_label.pack(padx=10, pady=(0, 5), fill="x", anchor="n")

        self.resolution_label = ctk.CTkLabel(self.preview_frame, text="", font=ctk.CTkFont(size=12), wraplength=350, justify="left")
        self.resolution_label.pack(padx=10, pady=(0, 10), fill="x", anchor="n")

        self.playlist_button = ctk.CTkButton(self.preview_frame, text="Wyświetl listę pobierania", command=self.show_playlist_dialog, state="disabled")
        self.playlist_button.pack(padx=10, pady=10, fill="x")
        
        # --- Ramka dolna (stopka) ---
        footer_frame = ctk.CTkFrame(self, height=25)
        footer_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        # === POCZĄTEK ZMIAN: Aktualizacja wersji ===
        ctk.CTkLabel(footer_frame, text="YT Downloader v3.0 by czipsu & Gemini", font=ctk.CTkFont(size=10)).pack(side="left", padx=10)
        # === KONIEC ZMIAN ===

    def _apply_settings(self):
        """Aplikuje wczytane ustawienia do elementów interfejsu."""
        self.tab_view.set(self.settings["last_tab"])
        self.path_entry.insert(0, self.settings["last_path"])
        self.video_quality_menu.set(self.settings["video_quality"])
        self.audio_quality_menu.set(self.settings["audio_format"])
        if self.settings["auto_download"]: self.auto_download_checkbox.select()
        if self.settings["show_advanced"]: self.adv_checkbox.select()
        self.start_time_entry.insert(0, self.settings["start_time"])
        self.end_time_entry.insert(0, self.settings["end_time"])
        self.subtitles_menu.set(self.settings["subtitles_option"])
        self.rate_limit_entry.insert(0, self.settings["rate_limit"])
        if self.settings["use_part_files"]: self.part_files_checkbox.select()
        
        cookies_path = self.settings.get("cookies_path", "")
        if cookies_path and os.path.exists(cookies_path):
            self.cookies_path_label.configure(text=os.path.basename(cookies_path))
        else:
            self.cookies_path_label.configure(text="Brak")

        self.toggle_advanced_options()
        self.on_tab_change()

    def set_status(self, text):
        """Ustawia tekst w polu statusu."""
        self.status_textbox.configure(state="normal")
        self.status_textbox.delete("1.0", "end")
        self.status_textbox.insert("1.0", text)
        self.status_textbox.see("end") # Automatycznie przewija na dół
        self.status_textbox.configure(state="disabled")

    # --- Metody obsługi zdarzeń i logiki UI ---
    def save_settings(self):
        """Zbiera aktualne ustawienia z UI i zleca ich zapis."""
        self.settings["last_tab"] = self.tab_view.get()
        self.settings["last_path"] = self.path_entry.get()
        self.settings["video_quality"] = self.video_quality_menu.get()
        self.settings["audio_format"] = self.audio_quality_menu.get()
        self.settings["auto_download"] = self.auto_download_checkbox.get()
        self.settings["show_advanced"] = self.adv_checkbox.get()
        self.settings["start_time"] = self.start_time_entry.get()
        self.settings["end_time"] = self.end_time_entry.get()
        self.settings["subtitles_option"] = self.subtitles_menu.get()
        self.settings["rate_limit"] = self.rate_limit_entry.get()
        self.settings["use_part_files"] = self.part_files_checkbox.get()
        settings_manager.save_settings(self.config_path, self.settings)

    def toggle_advanced_options(self):
        if self.adv_checkbox.get() == 1:
            self.advanced_frame.grid(row=6, column=0, padx=10, pady=5, sticky="ew")
            self.geometry(f"900x{self.expanded_height}")
        else:
            self.advanced_frame.grid_forget()
            self.geometry(f"900x{self.compact_height}")
        self.save_settings()

    def on_tab_change(self):
        tab = self.tab_view.get()
        is_sc = (tab == "SoundCloud")
        
        self.video_quality_menu.configure(state="normal" if not is_sc else "disabled")
        if is_sc: self.video_quality_menu.set("Brak")
            
        self.playlist_button.configure(state="normal" if self.is_playlist and not (tab == "Inne") else "disabled")
        self.save_settings()

    def schedule_action_on_url(self, event=None):
        if self.action_timer:
            self.after_cancel(self.action_timer)
        self.action_timer = self.after(750, self.process_url_and_take_action)

    def process_url_and_take_action(self):
        url = self.url_entry.get()
        if url:
            self.download_button.configure(state="normal")
            if "soundcloud.com" in url: self.tab_view.set("SoundCloud")
            elif "youtube.com" in url or "youtu.be" in url: self.tab_view.set("YouTube")
        else:
            self.download_button.configure(state="disabled")

        if self.auto_download_checkbox.get() == 1:
            if url and not self.is_downloading:
                self.start_download()
        elif url:
            self.fetch_info()

    def browse_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder_path)
            self.save_settings()

    def browse_cookies(self):
        file_path = filedialog.askopenfilename(
            title="Wybierz plik cookies",
            filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")]
        )
        if file_path:
            self.settings["cookies_path"] = file_path
            self.cookies_path_label.configure(text=os.path.basename(file_path))
            self.save_settings()

    # --- Logika pobierania i wczytywania informacji ---
    def fetch_info(self):
        if self.tab_view.get() == "Inne" or self.is_downloading:
            return
        url = self.url_entry.get()
        if not url:
            self.clear_preview()
            return
        
        self.set_status("Pobieranie informacji...")
        self.downloader.fetch_info(url, 
            on_success=lambda data: self.after(0, self.update_info_success, data),
            on_error=lambda msg: self.after(0, self.update_info_error, msg)
        )

    def update_info_success(self, data):
        """Callback po pomyślnym wczytaniu danych o wideo/playliście."""
        self.set_status("Gotowy")
        self.current_item_info = data
        self.is_playlist = data.get('_type') == 'playlist'
        self.current_playlist_entries = data.get('entries', [])

        if self.is_playlist:
            title = data.get('title', 'Brak tytułu playlisty')
            resolution_text = "Playlista"
            self.title_label.configure(text=title)
            self.resolution_label.configure(text=resolution_text)
            
            if self.tab_view.get() != "Inne":
                self.playlist_button.configure(state="normal")

            self.downloader.fetch_thumbnail_for_playlist(
                self.current_playlist_entries,
                on_success=lambda thumb_url: self.after(0, self.update_playlist_thumbnail, thumb_url),
                on_error=lambda err_msg: print(err_msg)
            )
        else: 
            title = data.get('title', 'Brak tytułu')
            thumbnail_url = data.get('thumbnail')
            if self.tab_view.get() == "SoundCloud":
                resolution_text = "Utwór audio"
            else:
                max_h = max([f.get('height', 0) for f in data.get('formats', []) if f.get('height')]) if data.get('formats') else 0
                resolution_text = f"Maks. rozdzielczość: {max_h}p" if max_h > 0 else "Brak wideo"
            
            self.playlist_button.configure(state="disabled")
            self.update_preview_image(title, thumbnail_url, resolution_text)

    def update_playlist_thumbnail(self, thumbnail_url):
        """Callback, który aktualizuje miniaturkę po jej pobraniu w tle."""
        if thumbnail_url:
            self.update_preview_image(self.title_label.cget("text"), thumbnail_url, self.resolution_label.cget("text"))
        else:
            self._set_thumbnail(self.placeholder_image, "Brak miniaturki")

    def update_info_error(self, message):
        """Callback po błędzie wczytywania danych o wideo."""
        self.clear_preview(error=True)
        self.set_status(message)
        self.after(3000, self.reset_status_if_idle)

    def start_download(self):
        """Rozpoczyna lub anuluje proces pobierania."""
        if self.action_timer:
            self.after_cancel(self.action_timer)

        if self.is_downloading:
            self.downloader.cancel_download()
            self.reset_ui_to_idle("Anulowano pobieranie.")
            return

        self.is_downloading = True
        self.download_button.configure(text="Anuluj", fg_color="red", hover_color="#C00000")
        
        if self.selected_entries_for_download is not None:
            entries = self.selected_entries_for_download
        elif self.is_playlist:
            entries = self.current_playlist_entries
        else:
            entries = [{"webpage_url": self.url_entry.get(), "title": self.title_label.cget("text"), "thumbnail": self.current_item_info.get('thumbnail') if self.current_item_info else None}]
        
        options = { **self.settings } 
        options['create_playlist_folder'] = self.create_playlist_folder
        if self.is_playlist:
            options['playlist_title'] = self.current_item_info.get('title')
        
        if options["video_quality"] == "Brak" and options["audio_format"] == "Brak":
            self.show_error_dialog("Błąd", "Musisz wybrać jakość wideo lub format audio.")
            self.reset_ui_to_idle()
            return
            
        self.downloader.download(entries, options,
            on_progress=lambda p: self.after(0, self.handle_progress, p),
            on_complete=lambda msg: self.after(0, self.handle_completion, msg),
            on_error=lambda msg: self.after(0, self.show_error_dialog, "Błąd pobierania", msg)
        )

    def handle_progress(self, progress_data):
        """Obsługuje komunikaty o postępie z modułu downloader."""
        if progress_data["type"] == "status":
            self.set_status(progress_data["data"])
        elif progress_data["type"] == "preview":
            entry, current, total = progress_data["data"]
            self.update_preview_image(
                entry.get('title', 'Nieznany tytuł'),
                entry.get('thumbnail'),
                f"({current}/{total})"
            )
        elif progress_data["type"] == "history":
            self.settings["download_history"].insert(0, progress_data["data"])
            self.save_settings()

    def handle_completion(self, final_message):
        """Obsługuje zakończenie procesu pobierania."""
        if self.auto_download_checkbox.get():
             self.after(500, self.reset_for_next_download)
        self.reset_ui_to_idle(final_message)

    # --- Metody pomocnicze i aktualizujące UI ---
    def update_preview_image(self, title, thumbnail_url, resolution):
        """Aktualizuje panel podglądu (tytuł, rozdzielczość, miniaturka)."""
        self.title_label.configure(text=title)
        self.resolution_label.configure(text=resolution)
        
        if thumbnail_url:
            def fetch_image():
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
                    response = requests.get(thumbnail_url, headers=headers, timeout=5)
                    response.raise_for_status()
                    img_data = response.content
                    pil_img = Image.open(BytesIO(img_data))
                    self.after(0, lambda: self._set_thumbnail(pil_img, ""))
                except Exception as e:
                    print(f"Błąd pobierania miniaturki: {e}")
                    self.after(0, lambda: self._set_thumbnail(self.placeholder_image, "Błąd wczytania miniaturki"))
            
            threading.Thread(target=fetch_image, daemon=True).start()
        else:
            self._set_thumbnail(self.placeholder_image, "Brak miniaturki")
    
    def _set_thumbnail(self, pil_image, text):
        """Ustawia obraz w etykiecie miniaturki."""
        self.thumbnail_ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(320, 180))
        self.thumbnail_label.configure(image=self.thumbnail_ctk_image, text=text)

    def clear_preview(self, error=False):
        self._set_thumbnail(self.placeholder_image, "Wklej link, aby zobaczyć podgląd..." if not error else "Błędny link lub film niedostępny")
        self.title_label.configure(text="")
        self.resolution_label.configure(text="")
        self.playlist_button.configure(state="disabled")
        self.is_playlist = False
        self.current_playlist_entries = []
        self.current_item_info = None
        self.selected_entries_for_download = None
        self.create_playlist_folder = False

    def reset_for_next_download(self):
        self.url_entry.delete(0, "end")
        self.clear_preview()
    
    def reset_ui_to_idle(self, status_text="Gotowy"):
        self.is_downloading = False
        self.set_status(status_text)
        self.download_button.configure(text="Pobierz", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])
        self.selected_entries_for_download = None
        self.create_playlist_folder = False
        
        if self.is_playlist and self.current_item_info:
             self.update_info_success(self.current_item_info)

        if not self.url_entry.get():
            self.download_button.configure(state="disabled")
    
    def reset_status_if_idle(self):
        if not self.is_downloading:
            self.set_status("Gotowy")

    def show_playlist_dialog(self):
        if not self.current_playlist_entries:
            messagebox.showinfo("Informacja", "Brak wczytanej playlisty.")
            return
        PlaylistDialog(entries=self.current_playlist_entries, 
            callback=self.set_playlist_selection, 
            cancel_callback=lambda: None)

    def set_playlist_selection(self, selected_entries, create_folder):
        """Callback po zatwierdzeniu wyboru filmów z playlisty."""
        self.create_playlist_folder = create_folder
        self.selected_entries_for_download = selected_entries
        count = len(selected_entries)
        
        if count > 0:
            total = len(self.current_playlist_entries)
            self.title_label.configure(text=f"Wybrano {count} z {total} pozycji")
            self.resolution_label.configure(text="Możesz zmienić opcje i kliknąć 'Pobierz'")
            self.download_button.configure(state="normal")
        else:
            self.update_info_success(self.current_item_info)
        
    def show_update_notification(self, new_version, current_version):
        UpdateDialog(current_version=current_version, new_version=new_version)
    
    def show_error_dialog(self, title, message):
        messagebox.showerror(title, message)

