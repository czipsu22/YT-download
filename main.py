"""
Główny plik uruchomieniowy aplikacji.

Jego jedynym zadaniem jest zaimportowanie i uruchomienie głównego okna aplikacji.
"""

from app_window import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
