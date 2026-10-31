-- Unwired SQL asset. No migration, role creation or application wiring invokes it.
-- Install only after complete source/test review and separately qualified native
-- Owner/ACL/RLS/all-writer and maintenance/restore compatibility evidence.
-- These guards preserve projection origin, not business permission or FSM state.

CREATE FUNCTION public.automation_schedule_binding_projection_guard_v1()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $projection$
DECLARE dispatch record; binding record;
BEGIN
    IF TG_TABLE_SCHEMA <> 'public'
       OR TG_TABLE_NAME <> 'automation_schedule_binding'
       OR TG_WHEN <> 'BEFORE'
       OR TG_NARGS <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection context rejected';
    END IF;
    IF TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW' THEN
        IF ROW(OLD.org_id, OLD.project_id, OLD.policy_id, OLD.policy_revision, OLD.policy_hash, OLD.operation_id, OLD.installation_id, OLD.generation, OLD.execution_epoch, OLD.timezone, OLD.cadence, OLD.weekly_day, OLD.local_time, OLD.effective_from, OLD.effective_until, OLD.approved) IS DISTINCT FROM ROW(NEW.org_id, NEW.project_id, NEW.policy_id, NEW.policy_revision, NEW.policy_hash, NEW.operation_id, NEW.installation_id, NEW.generation, NEW.execution_epoch, NEW.timezone, NEW.cadence, NEW.weekly_day, NEW.local_time, NEW.effective_from, NEW.effective_until, NEW.approved) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'automation projection identity is immutable';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' AND TG_LEVEL = 'ROW' THEN
        SELECT d.installation_id, d.generation, d.execution_epoch, d.handler_kind
          INTO dispatch FROM public.extension_operation_dispatch_binding d
         WHERE d.org_id = NEW.org_id AND d.project_id = NEW.project_id
           AND d.operation_id = NEW.operation_id
         FOR SHARE NOWAIT;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'schedule dispatch parent unavailable';
        END IF;
        IF dispatch.handler_kind IS DISTINCT FROM 'extension'
           OR ROW(dispatch.installation_id, dispatch.generation, dispatch.execution_epoch)
              IS DISTINCT FROM ROW(NEW.installation_id, NEW.generation, NEW.execution_epoch) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'schedule dispatch projection differs';
        END IF;
        SELECT b.execution_epoch INTO binding FROM public.extension_runtime_binding b
         WHERE b.org_id = NEW.org_id AND b.project_id = NEW.project_id
           AND b.installation_id = NEW.installation_id AND b.generation = NEW.generation
         FOR SHARE NOWAIT;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'schedule runtime parent unavailable';
        END IF;
        IF binding.execution_epoch IS DISTINCT FROM NEW.execution_epoch THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'schedule runtime projection differs';
        END IF;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW')
       OR (TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT') THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection history must be retained';
    ELSE
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection event rejected';
    END IF;
END;
$projection$;

REVOKE ALL ON FUNCTION public.automation_schedule_binding_projection_guard_v1() FROM PUBLIC;
ALTER FUNCTION public.automation_schedule_binding_projection_guard_v1() OWNER TO aos_terminal_source_projection_owner;
CREATE TRIGGER automation_schedule_binding_projection_row_v1
BEFORE INSERT OR UPDATE OR DELETE ON public.automation_schedule_binding
FOR EACH ROW EXECUTE FUNCTION public.automation_schedule_binding_projection_guard_v1();
CREATE TRIGGER automation_schedule_binding_projection_truncate_v1
BEFORE TRUNCATE ON public.automation_schedule_binding
FOR EACH STATEMENT EXECUTE FUNCTION public.automation_schedule_binding_projection_guard_v1();

CREATE FUNCTION public.automation_occurrence_projection_guard_v1()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $projection$
DECLARE schedule record;
BEGIN
    IF TG_TABLE_SCHEMA <> 'public'
       OR TG_TABLE_NAME <> 'automation_occurrence'
       OR TG_WHEN <> 'BEFORE'
       OR TG_NARGS <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection context rejected';
    END IF;
    IF TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW' THEN
        IF ROW(OLD.org_id, OLD.project_id, OLD.occurrence_id, OLD.policy_id, OLD.policy_revision, OLD.policy_hash, OLD.operation_id, OLD.installation_id, OLD.generation, OLD.execution_epoch, OLD.scheduled_at, OLD.local_slot, OLD.trigger_source, OLD.source_event_id, OLD.deadline, OLD.created_at) IS DISTINCT FROM ROW(NEW.org_id, NEW.project_id, NEW.occurrence_id, NEW.policy_id, NEW.policy_revision, NEW.policy_hash, NEW.operation_id, NEW.installation_id, NEW.generation, NEW.execution_epoch, NEW.scheduled_at, NEW.local_slot, NEW.trigger_source, NEW.source_event_id, NEW.deadline, NEW.created_at) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'automation projection identity is immutable';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' AND TG_LEVEL = 'ROW' THEN
        SELECT s.policy_hash, s.operation_id, s.installation_id, s.generation, s.execution_epoch
          INTO schedule FROM public.automation_schedule_binding s
         WHERE s.org_id = NEW.org_id AND s.project_id = NEW.project_id
           AND s.policy_id = NEW.policy_id AND s.policy_revision = NEW.policy_revision
         FOR SHARE NOWAIT;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'occurrence schedule parent unavailable';
        END IF;
        IF ROW(schedule.policy_hash, schedule.operation_id, schedule.installation_id, schedule.generation, schedule.execution_epoch)
           IS DISTINCT FROM ROW(NEW.policy_hash, NEW.operation_id, NEW.installation_id, NEW.generation, NEW.execution_epoch) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'occurrence schedule projection differs';
        END IF;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW')
       OR (TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT') THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection history must be retained';
    ELSE
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection event rejected';
    END IF;
END;
$projection$;

REVOKE ALL ON FUNCTION public.automation_occurrence_projection_guard_v1() FROM PUBLIC;
ALTER FUNCTION public.automation_occurrence_projection_guard_v1() OWNER TO aos_terminal_source_projection_owner;
CREATE TRIGGER automation_occurrence_projection_row_v1
BEFORE INSERT OR UPDATE OR DELETE ON public.automation_occurrence
FOR EACH ROW EXECUTE FUNCTION public.automation_occurrence_projection_guard_v1();
CREATE TRIGGER automation_occurrence_projection_truncate_v1
BEFORE TRUNCATE ON public.automation_occurrence
FOR EACH STATEMENT EXECUTE FUNCTION public.automation_occurrence_projection_guard_v1();

CREATE FUNCTION public.automation_occurrence_dispatch_attempt_projection_guard_v1()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $projection$
DECLARE occurrence record;
BEGIN
    IF TG_TABLE_SCHEMA <> 'public'
       OR TG_TABLE_NAME <> 'automation_occurrence_dispatch_attempt'
       OR TG_WHEN <> 'BEFORE'
       OR TG_NARGS <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection context rejected';
    END IF;
    IF TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW' THEN
        IF ROW(OLD.org_id, OLD.project_id, OLD.attempt_id, OLD.occurrence_id, OLD.claim_owner, OLD.target_idempotency_key, OLD.claimed_at, OLD.claim_until) IS DISTINCT FROM ROW(NEW.org_id, NEW.project_id, NEW.attempt_id, NEW.occurrence_id, NEW.claim_owner, NEW.target_idempotency_key, NEW.claimed_at, NEW.claim_until) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'automation projection identity is immutable';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' AND TG_LEVEL = 'ROW' THEN
        SELECT o.status, o.claim_owner, o.claim_until, o.deadline
          INTO occurrence FROM public.automation_occurrence o
         WHERE o.org_id = NEW.org_id AND o.project_id = NEW.project_id
           AND o.occurrence_id = NEW.occurrence_id
         FOR SHARE NOWAIT;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'attempt occurrence parent unavailable';
        END IF;
        IF occurrence.status IS DISTINCT FROM 'claimed'
           OR occurrence.claim_owner IS DISTINCT FROM NEW.claim_owner
           OR occurrence.claim_until IS DISTINCT FROM NEW.claim_until
           OR NEW.target_idempotency_key IS DISTINCT FROM 'automation-occurrence:' || NEW.occurrence_id::text
           OR NEW.claimed_at >= NEW.claim_until
           OR NEW.claimed_at >= occurrence.deadline THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'attempt claim projection differs';
        END IF;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW')
       OR (TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT') THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection history must be retained';
    ELSE
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'automation projection event rejected';
    END IF;
END;
$projection$;

REVOKE ALL ON FUNCTION public.automation_occurrence_dispatch_attempt_projection_guard_v1() FROM PUBLIC;
ALTER FUNCTION public.automation_occurrence_dispatch_attempt_projection_guard_v1() OWNER TO aos_terminal_source_projection_owner;
CREATE TRIGGER automation_occurrence_dispatch_attempt_projection_row_v1
BEFORE INSERT OR UPDATE OR DELETE ON public.automation_occurrence_dispatch_attempt
FOR EACH ROW EXECUTE FUNCTION public.automation_occurrence_dispatch_attempt_projection_guard_v1();
CREATE TRIGGER automation_occurrence_dispatch_attempt_projection_truncate_v1
BEFORE TRUNCATE ON public.automation_occurrence_dispatch_attempt
FOR EACH STATEMENT EXECUTE FUNCTION public.automation_occurrence_dispatch_attempt_projection_guard_v1();
