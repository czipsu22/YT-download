"""
Moduł obsługujący logikę dla zakładki "Historia pobierania".

Odpowiada za wczytywanie, wyświetlanie i zarządzanie wpisami historii
w formie interaktywnych kart.
"""

import customtkinter as ctk
import webbrowser
import platform
import subprocess
from tkinter import messagebox
from datetime import datetime

# === NOWOŚĆ: Funkcja do otwierania folderu ===
def _open_file_in_explorer(filepath):
    """Otwiera folder i zaznacza podany plik (działa na Windows)."""
    try:
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{filepath}"')
        else:
            # TODO: Dodać obsługę macOS/Linux jeśli potrzebne
            print(f"Otwieranie folderu nie jest zaimplementowane dla {platform.system()}")
    except Exception as e:
        print(f"Nie udało się otworzyć folderu: {e}")

# === NOWOŚĆ: Funkcja do usuwania pojedynczego wpisu ===
def _delete_history_item(app, entry_to_delete):
    """Usuwa pojedynczy wpis z historii i odświeża widok."""
    if not messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz usunąć z historii:\n\n{entry_to_delete.get('title', 'Brak tytułu')}"):
        return
        
    try:
        # Znajdź i usuń wpis
        # Musimy iterować po kopii, aby bezpiecznie usunąć element
        for entry in list(app.settings["download_history"]):
            # Porównujemy po timestamp, zakładając że jest unikalny
            if entry.get("timestamp") == entry_to_delete.get("timestamp"):
                app.settings["download_history"].remove(entry)
                break
        
        app.save_settings()
        _load_history_cards(app) # Odśwież widok
    except Exception as e:
        app.show_error_dialog("Błąd", f"Nie udało się usunąć wpisu: {e}")


# === NOWOŚĆ: Funkcja tworząca pojedynczą kartę historii ===
def _create_history_card(parent_frame, app, entry):
    """Tworzy i zwraca ramkę (kartę) dla pojedynczego wpisu historii."""
    
    card = ctk.CTkFrame(parent_frame)
    card.grid(sticky="ew", padx=5, pady=(0, 5))
    card.grid_columnconfigure(0, weight=1) # Kolumna na tekst
    card.grid_columnconfigure(1, weight=0) # Kolumna na przycisk

    # --- Ramka na tekst (Tytuł, Data, Ścieżka) ---
    text_frame = ctk.CTkFrame(card, fg_color="transparent")
    text_frame.grid(row=0, column=0, padx=10, pady=5, sticky="w")
    
    # Tytuł
    title = entry.get('title', 'Brak tytułu')
    title_label = ctk.CTkLabel(text_frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), anchor="w", cursor="hand2")
    title_label.pack(fill="x", anchor="w")
    title_label.bind("<Button-1>", lambda e, url=entry.get('url'): webbrowser.open(url) if url else None)

    # Data i godzina
    try:
        ts_iso = entry.get("timestamp")
        ts_obj = datetime.fromisoformat(ts_iso)
        ts_formatted = ts_obj.strftime('Pobrano: %Y-%m-%d o %H:%M:%S')
    except (ValueError, TypeError, AttributeError):
        ts_formatted = "Data: Nieznana"
        
    date_label = ctk.CTkLabel(text_frame, text=ts_formatted, font=ctk.CTkFont(size=11), anchor="w", text_color="gray")
    date_label.pack(fill="x", anchor="w", pady=(0, 5))
    
    # Ścieżka zapisu
    path = entry.get('path', 'Brak ścieżki')
    path_label = ctk.CTkLabel(text_frame, text=f"Zapisano w: {path}", font=ctk.CTkFont(size=11), anchor="w", cursor="hand2")
    path_label.pack(fill="x", anchor="w")
    path_label.bind("<Button-1>", lambda e, p=path: _open_file_in_explorer(p) if p else None)

    # --- Przycisk usuwania (zabezpieczony przed brakiem ikony) ---
    
    # Dynamiczne tworzenie parametrów przycisku
    # Zapobiega crashowi, jeśli self.trash_icon jest None (choć wiemy, że jest)
    button_params = {
        "text": "Usuń",
        "width": 80,
        "fg_color": "transparent",
        "hover_color": "#3B3B3B",
        "text_color": "gray",
        "font": ctk.CTkFont(size=10),
        "command": lambda: _delete_history_item(app, entry)
    }
    
    if app.trash_icon:
        # Jeśli ikona istnieje, dodaj ją
        button_params["image"] = app.trash_icon
        button_params["compound"] = "top"
    else:
        # Jeśli ikony nie ma, przycisk będzie tylko tekstowy
        button_params["compound"] = "left" 
    
    delete_button = ctk.CTkButton(card, **button_params)
    delete_button.grid(row=0, column=1, padx=10, pady=10, sticky="e")
    
    return card

# === PRZEBUDOWANA: Główna funkcja ładowania ===
def _load_history_cards(app):
    """Wczytuje historię pobierania i tworzy karty w ramce."""
    
    # === POPRAWKA: Leniwe tworzenie ramki ===
    # Tworzymy CTkScrollableFrame dopiero przy pierwszym ładowaniu,
    # a nie podczas inicjalizacji okna, co zapobiega crashom.
    if app.history_scrollable_frame is None:
        app.history_scrollable_frame = ctk.CTkScrollableFrame(app.inne_tab, fg_color="transparent")
        app.history_scrollable_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        # === POPRAWKA: Literówka w nazwie metody ===
        # Usunięto błędny podkreślnik z 'grid_column_configure'
        app.history_scrollable_frame.grid_columnconfigure(0, weight=1)
        # === KONIEC POPRAWKI ===
    else:
        # 1. Wyczyść stare widgety (karty) z ramki
        for widget in app.history_scrollable_frame.winfo_children():
            widget.destroy()
    # === KONIEC POPRAWKI ===

    # 2. Wyczyść starą mapę URLi (już niepotrzebna)
    app.history_url_map.clear() 

    # 3. Pobierz historię (zawsze najpierw najnowsze)
    history = app.settings.get("download_history", [])

    if not history:
        # Pokaż informację, jeśli historia jest pusta
        ctk.CTkLabel(app.history_scrollable_frame, text="Historia pobierania jest pusta.",
                                                  font=ctk.CTkFont(size=14, slant="italic"),
                                                  text_color="gray").pack(padx=10, pady=20)
        return

    # 4. Utwórz nowe karty
    for entry in history:
        _create_history_card(app.history_scrollable_frame, app, entry)


# === ZMODYFIKOWANA: Funkcja czyszczenia historii ===
def _clear_history(app):
    """Czyści całą historię pobierania."""
    if not app.settings.get("download_history"):
         app.show_error_dialog("Informacja", "Historia pobierania jest już pusta.")
         return

    if messagebox.askyesno("Potwierdzenie", "Czy na pewno chcesz trwale usunąć CAŁĄ historię pobierania? Tej operacji nie można cofnąć."):
        app.settings["download_history"] = []
        app.save_settings()
        _load_history_cards(app) # Odśwież UI (pokaże pusty stan)


