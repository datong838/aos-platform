"""Align cutover SQL approval version with committed AIP approval events."""

from alembic import op


revision = "a0v_051"
down_revision = "a0v_050"
branch_labels = depends_on = None


FUNCTION = "public.extension_dispatch_cutover_commit_ar2_014(uuid,text)"
OLD = "v_proposal.version IS DISTINCT FROM v_approval.proposal_version"
NEW = "v_proposal.version IS DISTINCT FROM v_approval.proposal_version + 1"


def _replace(expected: str, replacement: str) -> None:
    already_applied = (
        f"IF strpos(v_definition, '{NEW}') > 0 THEN RETURN; END IF;"
        if expected == OLD
        else f"IF strpos(v_definition, '{NEW}') = 0 THEN RETURN; END IF;"
    )
    op.execute(
        f"""DO $migration$
        DECLARE v_definition text;
        BEGIN
          SELECT pg_get_functiondef(to_regprocedure('{FUNCTION}')) INTO v_definition;
          IF v_definition IS NULL THEN
            RAISE EXCEPTION 'cutover commit function is unavailable';
          END IF;
          {already_applied}
          IF strpos(v_definition, '{expected}') = 0 THEN
            RAISE EXCEPTION 'cutover approval version predicate drifted';
          END IF;
          EXECUTE replace(v_definition, '{expected}', '{replacement}');
        END $migration$"""
    )


def upgrade() -> None:
    _replace(OLD, NEW)


def downgrade() -> None:
    _replace(NEW, OLD)
