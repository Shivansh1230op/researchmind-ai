"""Add durable cloud vector chunks and private upload reservations."""
from alembic import op
from sqlalchemy import text
from app.database.models import StoredChunk, UploadTicket

revision = "0004_cloud_storage"
down_revision = "0003_signup_otp"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    StoredChunk.__table__.create(bind=connection, checkfirst=True)
    UploadTicket.__table__.create(bind=connection, checkfirst=True)


def downgrade():
    raise RuntimeError("Restore a backup to remove cloud document storage.")
