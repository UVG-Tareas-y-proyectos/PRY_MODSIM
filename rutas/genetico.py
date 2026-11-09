import math
import random
from dataclasses import asdict, dataclass
from time import perf_counter

from .recorridos import (distancia_total, mejorar_2opt, ruta_canonica,
                        validar_ruta, vecino_cercano)


@dataclass
class ConfigGA:
    poblacion: int = 150
    iteraciones: int = 500
    seleccion: str = "torneo"
    sobrevivientes: float = 0.10
    cruce: float = 0.70
    mutacion: float = 0.20
    torneo: int = 3
    inicializacion: str = "mixta"
    mejora_local: int = 0

    def validar(self):
        if self.poblacion < 4 or self.iteraciones < 1:
            raise ValueError("Población >= 4 e iteraciones >= 1.")
        if self.seleccion not in {"torneo", "ranking", "elitismo", "mezcla"}:
            raise ValueError("Selección no reconocida.")
        tasas = [self.sobrevivientes, self.cruce, self.mutacion]
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in tasas) or not math.isclose(sum(tasas), 1):
            raise ValueError("Las fracciones deben estar entre 0 y 1 y sumar 1.")
        if int(self.poblacion * self.sobrevivientes) < 1:
            raise ValueError("Debe conservar al menos un sobreviviente.")
        if not 2 <= self.torneo <= self.poblacion:
            raise ValueError("Torneo debe estar entre 2 y el tamaño de población.")
        if self.inicializacion not in {"aleatoria", "mixta"}:
            raise ValueError("Inicialización no reconocida.")
        if self.mejora_local < 0:
            raise ValueError("Mejora local debe ser >= 0.")


def cruce_ox(padre, madre, rng):
    inicio, fin = sorted(rng.sample(range(len(padre)), 2))
    fin += 1
    hijo = [None] * len(padre)
    hijo[inicio:fin] = padre[inicio:fin]
    usados = set(padre[inicio:fin])
    restantes = [ciudad for ciudad in madre[fin:] + madre[:fin] if ciudad not in usados]
    posiciones = list(range(fin, len(padre))) + list(range(inicio))
    for posicion, ciudad in zip(posiciones, restantes):
        hijo[posicion] = ciudad
    return hijo


def mutar_inversion(ruta, rng):
    hijo = ruta.copy()
    inicio, fin = sorted(rng.sample(range(len(ruta)), 2))
    hijo[inicio:fin + 1] = reversed(hijo[inicio:fin + 1])
    return hijo


def seleccionar(poblacion, config, rng):
    metodo = config.seleccion
    if metodo == "mezcla":
        metodo = rng.choice(["ranking", "torneo"])
    if metodo == "ranking":
        return rng.choices(poblacion, weights=range(len(poblacion), 0, -1))[0]
    if metodo == "elitismo":
        limite = max(2, int(config.poblacion * config.sobrevivientes))
        return rng.choice(poblacion[:limite])
    # Los índices pequeños corresponden a las rutas de menor distancia.
    return poblacion[min(rng.sample(range(len(poblacion)), config.torneo))]


def resolver_ga(instancia, config, semilla):
    config.validar()
    inicio = perf_counter()
    rng = random.Random(semilla)
    matriz, n = instancia.distancias, instancia.cantidad
    poblacion = [rng.sample(range(n), n) for _ in range(config.poblacion)]
    if config.inicializacion == "mixta":
        for i in range(max(1, config.poblacion // 5)):
            poblacion[i] = vecino_cercano(matriz, rng.randrange(n), rng)
    n_sobrev = int(config.poblacion * config.sobrevivientes)
    n_cruce = int(config.poblacion * config.cruce)
    n_mutacion = config.poblacion - n_sobrev - n_cruce
    historial, instantaneas, mejores = [], [], {}

    for generacion in range(config.iteraciones + 1):
        evaluados = sorted((distancia_total(ruta, matriz), ruta) for ruta in poblacion)
        poblacion = [ruta for _, ruta in evaluados]
        costos = [costo for costo, _ in evaluados]
        diversidad = len({ruta_canonica(ruta) for ruta in poblacion}) / config.poblacion
        historial.append({"generacion": generacion, "mejor": costos[0],
                          "promedio": sum(costos) / len(costos), "diversidad": diversidad})
        for costo, ruta in evaluados:
            clave = ruta_canonica(ruta)
            if clave not in mejores:
                mejores[clave] = {"ruta": list(clave), "distancia": costo,
                                  "semilla": semilla, "generacion": generacion,
                                  "tiempo_hallazgo_s": perf_counter() - inicio}
            if len(mejores) > 3:
                peor = max(mejores, key=lambda clave: mejores[clave]["distancia"])
                del mejores[peor]
        if generacion % max(1, config.iteraciones // 40) == 0 or generacion == config.iteraciones:
            instantaneas.append({"generacion": generacion, "ruta": poblacion[0].copy(), "distancia": costos[0]})
        if generacion == config.iteraciones:
            break
        nueva = [ruta.copy() for ruta in poblacion[:n_sobrev]]
        for _ in range(n_cruce):
            hijo = cruce_ox(seleccionar(poblacion, config, rng), seleccionar(poblacion, config, rng), rng)
            nueva.append(mejorar_2opt(hijo, matriz, config.mejora_local) if config.mejora_local else hijo)
        for _ in range(n_mutacion):
            hijo = mutar_inversion(seleccionar(poblacion, config, rng), rng)
            nueva.append(mejorar_2opt(hijo, matriz, config.mejora_local) if config.mejora_local else hijo)
        vistos = {ruta_canonica(ruta) for ruta in nueva[:n_sobrev]}
        for i in range(n_sobrev, len(nueva)):
            for _ in range(10):
                if ruta_canonica(nueva[i]) not in vistos:
                    break
                nueva[i] = rng.sample(range(n), n)
            vistos.add(ruta_canonica(nueva[i]))
        poblacion = nueva

    validar_ruta(poblacion[0], n)
    return {"metodo": "GA+2opt" if config.mejora_local else "GA", "semilla": semilla,
            "ruta": poblacion[0], "distancia": costos[0], "tiempo_s": perf_counter() - inicio,
            "mejores": sorted(mejores.values(), key=lambda solucion: solucion["distancia"]),
            "historial": historial, "instantaneas": instantaneas, "configuracion": asdict(config),
            "composicion": {"sobrevivientes": n_sobrev, "cruce": n_cruce, "mutacion": n_mutacion}}
