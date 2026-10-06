BEGIN;
CREATE TEMP TABLE publication_attempt_probe (id text PRIMARY KEY, finalized boolean NOT NULL) ON COMMIT DROP;
CREATE FUNCTION pg_temp.publication_attempt_probe_check() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $fn$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_temp.publication_attempt_probe WHERE id=NEW.id AND finalized IS NOT TRUE) THEN
  RAISE EXCEPTION USING MESSAGE='PUBLICATION_PREPARE_ONLY_COMMIT_REJECTED',ERRCODE='23514';
 END IF;
 RETURN NULL;
END;$fn$;
CREATE CONSTRAINT TRIGGER publication_attempt_probe_deferred AFTER INSERT OR UPDATE ON publication_attempt_probe DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pg_temp.publication_attempt_probe_check();
INSERT INTO publication_attempt_probe VALUES ('one',false); SAVEPOINT check_attempt; SET CONSTRAINTS ALL IMMEDIATE; ROLLBACK TO check_attempt; COMMIT;
