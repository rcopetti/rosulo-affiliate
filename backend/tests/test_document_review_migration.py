from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_document_review_migration_follows_current_head():
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("a9b0c1d2e3f4")
    assert revision.down_revision == "d4e5f6a7b8c9"


def test_manual_payout_migration_follows_document_review_head():
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "b1c2d3e4f5a6"
    revision = script.get_revision("b1c2d3e4f5a6")
    assert revision.down_revision == "a9b0c1d2e3f4"


def test_document_review_models_include_merchant_scope_and_decisions():
    from app.db.models import AffiliateDocument, AffiliateDocumentReview

    assert AffiliateDocument.__table__.c.affiliate_id.nullable is True
    assert AffiliateDocumentReview.__tablename__ == "affiliate_document_reviews"
    assert AffiliateDocumentReview.__table__.c.rejection_reason.nullable is True
    assert {
        constraint.name for constraint in AffiliateDocumentReview.__table__.constraints
    } >= {
        "ck_affiliate_document_reviews_status",
        "ck_affiliate_document_reviews_rejection_reason",
    }
