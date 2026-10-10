#include "postgres.h"
#include "fmgr.h"
#include "commands/trigger.h"
#include "utils/lsyscache.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_test_pending_on_relation);
Datum aos_test_pending_on_relation(PG_FUNCTION_ARGS)
{
    Oid relation = PG_GETARG_OID(0);
    if (!OidIsValid(relation) || get_rel_relkind(relation) == 0)
        ereport(ERROR, (errcode(ERRCODE_UNDEFINED_TABLE), errmsg("TEST_PENDING_RELATION_REQUIRED")));
    PG_RETURN_BOOL(AfterTriggerPendingOnRel(relation));
}
