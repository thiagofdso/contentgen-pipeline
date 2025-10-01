"""Ponto de entrada principal do ContentGen Pipeline."""

from pathlib import Path

from dotenv import load_dotenv

# Garante que o .env seja aplicado sempre que a aplicacao iniciar
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from .cli import app

if __name__ == "__main__":
    app()
