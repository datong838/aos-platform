#include "postgres.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "commands/dbcommands.h"
#include "parser/parse_func.h"
#include "catalog/pg_type_d.h"
#include "utils/builtins.h"
#include "utils/fmgrprotos.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(probe_fmgr_calibration);
static bool active=false;
static unsigned int events=0;
static bool needs(Oid oid) { return active && OidIsValid(oid); }
static void observe(FmgrHookEventType event,FmgrInfo *info,Datum *private)
{
    if (!active) return;
    events++;
    ereport(NOTICE,(errmsg("TEST_FMGR_EVENT %u %u",info->fn_oid,(unsigned int)event)));
}
Datum probe_fmgr_calibration(PG_FUNCTION_ARGS)
{
    bool forced=PG_GETARG_BOOL(0);
    FmgrInfo positive, builtin, aborter;
    Oid textarg=TEXTOID,positive_oid,builtin_oid;
    volatile int p=0,b=0,d=0;
    unsigned int before,after;
    if (!superuser() || strcmp(GetUserNameFromId(GetUserId(),false),"aos_app")!=0 || strcmp(get_database_name(MyDatabaseId),"aos_test_9da5ae38343d_ti4_test")!=0)
        ereport(ERROR,(errmsg("TEST_FMGR_IDENTITY_REQUIRED")));
    if (active || fmgr_hook || needs_fmgr_hook)
        ereport(ERROR,(errmsg("TEST_FMGR_EXISTING_HOOK_REJECTED")));
    active=true;events=0;fmgr_hook=observe;needs_fmgr_hook=needs;
    PG_TRY();
    {
        positive_oid=LookupFuncName(list_make2(makeString("pg_temp"),makeString("fmgr_positive")),1,&textarg,false);
        builtin_oid=LookupFuncName(list_make2(makeString("pg_catalog"),makeString("length")),1,&textarg,false);
        fmgr_info(positive_oid,&positive);
        p=DatumGetInt32(FunctionCall1(&positive,CStringGetTextDatum("calibrat")));
        before=events;
        fmgr_info(builtin_oid,&builtin);
        b=DatumGetInt32(FunctionCall1(&builtin,CStringGetTextDatum("calibrat")));
        after=events;
        d=DatumGetInt32(DirectFunctionCall1(textlen,CStringGetTextDatum("calibrat")));
        ereport(NOTICE,(errmsg("TEST_FMGR_COVERAGE %u %d %u %d %u %u %u %d",positive_oid,p,builtin_oid,b,before,after,events,d)));
        if (forced)
        {
            Oid abort_oid=LookupFuncName(list_make2(makeString("pg_temp"),makeString("fmgr_abort")),0,NULL,false);
            fmgr_info(abort_oid,&aborter);
            (void)FunctionCall0(&aborter);
            ereport(ERROR,(errmsg("TEST_FMGR_ABORT_FUNCTION_RETURNED")));
        }
    }
    PG_CATCH();
    {
        fmgr_hook=NULL;needs_fmgr_hook=NULL;active=false;
        PG_RE_THROW();
    }
    PG_END_TRY();
    fmgr_hook=NULL;needs_fmgr_hook=NULL;active=false;
    if (p!=8 || b!=8 || d!=8)
        ereport(ERROR,(errmsg("TEST_FMGR_FIXED_RESULT_REQUIRED")));
    PG_RETURN_BOOL(true);
}
