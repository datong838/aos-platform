/* Test-only two-callback order counterexample; no production authority. */
#include "postgres.h"
#include "fmgr.h"
#include "access/xact.h"
#include "access/table.h"
#include "catalog/pg_class.h"
#include "commands/trigger.h"
#include "executor/spi.h"
#include "miscadmin.h"
#include "utils/builtins.h"
#include "utils/lsyscache.h"
#include "utils/memutils.h"
#include "utils/snapmgr.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_test_order_arm);
static bool registered = false;
static bool armed = false;
static Oid sample_oid;
static char *writer_sql;
static char *observer_name;
static void terminal(XactEvent event)
{
    if (event == XACT_EVENT_ABORT || event == XACT_EVENT_COMMIT) {
        armed = false;
        sample_oid = InvalidOid;
        writer_sql = NULL;
        observer_name = NULL;
    }
}
static void guard_channel(XactEvent event)
{
    if (event == XACT_EVENT_PRE_PREPARE || event == XACT_EVENT_PARALLEL_PRE_COMMIT)
        ereport(ERROR, (errcode(ERRCODE_CHECK_VIOLATION), errmsg("TEST_ORDER_END_CHANNEL_REQUIRED")));
}
static void writer(XactEvent event, void *unused)
{
    if (!armed) return;
    guard_channel(event);
    if (event == XACT_EVENT_PRE_COMMIT) {
        PushActiveSnapshot(GetTransactionSnapshot());
        if (SPI_connect() != SPI_OK_CONNECT || SPI_execute(writer_sql, false, 0) != SPI_OK_INSERT || SPI_processed != 1)
            elog(ERROR, "TEST_ORDER_SINGLE_INSERT_REQUIRED");
        SPI_finish();
        PopActiveSnapshot();
        if (!AfterTriggerPendingOnRel(sample_oid))
            elog(ERROR, "TEST_ORDER_EXPECTED_NEW_PENDING_REQUIRED");
    }
    terminal(event);
}
static void observer(XactEvent event, void *unused)
{
    if (!armed) return;
    guard_channel(event);
    if (event == XACT_EVENT_PRE_COMMIT) {
        char *statement;
        bool pending = AfterTriggerPendingOnRel(sample_oid);
        if (pending)
            ereport(ERROR, (errcode(ERRCODE_CHECK_VIOLATION), errmsg("TEST_ORDER_OBSERVER_PENDING_REJECTED")));
        statement = psprintf("INSERT INTO %s(id,pending) VALUES(1,false)", observer_name);
        PushActiveSnapshot(GetTransactionSnapshot());
        if (SPI_connect() != SPI_OK_CONNECT || SPI_execute(statement, false, 0) != SPI_OK_INSERT || SPI_processed != 1)
            elog(ERROR, "TEST_ORDER_SINGLE_OBSERVATION_REQUIRED");
        SPI_finish();
        PopActiveSnapshot();
        pfree(statement);
    }
    terminal(event);
}
static char *owned_name(Oid oid)
{
    Relation rel = table_open(oid, AccessShareLock);
    char *ns = get_namespace_name(RelationGetNamespace(rel));
    char *name;
    if (rel->rd_rel->relowner != GetUserId() || rel->rd_rel->relkind != RELKIND_RELATION ||
        ns == NULL || strncmp(ns, "test_owned_order_", 17) != 0)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("TEST_ORDER_PRIVATE_RELATION_REQUIRED")));
    name = quote_qualified_identifier(ns, RelationGetRelationName(rel));
    table_close(rel, NoLock);
    return name;
}
Datum aos_test_order_arm(PG_FUNCTION_ARGS)
{
    MemoryContext old;
    char *sample_name;
    if (!superuser() || registered || armed || IsSubTransaction() || IsInParallelMode())
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("TEST_ORDER_FRESH_TOP_OWNED_ARM_REQUIRED")));
    old = MemoryContextSwitchTo(TopTransactionContext);
    sample_name = owned_name(PG_GETARG_OID(0));
    observer_name = owned_name(PG_GETARG_OID(1));
    writer_sql = psprintf("INSERT INTO %s(id) VALUES(1)", sample_name);
    MemoryContextSwitchTo(old);
    sample_oid = PG_GETARG_OID(0);
    if (PG_GETARG_BOOL(2)) {
        RegisterXactCallback(writer, NULL);
        RegisterXactCallback(observer, NULL);
    } else {
        RegisterXactCallback(observer, NULL);
        RegisterXactCallback(writer, NULL);
    }
    registered = true;
    armed = true;
    PG_RETURN_VOID();
}
