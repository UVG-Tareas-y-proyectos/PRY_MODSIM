import unittest

from rutas.datos import cargar_escenario
from rutas.genetico import ConfigGA, resolver_ga
from interfaz.trabajos import validar_solicitud


class PruebasProgreso(unittest.TestCase):
    def test_observador_no_cambia_el_resultado(self):
        instancia = cargar_escenario("demo")
        config = ConfigGA(poblacion=30, iteraciones=20)
        eventos = []
        a = resolver_ga(instancia, config, 11)
        b = resolver_ga(instancia, config, 11, eventos.append)
        self.assertEqual(a["ruta"], b["ruta"])
        self.assertEqual(a["historial"], b["historial"])
        self.assertEqual(eventos[0]["generacion"], 0)
        self.assertEqual(eventos[-1]["generacion"], 20)
        eventos[0]["ruta"].clear()
        self.assertEqual(len(b["ruta"]), 10)

    def test_cancelacion(self):
        with self.assertRaises(InterruptedError):
            resolver_ga(cargar_escenario("demo"), ConfigGA(), 11, cancelar=lambda: True)

    def test_validacion_solicitud(self):
        for solicitud in [{"metodo": "otro"}, {"semillas": [1, 1]},
                          {"configuracion": {"poblacion": 12.5}}, {"limite_lp": float("nan")}]:
            with self.assertRaises(ValueError):
                validar_solicitud(solicitud)
