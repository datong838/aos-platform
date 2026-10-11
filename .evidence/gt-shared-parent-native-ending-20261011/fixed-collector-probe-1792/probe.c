#include "postgres.h"
#include "fmgr.h"
#include "executor/executor.h"
#include "executor/spi.h"
#include "miscadmin.h"
#include "utils/builtins.h"
#include "utils/lsyscache.h"
#include "utils/guc.h"
#include "commands/dbcommands.h"
#include "tcop/utility.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(probe_fixed_collector);
static ExecutorStart_hook_type prior_hook;
static ProcessUtility_hook_type prior_utility;
static bool fenced;

static void
guard_start(QueryDesc *desc, int flags)
{
    if (fenced && (desc->plannedstmt == NULL ||
        desc->plannedstmt->commandType != CMD_SELECT ||
        desc->plannedstmt->hasModifyingCTE))
        ereport(ERROR, (errcode(ERRCODE_READ_ONLY_SQL_TRANSACTION),
                       errmsg("FINAL_VALIDATION_NESTED_WRITE_FORBIDDEN")));
    if (prior_hook != NULL)
        prior_hook(desc, flags);
    else
        standard_ExecutorStart(desc, flags);
}

static void
guard_utility(PlannedStmt *stmt, const char *query, bool read_only_tree,
              ProcessUtilityContext context, ParamListInfo params,
              QueryEnvironment *environment, DestReceiver *dest,
              QueryCompletion *completion)
{
    if (fenced)
        ereport(ERROR, (errcode(ERRCODE_READ_ONLY_SQL_TRANSACTION),
                       errmsg("FINAL_VALIDATION_UTILITY_FORBIDDEN")));
    if (prior_utility != NULL)
        prior_utility(stmt, query, read_only_tree, context, params, environment, dest, completion);
    else
        standard_ProcessUtility(stmt, query, read_only_tree, context, params, environment, dest, completion);
}


#include "access/xact.h"
#include "catalog/pg_type_d.h"
#include "utils/jsonb.h"
#include "utils/xid8.h"

Datum
probe_fixed_collector(PG_FUNCTION_ARGS)
{
    Oid types[4] = {UUIDOID, TEXTOID, XID8OID, INT4OID};
    Datum values[4];
    bool isnull;
    Datum value;
    Jsonb *source;
    Jsonb *result;
    char *hash;
    char *database = get_database_name(MyDatabaseId);
    int i;
    if (fenced || PG_NARGS() != 4 || PG_ARGISNULL(0) || PG_ARGISNULL(1) ||
        PG_ARGISNULL(2) || PG_ARGISNULL(3) ||
        strcmp(GetUserNameFromId(GetUserId(), false), "aos_physical_capacity_occupation_owner") != 0 ||
        strcmp(GetUserNameFromId(GetSessionUserId(), false), "aos_provider_capacity_occupation") != 0 ||
        strcmp(GetConfigOption("role", false, false), "aos_runtime") != 0 ||
        database == NULL || strncmp(database, "aos_test_", 9) != 0 ||
        strlen(database) < 18 || strcmp(database + strlen(database) - 9, "_ti4_test") != 0)
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_IDENTITY_REQUIRED")));
    if (strcmp(GetConfigOption("aos.org_id", false, false), "org-org") != 0 ||
        strcmp(GetConfigOption("aos.project_id", false, false), "dev-project") != 0 ||
        strcmp(GetConfigOption("transaction_isolation", false, false), "serializable") != 0 ||
        strcmp(GetConfigOption("transaction_read_only", false, false), "off") != 0 ||
        strcmp(GetConfigOption("session_replication_role", false, false), "origin") != 0 ||
        strcmp(GetConfigOption("TimeZone", false, false), "UTC") != 0 ||
        PG_GETARG_INT32(3) != MyProcPid ||
        U64FromFullTransactionId(PG_GETARG_FULLTRANSACTIONID(2)) != U64FromFullTransactionId(GetTopFullTransactionId()))
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_CONTEXT_REQUIRED")));
    hash = text_to_cstring(PG_GETARG_TEXT_PP(1));
    if (strlen(hash) != 71 || strncmp(hash, "sha256:", 7) != 0 ||
        strspn(hash + 7, "0123456789abcdef") != 64 ||
        ExecutorStart_hook != NULL || ProcessUtility_hook != NULL)
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_HASH_OR_HOOK_DRIFT")));
    for (i = 0; i < 4; i++) values[i] = PG_GETARG_DATUM(i);
    if (SPI_connect() != SPI_OK_CONNECT)
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_SPI_REQUIRED")));
    prior_hook = ExecutorStart_hook;
    prior_utility = ProcessUtility_hook;
    ExecutorStart_hook = guard_start;
    ProcessUtility_hook = guard_utility;
    fenced = true;
    PG_TRY();
    {
        if (SPI_execute_with_args("SELECT public.read_shared_parent_complete_end_facts($1,$2,$3,$4)",
                                  4, types, values, NULL, false, 1) != SPI_OK_SELECT || SPI_processed != 1)
            ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_RESULT_REQUIRED")));
        value = SPI_getbinval(SPI_tuptable->vals[0], SPI_tuptable->tupdesc, 1, &isnull);
        if (isnull) ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_NULL_RESULT")));
        source = DatumGetJsonbP(value);
        result = SPI_palloc(VARSIZE(source));
        memcpy(result, source, VARSIZE(source));
    }
    PG_CATCH();
    {
        fenced = false;
        ExecutorStart_hook = prior_hook;
        ProcessUtility_hook = prior_utility;
        prior_hook = NULL;
        prior_utility = NULL;
        PG_RE_THROW();
    }
    PG_END_TRY();
    fenced = false;
    ExecutorStart_hook = prior_hook;
    ProcessUtility_hook = prior_utility;
    prior_hook = NULL;
    prior_utility = NULL;
    SPI_finish();
    PG_RETURN_JSONB_P(result);
}
