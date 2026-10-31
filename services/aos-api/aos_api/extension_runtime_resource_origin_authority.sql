-- Unwired SQL asset: apply only in a separately authorized atomic installation.
-- This guard cannot establish historical completeness or protect against DDL owners.
CREATE FUNCTION public.extension_runtime_resource_origin_guard_v1()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $resource_origin$
BEGIN
    IF TG_TABLE_SCHEMA <> 'public'
       OR TG_TABLE_NAME <> 'extension_runtime_resource_lease'
       OR TG_WHEN <> 'BEFORE'
       OR TG_NARGS <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'resource origin trigger context rejected';
    END IF;

    IF TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW' THEN
        IF ROW(OLD.org_id, OLD.project_id, OLD.resource_id, OLD.operation_id, OLD.generation,
               OLD.package_id, OLD.package_hash, OLD.engine_context, OLD.resource_name, OLD.owner_token_ref)
           IS DISTINCT FROM ROW(NEW.org_id, NEW.project_id, NEW.resource_id, NEW.operation_id, NEW.generation,
                                NEW.package_id, NEW.package_hash, NEW.engine_context, NEW.resource_name, NEW.owner_token_ref) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'resource origin identity is immutable';
        END IF;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW')
       OR (TG_OP = 'TRUNCATE' AND TG_LEVEL = 'STATEMENT') THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'resource origin history must be retained';
    ELSE
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'resource origin event rejected';
    END IF;
END;
$resource_origin$;

REVOKE ALL ON FUNCTION public.extension_runtime_resource_origin_guard_v1() FROM PUBLIC;
ALTER FUNCTION public.extension_runtime_resource_origin_guard_v1() OWNER TO aos_terminal_source_projection_owner;

CREATE TRIGGER extension_runtime_resource_origin_row_v1
BEFORE UPDATE OR DELETE ON public.extension_runtime_resource_lease
FOR EACH ROW EXECUTE FUNCTION public.extension_runtime_resource_origin_guard_v1();

CREATE TRIGGER extension_runtime_resource_origin_truncate_v1
BEFORE TRUNCATE ON public.extension_runtime_resource_lease
FOR EACH STATEMENT EXECUTE FUNCTION public.extension_runtime_resource_origin_guard_v1();
