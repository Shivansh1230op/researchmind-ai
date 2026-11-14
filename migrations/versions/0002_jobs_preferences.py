"""Persist processing jobs and conversation display titles."""
from alembic import op
from app.database.models import DocumentProcessingJob, ConversationPreferences

revision = "0002_jobs_preferences"
down_revision = "0001_researchmind"
branch_labels = None
depends_on = None


def upgrade():
    DocumentProcessingJob.__table__.create(bind=op.get_bind(), checkfirst=True)
    ConversationPreferences.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Downgrade would remove saved processing state; restore a backup instead.")
