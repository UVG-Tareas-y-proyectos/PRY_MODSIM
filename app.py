import argparse
from pathlib import Path

from interfaz.servidor import iniciar_servidor


def main():
    parser = argparse.ArgumentParser(description="TRAZA: laboratorio visual del TSP.")
    parser.add_argument("--puerto", type=int, default=8080)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    if not 1 <= args.puerto <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    try:
        iniciar_servidor(args.puerto, args.salida)
    except ImportError as error:
        parser.error("Faltan dependencias de la interfaz. Ejecute: python -m pip install -r requirements-ui.txt")


if __name__ == "__main__":
    main()
