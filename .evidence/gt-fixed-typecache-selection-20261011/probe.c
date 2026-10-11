#include "postgres.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "commands/dbcommands.h"
#include "utils/builtins.h"
#include "utils/typcache.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(probe_fixed_typecache);
static const Oid fixed_types[] = {16,17,18,19,20,21,22,23,25,26,28,30,114,194,701,705,1002,1003,1005,1007,1009,1028,1033,1034,1114,1184,1186,1700,2202,2205,2249,2278,2950,3802,3807,4096,5069,5791110,5801985,5802013,5802059,5802109,5802771,5802980};
Datum probe_fixed_typecache(PG_FUNCTION_ARGS)
{
    bool forced = PG_GETARG_BOOL(0);
    int i;
    if (!superuser() || strcmp(GetUserNameFromId(GetUserId(),false),"aos_app") != 0 || strcmp(get_database_name(MyDatabaseId),"aos_test_9da5ae38343d_ti4_test") != 0)
        ereport(ERROR,(errmsg("TEST_TYPECACHE_IDENTITY_REQUIRED")));
    for (i=0;i<(int)(sizeof(fixed_types)/sizeof(fixed_types[0]));i++)
    {
        TypeCacheEntry *entry = lookup_type_cache(fixed_types[i], TYPECACHE_BTREE_OPFAMILY | TYPECACHE_HASH_OPFAMILY | TYPECACHE_EQ_OPR | TYPECACHE_LT_OPR | TYPECACHE_GT_OPR | TYPECACHE_CMP_PROC | TYPECACHE_HASH_PROC | TYPECACHE_HASH_EXTENDED_PROC);
        ereport(NOTICE,(errmsg("TEST_FIXED_TYPECACHE %u %u %u %u %u %u %u %u %u %u %u",fixed_types[i],entry->btree_opf,entry->btree_opintype,entry->hash_opf,entry->hash_opintype,entry->eq_opr,entry->lt_opr,entry->gt_opr,entry->cmp_proc,entry->hash_proc,entry->hash_extended_proc)));
    }
    if (forced) ereport(ERROR,(errmsg("TEST_TYPECACHE_FORCED_ERROR")));
    PG_RETURN_BOOL(true);
}
