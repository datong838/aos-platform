"""Allow digest-identical canonical aliases in replacement saved recovery."""
from alembic import op

revision='a0v_090'
down_revision='a0v_089'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    DO $migration$
    DECLARE current_definition text; updated_definition text;
        old_policy text; new_policy text; old_members text; new_members text;
    BEGIN
        SELECT pg_get_functiondef('public.validate_snapshot_recovery_a0v_065()'::regprocedure)
            INTO STRICT current_definition;
        old_policy := $old$AND original.body->'policyRef'=NEW.policy_ref AND renewed.body->'policyRef'=NEW.policy_ref$old$;
        new_policy := $new$AND ((NOT transferred AND original.body->'policyRef'=NEW.policy_ref)
                OR (transferred
                    AND original.body->'policyRef'->>'resourceType'=NEW.policy_ref->>'resourceType'
                    AND original.body->'policyRef'->>'resourceId'=NEW.policy_ref->>'resourceId'))
            AND renewed.body->'policyRef'=NEW.policy_ref$new$;
        old_members := $old$AND m.old_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef']=
                        m.new_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef']))$old$;
        new_members := $new$AND m.old_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef','mappingRef','schemaRef','maskingPolicyRef']=
                        m.new_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef','mappingRef','schemaRef','maskingPolicyRef']
                    AND (m.old_draft->'mappingRef')- 'revision'=(m.new_draft->'mappingRef')- 'revision'
                    AND (m.old_draft->'schemaRef')- 'revision'=(m.new_draft->'schemaRef')- 'revision'
                    AND (m.old_draft->'maskingPolicyRef')- 'revision'=(m.new_draft->'maskingPolicyRef')- 'revision'))$new$;
        IF strpos(current_definition,old_policy)=0 OR strpos(current_definition,old_members)=0 THEN
            RAISE EXCEPTION 'a0v087 exact trigger source required';
        END IF;
        updated_definition := replace(replace(current_definition,old_policy,new_policy),old_members,new_members);
        IF updated_definition=current_definition THEN
            RAISE EXCEPTION 'a0v090 trigger rewrite differs';
        END IF;
        EXECUTE updated_definition;
    END $migration$;
    ''')


def downgrade():
    raise RuntimeError('a0v_090 fail-closed migration is forward only')
