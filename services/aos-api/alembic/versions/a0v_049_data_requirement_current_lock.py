"""Lock an exact current Requirement without granting runtime table updates."""
from alembic import op

revision = 'a0v_049'
down_revision = 'a0v_048'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE FUNCTION data_requirement_lock_current_a0v_049(
        p_requirement_id text, p_revision bigint, p_hash text)
        RETURNS TABLE(locked_requirement_id text, locked_revision bigint, locked_content_hash text)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            v_org text := NULLIF(current_setting('aos.org_id',true),'');
            v_project text := NULLIF(current_setting('aos.project_id',true),'');
            v_head record;
        BEGIN
            IF v_org IS NULL OR v_project IS NULL THEN
                RAISE EXCEPTION USING ERRCODE='DR004',MESSAGE='tenant scope is required';
            END IF;
            IF p_requirement_id IS NULL OR length(p_requirement_id) NOT BETWEEN 1 AND 200
                OR p_requirement_id<>btrim(p_requirement_id)
                OR p_revision IS NULL OR p_revision<1
                OR p_hash IS NULL OR p_hash !~ '^sha256:[0-9a-f]{64}$' THEN
                RAISE EXCEPTION USING ERRCODE='DR003',MESSAGE='exact requirement reference is required';
            END IF;
            SELECT h.requirement_id,h.current_revision,h.current_content_hash INTO v_head
                FROM public.data_requirement_head h
                WHERE h.org_id=v_org AND h.project_id=v_project AND h.requirement_id=p_requirement_id
                FOR SHARE OF h;
            IF NOT FOUND OR v_head.current_revision IS DISTINCT FROM p_revision
                OR btrim(v_head.current_content_hash) IS DISTINCT FROM substring(p_hash from 8) THEN
                RAISE EXCEPTION USING ERRCODE='DR001',MESSAGE='requirement exact ref is not current';
            END IF;
            RETURN QUERY SELECT v_head.requirement_id,v_head.current_revision,
                'sha256:'||btrim(v_head.current_content_hash);
        END $$''')
    op.execute('REVOKE ALL ON FUNCTION data_requirement_lock_current_a0v_049(text,bigint,text) FROM PUBLIC')
    op.execute('GRANT EXECUTE ON FUNCTION data_requirement_lock_current_a0v_049(text,bigint,text) TO aos_runtime')


def downgrade():
    op.execute('DROP FUNCTION data_requirement_lock_current_a0v_049(text,bigint,text)')
