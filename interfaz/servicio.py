from pathlib import Path
from uuid import uuid4

from rutas.datos import cargar_escenario, generar_escenario, leer_instancia
from .trabajos import Trabajo, datos_instancia, validar_solicitud


RAIZ = Path(__file__).resolve().parent.parent


class Laboratorio:
    def __init__(self, carpeta=None):
        self.carpeta = Path(carpeta or RAIZ / "resultados" / "interfaz")
        self.trabajos = {}
        self.archivos = {}

    def escenario(self, nombre):
        if nombre in self.archivos:
            return leer_instancia(self.archivos[nombre])
        return cargar_escenario(nombre)

    def vista_escenario(self, nombre):
        return datos_instancia(self.escenario(nombre))

    def iniciar(self, solicitud):
        if not isinstance(solicitud, dict):
            raise ValueError("La solicitud debe contener un objeto de parámetros.")
        solicitud = dict(solicitud)
        # Las rutas de archivos solo pueden proceder de una carga validada.
        solicitud.pop("archivo", None)
        nombre = solicitud.get("escenario", "demo")
        if nombre in self.archivos:
            solicitud["archivo"] = str(self.archivos[nombre])
        elif nombre not in {"demo", "eil101", "gr229", "propio", "todos"}:
            raise ValueError("Escenario no reconocido.")
        validar_solicitud(solicitud)
        for trabajo in self.trabajos.values():
            if trabajo.consultar()["estado"] == "ejecutando":
                raise ValueError("Ya hay un experimento en ejecución. Espere o deténgalo antes de iniciar otro.")
        trabajo = Trabajo(solicitud, self.carpeta)
        self.trabajos[trabajo.id] = trabajo
        return {"id": trabajo.id}

    def buscar(self, identificador):
        if identificador not in self.trabajos:
            raise ValueError("Ejecución no encontrada en esta sesión.")
        return self.trabajos[identificador]

    def cargar(self, contenido, nombre):
        if len(contenido) > 2 * 1024 * 1024:
            raise ValueError("El archivo no puede superar 2 MB.")
        extension = Path(nombre).suffix.lower()
        if extension not in {".tsp", ".csv"}:
            raise ValueError("Seleccione un archivo .tsp o .csv.")
        identificador = f"archivo_{uuid4().hex}"
        nombre_seguro = Path(nombre.replace("\\", "/")).name
        destino = self.carpeta / "cargas" / identificador / nombre_seguro
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        try:
            instancia = leer_instancia(destino)
        except (ValueError, KeyError, UnicodeError) as error:
            destino.unlink(missing_ok=True)
            raise ValueError(f"No se pudo leer el archivo: {error}") from error
        self.archivos[identificador] = destino
        return {"id": identificador, "instancia": datos_instancia(instancia)}

    def generar(self, cantidad, semilla):
        if type(cantidad) is not int or type(semilla) is not int:
            raise ValueError("Cantidad y semilla deben ser números enteros.")
        identificador = f"archivo_{uuid4().hex}"
        destino = self.carpeta / "cargas" / f"{identificador}.tsp"
        generar_escenario(destino, cantidad, semilla)
        self.archivos[identificador] = destino
        return {"id": identificador, "instancia": datos_instancia(leer_instancia(destino))}

    def archivo(self, identificador, nombre):
        carpeta = self.buscar(identificador).carpeta.resolve()
        archivo = (carpeta / nombre).resolve()
        if not archivo.is_relative_to(carpeta) or not archivo.is_file():
            raise ValueError("Archivo no encontrado.")
        return archivo

    def historial(self):
        filas = []
        for identificador, trabajo in self.trabajos.items():
            filas.append({"id": identificador, "estado": trabajo.estado,
                          "escenario": trabajo.solicitud.get("escenario", "demo"),
                          "metodo": trabajo.solicitud.get("metodo", "ga")})
        return filas[::-1]

    def cerrar(self):
        for trabajo in self.trabajos.values():
            if trabajo.proceso.is_alive():
                trabajo.detener()
