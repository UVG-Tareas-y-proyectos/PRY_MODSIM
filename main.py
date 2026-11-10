import argparse
import math
from datetime import datetime
from pathlib import Path

from rutas.datos import (CARPETA_DATOS, cargar_escenario, descargar_escenario,
                         generar_escenario, leer_instancia)
from rutas.experimentos import ejecutar_experimento, guardar_csv
from rutas.genetico import ConfigGA
from rutas.lineal import importar_pulp


RAIZ = Path(__file__).resolve().parent


def agregar_parametros(parser):
    parser.add_argument("--metodo", choices=["ga", "lp", "ambos"], default="ambos")
    parser.add_argument("--poblacion", type=int, default=150)
    parser.add_argument("--iteraciones", type=int, default=500)
    parser.add_argument("--seleccion", choices=["torneo", "ranking", "elitismo", "mezcla"], default="torneo")
    parser.add_argument("--sobrevivientes", type=float, default=0.10)
    parser.add_argument("--cruce", type=float, default=0.70)
    parser.add_argument("--mutacion", type=float, default=0.20)
    parser.add_argument("--torneo", type=int, default=3)
    parser.add_argument("--inicializacion", choices=["aleatoria", "mixta"], default="mixta")
    parser.add_argument("--mejora-local", type=int, default=0, help="Cambios 2-opt por hijo; 0 desactiva la mejora.")
    parser.add_argument("--semillas", type=int, nargs="+", default=[11, 22, 33, 44, 55])
    parser.add_argument("--limite-lp", type=float, default=120)
    parser.add_argument("--salida", type=Path, default=RAIZ / "resultados")
    parser.add_argument("--sin-graficas", action="store_true")
    parser.add_argument("--sin-animacion", action="store_true")


def crear_parser():
    parser = argparse.ArgumentParser(description="Proyecto TSP: algoritmo genético y programación entera.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    ejecutar = comandos.add_parser("ejecutar", help="Resolver un escenario o archivo propio.")
    escenario = ejecutar.add_mutually_exclusive_group()
    escenario.add_argument("--escenario", choices=["demo", "eil101", "gr229", "propio"], default="demo")
    escenario.add_argument("--archivo", type=Path, help="Archivo CSV o TSPLIB con coordenadas.")
    agregar_parametros(ejecutar)
    comparar = comandos.add_parser("comparar", help="Ejecutar los tres escenarios del curso.")
    agregar_parametros(comparar)
    generar = comandos.add_parser("generar", help="Crear el escenario propio de cuatro barrios.")
    generar.add_argument("--ciudades", type=int, default=80)
    generar.add_argument("--semilla", type=int, default=2026)
    generar.add_argument("--archivo", type=Path, default=CARPETA_DATOS / "propio.tsp")
    generar.add_argument("--reemplazar", action="store_true", help="Permitir reemplazar el archivo existente.")
    descargar = comandos.add_parser("descargar", help="Descargar las instancias oficiales de TSPLIB.")
    descargar.add_argument("escenarios", nargs="*", metavar="ESCENARIO", help="eil101, gr229 o ambos si se omite.")
    return parser


def carpeta_ejecucion(salida):
    nombre = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = salida / nombre
    numero = 1
    while carpeta.exists():
        carpeta = salida / f"{nombre}_{numero}"
        numero += 1
    carpeta.mkdir(parents=True)
    return carpeta


def main(argv=None):
    parser = crear_parser()
    args = parser.parse_args(argv)
    try:
        if args.comando == "generar":
            if args.archivo.exists() and not args.reemplazar:
                parser.error("El archivo ya existe. Use --reemplazar o elija otro --archivo.")
            print(generar_escenario(args.archivo, args.ciudades, args.semilla))
            return 0
        if args.comando == "descargar":
            nombres = args.escenarios or ["eil101", "gr229"]
            if any(nombre not in {"eil101", "gr229"} for nombre in nombres):
                raise ValueError("Solo se pueden descargar eil101 y gr229.")
            for nombre in nombres:
                destino = CARPETA_DATOS / f"{nombre}.tsp"
                if destino.exists():
                    cargar_escenario(nombre)
                    print(f"Disponible: {destino}")
                else:
                    print(descargar_escenario(nombre))
            return 0
        config = ConfigGA(args.poblacion, args.iteraciones, args.seleccion,
                          args.sobrevivientes, args.cruce, args.mutacion, args.torneo,
                          args.inicializacion, args.mejora_local)
        config.validar()
        if len(set(args.semillas)) != len(args.semillas):
            raise ValueError("Las semillas de las repeticiones deben ser distintas.")
        if not math.isfinite(args.limite_lp) or args.limite_lp <= 0:
            raise ValueError("El límite de LP debe ser positivo y finito.")
        if args.metodo in {"lp", "ambos"}:
            pulp = importar_pulp()
            if not pulp.PULP_CBC_CMD(msg=False).available():
                raise RuntimeError("CBC no está disponible. Revise la instalación de PuLP.")
        if args.comando == "comparar":
            instancias = [cargar_escenario(nombre) for nombre in ["eil101", "gr229", "propio"]]
        else:
            instancias = [leer_instancia(args.archivo) if args.archivo else cargar_escenario(args.escenario)]
        carpeta = carpeta_ejecucion(args.salida)
        tabla = []
        for indice, instancia in enumerate(instancias):
            print(f"\n{instancia.nombre}: {instancia.cantidad} ciudades ({instancia.tipo})", flush=True)
            nombre_carpeta = instancia.nombre.replace("/", "_").replace("\\", "_")
            resultados = ejecutar_experimento(instancia, config, args.semillas, args.metodo,
                                              carpeta / f"{indice + 1}_{nombre_carpeta}",
                                              args.limite_lp, not args.sin_graficas,
                                              not args.sin_animacion)
            tabla.extend(resultados)
        guardar_csv(carpeta / "comparacion_total.csv", tabla)
        print(f"\nResultados: {carpeta.resolve()}")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
