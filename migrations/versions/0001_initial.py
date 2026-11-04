"""initial schema: landmarks, photos, model classes, itineraries, reports

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Case-insensitive-ish search over landmark names. pg_trgm is bundled with
    # PostgreSQL, so this needs no extra service.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "landmarks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_ru", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("year_built", sa.SmallInteger()),
        sa.Column("building_type", sa.Text()),
        sa.Column("style", sa.Text()),
        sa.Column("architect", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("fun_fact", sa.Text()),
        sa.Column("lat", sa.Double()),
        sa.Column("lon", sa.Double()),
        sa.Column("coordinate_source", sa.Text()),
        sa.Column(
            "angles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "source_photos",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("lat IS NULL OR lat BETWEEN -90 AND 90", name="landmarks_lat_range"),
        sa.CheckConstraint("lon IS NULL OR lon BETWEEN -180 AND 180", name="landmarks_lon_range"),
        sa.CheckConstraint(
            "year_built IS NULL OR year_built BETWEEN 1000 AND 2100",
            name="landmarks_year_range",
        ),
        sa.CheckConstraint("sort_order >= 0", name="landmarks_sort_order_non_negative"),
    )
    op.create_index("landmarks_lat_lon_idx", "landmarks", ["lat", "lon"])
    op.create_index("landmarks_sort_order_idx", "landmarks", ["sort_order"])
    op.create_index(
        "landmarks_name_trgm_idx",
        "landmarks",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "landmarks_name_ru_trgm_idx",
        "landmarks",
        ["name_ru"],
        postgresql_using="gin",
        postgresql_ops={"name_ru": "gin_trgm_ops"},
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER landmarks_set_updated_at
        BEFORE UPDATE ON landmarks
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )

    op.create_table(
        "photos",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "landmark_id",
            sa.Text(),
            sa.ForeignKey("landmarks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text()),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(64)),
        sa.Column("mime", sa.Text(), nullable=False, server_default="image/jpeg"),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("author", sa.Text()),
        sa.Column("license", sa.Text()),
        sa.Column("license_url", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "NOT is_published OR ("
            "  author IS NOT NULL AND length(btrim(author)) > 0 AND "
            "  license IS NOT NULL AND length(btrim(license)) > 0 AND "
            "  license_url IS NOT NULL AND "
            "  source_url IS NOT NULL"
            ")",
            name="photos_published_needs_credit",
        ),
        sa.CheckConstraint("width IS NULL OR width > 0", name="photos_width_positive"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="photos_height_positive"),
    )
    op.create_index("photos_landmark_idx", "photos", ["landmark_id"])
    op.create_index(
        "photos_one_published_per_landmark",
        "photos",
        ["landmark_id"],
        unique=True,
        postgresql_where=sa.text("is_published"),
    )

    op.create_table(
        "model_classes",
        sa.Column("class_name", sa.Text(), primary_key=True),
        sa.Column(
            "landmark_id",
            sa.Text(),
            sa.ForeignKey("landmarks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("class_index", sa.SmallInteger(), nullable=False),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mapping_note", sa.Text()),
        sa.Column("train_images", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("val_images", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("test_images", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("class_index >= 0", name="model_classes_index_non_negative"),
        sa.CheckConstraint(
            "train_images >= 0 AND val_images >= 0 AND test_images >= 0",
            name="model_classes_counts_non_negative",
        ),
    )
    op.create_index("model_classes_class_index_key", "model_classes", ["class_index"], unique=True)
    op.create_index("model_classes_landmark_idx", "model_classes", ["landmark_id"])

    op.create_table(
        "itineraries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "start_landmark_id",
            sa.Text(),
            sa.ForeignKey("landmarks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("minutes", sa.SmallInteger()),
        sa.Column("mode", sa.Text(), nullable=False, server_default="custom"),
        sa.Column("total_minutes", sa.SmallInteger()),
        sa.Column("total_distance_m", sa.Integer()),
        sa.Column("route", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "minutes IS NULL OR minutes BETWEEN 15 AND 480",
            name="itineraries_minutes_range",
        ),
        sa.CheckConstraint("mode IN ('custom', 'suggested')", name="itineraries_mode"),
        sa.CheckConstraint(
            "total_minutes IS NULL OR total_minutes >= 0",
            name="itineraries_total_minutes_non_negative",
        ),
        sa.CheckConstraint(
            "total_distance_m IS NULL OR total_distance_m >= 0",
            name="itineraries_total_distance_non_negative",
        ),
    )
    op.create_index("itineraries_created_idx", "itineraries", [sa.text("created_at DESC")])

    op.create_table(
        "itinerary_items",
        sa.Column(
            "itinerary_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("itineraries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "landmark_id",
            sa.Text(),
            sa.ForeignKey("landmarks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dwell_minutes", sa.SmallInteger()),
        sa.PrimaryKeyConstraint("itinerary_id", "position"),
        sa.CheckConstraint("position >= 0", name="itinerary_items_position_non_negative"),
        sa.CheckConstraint(
            "dwell_minutes IS NULL OR dwell_minutes BETWEEN 0 AND 120",
            name="itinerary_items_dwell_range",
        ),
    )
    op.create_index("itinerary_items_landmark_idx", "itinerary_items", ["landmark_id"])

    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "landmark_id",
            sa.Text(),
            sa.ForeignKey("landmarks.id", ondelete="SET NULL"),
        ),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "category IN ('wrong_photo', 'wrong_info', 'closed', 'other')",
            name="reports_category",
        ),
        sa.CheckConstraint(
            "char_length(message) BETWEEN 10 AND 2000",
            name="reports_message_length",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="reports_status",
        ),
    )
    op.create_index("reports_status_created_idx", "reports", ["status", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("itinerary_items")
    op.drop_table("itineraries")
    op.drop_table("model_classes")
    op.drop_table("photos")
    op.drop_table("landmarks")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # pg_trgm is left in place: other objects in the database may depend on it.
