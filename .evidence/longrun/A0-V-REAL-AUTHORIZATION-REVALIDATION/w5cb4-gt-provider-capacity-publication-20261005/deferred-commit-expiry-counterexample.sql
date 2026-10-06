BEGIN;
CREATE TEMP TABLE publication_time_probe(id text PRIMARY KEY, expires_at timestamptz NOT NULL) ON COMMIT PRESERVE ROWS;
CREATE FUNCTION pg_temp.publication_time_probe_check() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $fn$
BEGIN
 IF EXISTS(SELECT 1 FROM pg_temp.publication_time_probe WHERE id=NEW.id AND expires_at<=clock_timestamp()) THEN
  RAISE EXCEPTION USING MESSAGE='PUBLICATION_COMMIT_EXPIRY_REJECTED',ERRCODE='23514';
 END IF;
 RETURN NULL;
END;$fn$;
CREATE CONSTRAINT TRIGGER publication_time_probe_deferred AFTER INSERT ON publication_time_probe DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pg_temp.publication_time_probe_check();
INSERT INTO publication_time_probe VALUES('one',clock_timestamp()+interval '1 second');
SET CONSTRAINTS ALL IMMEDIATE;
SELECT pg_sleep(2);
COMMIT;
SELECT 'EXPIRED_ROW_COMMITTED='||(expires_at<=clock_timestamp())::text FROM publication_time_probe;
