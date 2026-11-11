import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile


RAIZ = Path(__file__).resolve().parent.parent


class PruebasHTTP(unittest.TestCase):
    def test_recorrido_completo_por_http(self):
        with tempfile.TemporaryDirectory() as temporal:
            with socket.socket() as conexion:
                conexion.bind(("127.0.0.1", 0))
                puerto = conexion.getsockname()[1]
            proceso = subprocess.Popen([sys.executable, "-m", "tests.servidor_navegador",
                                         "--puerto", str(puerto), "--salida", temporal],
                                        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            base = f"http://127.0.0.1:{puerto}"

            def api(ruta, datos=None, contenido=None):
                cuerpo = json.dumps(datos).encode() if datos is not None else contenido
                peticion = Request(base + ruta, data=cuerpo, headers={"Content-Type": "application/json"})
                with urlopen(peticion, timeout=10) as respuesta:
                    datos_recibidos = respuesta.read()
                    if respuesta.headers.get_content_type() == "application/json":
                        return json.loads(datos_recibidos)
                    return datos_recibidos

            try:
                for _ in range(100):
                    try:
                        api("/api/escenario/demo")
                        break
                    except URLError:
                        if proceso.poll() is not None:
                            self.fail(proceso.stdout.read().decode())
                        time.sleep(.03)
                for nombre, cantidad in [("demo", 10), ("eil101", 101), ("gr229", 229), ("propio", 80)]:
                    self.assertEqual(api("/api/escenario/" + nombre)["cantidad"], cantidad)
                carga = api("/api/cargar?nombre=cuadrado.csv", contenido=b"ciudad,x,y\nA,0,0\nB,1,0\nC,1,1\nD,0,1\n")
                self.assertEqual(carga["instancia"]["nombre"], "cuadrado")
                self.assertEqual(api("/api/generar", {"ciudades": 60, "semilla": 2026})["instancia"]["cantidad"], 60)
                job = api("/api/ejecuciones", {"escenario": "demo", "metodo": "ga", "semillas": [11, 22, 33],
                                               "configuracion": {"poblacion": 30, "iteraciones": 20},
                                               "exportar_graficas": False})["id"]
                eventos = []
                for _ in range(300):
                    estado = api("/api/ejecuciones/" + job)
                    eventos.extend(estado["eventos"])
                    if estado["estado"] != "ejecutando":
                        break
                    time.sleep(.03)
                self.assertEqual(estado["estado"], "completo", estado["mensaje"])
                self.assertTrue(any(e["tipo"] == "progreso" for e in eventos))
                informes = api(f"/api/ejecuciones/{job}/resultados")["informes"]
                self.assertEqual(len(informes[0]["corridas"]), 3)
                self.assertEqual(len(informes[0]["tabla"]), 3)
                descarga = api(f"/api/ejecuciones/{job}/archivo?nombre=resultados.zip")
                with ZipFile(io.BytesIO(descarga)) as archivo:
                    self.assertIn("comparacion_total.csv", archivo.namelist())
                with self.assertRaises(HTTPError) as error:
                    api(f"/api/ejecuciones/{job}/archivo?nombre=../../README.md")
                self.assertEqual(error.exception.code, 400)
            finally:
                proceso.terminate()
                proceso.wait(timeout=5)
                proceso.stdout.close()
