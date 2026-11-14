"""Add authenticated research workspace tables; preserve legacy documents.

Revision ID: 0001_researchmind
Revises: None
"""
from alembic import op
from app.database.database import Base
from app.database import models

revision = "0001_researchmind"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # This additive initial migration handles both empty and legacy databases.
    # Existing unowned documents remain unassigned; no cross-user auto-claim.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    raise RuntimeError("Automatic downgrade would delete research data; restore a backup instead.")
