from tests.conftest import fixture_db  # noqa: F401  # pyright: ignore
from tests.test_pdf_pipeline import TestCreditLoadVariations, default_config, pdf_dir  # noqa: F401, E501  # pyright: ignore
# ignore error lines

def test_manual(pdf_dir, fixture_db, default_config):  # noqa: F811
    t = TestCreditLoadVariations()
    t.test_credit_load_respected(pdf_dir, fixture_db, default_config, 15)
