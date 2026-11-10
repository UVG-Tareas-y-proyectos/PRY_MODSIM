import math
import random
import re
from pathlib import Path
from time import perf_counter

from .recorridos import distancia_total, mejorar_2opt, validar_ruta, vecino_cercano


def importar_pulp():
    try:
        import pulp
    except ImportError as error:
        raise RuntimeError("Falta PuLP. Instale: python -m pip install -r requirements.txt") from error
    if not hasattr(pulp, "PULP_CBC_CMD"):
        raise RuntimeError("Este proyecto usa PuLP 3.3.0. Instale la versión de requirements.txt.")
    return pulp


def crear_modelo(instancia):
    pulp = importar_pulp()
    n = instancia.cantidad
    modelo = pulp.LpProblem("TSP_DFJ", pulp.LpMinimize)
    aristas = {(i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
               for i in range(n) for j in range(i + 1, n)}
    modelo += pulp.lpSum(instancia.distancias[i][j] * x for (i, j), x in aristas.items())
    incidentes = [[] for _ in range(n)]
    for (i, j), x in aristas.items():
        incidentes[i].append(x)
        incidentes[j].append(x)
    for i in range(n):
        modelo += pulp.lpSum(incidentes[i]) == 2, f"grado_{i}"
    return modelo, aristas


def encontrar_componentes(cantidad, aristas):
    vecinos = [[] for _ in range(cantidad)]
    for i, j in aristas:
        vecinos[i].append(j)
        vecinos[j].append(i)
    pendientes = set(range(cantidad))
    componentes = []
    while pendientes:
        pila = [min(pendientes)]
        componente = set()
        while pila:
            actual = pila.pop()
            if actual in componente:
                continue
            componente.add(actual)
            pila.extend(vecino for vecino in vecinos[actual] if vecino not in componente)
        pendientes -= componente
        componentes.append(sorted(componente))
    return componentes


def reconstruir_ruta(cantidad, aristas):
    vecinos = [[] for _ in range(cantidad)]
    for i, j in aristas:
        vecinos[i].append(j)
        vecinos[j].append(i)
    if any(len(lista) != 2 for lista in vecinos):
        return None
    ruta, anterior, actual = [], -1, 0
    while actual not in ruta:
        ruta.append(actual)
        siguiente = next(j for j in vecinos[actual] if j != anterior)
        anterior, actual = actual, siguiente
    if actual != 0 or len(ruta) != cantidad:
        return None
    validar_ruta(ruta, cantidad)
    return ruta


def leer_cota(texto):
    valores = []
    for patron in [r"Lower bound:\s*([-+\d.eE]+)",
                   r"best possible\s+([-+\d.eE]+)",
                   r"Continuous objective value is\s+([-+\d.eE]+)"]:
        for valor in re.findall(patron, texto):
            numero = float(valor)
            if math.isfinite(numero):
                valores.append(numero)
    return max(valores) if valores else None


def resolver_lp(instancia, carpeta, limite=120, progreso=None, cancelar=None):
    if not math.isfinite(limite) or limite <= 0:
        raise ValueError("El límite del modelo debe ser positivo y finito.")
    pulp = importar_pulp()
    inicio = perf_counter()
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    modelo, variables = crear_modelo(instancia)
    if not pulp.PULP_CBC_CMD(msg=False).available():
        raise RuntimeError("CBC no está disponible en esta instalación de PuLP.")

    # La misma heurística inicia el modelo aunque no se ejecute el genético.
    mejor = vecino_cercano(instancia.distancias, 0, random.Random(0))
    mejor = mejorar_2opt(mejor, instancia.distancias, instancia.cantidad)
    mejor_distancia = distancia_total(mejor, instancia.distancias)
    origen = "inicio_factible"
    cota, optima, vueltas, cortes = None, False, 0, set()
    estado, estados = "limite_tiempo", []

    def informar():
        if progreso:
            progreso({"etapa": "lp", "ruta": mejor.copy(), "mejor": mejor_distancia,
                      "cota_inferior": cota, "variables": len(variables),
                      "restricciones": len(modelo.constraints), "cortes": len(cortes),
                      "estado": estado, "origen": origen, "optima_demostrada": optima})

    informar()

    while perf_counter() - inicio < limite:
        if cancelar and cancelar():
            raise InterruptedError("Ejecución detenida.")
        restantes = limite - (perf_counter() - inicio)
        if restantes <= 0:
            break
        aristas_inicio = {tuple(sorted((mejor[i], mejor[(i + 1) % len(mejor)]))) for i in range(len(mejor))}
        for arista, variable in variables.items():
            variable.setInitialValue(int(arista in aristas_inicio))
        vueltas += 1
        log = carpeta / f"cbc_{vueltas:03d}.log"
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=restantes, threads=1,
                                   gapRel=0, warmStart=True, logPath=str(log),
                                   options=["randomSeed 1"])
        try:
            modelo.solve(solver)
        except pulp.PulpSolverError as error:
            raise RuntimeError(f"CBC no pudo resolver el modelo. Revise {log}.") from error
        probado = (modelo.status == pulp.LpStatusOptimal and modelo.sol_status == pulp.LpSolutionOptimal)
        estados.append({"iteracion": vueltas, "estado": pulp.LpStatus[modelo.status],
                        "solucion": pulp.LpSolution[modelo.sol_status],
                        "restricciones": len(modelo.constraints)})
        texto_log = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        nueva_cota = leer_cota(texto_log)
        if probado:
            nueva_cota = pulp.value(modelo.objective)
        if nueva_cota is not None:
            cota = nueva_cota if cota is None else max(cota, nueva_cota)

        factible = modelo.sol_status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible)
        if not factible:
            estado = "sin_solucion_del_solver"
            informar()
            break
        elegidas = [arista for arista, x in variables.items() if x.value() is not None and x.value() > 0.5]
        grados = [0] * instancia.cantidad
        for i, j in elegidas:
            grados[i] += 1
            grados[j] += 1
        if any(grado != 2 for grado in grados):
            estado = "sin_recorrido_valido"
            informar()
            break
        ruta = reconstruir_ruta(instancia.cantidad, elegidas)
        if ruta is not None:
            costo = distancia_total(ruta, instancia.distancias)
            if costo <= mejor_distancia + 1e-8:
                mejor, mejor_distancia, origen = ruta, costo, "solver"
            if probado:
                optima, estado, cota = True, "optima", costo
            else:
                estado = "factible_sin_prueba"
            informar()
            break

        agregados = 0
        for componente in encontrar_componentes(instancia.cantidad, elegidas):
            clave = tuple(componente)
            if len(componente) == instancia.cantidad or clave in cortes:
                continue
            modelo += pulp.lpSum(variables[i, j] for i in componente for j in componente if i < j) <= len(componente) - 1
            cortes.add(clave)
            agregados += 1
        if not agregados:
            estado = "sin_recorrido_valido"
            informar()
            break
        informar()

    if cancelar and cancelar():
        raise InterruptedError("Ejecución detenida.")

    tiempo = perf_counter() - inicio
    modelo.writeLP(str(carpeta / "modelo.lp"))
    validar_ruta(mejor, instancia.cantidad)
    gap = None
    if cota is not None:
        gap = 100 * max(0, mejor_distancia - cota) / max(abs(mejor_distancia), 1e-9)
    return {"metodo": "LP", "formulacion": "DFJ entera", "ruta": mejor,
            "distancia": mejor_distancia, "tiempo_s": tiempo, "estado": estado,
            "optima_demostrada": optima, "origen": origen, "cota_inferior": cota,
            "gap_pct": gap, "variables": len(variables),
            "restricciones": len(modelo.constraints), "cortes": len(cortes),
            "iteraciones_solver": vueltas, "estados_solver": estados, "limite_s": limite}
