
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import unittest

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.assembly import simulate_digest_ligation, simulate_overlap_assembly


class FinalReactionInputTests(unittest.TestCase):
    @staticmethod
    def _overlap_fragments():
        left = "G" * 15 + "A" * 20 + "T" * 15
        right = "T" * 15 + "C" * 20 + "G" * 15
        return left, right

    def test_overlap_rejects_explicit_circular_input_fragment(self):
        left, right = self._overlap_fragments()
        circular_fragment = SeqRecord(
            Seq(left),
            id="circular_fragment",
            annotations={"molecule_type": "DNA", "topology": "circular"},
        )
        linear_fragment = SeqRecord(
            Seq(right),
            id="linear_fragment",
            annotations={"molecule_type": "DNA", "topology": "linear"},
        )

        with self.assertRaisesRegex(ValueError, "physically linear"):
            simulate_overlap_assembly(
                [circular_fragment, linear_fragment],
                min_overlap=15,
                circular=True,
            )

    def test_overlap_keeps_plain_strings_as_linear_fragments(self):
        left, right = self._overlap_fragments()
        result = simulate_overlap_assembly([left, right], min_overlap=15, circular=True)

        self.assertEqual(result.analysis['product_topology'], "circular")
        self.assertEqual(result.analysis['product_length'], 70)

    def test_digest_rejects_explicit_linear_vector(self):
        vector = SeqRecord(
            Seq("A" * 30 + "GAATTC" + "C" * 40 + "GGATCC" + "T" * 30),
            id="linear_vector",
            annotations={"molecule_type": "DNA", "topology": "linear"},
        )
        insert = "A" * 15 + "GAATTC" + "G" * 40 + "GGATCC" + "T" * 15

        with self.assertRaisesRegex(ValueError, "requires a circular vector"):
            simulate_digest_ligation(
                vector,
                insert,
                ["EcoRI", "BamHI"],
                ["EcoRI", "BamHI"],
            )


if __name__ == "__main__":
    unittest.main()
