/* Test-only candidate rejection experiment. No Source or permission input. */
#include "postgres.h"
#include "fmgr.h"
#include "access/xact.h"
#include "utils/timestamp.h"
#include "miscadmin.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_precommit_probe_arm);
static TimestampTz deadline;
static bool armed = false;
static void check_callback(XactEvent event, void *arg)
{
    if (armed && event == XACT_EVENT_PRE_COMMIT && GetCurrentTimestamp() >= deadline)
        ereport(ERROR, (errcode(ERRCODE_CHECK_VIOLATION), errmsg("AOS_TEST_PRECOMMIT_DEADLINE_EXPIRED")));
    if (event == XACT_EVENT_COMMIT || event == XACT_EVENT_ABORT)
        armed = false;
}
static void wait_callback(XactEvent event, void *arg)
{
    if (armed && event == XACT_EVENT_PRE_COMMIT)
        pg_usleep(900000L);
}
Datum aos_precommit_probe_arm(PG_FUNCTION_ARGS)
{
    bool check_first = PG_GETARG_BOOL(1);
    if (!superuser() || armed)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("AOS_TEST_OWNED_SINGLE_ARM_REQUIRED")));
    deadline = PG_GETARG_TIMESTAMPTZ(0);
    UnregisterXactCallback(check_callback, NULL);
    UnregisterXactCallback(wait_callback, NULL);
    if (check_first) {
        RegisterXactCallback(wait_callback, NULL);
        RegisterXactCallback(check_callback, NULL);
    } else {
        RegisterXactCallback(check_callback, NULL);
        RegisterXactCallback(wait_callback, NULL);
    }
    armed = true;
    PG_RETURN_VOID();
}
