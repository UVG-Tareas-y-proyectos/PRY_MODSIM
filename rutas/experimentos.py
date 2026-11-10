import csv
import hashlib
import json
import platform
import statistics
from dataclasses import asdict

from .genetico import resolver_ga
from .graficas import guardar_animacion, guardar_graficas
from .lineal import resolver_lp
from .recorridos import ruta_canonica


def guardar_json(archivo, contenido):
    archivo.write_text(json.dumps(contenido, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def guardar_csv(archivo, filas):
    if not filas:
        return
    with archivo.open("w", encoding="utf-8", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def tres_mejores(corridas):
    unicas = {}
    for corrida in corridas:
        for solucion in corrida["mejores"]:
            clave = ruta_canonica(solucion["ruta"])
            if clave not in unicas:
                unicas[clave] = {**solucion, "metodo": corrida["metodo"], "tiempo_s": corrida["tiempo_s"]}
    return sorted(unicas.values(), key=lambda solucion: solucion["distancia"])[:3]


def error_porcentual(distancia, referencia):
    if referencia is None:
        return None
    if distancia < referencia - 1e-7:
        raise ValueError("Una solución es menor al óptimo de referencia. Revise datos y distancias.")
    if referencia == 0:
        return 0 if distancia == 0 else None
    return 100 * max(0, distancia - referencia) / referencia


def construir_tabla(instancia, config, corridas, lp):
    referencia = instancia.optimo
    fuente = "TSPLIB" if referencia is not None else "sin_referencia"
    if referencia is None and lp and lp["optima_demostrada"]:
        referencia, fuente = lp["distancia"], "LP_demostrado"
    filas = []
    soluciones = ([lp] if lp else []) + tres_mejores(corridas)
    for indice, solucion in enumerate(soluciones):
        es_ga = solucion["metodo"] != "LP"
        posicion = indice if lp else indice + 1
        filas.append({"escenario": instancia.nombre, "ciudades": instancia.cantidad,
                      "metodo": solucion["metodo"], "puesto_ga": posicion if es_ga else None,
                      "semilla": solucion.get("semilla"),
                      "poblacion_ga": config.poblacion if es_ga else None,
                      "iteraciones_ga": config.iteraciones if es_ga else None,
                      "variables_lp": lp["variables"] if lp else None,
                      "restricciones_lp": lp["restricciones"] if lp else None,
                      "tiempo_s": solucion["tiempo_s"], "optimo_teorico": referencia,
                      "fuente_referencia": fuente, "distancia_encontrada": solucion["distancia"],
                      "error_pct": error_porcentual(solucion["distancia"], referencia),
                      "estado": "heuristica" if es_ga else lp["estado"],
                      "origen": "genetico" if es_ga else lp["origen"],
                      "optima_demostrada_lp": lp["optima_demostrada"] if not es_ga else False,
                      "cota_inferior_lp": lp["cota_inferior"] if lp else None,
                      "gap_lp_pct": lp["gap_pct"] if not es_ga else None})
    return filas, referencia


def ejecutar_experimento(instancia, config, semillas, metodo, carpeta,
                        limite_lp=120, graficas=True, animacion=True):
    carpeta.mkdir(parents=True, exist_ok=True)
    corridas, lp = [], None
    if metodo in {"ga", "ambos"}:
        for semilla in semillas:
            print(f"  GA: semilla {semilla}", flush=True)
            corrida = resolver_ga(instancia, config, semilla)
            corridas.append(corrida)
            guardar_json(carpeta / f"ga_{semilla}.json", corrida)
            print(f"    Distancia: {corrida['distancia']:.3f} | {corrida['tiempo_s']:.2f} s", flush=True)
    if metodo in {"lp", "ambos"}:
        print(f"  LP: límite {limite_lp:g} s", flush=True)
        lp = resolver_lp(instancia, carpeta / "lp", limite_lp)
        guardar_json(carpeta / "lp.json", lp)
        print(f"    Distancia: {lp['distancia']:.3f} | Estado: {lp['estado']}", flush=True)
    tabla, referencia = construir_tabla(instancia, config, corridas, lp)
    guardar_csv(carpeta / "comparacion.csv", tabla)
    detalle = []
    for resultado in corridas:
        detalle.append({"semilla": resultado["semilla"], "distancia": resultado["distancia"],
                        "tiempo_s": resultado["tiempo_s"],
                        "error_pct": error_porcentual(resultado["distancia"], referencia)})
    guardar_csv(carpeta / "corridas.csv", detalle)
    if corridas:
        costos = [resultado["distancia"] for resultado in corridas]
        resumen = {"escenario": instancia.nombre, "repeticiones": len(costos), "mejor": min(costos),
                   "peor": max(costos), "promedio": statistics.mean(costos),
                   "desviacion_estandar": statistics.stdev(costos) if len(costos) > 1 else 0,
                   "tiempo_promedio_s": statistics.mean(r["tiempo_s"] for r in corridas)}
        guardar_csv(carpeta / "estadisticas.csv", [resumen])
    guardar_json(carpeta / "ejecucion.json", {
        "instancia": {"nombre": instancia.nombre, "ciudades": instancia.ciudades,
                      "coordenadas": instancia.coordenadas, "tipo_distancia": instancia.tipo,
                      "optimo_publicado": instancia.optimo,
                      "sha256_coordenadas": hashlib.sha256(json.dumps(instancia.coordenadas).encode()).hexdigest()},
        "python": platform.python_version(), "configuracion_ga": asdict(config),
        "semillas": semillas if corridas else [], "metodo": metodo, "limite_lp_s": limite_lp,
        "mejores_ga": tres_mejores(corridas), "lp": lp, "tabla": tabla})
    filas_rutas = []
    for indice, resultado in enumerate(([lp] if lp else []) + tres_mejores(corridas)):
        ruta = resultado["ruta"] + [resultado["ruta"][0]]
        for paso, ciudad in enumerate(ruta):
            filas_rutas.append({"solucion": indice + 1, "metodo": resultado["metodo"],
                                "paso": paso, "ciudad": instancia.ciudades[ciudad]})
    guardar_csv(carpeta / "rutas.csv", filas_rutas)
    if graficas:
        guardar_graficas(instancia, corridas, lp, carpeta, referencia)
    if animacion and corridas:
        mejor = min(corridas, key=lambda resultado: resultado["distancia"])
        guardar_animacion(instancia, mejor, carpeta / "evolucion.gif")
    return tabla
