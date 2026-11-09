import itertools
import random
import unittest

from rutas.datos import Instancia, crear_matriz
from rutas.genetico import ConfigGA, cruce_ox, mutar_inversion, resolver_ga
from rutas.recorridos import (distancia_total, mejorar_2opt, ruta_canonica,
                              validar_ruta)


def instancia_pequena():
    puntos = [(0, 0), (1, 0), (2, 1), (1, 3), (0, 2), (1, 1)]
    return Instancia("prueba", list(map(str, range(6))), puntos, crear_matriz(puntos, "REAL_2D"), "REAL_2D")


class PruebasGenetico(unittest.TestCase):
    def test_ruta_cierra(self):
        self.assertEqual(distancia_total([0, 1, 2], [[0, 3, 4], [3, 0, 5], [4, 5, 0]]), 12)

    def test_equivalencia_rotaciones(self):
        self.assertEqual(ruta_canonica([0, 1, 3, 2]), ruta_canonica([3, 2, 0, 1]))
        self.assertEqual(ruta_canonica([0, 1, 3, 2]), ruta_canonica([0, 2, 3, 1]))

    def test_operadores_no_pierden_ciudades(self):
        rng = random.Random(99)
        for n in range(4, 30):
            for _ in range(20):
                a, b = rng.sample(range(n), n), rng.sample(range(n), n)
                original_a, original_b = a.copy(), b.copy()
                validar_ruta(cruce_ox(a, b, rng), n)
                validar_ruta(mutar_inversion(a, rng), n)
                self.assertEqual(a, original_a)
                self.assertEqual(b, original_b)

    def test_configuraciones_invalidas(self):
        casos = [ConfigGA(poblacion=3), ConfigGA(iteraciones=0), ConfigGA(cruce=0.9),
                 ConfigGA(sobrevivientes=0, cruce=0.8), ConfigGA(torneo=999),
                 ConfigGA(cruce=float("nan")), ConfigGA(mejora_local=-1)]
        for config in casos:
            with self.assertRaises(ValueError):
                config.validar()

    def test_selecciones_y_conservacion_del_mejor(self):
        instancia = instancia_pequena()
        optimo = min(distancia_total([0] + list(r), instancia.distancias)
                     for r in itertools.permutations(range(1, instancia.cantidad)))
        for seleccion in ["torneo", "ranking", "elitismo", "mezcla"]:
            config = ConfigGA(poblacion=30, iteraciones=40, seleccion=seleccion)
            resultado = resolver_ga(instancia, config, 11)
            self.assertAlmostEqual(resultado["distancia"], optimo)
            historia = resultado["historial"]
            self.assertTrue(all(a["mejor"] >= b["mejor"] - 1e-9 for a, b in zip(historia, historia[1:])))
            self.assertTrue(all(0 < fila["diversidad"] <= 1 for fila in historia))
            self.assertEqual(sum(resultado["composicion"].values()), 30)

    def test_semilla_reproducible_y_archivo_de_tres_rutas(self):
        config = ConfigGA(poblacion=30, iteraciones=30, inicializacion="aleatoria")
        a = resolver_ga(instancia_pequena(), config, 42)
        b = resolver_ga(instancia_pequena(), config, 42)
        self.assertEqual(a["ruta"], b["ruta"])
        self.assertEqual(a["historial"], b["historial"])
        self.assertEqual(len(a["mejores"]), 3)
        self.assertEqual(len({ruta_canonica(r["ruta"]) for r in a["mejores"]}), 3)
        self.assertEqual(a["instantaneas"][0]["generacion"], 0)
        self.assertEqual(a["instantaneas"][-1]["generacion"], config.iteraciones)

    def test_2opt_mejora_un_cruce(self):
        puntos = [(0, 0), (1, 0), (1, 1), (0, 1)]
        matriz = crear_matriz(puntos, "REAL_2D")
        ruta = [0, 2, 1, 3]
        mejor = mejorar_2opt(ruta, matriz, 1)
        self.assertEqual(distancia_total(mejor, matriz), 4)
        self.assertGreater(distancia_total(ruta, matriz), 4)
        validar_ruta(mejor, 4)
