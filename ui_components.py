"""
Moduł zawierający pomocnicze komponenty interfejsu,
takie jak niestandardowe okna dialogowe.
"""
import customtkinter as ctk
import webbrowser

class UpdateDialog(ctk.CTkToplevel):
    """Okno dialogowe informujące o dostępnej aktualizacji yt-dlp."""
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

class PlaylistDialog(ctk.CTkToplevel):
    """Okno dialogowe do wyboru filmów z playlisty."""
    def __init__(self, entries, callback, cancel_callback):
        super().__init__()
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.entries = entries
        self.checkboxes = []
        self.all_selected = True 

        self.title("Wybierz pozycje do pobrania")
        self.geometry("700x550") # Zwiększona wysokość
        self.resizable(True, True)
        self.transient()
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Zawartość playlisty")
        scrollable_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=15, sticky="nsew")
        scrollable_frame.grid_columnconfigure(0, weight=1)

        for i, entry in enumerate(self.entries):
            if not entry:
                continue
            title = entry.get('title', 'Brak tytułu')
            url = entry.get('webpage_url', entry.get('url'))
            if not url: continue

            var = ctk.StringVar(value="on")
            checkbox = ctk.CTkCheckBox(scrollable_frame, text=title, variable=var, onvalue="on", offvalue="off")
            checkbox.grid(row=i, column=0, padx=10, pady=5, sticky="w")
            self.checkboxes.append((var, entry))

        # === POCZĄTEK ZMIAN: Dodanie checkboxa do tworzenia folderu ===
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.grid(row=1, column=0, columnspan=2, padx=15, pady=(5,0), sticky="ew")
        
        self.create_folder_var = ctk.StringVar(value="on")
        create_folder_checkbox = ctk.CTkCheckBox(options_frame, text="Utwórz folder z nazwą playlisty", variable=self.create_folder_var, onvalue="on", offvalue="off")
        create_folder_checkbox.pack(side="left", padx=5)
        # === KONIEC ZMIAN ===

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        download_button = ctk.CTkButton(button_frame, text="Zatwierdź wybór", command=self.confirm_selection)
        download_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.toggle_all_button = ctk.CTkButton(button_frame, text="Odznacz wszystko", command=self.toggle_all_checkboxes)
        self.toggle_all_button.grid(row=0, column=1, padx=5, sticky="ew")

        cancel_button = ctk.CTkButton(button_frame, text="Anuluj", command=self.cancel, fg_color="gray")
        cancel_button.grid(row=0, column=2, padx=5, sticky="ew")

    def toggle_all_checkboxes(self):
        """Zaznacza lub odznacza wszystkie pozycje na liście."""
        self.all_selected = not self.all_selected
        
        new_state = "on" if self.all_selected else "off"
        for var, _ in self.checkboxes:
            var.set(new_state)
            
        new_text = "Odznacz wszystko" if self.all_selected else "Zaznacz wszystko"
        self.toggle_all_button.configure(text=new_text)

    def confirm_selection(self):
        selected_entries = [entry for var, entry in self.checkboxes if var.get() == "on"]
        # === POCZĄTEK ZMIAN: Przekazanie stanu checkboxa ===
        create_folder = self.create_folder_var.get() == "on"
        self.callback(selected_entries, create_folder)
        # === KONIEC ZMIAN ===
        self.destroy()

    def cancel(self):
        self.cancel_callback()
        self.destroy()
