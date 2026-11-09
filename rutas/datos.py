import csv
import gzip
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"
REFERENCIAS = {
    "eil101": {"ciudades": 101, "tipo": "EUC_2D", "optimo": 629,
               "huella": "a7ad1da073a11c2fb150f283608b54da1b8db7415d6865571ca18392e3d963fd"},
    "gr229": {"ciudades": 229, "tipo": "GEO", "optimo": 134602,
              "huella": "e90bf112c1011bfd512c0b4cba7ae75595908e150ca13f04c4ee556a8842a2f8"},
}


@dataclass
class Instancia:
    nombre: str
    ciudades: list
    coordenadas: list
    distancias: list
    tipo: str
    optimo: float | None = None

    @property
    def cantidad(self):
        return len(self.ciudades)


def radianes_geo(valor):
    grados = int(valor)
    return 3.141592 * (grados + 5 * (valor - grados) / 3) / 180


def distancia_geo(a, b):
    lat_a, lon_a = map(radianes_geo, a)
    lat_b, lon_b = map(radianes_geo, b)
    q1 = math.cos(lon_a - lon_b)
    q2 = math.cos(lat_a - lat_b)
    q3 = math.cos(lat_a + lat_b)
    argumento = ((1 + q1) * q2 - (1 - q1) * q3) / 2
    return int(6378.388 * math.acos(max(-1, min(1, argumento))) + 1)


def crear_matriz(coordenadas, tipo):
    if tipo not in {"EUC_2D", "GEO", "REAL_2D"}:
        raise ValueError(f"Distancia no soportada: {tipo}.")
    n = len(coordenadas)
    matriz = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if tipo == "GEO":
                valor = distancia_geo(coordenadas[i], coordenadas[j])
            else:
                valor = math.dist(coordenadas[i], coordenadas[j])
                if tipo == "EUC_2D":
                    # TSPLIB redondea .5 hacia arriba, a diferencia de round().
                    valor = int(valor + 0.5)
            matriz[i][j] = matriz[j][i] = valor
    return matriz


def leer_instancia(archivo):
    archivo = Path(archivo)
    if archivo.suffix.lower() == ".csv":
        with archivo.open(encoding="utf-8", newline="") as entrada:
            filas = list(csv.DictReader(entrada))
        ciudades = [fila["ciudad"] for fila in filas]
        coordenadas = [(float(fila["x"]), float(fila["y"])) for fila in filas]
        nombre, tipo = archivo.stem, "REAL_2D"
    else:
        encabezado, ciudades, coordenadas = {}, [], []
        en_coordenadas = False
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            if linea == "EOF":
                break
            if linea == "NODE_COORD_SECTION":
                en_coordenadas = True
            elif en_coordenadas:
                partes = linea.split()
                if len(partes) != 3:
                    raise ValueError(f"Coordenada inválida: {linea}")
                ciudades.append(partes[0])
                coordenadas.append((float(partes[1]), float(partes[2])))
            elif ":" in linea:
                clave, valor = linea.split(":", 1)
                encabezado[clave.strip()] = valor.strip()
        if encabezado.get("TYPE") != "TSP":
            raise ValueError("El archivo debe tener TYPE: TSP.")
        if int(encabezado.get("DIMENSION", 0)) != len(ciudades):
            raise ValueError("DIMENSION no coincide con las coordenadas del archivo.")
        nombre = encabezado.get("NAME", archivo.stem)
        tipo = encabezado.get("EDGE_WEIGHT_TYPE", "")
    if len(ciudades) < 4 or len(set(ciudades)) != len(ciudades):
        raise ValueError("Se necesitan al menos 4 ciudades con identificadores únicos.")
    if not all(math.isfinite(v) for punto in coordenadas for v in punto):
        raise ValueError("Las coordenadas deben ser números finitos.")
    if tipo == "GEO" and any(abs(x) > 90 or abs(y) > 180 for x, y in coordenadas):
        raise ValueError("Coordenadas GEO fuera de rango.")
    return Instancia(nombre, ciudades, coordenadas, crear_matriz(coordenadas, tipo), tipo)


def descargar_escenario(nombre, carpeta=CARPETA_DATOS):
    if nombre not in REFERENCIAS:
        raise ValueError("Solo se descargan eil101 y gr229.")
    carpeta = Path(carpeta)
    destino = carpeta / f"{nombre}.tsp"
    urls = [
        f"https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/{nombre}.tsp.gz",
        f"https://softlib.rice.edu/pub/tsplib/tsp/{nombre}.tsp.gz",
    ]
    errores = []
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".descarga")
    for url in urls:
        try:
            with urlopen(url, timeout=30) as respuesta:
                contenido = gzip.decompress(respuesta.read()).decode("utf-8")
            temporal.write_text(contenido, encoding="utf-8")
            instancia = leer_instancia(temporal)
            validar_oficial(instancia, nombre)
            temporal.replace(destino)
            return destino
        except (URLError, OSError, ValueError, UnicodeError, EOFError) as error:
            errores.append(f"{url}: {error}")
        finally:
            temporal.unlink(missing_ok=True)
    raise RuntimeError("No se pudo descargar el escenario. Guarde el .tsp en datos/.\n" + "\n".join(errores))


def validar_oficial(instancia, nombre):
    referencia = REFERENCIAS[nombre]
    if (instancia.nombre != nombre or instancia.cantidad != referencia["ciudades"]
            or instancia.tipo != referencia["tipo"]):
        raise ValueError(f"El archivo no corresponde al escenario {nombre}.")
    contenido = json.dumps([instancia.nombre, instancia.tipo, instancia.ciudades,
                            instancia.coordenadas], separators=(",", ":"))
    huella = hashlib.sha256(contenido.encode()).hexdigest()
    if huella != referencia["huella"]:
        raise ValueError(f"Las coordenadas de {nombre} difieren de la copia oficial verificada.")


def cargar_escenario(nombre):
    if nombre == "demo":
        return leer_instancia(CARPETA_DATOS / "demo10.csv")
    if nombre == "propio":
        archivo = CARPETA_DATOS / "propio.tsp"
        if not archivo.exists():
            generar_escenario(archivo)
        return leer_instancia(archivo)
    archivo = CARPETA_DATOS / f"{nombre}.tsp"
    if not archivo.exists():
        raise FileNotFoundError(f"Falta {archivo.name}. Ejecute: python main.py descargar {nombre}")
    instancia = leer_instancia(archivo)
    validar_oficial(instancia, nombre)
    instancia.optimo = REFERENCIAS[nombre]["optimo"]
    return instancia


def generar_escenario(archivo, cantidad=80, semilla=2026):
    if not 50 <= cantidad <= 200:
        raise ValueError("El escenario propio debe tener entre 50 y 200 ciudades.")
    rng = random.Random(semilla)
    centros = [(20, 20), (80, 20), (80, 80), (20, 80)]
    lineas = ["NAME : propio", "TYPE : TSP",
              f"COMMENT : Cuatro barrios ficticios; semilla {semilla}",
              f"DIMENSION : {cantidad}", "EDGE_WEIGHT_TYPE : EUC_2D", "NODE_COORD_SECTION"]
    for i in range(cantidad):
        cx, cy = centros[i % len(centros)]
        x, y = cx + rng.uniform(-15, 15), cy + rng.uniform(-15, 15)
        lineas.append(f"{i + 1} {x:.4f} {y:.4f}")
    archivo = Path(archivo)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("\n".join(lineas + ["EOF", ""]), encoding="utf-8")
    return archivo
