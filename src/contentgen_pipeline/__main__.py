"""Entry point para execução como módulo Python.

Permite executar o ContentGen Pipeline como:
python -m contentgen_pipeline process <caminho>
python -m contentgen_pipeline watch <caminho>
python -m contentgen_pipeline health
"""

import sys
from .cli import app

if __name__ == "__main__":
    app() 