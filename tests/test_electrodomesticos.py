import unittest
from datetime import date

from brain.core.config import Config
from brain.modules.electrodomesticos import Electrodomesticos, sumar_meses
from tests.helpers import CasoBrain


class TestElectrodomesticos(CasoBrain):
    def setUp(self):
        super().setUp()
        self.e = self.brain.tools.ejecutar

    def test_guardar_completar_y_listar(self):
        r = self.e("anadir_electrodomestico", {"nombre": "Lavadora", "marca": "Bosch", "modelo": "WAN28258ES", "fecha_compra": "2025-03-15", "garantia_meses": 36})["guardado"]
        self.assertEqual(r["garantia_hasta"], "2028-03-15")
        self.assertFalse(r["actualizado"])

        r = self.e("anadir_electrodomestico", {"nombre": "lavadora", "ubicacion": "lavadero"})["guardado"]  # completa, no pisa
        self.assertTrue(r["actualizado"])
        self.assertEqual((r["marca"], r["ubicacion"]), ("Bosch", "lavadero"))

        lista = self.e("ver_electrodomesticos")["electrodomesticos"]
        self.assertEqual(len(lista), 1)
        self.assertIn("garantía", lista[0]["garantia"])

    def test_errores_y_quitar(self):
        self.assertIn("error", self.e("anadir_electrodomestico", {"nombre": " "}))
        self.assertIn("error", self.e("anadir_electrodomestico", {"nombre": "x", "garantia_meses": 0}))
        self.assertIn("error", self.e("quitar_electrodomestico", {"nombre": "horno"}))

        self.e("anadir_electrodomestico", {"nombre": "Horno"})
        self.assertEqual(self.e("quitar_electrodomestico", {"nombre": "horno"}), {"quitado": "Horno"})
        self.assertIn("mensaje", self.e("ver_electrodomesticos"))

    def test_meses_a_fin_de_mes(self):
        self.assertEqual(sumar_meses(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertEqual(sumar_meses(date(2025, 11, 15), 3), date(2026, 2, 15))

    def test_garantias_por_caducar(self):
        self.e("anadir_electrodomestico", {"nombre": "Nevera", "fecha_compra": "2024-01-10", "garantia_meses": 24})
        modulo = Electrodomesticos()

        self.assertEqual([a["nombre"] for a in modulo.garantias_por_caducar(30, hoy=date(2025, 12, 20))], ["Nevera"])
        self.assertEqual(modulo.garantias_por_caducar(30, hoy=date(2025, 6, 1)), [])
        self.assertIn("caducó", modulo.estado_garantia(modulo.aparatos()[0], hoy=date(2026, 6, 1)))

    def test_consultar_trae_la_ficha_y_el_manual(self):
        carpeta = Config.DATOS / "documentos"
        carpeta.mkdir(parents=True)
        (carpeta / "manual_bosch_lavadora.md").write_text(
            "# Lavadora Bosch\n\n## Error E18\n\nEl error E18 indica que el desagüe está obstruido. Limpia el filtro de la bomba.\n",
            encoding="utf-8",
        )
        (carpeta / "caldera.txt").write_text("La caldera se purga abriendo la válvula roja.", encoding="utf-8")
        self.e("anadir_electrodomestico", {"nombre": "Lavadora", "marca": "Bosch", "modelo": "WAN28258ES"})

        r = self.e("consultar_electrodomestico", {"nombre": "la lavadora", "problema": "da el error E18"})

        self.assertEqual(r["aparato"]["modelo"], "WAN28258ES")
        self.assertEqual(r["fragmentos_de_manuales"][0]["documento"], "manual_bosch_lavadora.md")

    def test_consultar_sin_manuales_o_sin_aparato(self):
        self.e("anadir_electrodomestico", {"nombre": "Horno", "marca": "Teka"})

        self.assertEqual(self.e("consultar_electrodomestico", {"nombre": "horno", "problema": "no calienta"})["fragmentos_de_manuales"], [])
        self.assertIn("No tengo registrado", self.e("consultar_electrodomestico", {"nombre": "secadora"})["error"])


if __name__ == "__main__":
    unittest.main()
