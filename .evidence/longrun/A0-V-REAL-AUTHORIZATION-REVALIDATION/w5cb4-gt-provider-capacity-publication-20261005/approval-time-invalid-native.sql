BEGIN READ ONLY;
SET LOCAL TimeZone = 'UTC';
SELECT label, isfinite(value), extract(year FROM value),
       to_char(value AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS'),
       isfinite(value) AND extract(year FROM value) BETWEEN 1 AND 9999 AS python_year_domain
FROM (VALUES
 ('positive-infinity','infinity'::timestamptz),
 ('negative-infinity','-infinity'::timestamptz),
 ('year-10000','10000-01-01 00:00:00+00'::timestamptz),
 ('year-bc','0001-01-01 00:00:00+00 BC'::timestamptz),
 ('first-python-year','0001-01-01 00:00:00+00'::timestamptz),
 ('last-python-year','9999-12-31 23:59:59.999999+00'::timestamptz)
) examples(label,value) ORDER BY label;
COMMIT;
