
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.io.input_resolution import resolve_sequence_record
from core.models.construct_model import ConstructModel
from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
from core.recipes.restriction_cloning import recipe_restriction_cloning
from core.tools.assembly import simulate_digest_ligation
from core.tools.restriction import get_enzyme, restriction_hits


class FinalCircularReactionTests(unittest.TestCase):
    @staticmethod
    def _record(sequence, record_id, topology):
        return SeqRecord(
            Seq(sequence),
            id=record_id,
            annotations={"molecule_type": "DNA", "topology": topology},
        )

    def test_forward_cross_origin_cloning_keeps_complementary_backbone_arc(self):
        base = "C" * 50 + "GAATTC" + "G" * 20 + "A" * 70 + "GGATCC" + "T" * 10
        vector_sequence = base[80:] + base[:80]
        insert_core = (
            "ATGTACTTTTCTACTCTAGTGGCCATGGTGGAGCTACCATATGTTCCTTACTCGACAGTTGGGCGTAGACGTGATGGAGTCGTGCTGAGCCCCCGAGGCCCAACTCTATGATTAAAGTAA"
        )
        insert_template = "G" * 40 + insert_core + "C" * 40
        vector = self._record(vector_sequence, "cross_origin_vector", "circular")
        vector.features = [
            SeqFeature(
                FeatureLocation(75, 100, strand=-1),
                type="misc_feature",
                qualifiers={"label": ["retained_negative"]},
            ),
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(105, 115, strand=-1),
                        FeatureLocation(120, 130, strand=-1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["retained_join"]},
            ),
        ]
        template = self._record(insert_template, "insert_template", "linear")

        result = recipe_restriction_cloning(
            vector,
            template,
            40,
            40 + len(insert_core),
            enzyme5="EcoRI",
            enzyme3="BamHI",
            orientation="auto",
        )
        amplicon = str(result.details["preparation"][0]["product"].seq)
        eco = restriction_hits(vector_sequence, get_enzyme("EcoRI"), circular=True)[0]
        bam = restriction_hits(vector_sequence, get_enzyme("BamHI"), circular=True)[0]
        i_eco = restriction_hits(amplicon, get_enzyme("EcoRI"), circular=False)[0]
        i_bam = restriction_hits(amplicon, get_enzyme("BamHI"), circular=False)[0]
        insert = amplicon[i_eco["top_cut_boundary_0based"] : i_bam["top_cut_boundary_0based"]]
        t5 = eco["top_cut_boundary_0based"]
        t3 = bam["top_cut_boundary_0based"]
        expected = vector_sequence[t3:t5] + insert

        self.assertEqual(result.details["orientation"], "forward")
        self.assertEqual((t5, t3), (133, 67))
        self.assertEqual(len(vector_sequence[t3:t5]), 66)
        self.assertEqual(len(vector_sequence) - len(vector_sequence[t3:t5]), 96)
        self.assertEqual(result.product_sequence, expected)
        product = resolve_sequence_record({"sequence": result.product_sequence, "features": result.features})
        for label in ("retained_negative", "retained_join"):
            source = next(feature for feature in vector.features if feature.qualifiers.get("label") == [label])
            observed = next(feature for feature in product.features if feature.qualifiers.get("label") == [label])
            self.assertEqual(str(observed.extract(product.seq)), str(source.extract(vector.seq)))
        self.assertEqual(next(feature for feature in product.features if feature.qualifiers.get("label") == ["retained_join"]).location.operator, "join")

    def test_reverse_cross_origin_cloning_keeps_complementary_backbone_arc(self):
        vector_sequence = "A" * 50 + "TCATGA" + "C" * 20 + "G" * 70 + "CCATGG" + "T" * 10
        insert_sequence = "G" * 15 + "TCATGA" + "C" * 30 + "CCATGG" + "A" * 15
        vector = self._record(vector_sequence, "reverse_cross_origin_vector", "circular")
        insert = self._record(insert_sequence, "insert", "linear")

        result = simulate_digest_ligation(
            vector,
            insert,
            ["BspHI", "NcoI"],
            ["BspHI", "NcoI"],
            orientation="reverse",
        )
        h5 = restriction_hits(vector_sequence, get_enzyme("BspHI"), circular=True)[0]
        h3 = restriction_hits(vector_sequence, get_enzyme("NcoI"), circular=True)[0]
        i5 = restriction_hits(insert_sequence, get_enzyme("BspHI"), circular=False)[0]
        i3 = restriction_hits(insert_sequence, get_enzyme("NcoI"), circular=False)[0]
        reverse_insert = str(
            Seq(insert_sequence[i5["bottom_cut_boundary_0based"] : i3["bottom_cut_boundary_0based"]]).reverse_complement()
        )
        expected = vector_sequence[h5["top_cut_boundary_0based"] : h3["top_cut_boundary_0based"]] + reverse_insert

        self.assertEqual(result.analysis['insert_orientation'], "reverse")
        self.assertEqual(str(result.only_product().seq), expected)

    def test_cross_origin_mutagenesis_deletion_returns_circular_product(self):
        sequence = "ACGT" * 25
        record = self._record(sequence, "circular_parent", "circular")

        result = recipe_site_directed_mutagenesis(record, 95, 5, "")

        self.assertEqual(result.product_sequence, sequence[5:95])
        self.assertEqual(result.product_topology, "circular")
        self.assertEqual(result.details["mutation_type"], "deletion")

    def test_mutating_cds_refreshes_only_touched_translation(self):
        record = self._record("ATGGCTTAAATGAAATAA", "cds_parent", "linear")
        first = SeqFeature(
            FeatureLocation(0, 9, strand=1),
            type="CDS",
            qualifiers={"label": ["first"], "translation": ["MA"]},
        )
        second = SeqFeature(
            FeatureLocation(9, 18, strand=1),
            type="CDS",
            qualifiers={"label": ["second"], "translation": ["MK"]},
        )
        record.features = [first, second]

        result = ConstructModel(record).mutate([(4, "A")]).to_record()

        self.assertEqual(str(result.seq), "ATGGATTAAATGAAATAA")
        self.assertEqual(result.features[0].qualifiers["translation"], ["MD"])
        self.assertNotIn("partial", result.features[0].qualifiers)
        self.assertEqual(result.features[1].qualifiers, second.qualifiers)


if __name__ == "__main__":
    unittest.main()
