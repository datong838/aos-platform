/* Isolated test-only clock window; no production admission authority. */
#include "postgres.h"
#include "fmgr.h"
#include "access/xact.h"
#include "miscadmin.h"
#include "utils/timestamp.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_test_clock_arm);
static bool armed = false;
static bool registered = false;
static int mode;
static TimestampTz deadline;
static void clock_guard(XactEvent event, void *arg)
{
    TimestampTz now;
    if (!armed) return;
    if (event == XACT_EVENT_PRE_PREPARE || event == XACT_EVENT_PARALLEL_PRE_COMMIT)
        elog(ERROR, "TEST_CLOCK_TOP_COMMIT_REQUIRED");
    if (event == XACT_EVENT_PRE_COMMIT) {
        now = GetCurrentTimestamp();
        elog(NOTICE, "TEST_CLOCK_CHECK:%lld:%lld", (long long) now, (long long) deadline);
        if (now >= deadline) elog(ERROR, "TEST_CLOCK_EXPIRED");
    }
    if (event == XACT_EVENT_ABORT || event == XACT_EVENT_COMMIT) {
        if (event == XACT_EVENT_COMMIT)
            elog(NOTICE, "TEST_CLOCK_COMMITTED:%lld", (long long) GetCurrentTimestamp());
        armed = false;
    }
}
static void clock_delay(XactEvent event, void *arg)
{
    if (armed && event == XACT_EVENT_PRE_COMMIT && mode == 2) {
        pg_usleep(600000L);
        elog(NOTICE, "TEST_CLOCK_DELAY_DONE:%lld", (long long) GetCurrentTimestamp());
    }
}
Datum aos_test_clock_arm(PG_FUNCTION_ARGS)
{
    if (!superuser() || registered || armed || IsSubTransaction() || IsInParallelMode())
        elog(ERROR, "TEST_CLOCK_FRESH_SUPERUSER_TOP_REQUIRED");
    mode = PG_GETARG_INT32(0);
    if (mode < 0 || mode > 2) elog(ERROR, "TEST_CLOCK_FIXED_CASE_REQUIRED");
    deadline = GetCurrentTimestamp() + (mode == 0 ? -1 : mode == 1 ? 5000000 : 200000);
    /* Registration prepends: guard then delay executes in that order. */
    RegisterXactCallback(clock_delay, NULL);
    RegisterXactCallback(clock_guard, NULL);
    registered = true;
    armed = true;
    PG_RETURN_VOID();
}
