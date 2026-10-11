-- PROPOSAL ONLY. Formal source is currently READ ONLY.
-- Requires explicit scoped maintenance authorization and fresh identity/backup checks.
-- Execute using psql ON_ERROR_STOP=1; zero affected rows must abort.
BEGIN ISOLATION LEVEL SERIALIZABLE;
WITH changed AS (UPDATE ONLY public.meta_org SET name='栖月汇商贸有限公司',updated_at=clock_timestamp() WHERE id='org-org' AND name='org-org' AND updated_at='2026-10-05 02:21:26.625638+00'::timestamptz RETURNING id,name) SELECT 1 / count(*) AS exactly_one_row FROM changed;
COMMIT;
