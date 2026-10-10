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
PG_FUNCTION_INFO_V1(probe_final_epoch);
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

Datum
probe_final_epoch(PG_FUNCTION_ARGS)
{
    char *id;
    Oid types[1] = {TEXTOID};
    Datum values[1];
    bool isnull;
    int64 result = 0;
    const char *sql;
    const char *org = GetConfigOption("aos.org_id", true, false);
    const char *project = GetConfigOption("aos.project_id", true, false);
    char *database = get_database_name(MyDatabaseId);
    if (PG_ARGISNULL(0) || PG_ARGISNULL(1) || fenced ||
        strcmp(GetUserNameFromId(GetUserId(), false), "aos_app") != 0 ||
        strcmp(GetUserNameFromId(GetSessionUserId(), false), "aos_app") != 0 ||
        database == NULL || strncmp(database, "aos_test_", 9) != 0 ||
        strlen(database) < 9 || strcmp(database + strlen(database) - 9, "_ti4_test") != 0 ||
        org == NULL || project == NULL || strcmp(org, "org-org") != 0 ||
        strcmp(project, "dev-project") != 0 ||
        !superuser())
        ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_ADMIN_REQUIRED")));
    id = text_to_cstring(PG_GETARG_TEXT_PP(0));
    if (strlen(id) > 100 || strncmp(id, "final-fence-", 12) != 0)
        ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_ID_REQUIRED")));
    values[0] = PG_GETARG_DATUM(0);
    switch (PG_GETARG_INT32(1))
    {
        case 0: sql = "SELECT public.aos_capacity_evidence_epoch_lock('org-org','dev-project',$1)"; break;
        case 1: sql = "WITH changed AS (INSERT INTO public.aip_capacity_evidence_epoch(org_id,project_id,bundle_id) VALUES('org-org','dev-project',$1) RETURNING epoch) SELECT epoch FROM changed"; break;
        case 2: sql = "SET LOCAL application_name='final_fence_utility_changed'"; break;
        case 3: sql = "CREATE TEMP TABLE final_fence_utility_probe(i integer)"; break;
        case 4: sql = "SELECT nextval('pg_temp.final_fence_sequence_probe')"; break;
        case 5: sql = "SELECT length(set_config('application_name','final_fence_select_changed',true))::bigint"; break;
        default: ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_MODE_REQUIRED"))); sql = NULL;
    }
    if (SPI_connect() != SPI_OK_CONNECT)
        ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_SPI_REQUIRED")));
    prior_hook = ExecutorStart_hook;
    prior_utility = ProcessUtility_hook;
    ExecutorStart_hook = guard_start;
    ProcessUtility_hook = guard_utility;
    fenced = true;
    PG_TRY();
    {
        if (SPI_execute_with_args(sql, 1, types, values, NULL, false, 0) != SPI_OK_SELECT || SPI_processed != 1)
            ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_RESULT_REQUIRED")));
        result = DatumGetInt64(SPI_getbinval(SPI_tuptable->vals[0], SPI_tuptable->tupdesc, 1, &isnull));
        if (isnull)
            ereport(ERROR, (errmsg("TEST_ONLY_FINAL_FENCE_NULL_RESULT")));
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
    PG_RETURN_INT64(result);
}
