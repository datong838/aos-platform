/* Test-only fixed owned INSERT after deferred drain, never production authority. */
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
PG_FUNCTION_INFO_V1(aos_test_postdrain_arm);
static bool registered = false;
static bool armed = false;
static bool reject_pending;
static Oid relation_oid;
static char *insert_sql = NULL;
static void callback(XactEvent event, void *unused)
{
    if (!armed) return;
    if (event == XACT_EVENT_PRE_PREPARE || event == XACT_EVENT_PARALLEL_PRE_COMMIT)
        ereport(ERROR, (errcode(ERRCODE_CHECK_VIOLATION), errmsg("TEST_CALLBACK_END_CHANNEL_REQUIRED")));
    if (event == XACT_EVENT_PRE_COMMIT) {
        int status;
        PushActiveSnapshot(GetTransactionSnapshot());
        if (SPI_connect() != SPI_OK_CONNECT)
            elog(ERROR, "TEST_CALLBACK_SPI_CONNECT_REQUIRED");
        status = SPI_execute(insert_sql, false, 0);
        if (status != SPI_OK_INSERT || SPI_processed != 1)
            elog(ERROR, "TEST_CALLBACK_SINGLE_OWNED_INSERT_REQUIRED");
        SPI_finish();
        PopActiveSnapshot();
        if (!AfterTriggerPendingOnRel(relation_oid))
            elog(ERROR, "TEST_CALLBACK_EXPECTED_NEW_DEFERRED_EVENT_REQUIRED");
        if (reject_pending)
            ereport(ERROR, (errcode(ERRCODE_CHECK_VIOLATION), errmsg("TEST_CALLBACK_NEW_PENDING_EVENT_REJECTED")));
    }
    if (event == XACT_EVENT_ABORT || event == XACT_EVENT_COMMIT) {
        armed = false;
        insert_sql = NULL;
        relation_oid = InvalidOid;
    }
}
Datum aos_test_postdrain_arm(PG_FUNCTION_ARGS)
{
    Relation rel;
    char *namespace_name;
    MemoryContext old;
    Oid oid = PG_GETARG_OID(0);
    if (!superuser() || armed || IsSubTransaction() || IsInParallelMode())
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("TEST_CALLBACK_TOP_OWNED_ARM_REQUIRED")));
    rel = table_open(oid, AccessShareLock);
    namespace_name = get_namespace_name(RelationGetNamespace(rel));
    if (rel->rd_rel->relowner != GetUserId() || rel->rd_rel->relkind != RELKIND_RELATION ||
        namespace_name == NULL || strncmp(namespace_name, "test_owned_callback_", 20) != 0)
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("TEST_CALLBACK_PRIVATE_RELATION_REQUIRED")));
    old = MemoryContextSwitchTo(TopTransactionContext);
    insert_sql = psprintf("INSERT INTO %s(id) VALUES(1)",
                         quote_qualified_identifier(namespace_name, RelationGetRelationName(rel)));
    MemoryContextSwitchTo(old);
    table_close(rel, NoLock);
    if (!registered) { RegisterXactCallback(callback, NULL); registered = true; }
    relation_oid = oid;
    reject_pending = PG_GETARG_BOOL(1);
    armed = true;
    PG_RETURN_VOID();
}
