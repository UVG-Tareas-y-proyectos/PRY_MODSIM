import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rutas.datos import cargar_escenario
from rutas.experimentos import construir_tabla, error_porcentual, tres_mejores
from rutas.genetico import ConfigGA, resolver_ga


RAIZ = Path(__file__).resolve().parent.parent


class PruebasExperimentos(unittest.TestCase):
    def test_error_sin_referencia_y_con_referencia(self):
        self.assertIsNone(error_porcentual(100, None))
        self.assertEqual(error_porcentual(110, 100), 10)
        self.assertEqual(error_porcentual(0, 0), 0)
        with self.assertRaises(ValueError):
            error_porcentual(90, 100)

    def test_tres_rutas_distintas_y_tabla(self):
        instancia = cargar_escenario("demo")
        config = ConfigGA(poblacion=20, iteraciones=10)
        corrida = resolver_ga(instancia, config, 11)
        self.assertEqual(len(tres_mejores([corrida, corrida])), 3)
        tabla, referencia = construir_tabla(instancia, config, [corrida], None)
        self.assertIsNone(referencia)
        self.assertEqual([fila["puesto_ga"] for fila in tabla], [1, 2, 3])
        self.assertTrue(all(fila["error_pct"] is None for fila in tabla))

    def test_cli_genera_resultados(self):
        with tempfile.TemporaryDirectory() as temporal:
            resultado = subprocess.run([sys.executable, "main.py", "ejecutar", "--escenario", "demo",
                                        "--metodo", "ga", "--poblacion", "20", "--iteraciones", "10",
                                        "--semillas", "11", "22", "--sin-graficas", "--sin-animacion",
                                        "--salida", temporal], cwd=RAIZ, capture_output=True, text=True)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            json_archivo = next(Path(temporal).rglob("ejecucion.json"))
            datos = json.loads(json_archivo.read_text())
            self.assertEqual(datos["semillas"], [11, 22])
            self.assertEqual(len(datos["mejores_ga"]), 3)
            self.assertIsNone(datos["lp"])
            archivo = next(Path(temporal).rglob("comparacion_total.csv"))
            with archivo.open() as entrada:
                self.assertEqual(len(list(csv.DictReader(entrada))), 3)

    def test_cli_rechaza_porcentajes_y_semillas(self):
        for opciones in [["--cruce", "0.9"], ["--semillas", "1", "1"]]:
            resultado = subprocess.run([sys.executable, "main.py", "ejecutar", "--metodo", "ga", *opciones],
                                       cwd=RAIZ, capture_output=True, text=True)
            self.assertEqual(resultado.returncode, 2)
            self.assertNotIn("Traceback", resultado.stderr)

    def test_cli_descargar_usa_copias_locales(self):
        resultado = subprocess.run([sys.executable, "main.py", "descargar"], cwd=RAIZ,
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("eil101.tsp", resultado.stdout)
        self.assertIn("gr229.tsp", resultado.stdout)
