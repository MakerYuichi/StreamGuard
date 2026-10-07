# Database Migrations

All schema changes are stored as idempotent SQL files here. Each file is safe to re-run.

**Versioning:** Files are named `NNNN_<description>.sql` where `NNNN` is a zero-padded sequence number (0001, 0002, etc.).

**Execution:** The `infra/docker-entrypoint-initdb.d/` entry point runs the base schema first (`01_init.sql`), then these migrations in alphabetical order. New container starts always run the full sequence (idempotency is required).

**Schema:** All statements use `IF NOT EXISTS`, `IF EXISTS`, or other guards so they can be safely re-run.

| File | Change | Status |
|---|---|---|
| (none yet) | — | Base schema in 01_init.sql covers Phase 1 |
