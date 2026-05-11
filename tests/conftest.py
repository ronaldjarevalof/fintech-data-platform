"""Configuración de pytest: agrega la raíz del proyecto al sys.path."""

import sys
from pathlib import Path

# Permite importar 'src.*' sin instalar el paquete ni configurar PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))
