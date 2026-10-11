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
#include "optimizer/planner.h"
#include "nodes/nodeFuncs.h"
#include "nodes/bitmapset.h"
#include "utils/memutils.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(probe_fixed_collector);
static ExecutorStart_hook_type prior_hook;
static ProcessUtility_hook_type prior_utility;
static bool fenced;
static planner_hook_type prior_planner;
static Bitmapset *observed_functions;
static Bitmapset *observed_tags;
static Bitmapset *unreviewed_tags;

static void observe_oid(Oid oid)
{
    MemoryContext previous;
    if (!OidIsValid(oid) || bms_is_member((int) oid, observed_functions)) return;
    previous = MemoryContextSwitchTo(TopTransactionContext);
    observed_functions = bms_add_member(observed_functions, (int) oid);
    MemoryContextSwitchTo(previous);
    ereport(NOTICE, (errmsg("TEST_FIXED_COLLECTOR_FUNCTION_OID %u", oid)));
}

static bool observe_expression(Node *node, void *context)
{
    if (node == NULL) return false;
    if (IsA(node, Query))
        return query_tree_walker((Query *) node, observe_expression, context, 0);
    if (IsA(node, FuncExpr)) observe_oid(((FuncExpr *) node)->funcid);
    else if (IsA(node, OpExpr)) observe_oid(get_opcode(((OpExpr *) node)->opno));
    else if (IsA(node, DistinctExpr)) observe_oid(get_opcode(((DistinctExpr *) node)->opno));
    else if (IsA(node, NullIfExpr)) observe_oid(get_opcode(((NullIfExpr *) node)->opno));
    else if (IsA(node, ScalarArrayOpExpr)) observe_oid(get_opcode(((ScalarArrayOpExpr *) node)->opno));
    else if (IsA(node, Aggref)) observe_oid(((Aggref *) node)->aggfnoid);
    else if (IsA(node, WindowFunc)) observe_oid(((WindowFunc *) node)->winfnoid);
    else if (IsA(node, CoerceViaIO)) {
        CoerceViaIO *coerce = (CoerceViaIO *) node;
        Oid output, input, parameter;
        bool variable;
        getTypeOutputInfo(exprType((Node *) coerce->arg), &output, &variable);
        getTypeInputInfo(coerce->resulttype, &input, &parameter);
        observe_oid(output); observe_oid(input);
    }
    return expression_tree_walker(node, observe_expression, context);
}

static PlannedStmt *observe_plan(Query *query, const char *text, int options, ParamListInfo params)
{
    if (fenced) observe_expression((Node *) query, NULL);
    return standard_planner(query, text, options, params);
}

static void observe_tag(int tag, bool unreviewed)
{
    Bitmapset **set = unreviewed ? &unreviewed_tags : &observed_tags;
    MemoryContext previous;
    if (bms_is_member(tag, *set)) return;
    previous = MemoryContextSwitchTo(TopTransactionContext);
    *set = bms_add_member(*set, tag);
    MemoryContextSwitchTo(previous);
    ereport(NOTICE, (errmsg("%s %d", unreviewed ? "TEST_FIXED_COLLECTOR_PLAN_EXTRA_UNREVIEWED" : "TEST_FIXED_COLLECTOR_PLAN_TAG", tag)));
}

static bool observe_planstate(PlanState *state, void *context)
{
    Plan *plan = state->plan;
    ListCell *parameter;
    observe_tag((int) nodeTag(plan), false);
    observe_expression((Node *) plan->targetlist, NULL);
    observe_expression((Node *) plan->qual, NULL);
    switch (nodeTag(plan)) {
        case T_Result:
            observe_expression(((Result *) plan)->resconstantqual, NULL); break;
        case T_IndexScan:
            observe_expression((Node *) ((IndexScan *) plan)->indexqual, NULL);
            observe_expression((Node *) ((IndexScan *) plan)->indexqualorig, NULL);
            observe_expression((Node *) ((IndexScan *) plan)->indexorderby, NULL); break;
        case T_IndexOnlyScan:
            observe_expression((Node *) ((IndexOnlyScan *) plan)->indexqual, NULL);
            observe_expression((Node *) ((IndexOnlyScan *) plan)->recheckqual, NULL);
            observe_expression((Node *) ((IndexOnlyScan *) plan)->indexorderby, NULL); break;
        case T_BitmapHeapScan:
            observe_expression((Node *) ((BitmapHeapScan *) plan)->bitmapqualorig, NULL); break;
        case T_FunctionScan:
            observe_expression((Node *) ((FunctionScan *) plan)->functions, NULL); break;
        case T_ValuesScan:
            observe_expression((Node *) ((ValuesScan *) plan)->values_lists, NULL); break;
        case T_NestLoop:
            observe_expression((Node *) ((Join *) plan)->joinqual, NULL);
            foreach(parameter, ((NestLoop *) plan)->nestParams)
                observe_expression((Node *) ((NestLoopParam *) lfirst(parameter))->paramval, NULL);
            break;
        case T_HashJoin:
            observe_expression((Node *) ((Join *) plan)->joinqual, NULL);
            observe_expression((Node *) ((HashJoin *) plan)->hashclauses, NULL); break;
        case T_MergeJoin:
            observe_expression((Node *) ((Join *) plan)->joinqual, NULL);
            observe_expression((Node *) ((MergeJoin *) plan)->mergeclauses, NULL); break;
        case T_Limit:
            observe_expression(((Limit *) plan)->limitOffset, NULL);
            observe_expression(((Limit *) plan)->limitCount, NULL); break;
        default:
            observe_tag((int) nodeTag(plan), true);
    }
    return planstate_tree_walker(state, observe_planstate, context);
}

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
    if (fenced) observe_planstate(desc->planstate, NULL);
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
        ExecutorStart_hook != NULL || ProcessUtility_hook != NULL || planner_hook != NULL)
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_HASH_OR_HOOK_DRIFT")));
    for (i = 0; i < 4; i++) values[i] = PG_GETARG_DATUM(i);
    if (SPI_connect() != SPI_OK_CONNECT)
        ereport(ERROR, (errmsg("TEST_FIXED_COLLECTOR_SPI_REQUIRED")));
    prior_planner = planner_hook;
    observed_functions = NULL;
    observed_tags = NULL;
    unreviewed_tags = NULL;
    planner_hook = observe_plan;
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
        planner_hook = prior_planner;
        prior_planner = NULL;
        ExecutorStart_hook = prior_hook;
        ProcessUtility_hook = prior_utility;
        prior_hook = NULL;
        prior_utility = NULL;
        PG_RE_THROW();
    }
    PG_END_TRY();
    fenced = false;
        planner_hook = prior_planner;
        prior_planner = NULL;
    ExecutorStart_hook = prior_hook;
    ProcessUtility_hook = prior_utility;
    prior_hook = NULL;
    prior_utility = NULL;
    SPI_finish();
    PG_RETURN_JSONB_P(result);
}
