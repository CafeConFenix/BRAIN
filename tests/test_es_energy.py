from brain import i18n
from brain.modules.energy import RealtimeEnergy, describe
from tests.test_energy import CaseEnergy


class TestSpanishEnergy(CaseEnergy):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)
        self.addCleanup(i18n.reset)

    def test_the_summary_speaks_spanish(self):
        text_ = describe(RealtimeEnergy().read())

        self.assertIn("Las placas producen 3.20 kW", text_)
        self.assertIn("se vierten 900 W a la red", text_)
