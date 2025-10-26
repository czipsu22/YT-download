"""
Moduł obsługujący logikę zakładki "Subskrypcje".

Zawiera funkcje do zarządzania usługą Autostart oraz
listą subskrybowanych kanałów.
"""

import customtkinter as ctk
from tkinter import messagebox
import os

def _update_service_status_ui(app):
    """Aktualizuje UI w zakładce Subskrypcje na podstawie configu."""
    if not app.startup_folder_path:
        app.service_status_label.configure(text="Status usługi: Nieobsługiwane (Tylko Windows)")
        app.service_toggle_button.configure(state="disabled")
        app.monitoring_enabled_checkbox.configure(state="disabled")
        app.monitoring_interval_menu.configure(state="disabled")
        return

    is_installed = os.path.exists(app.autostart_script_path)

    if is_installed != app.settings.get("service_installed", False):
        app.settings["service_installed"] = is_installed
        app.save_settings()

    if is_installed:
        app.service_status_label.configure(text="Status usługi: Aktywna (w Autostart)")
        app.service_toggle_button.configure(text="Odinstaluj usługę z Autostart", fg_color="red", hover_color="#C00000")
    else:
        app.service_status_label.configure(text="Status usługi: Nieaktywna")
        app.service_toggle_button.configure(text="Zainstaluj usługę w Autostart", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"])

    # Opcje monitorowania muszą być zawsze aktywne, aby umożliwić konfigurację przed instalacją
    app.monitoring_enabled_checkbox.configure(state="normal")
    app.monitoring_interval_menu.configure(state="normal")


def _toggle_service(app):
    """Instaluje lub odinstalowuje usługę (skrót w Autostart)."""
    is_installed = app.settings.get("service_installed", False)

    if is_installed:
        try:
            if os.path.exists(app.autostart_script_path): os.remove(app.autostart_script_path)
            app.settings["service_installed"] = False
            app.save_settings()
            _update_service_status_ui(app)
            messagebox.showinfo("Sukces", "Usługa została odinstalowana z folderu Autostart.")
        except Exception as e:
            app.show_error_dialog("Błąd", f"Nie udało się usunąć pliku z Autostart:\n{e}\n\nSpróbuj ręcznie usunąć plik:\n{app.autostart_script_path}")
    else:
        try:
            # === POCZĄTEK POPRAWKI: Dodanie "start" do .bat ===
            # Używamy `start ""` aby uruchomić proces w nowym,
            # oddzielnym wątku i natychmiast zamknąć okno .bat,
            # a `pythonw.exe` (z app.executable_path) ukryje samo okno Pythona.
            bat_content = (
                f'@echo off\n'
                f'cd /D "{app.application_path}"\n'
                f'start "" {app.executable_path} --run-service\n'
            )
            # === KONIEC POPRAWKI ===
            with open(app.autostart_script_path, "w") as f: f.write(bat_content)
            app.settings["service_installed"] = True
            app.save_settings()
            _update_service_status_ui(app)
            messagebox.showinfo("Sukces", "Usługa została zainstalowana w Autostart.\n\nUruchomi się automatycznie (w tle) przy następnym starcie systemu.")
        except Exception as e:
            app.show_error_dialog("Błąd", f"Nie udało się utworzyć pliku w Autostart:\n{e}\n\nUpewnij się, że masz uprawnienia do zapisu w:\n{app.startup_folder_path}")

def _on_monitoring_toggle(app):
    """Włącza/wyłącza monitorowanie w configu."""
    is_enabled = app.monitoring_enabled_checkbox.get() == 1
    app.settings["monitoring_enabled"] = is_enabled
    app.save_settings()
    _update_service_status_ui(app)

def _on_interval_change(app, choice):
    """Zapisuje nowy interwał monitorowania."""
    interval_map = {"15 minut": 15, "30 minut": 30, "1 godzina": 60, "4 godziny": 240}
    app.settings["monitoring_interval"] = interval_map.get(choice, 30)
    app.save_settings()


def _load_subs_listbox(app):
    """Wczytuje listę subskrypcji z configu do Listboxa."""
    app.subs_list_box.delete(0, "end")
    for sub_url in app.settings.get("subscriptions", []):
        app.subs_list_box.insert("end", sub_url)
    app.remove_sub_button.configure(state="disabled")

def _add_subscription(app):
    """Dodaje nowy kanał do listy subskrypcji."""
    new_url = app.new_sub_entry.get().strip()

    if not new_url or (not "youtube.com/" and not "youtu.be/"):
        app.show_error_dialog("Błąd", "Wprowadź poprawny link do kanału YouTube.")
        return

    if not isinstance(app.settings.get("subscriptions"), list):
        app.settings["subscriptions"] = []

    if new_url in app.settings.get("subscriptions", []):
        app.show_error_dialog("Informacja", "Ten kanał jest już na liście.")
        return

    app.settings.setdefault("subscriptions", []).append(new_url)
    app.save_settings()
    _load_subs_listbox(app) # Odśwież
    app.new_sub_entry.delete(0, "end")

def _on_sub_selected(app, event=None):
    """Aktywuje przycisk usuwania po zaznaczeniu elementu."""
    app.remove_sub_button.configure(state="normal" if app.subs_list_box.curselection() else "disabled")

def _remove_subscription(app):
    """Usuwa zaznaczony kanał z listy subskrypcji."""
    try:
        selected_index = app.subs_list_box.curselection()[0]
        selected_url = app.subs_list_box.get(selected_index)

        if messagebox.askyesno("Potwierdzenie", f"Czy na pewno chcesz usunąć subskrypcję dla:\n\n{selected_url}"):
            if selected_url in app.settings.get("subscriptions", []):
                app.settings["subscriptions"].remove(selected_url)
                app.save_settings()
                _load_subs_listbox(app) # Odśwież
            else:
                app.show_error_dialog("Błąd", "Nie znaleziono kanału w ustawieniach. Przeładowuję listę.")
                _load_subs_listbox(app)

    except IndexError:
        _on_sub_selected(app) # Odśwież stan przycisku

