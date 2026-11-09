import gzip
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

from rutas.datos import (CARPETA_DATOS, cargar_escenario, crear_matriz,
                         descargar_escenario, distancia_geo, generar_escenario,
                         leer_instancia, validar_oficial)
from rutas.recorridos import distancia_total


class PruebasDatos(unittest.TestCase):
    def test_redondeo_tsplib(self):
        matriz = crear_matriz([(0, 0), (2.5, 0), (0, 3)], "EUC_2D")
        self.assertEqual(matriz[0][1], 3)
        self.assertEqual(matriz[0][2], 3)
        self.assertEqual(matriz[1][1], 0)

    def test_distancia_real(self):
        self.assertEqual(crear_matriz([(0, 0), (2.5, 0)], "REAL_2D")[0][1], 2.5)

    def test_geo_grados_minutos_y_signos(self):
        self.assertEqual(distancia_geo((0, 0), (0, 1)), 112)
        self.assertEqual(distancia_geo((0, 0), (0, 1.30)), 167)
        self.assertEqual(distancia_geo((0, 0), (0, -0.30)), 56)

    def test_escenarios_y_simetria(self):
        for nombre, n, tipo in [("eil101", 101, "EUC_2D"), ("gr229", 229, "GEO"), ("propio", 80, "EUC_2D")]:
            instancia = cargar_escenario(nombre)
            self.assertEqual(instancia.cantidad, n)
            self.assertEqual(instancia.tipo, tipo)
            for i in range(n):
                self.assertEqual(instancia.distancias[i][i], 0)
                for j in range(n):
                    self.assertEqual(instancia.distancias[i][j], instancia.distancias[j][i])

    def test_recorrido_publicado_eil101(self):
        contenido = (Path(__file__).parent / "fixtures/eil101.opt.tour").read_text()
        ids = contenido.split("TOUR_SECTION")[1].split("-1")[0].split()
        instancia = cargar_escenario("eil101")
        indices = {nombre: i for i, nombre in enumerate(instancia.ciudades)}
        ruta = [indices[nombre] for nombre in ids]
        self.assertEqual(len(set(ruta)), 101)
        self.assertEqual(distancia_total(ruta, instancia.distancias), 629)

    def test_oficial_modificado_se_rechaza(self):
        instancia = cargar_escenario("eil101")
        instancia.coordenadas[0] = (0, 0)
        with self.assertRaises(ValueError):
            validar_oficial(instancia, "eil101")

    def test_generador_reproducible(self):
        with tempfile.TemporaryDirectory() as temporal:
            a, b = Path(temporal) / "a.tsp", Path(temporal) / "b.tsp"
            generar_escenario(a, 60, 42)
            generar_escenario(b, 60, 42)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(leer_instancia(a).cantidad, 60)
            with self.assertRaises(ValueError):
                generar_escenario(a, 49)

    def test_csv_invalido(self):
        with tempfile.TemporaryDirectory() as temporal:
            archivo = Path(temporal) / "entrada.csv"
            archivo.write_text("ciudad,x,y\n1,0,0\n2,1,0\n3,0,1\n1,2,2\n")
            with self.assertRaises(ValueError):
                leer_instancia(archivo)
            archivo.write_text("ciudad,x,y\n1,nan,0\n2,1,0\n3,0,1\n4,2,2\n")
            with self.assertRaises(ValueError):
                leer_instancia(archivo)

    def test_dimension_incorrecta(self):
        with tempfile.TemporaryDirectory() as temporal:
            archivo = Path(temporal) / "entrada.tsp"
            archivo.write_text("NAME: prueba\nTYPE: TSP\nDIMENSION: 4\nEDGE_WEIGHT_TYPE: EUC_2D\nNODE_COORD_SECTION\n1 0 0\nEOF\n")
            with self.assertRaises(ValueError):
                leer_instancia(archivo)

    def test_descarga_valida_y_no_corrompe_archivo(self):
        contenido = (CARPETA_DATOS / "eil101.tsp").read_bytes()
        with tempfile.TemporaryDirectory() as temporal:
            with patch("rutas.datos.urlopen", return_value=BytesIO(gzip.compress(contenido))):
                destino = descargar_escenario("eil101", temporal)
            self.assertEqual(leer_instancia(destino).cantidad, 101)
            copia = destino.read_bytes()
            with patch("rutas.datos.urlopen", side_effect=OSError("sin red")):
                with self.assertRaises(RuntimeError):
                    descargar_escenario("eil101", temporal)
            self.assertEqual(destino.read_bytes(), copia)
