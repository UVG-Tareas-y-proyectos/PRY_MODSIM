import json
import math
import multiprocessing
from pathlib import Path
from queue import Empty
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from rutas.datos import cargar_escenario, leer_instancia
from rutas.experimentos import ejecutar_experimento, guardar_csv
from rutas.genetico import ConfigGA
from rutas.lineal import importar_pulp


ESCENARIOS = {"demo", "eil101", "gr229", "propio", "todos"}


def validar_solicitud(solicitud):
    config = ConfigGA(**solicitud.get("configuracion", {}))
    for campo in ["poblacion", "iteraciones", "torneo", "mejora_local"]:
        if type(getattr(config, campo)) is not int:
            raise ValueError(f"{campo} debe ser un número entero.")
    for campo in ["sobrevivientes", "cruce", "mutacion"]:
        if type(getattr(config, campo)) not in {int, float}:
            raise ValueError(f"{campo} debe ser un número.")
    config.validar()
    semillas = solicitud.get("semillas", [11, 22, 33])
    if not isinstance(semillas, list) or not semillas or len(semillas) > 20:
        raise ValueError("Ingrese entre 1 y 20 semillas.")
    if any(type(semilla) is not int for semilla in semillas) or len(set(semillas)) != len(semillas):
        raise ValueError("Las semillas deben ser enteros distintos.")
    metodo = solicitud.get("metodo", "ga")
    if metodo not in {"ga", "lp", "ambos"}:
        raise ValueError("Método no reconocido.")
    limite = solicitud.get("limite_lp", 120)
    if not isinstance(limite, (int, float)) or not math.isfinite(limite) or limite <= 0:
        raise ValueError("El límite del modelo debe ser positivo y finito.")
    if solicitud.get("escenario", "demo") not in ESCENARIOS and not solicitud.get("archivo"):
        raise ValueError("Escenario no reconocido.")
    if config.poblacion > 5000 or config.iteraciones > 100000:
        raise ValueError("Use como máximo 5000 individuos y 100000 generaciones en la interfaz.")
    if metodo in {"lp", "ambos"}:
        pulp = importar_pulp()
        if not pulp.PULP_CBC_CMD(msg=False).available():
            raise RuntimeError("CBC no está disponible en esta instalación.")
    return config, semillas, metodo, limite


def datos_instancia(instancia):
    return {"nombre": instancia.nombre, "ciudades": instancia.ciudades,
            "coordenadas": instancia.coordenadas, "tipo": instancia.tipo,
            "cantidad": instancia.cantidad, "optimo": instancia.optimo}


def ejecutar_trabajo(solicitud, carpeta, cola, cancelar):
    try:
        config, semillas, metodo, limite = validar_solicitud(solicitud)
        nombres = ["eil101", "gr229", "propio"] if solicitud.get("escenario") == "todos" else [solicitud.get("escenario", "demo")]
        tabla, carpetas = [], []
        for numero, nombre in enumerate(nombres):
            if cancelar.is_set():
                raise InterruptedError("Ejecución detenida.")
            instancia = leer_instancia(solicitud["archivo"]) if solicitud.get("archivo") else cargar_escenario(nombre)
            cola.put({"tipo": "escenario", "instancia": datos_instancia(instancia),
                      "numero": numero + 1, "total": len(nombres)})
            destino = Path(carpeta) / f"escenario_{numero + 1}"

            def informar(evento):
                cola.put({"tipo": "progreso", "escenario": instancia.nombre, **evento})

            filas = ejecutar_experimento(instancia, config, semillas, metodo, destino, limite,
                                          graficas=bool(solicitud.get("exportar_graficas", True)),
                                          animacion=bool(solicitud.get("exportar_gif", False)),
                                          progreso=informar, cancelar=cancelar.is_set)
            tabla.extend(filas)
            carpetas.append(destino.name)
            cola.put({"tipo": "escenario_completo", "carpeta": destino.name})
        guardar_csv(Path(carpeta) / "comparacion_total.csv", tabla)
        with ZipFile(Path(carpeta) / "resultados.zip", "w", ZIP_DEFLATED) as archivo:
            for ruta in sorted(Path(carpeta).rglob("*")):
                if ruta.is_file() and ruta.name != "resultados.zip":
                    archivo.write(ruta, ruta.relative_to(carpeta))
        cola.put({"tipo": "completo", "carpetas": carpetas})
    except InterruptedError:
        cola.put({"tipo": "cancelado", "mensaje": "La ejecución se detuvo. Los archivos ya generados se conservan."})
    except Exception as error:
        cola.put({"tipo": "error", "mensaje": str(error)})


class Trabajo:
    def __init__(self, solicitud, carpeta):
        self.id = uuid4().hex
        self.carpeta = Path(carpeta) / self.id
        self.carpeta.mkdir(parents=True)
        self.solicitud = solicitud
        contexto = multiprocessing.get_context("spawn")
        self.cola = contexto.Queue()
        self.cancelacion = contexto.Event()
        self.proceso = contexto.Process(target=ejecutar_trabajo,
                                         args=(solicitud, self.carpeta, self.cola, self.cancelacion))
        self.estado = "ejecutando"
        self.ultimo = None
        self.instancia = None
        self.mensaje = "Preparando el experimento"
        self.proceso.start()

    def consultar(self):
        eventos = []
        for _ in range(500):
            try:
                evento = self.cola.get_nowait()
            except Empty:
                break
            eventos.append(evento)
            if evento["tipo"] == "progreso":
                self.ultimo = evento
            elif evento["tipo"] == "escenario":
                self.instancia, self.ultimo = evento["instancia"], None
            elif evento["tipo"] in {"completo", "cancelado", "error"}:
                self.estado = evento["tipo"]
                self.mensaje = evento.get("mensaje", "Experimento terminado")
        if not self.proceso.is_alive() and self.proceso.exitcode not in {None, 0} and self.estado == "ejecutando":
            self.estado, self.mensaje = "error", "El proceso terminó inesperadamente. Revise la terminal."
        if not self.proceso.is_alive():
            self.proceso.join(timeout=0)
        return {"id": self.id, "estado": self.estado, "mensaje": self.mensaje,
                "instancia": self.instancia, "ultimo": self.ultimo, "eventos": eventos}

    def detener(self):
        self.cancelacion.set()
        self.mensaje = "Se detendrá al terminar el cálculo en curso"

    def resultados(self):
        informes = []
        for ruta in sorted(self.carpeta.glob("escenario_*/ejecucion.json")):
            informe = json.loads(ruta.read_text(encoding="utf-8"))
            informe["carpeta"] = ruta.parent.name
            informe["corridas"] = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ruta.parent.glob("ga_*.json"))]
            informes.append(informe)
        archivos = [str(p.relative_to(self.carpeta)) for p in sorted(self.carpeta.rglob("*")) if p.is_file()]
        return {"informes": informes, "archivos": archivos}
