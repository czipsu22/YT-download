"""
Główny plik uruchomieniowy aplikacji.

Jego jedynym zadaniem jest zaimportowanie i uruchomienie głównego okna aplikacji
lub, jeśli podano odpowiedni argument, uruchomienie usługi w tle.
"""

import sys
import os

def run_app_window():
    """Uruchamia normalne okno UI."""
    from app_window import App
    app = App()
    app.mainloop()

def run_service_mode():
    """Uruchamia logikę usługi w tle."""
    
    # Próba ustalenia ścieżki do logów
    try:
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        # Przekierowujemy stdout i stderr do plików logów
        # To zapobiega wyskakiwaniu okna konsoli
        log_out_path = os.path.join(base_path, "service-out.log")
        log_err_path = os.path.join(base_path, "service-err.log")
        
        sys.stdout = open(log_out_path, "a", encoding="utf-8")
        sys.stderr = open(log_err_path, "a", encoding="utf-8")

    except Exception as e:
        # Jeśli nawet to zawiedzie, trudno, usługa i tak spróbuje działać
        print(f"Nie udało się przekierować stdout/stderr: {e}")

    
    try:
        import service
        print("Uruchamianie pętli usługi...")
        service.start_service()
    except Exception as e:
        # Logowanie błędów krytycznych serwisu
        import time
        print(f"{time.ctime()}: Krytyczny błąd startu usługi: {e}\n")

if __name__ == "__main__":
    if "--run-service" in sys.argv:
        run_service_mode()
    else:
        run_app_window()
