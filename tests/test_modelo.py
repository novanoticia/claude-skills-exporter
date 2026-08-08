import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.modelo import (  # noqa: E402
    Capacidad,
    Estado,
    Senal,
    capacidades_de,
)


class PrecedenciaDeEstados(unittest.TestCase):

    def test_no_compatible_gana_a_todo(self):
        self.assertEqual(
            Estado.peor([Estado.COMPATIBLE, Estado.NO_COMPATIBLE, Estado.DEGRADADO]),
            Estado.NO_COMPATIBLE)

    def test_no_verificable_gana_a_degradado(self):
        self.assertEqual(
            Estado.peor([Estado.DEGRADADO, Estado.NO_VERIFICABLE]),
            Estado.NO_VERIFICABLE)

    def test_sin_estados_es_compatible(self):
        self.assertEqual(Estado.peor([]), Estado.COMPATIBLE)


class InferenciaDeCapacidades(unittest.TestCase):

    def test_mcp_exige_cliente_mcp(self):
        caps = capacidades_de([Senal("mcp-tool", "SKILL.md:12", "mcp__gmail__buscar", "alta")],
                              tiene_scripts=False)
        self.assertIn(Capacidad("mcp.cliente", "requerida"), caps)

    def test_estado_persistente_exige_escribir_no_una_capacidad_propia(self):
        # El hibrido en accion: la capacidad es escribir, que Mistral SI tiene.
        # Que la escritura no sobreviva es un peligro, no una capacidad ausente.
        caps = capacidades_de([Senal("estado-persistente", "SKILL.md:40", ">> log.jsonl", "media")],
                              tiene_scripts=False)
        self.assertIn(Capacidad("filesystem.escribir", "requerida"), caps)
        self.assertNotIn("filesystem.persistencia", [c.nombre for c in caps])

    def test_carpeta_scripts_exige_ejecutarlos(self):
        caps = capacidades_de([], tiene_scripts=True)
        self.assertEqual(caps, [Capacidad("scripts.ejecutar", "requerida")])

    def test_los_comandos_con_namespace_son_opcionales(self):
        caps = capacidades_de([Senal("slash-plugin", "SKILL.md:5", "/mi-plugin:comando", "media")],
                              tiene_scripts=False)
        self.assertEqual(caps, [Capacidad("comandos.namespace", "opcional")])

    def test_las_senales_cosmeticas_no_exigen_nada(self):
        caps = capacidades_de([Senal("claude-brand", "SKILL.md:3", "Claude Code", "baja")],
                              tiene_scripts=False)
        self.assertEqual(caps, [])

    def test_no_duplica_capacidades_repetidas(self):
        caps = capacidades_de([
            Senal("mcp-tool", "SKILL.md:12", "mcp__a__b", "alta"),
            Senal("mcp-tool", "SKILL.md:30", "mcp__c__d", "alta"),
        ], tiene_scripts=False)
        self.assertEqual(caps, [Capacidad("mcp.cliente", "requerida")])


if __name__ == "__main__":
    unittest.main()
