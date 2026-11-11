"""Servidor de prueba para revisar el cliente web sin instalar NiceGUI."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from interfaz.servicio import Laboratorio


ESTATICOS = Path(__file__).resolve().parent.parent / "interfaz/estaticos"


def ejecutar(puerto, carpeta):
    laboratorio = Laboratorio(carpeta)

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def responder(self, contenido, tipo="application/json", estado=200):
            if tipo == "application/json":
                contenido = json.dumps(contenido, ensure_ascii=False).encode()
            self.send_response(estado)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

        def do_GET(self):
            url = urlparse(self.path)
            partes = unquote(url.path).strip("/").split("/")
            try:
                if url.path == "/":
                    contenido = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                                 '<link rel="stylesheet" href="/laboratorio/estilos.css"></head><body>'
                                 + (ESTATICOS / "index.html").read_text()
                                 + '<script src="/laboratorio/graficas.js"></script>'
                                 '<script src="/laboratorio/interfaz.js"></script></body></html>')
                    return self.responder(contenido.encode(), "text/html; charset=utf-8")
                if partes[0] == "laboratorio":
                    archivo = (ESTATICOS / partes[-1]).resolve()
                    if archivo.parent != ESTATICOS.resolve():
                        raise ValueError("Archivo no encontrado")
                    tipo = "text/css" if archivo.suffix == ".css" else "application/javascript"
                    return self.responder(archivo.read_bytes(), tipo)
                if partes[:2] == ["api", "escenario"]:
                    return self.responder(laboratorio.vista_escenario(partes[2]))
                if url.path == "/api/historial":
                    return self.responder(laboratorio.historial())
                if partes[:2] == ["api", "ejecuciones"]:
                    trabajo = laboratorio.buscar(partes[2])
                    if len(partes) == 3:
                        return self.responder(trabajo.consultar())
                    if partes[3] == "resultados":
                        return self.responder(trabajo.resultados())
                    if partes[3] == "archivo":
                        archivo = laboratorio.archivo(partes[2], parse_qs(url.query)["nombre"][0])
                        self.send_response(200)
                        self.send_header("Content-Disposition", f'attachment; filename="{archivo.name}"')
                        self.end_headers()
                        self.wfile.write(archivo.read_bytes())
                        return
                self.responder({"detail": "Ruta no encontrada"}, estado=404)
            except Exception as error:
                self.responder({"detail": str(error)}, estado=400)

        def do_POST(self):
            url = urlparse(self.path)
            contenido = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                if url.path == "/api/cargar":
                    return self.responder(laboratorio.cargar(contenido, parse_qs(url.query)["nombre"][0]))
                datos = json.loads(contenido or "{}")
                if url.path == "/api/ejecuciones":
                    return self.responder(laboratorio.iniciar(datos))
                if url.path == "/api/generar":
                    return self.responder(laboratorio.generar(datos["ciudades"], datos["semilla"]))
                if url.path.endswith("/detener"):
                    laboratorio.buscar(url.path.split("/")[3]).detener()
                    return self.responder({"mensaje": "Se detendrá al terminar el cálculo en curso"})
                self.responder({"detail": "Ruta no encontrada"}, estado=404)
            except Exception as error:
                self.responder({"detail": str(error)}, estado=400)

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    try:
        servidor.serve_forever()
    finally:
        laboratorio.cerrar()
        servidor.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    ejecutar(args.puerto, args.salida)
