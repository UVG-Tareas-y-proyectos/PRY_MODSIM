from pathlib import Path
from html.parser import HTMLParser
import re
import tempfile
import time
import unittest

from interfaz.servicio import Laboratorio


class PruebasInterfaz(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.laboratorio = Laboratorio(Path(self.temporal.name))

    def tearDown(self):
        self.laboratorio.cerrar()
        for trabajo in self.laboratorio.trabajos.values():
            trabajo.proceso.join(timeout=5)
            trabajo.cola.close()
        self.temporal.cleanup()

    def esperar(self, trabajo):
        limite = time.monotonic() + 20
        eventos = []
        while time.monotonic() < limite:
            estado = trabajo.consultar()
            eventos.extend(estado["eventos"])
            if estado["estado"] != "ejecutando":
                return estado, eventos
            time.sleep(.02)
        self.fail("El trabajo no terminó dentro del tiempo de prueba.")

    def test_proceso_real_exporta_resultados(self):
        datos = self.laboratorio.iniciar({"escenario": "demo", "metodo": "ga", "semillas": [11, 22],
                                         "configuracion": {"poblacion": 20, "iteraciones": 15},
                                         "exportar_graficas": False})
        trabajo = self.laboratorio.buscar(datos["id"])
        estado, eventos = self.esperar(trabajo)
        self.assertEqual(estado["estado"], "completo", estado["mensaje"])
        self.assertTrue(any(e["tipo"] == "progreso" for e in eventos))
        resultados = trabajo.resultados()
        self.assertEqual(len(resultados["informes"][0]["corridas"]), 2)
        self.assertIn("resultados.zip", resultados["archivos"])
        self.assertTrue(self.laboratorio.archivo(trabajo.id, "comparacion_total.csv").exists())
        with self.assertRaises(ValueError):
            self.laboratorio.archivo(trabajo.id, "../fuera.csv")

    def test_cancelar_proceso(self):
        datos = self.laboratorio.iniciar({"escenario": "demo", "metodo": "ga", "semillas": [11],
                                         "configuracion": {"poblacion": 100, "iteraciones": 10000},
                                         "exportar_graficas": False})
        trabajo = self.laboratorio.buscar(datos["id"])
        trabajo.detener()
        estado, _ = self.esperar(trabajo)
        self.assertEqual(estado["estado"], "cancelado")

    def test_generar_no_modifica_escenario_original(self):
        datos = self.laboratorio.generar(60, 2026)
        self.assertEqual(datos["instancia"]["cantidad"], 60)
        self.assertEqual(self.laboratorio.escenario("propio").cantidad, 80)
        self.assertEqual(self.laboratorio.escenario(datos["id"]).cantidad, 60)

    def test_carga_validada_y_limites(self):
        csv = b"ciudad,x,y\nA,0,0\nB,1,0\nC,1,1\nD,0,1\n"
        datos = self.laboratorio.cargar(csv, "../ejemplo.csv")
        self.assertEqual(datos["instancia"]["cantidad"], 4)
        self.assertTrue(self.laboratorio.archivos[datos["id"]].is_relative_to(Path(self.temporal.name)))
        for contenido, nombre in [(b"no es un csv", "mal.csv"), (csv, "archivo.exe"), (b"x" * (2 * 1024 * 1024 + 1), "grande.tsp")]:
            with self.assertRaises(ValueError):
                self.laboratorio.cargar(contenido, nombre)

    def test_contrato_de_la_pagina(self):
        class Elementos(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.referencias = [], []

            def handle_starttag(self, etiqueta, atributos):
                datos = dict(atributos)
                if "id" in datos:
                    self.ids.append(datos["id"])
                for clave in ["for", "aria-controls", "aria-labelledby"]:
                    self.referencias.extend(datos.get(clave, "").split())

        carpeta = Path(__file__).resolve().parent.parent / "interfaz/estaticos"
        elementos = Elementos()
        elementos.feed((carpeta / "index.html").read_text())
        self.assertEqual(len(elementos.ids), len(set(elementos.ids)))
        for referencia in elementos.referencias:
            self.assertIn(referencia, elementos.ids)
        selectores = re.findall(r"\$\('([^']+)'\)", (carpeta / "interfaz.js").read_text())
        for identificador in selectores:
            self.assertIn(identificador, elementos.ids)
