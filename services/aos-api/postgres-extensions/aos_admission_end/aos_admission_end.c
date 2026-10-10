/* Local event observation only; this routine never authorizes admission. */
#include "postgres.h"
#include "fmgr.h"
#include "catalog/pg_type_d.h"
#include "commands/trigger.h"
#include "executor/spi.h"
#include "miscadmin.h"
#include "utils/acl.h"
#include "utils/array.h"
#include "utils/memutils.h"
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(aos_admission_pending_relations);
Datum aos_admission_pending_relations(PG_FUNCTION_ARGS)
{
    MemoryContext caller_context = CurrentMemoryContext;
    MemoryContext spi_context;
    Datum *pending;
    ArrayType *result;
    uint64 count = 0;
    uint64 i;
    if (GetUserId() != get_role_oid("aos_physical_capacity_occupation_owner", false))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("SHARED_ADMISSION_NATIVE_OWNER_REQUIRED")));
    if (SPI_connect() != SPI_OK_CONNECT)
        elog(ERROR, "SHARED_ADMISSION_NATIVE_CATALOG_REQUIRED");
    if (SPI_execute("SELECT oid FROM pg_catalog.pg_class ORDER BY oid", true, 0) != SPI_OK_SELECT)
        elog(ERROR, "SHARED_ADMISSION_NATIVE_CATALOG_REQUIRED");
    if (SPI_processed > MaxAllocSize / sizeof(Datum))
        ereport(ERROR, (errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED), errmsg("SHARED_ADMISSION_NATIVE_CATALOG_LIMIT")));
    spi_context = MemoryContextSwitchTo(caller_context);
    pending = palloc(sizeof(Datum) * Max(SPI_processed, 1));
    for (i = 0; i < SPI_processed; i++) {
        bool is_null;
        Datum relation = SPI_getbinval(SPI_tuptable->vals[i], SPI_tuptable->tupdesc, 1, &is_null);
        if (is_null)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_RELATION_REQUIRED");
        if (AfterTriggerPendingOnRel(DatumGetObjectId(relation)))
            pending[count++] = relation;
    }
    result = count ? construct_array(pending, (int) count, OIDOID, sizeof(Oid), true, 'i')
                   : construct_empty_array(OIDOID);
    pfree(pending);
    MemoryContextSwitchTo(spi_context);
    SPI_finish();
    PG_RETURN_ARRAYTYPE_P(result);
}
