"""Accept the canonical absent source-draft ref in cutover SQL validation."""

from alembic import op


revision = "a0v_052"
down_revision = "a0v_051"
branch_labels = depends_on = None


FUNCTION = "public.extension_dispatch_cutover_commit_ar2_014(uuid,text)"
OLD = "v_draft.snapshot->'sourceDraftRef' IS DISTINCT FROM (CASE"
NEW = "COALESCE(v_draft.snapshot->'sourceDraftRef','null'::jsonb) IS DISTINCT FROM (CASE"


def _replace(expected: str, replacement: str, *, upgrading: bool) -> None:
    guard = (
        f"IF strpos(v_definition, $new${NEW}$new$) > 0 THEN RETURN; END IF;"
        if upgrading
        else f"IF strpos(v_definition, $new${NEW}$new$) = 0 THEN RETURN; END IF;"
    )
    op.execute(
        f"""DO $migration$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef(to_regprocedure('{FUNCTION}')) INTO v_definition;
          IF v_definition IS NULL THEN
            RAISE EXCEPTION 'cutover commit function is unavailable';
          END IF;
          {guard}
          IF strpos(v_definition, $expected${expected}$expected$) = 0 THEN
            RAISE EXCEPTION 'cutover source draft predicate drifted';
          END IF;
          EXECUTE replace(v_definition, $expected${expected}$expected$,
                                      $replacement${replacement}$replacement$);
        END $migration$"""
    )


def upgrade() -> None:
    _replace(OLD, NEW, upgrading=True)


def downgrade() -> None:
    _replace(NEW, OLD, upgrading=False)
