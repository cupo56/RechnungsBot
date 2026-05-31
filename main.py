"""
RechnungsBot – Hauptprogramm.
Dies ist der Einstiegspunkt der Anwendung.
"""

import sys
import os

# Fügen wir den aktuellen Ordner zum PYTHONPATH hinzu, falls nicht vorhanden
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.gui import main

if __name__ == "__main__":
    main()
