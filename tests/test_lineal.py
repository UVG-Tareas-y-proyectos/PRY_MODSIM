import importlib.util
import itertools
from pathlib import Path
import tempfile
import unittest

from rutas.datos import Instancia, crear_matriz
from rutas.lineal import (crear_modelo, encontrar_componentes, leer_cota,
                          reconstruir_ruta, resolver_lp)
from rutas.recorridos import distancia_total, validar_ruta


def cbc_disponible():
    if importlib.util.find_spec("pulp") is None:
        return False
    import pulp
    return hasattr(pulp, "PULP_CBC_CMD") and bool(pulp.PULP_CBC_CMD(msg=False).available())


class PruebasSubrutas(unittest.TestCase):
    def test_componentes_desconectados(self):
        aristas = [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)]
        self.assertEqual(encontrar_componentes(6, aristas), [[0, 1, 2], [3, 4, 5]])
        self.assertIsNone(reconstruir_ruta(6, aristas))

    def test_reconstruccion_ciclo(self):
        ruta = reconstruir_ruta(4, [(0, 1), (1, 2), (2, 3), (0, 3)])
        validar_ruta(ruta, 4)
        self.assertEqual(ruta[0], 0)

    def test_rechaza_grados_invalidos(self):
        self.assertIsNone(reconstruir_ruta(4, [(0, 1), (1, 2), (0, 2)]))

    def test_lectura_cotas(self):
        texto = "Continuous objective value is 20\nLower bound: 25.5\nCbc best possible 26.0\n"
        self.assertEqual(leer_cota(texto), 26)
        self.assertIsNone(leer_cota("sin información de cota"))


@unittest.skipUnless(cbc_disponible(), "PuLP/CBC no están disponibles")
class PruebasModelo(unittest.TestCase):
    def crear_instancia(self):
        puntos = [(0, 0), (1, 0), (1, 1), (0, 1), (20, 0), (21, 0), (21, 1), (20, 1)]
        return Instancia("cuadrados", list(map(str, range(8))), puntos, crear_matriz(puntos, "REAL_2D"), "REAL_2D")

    def test_variables_y_grados(self):
        modelo, aristas = crear_modelo(self.crear_instancia())
        self.assertEqual(len(aristas), 28)
        self.assertEqual(len(modelo.constraints), 8)

    def test_optimo_con_cortes_frente_enumeracion(self):
        instancia = self.crear_instancia()
        optimo = min(distancia_total([0] + list(r), instancia.distancias)
                     for r in itertools.permutations(range(1, 8)))
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = resolver_lp(instancia, Path(carpeta), 30)
            self.assertTrue((Path(carpeta) / "modelo.lp").exists())
        self.assertTrue(resultado["optima_demostrada"])
        self.assertAlmostEqual(resultado["distancia"], optimo)
        self.assertGreater(resultado["cortes"], 0)
        self.assertEqual(resultado["gap_pct"], 0)
