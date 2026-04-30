-- Gems & Luxury — Supabase Postgres schema.
--
-- The application stores each "collection" as a row in a JSONB-backed
-- table named gl_<collection>. Schema is auto-created on backend startup
-- (see backend/db.py::_ensure_schema), but this file is kept as the
-- authoritative reference and is safe to run idempotently.

CREATE TABLE IF NOT EXISTS gl_users               (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_attendance_logs     (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_break_logs          (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_activity_logs       (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_admin_settings      (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_generated_products  (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_naming_families     (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_pricing_rules       (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_product_categories  (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_image_assets        (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_image_variations    (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_image_assignments   (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_export_logs         (id TEXT PRIMARY KEY, doc JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS gl_prompt_templates    (id TEXT PRIMARY KEY, doc JSONB NOT NULL);

CREATE INDEX IF NOT EXISTS idx_gl_users_email                   ON gl_users               ((doc->>'email'));
CREATE INDEX IF NOT EXISTS idx_gl_attendance_logs_user_id       ON gl_attendance_logs     ((doc->>'user_id'));
CREATE INDEX IF NOT EXISTS idx_gl_attendance_logs_punch_out     ON gl_attendance_logs     ((doc->>'punch_out'));
CREATE INDEX IF NOT EXISTS idx_gl_break_logs_attendance_id      ON gl_break_logs          ((doc->>'attendance_id'));
CREATE INDEX IF NOT EXISTS idx_gl_break_logs_end                ON gl_break_logs          ((doc->>'end'));
CREATE INDEX IF NOT EXISTS idx_gl_generated_products_user       ON gl_generated_products  ((doc->>'generated_by_user_id'));
CREATE INDEX IF NOT EXISTS idx_gl_generated_products_at         ON gl_generated_products  ((doc->>'generated_at'));
CREATE INDEX IF NOT EXISTS idx_gl_image_assets_status           ON gl_image_assets        ((doc->>'status'));
CREATE INDEX IF NOT EXISTS idx_gl_activity_logs_timestamp       ON gl_activity_logs       ((doc->>'timestamp'));
CREATE INDEX IF NOT EXISTS idx_gl_prompt_templates_key          ON gl_prompt_templates    ((doc->>'key'));
