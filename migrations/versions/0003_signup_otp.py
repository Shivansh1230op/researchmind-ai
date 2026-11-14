"""Add expiring email verification challenges for signup."""
from alembic import op
from app.database.models import SignupChallenge
revision = "0003_signup_otp"
down_revision = "0002_jobs_preferences"
branch_labels = None
depends_on = None

def upgrade():
    SignupChallenge.__table__.create(bind=op.get_bind(), checkfirst=True)

def downgrade():
    raise RuntimeError("Restore a database backup to remove signup verification state.")
