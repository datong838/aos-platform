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

/* Public Linux loader observation only; paths are not package authority. */
#ifdef __linux__
#include <link.h>
#include <limits.h>
#include <stdlib.h>
#include "utils/builtins.h"
#include "mb/pg_wchar.h"
#define AOS_MODULE_LIMIT 256
#define AOS_MODULE_PATH_LIMIT 4096
struct aos_module_snapshot {
    unsigned count;
    bool invalid;
    char names[AOS_MODULE_LIMIT][AOS_MODULE_PATH_LIMIT];
};
static int collect_module(struct dl_phdr_info *info, size_t size, void *data)
{
    struct aos_module_snapshot *snapshot = data;
    const char *name;
    size_t length;
    /* No PostgreSQL ERROR/allocation while the loader holds its locks. */
    if (size < offsetof(struct dl_phdr_info, dlpi_name) + sizeof(info->dlpi_name) ||
        info->dlpi_name == NULL || snapshot->count >= AOS_MODULE_LIMIT) {
        snapshot->invalid = true;
        return 1;
    }
    name = info->dlpi_name;
    length = strnlen(name, AOS_MODULE_PATH_LIMIT);
    if (length >= AOS_MODULE_PATH_LIMIT) {
        snapshot->invalid = true;
        return 1;
    }
    memcpy(snapshot->names[snapshot->count++], name, length + 1);
    return 0;
}
static int compare_module_names(const void *left, const void *right)
{
    return strcmp((const char *) left, (const char *) right);
}
#endif
PG_FUNCTION_INFO_V1(aos_admission_loaded_module_paths);
Datum aos_admission_loaded_module_paths(PG_FUNCTION_ARGS)
{
    if (GetUserId() != get_role_oid("aos_physical_capacity_occupation_owner", false))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("SHARED_ADMISSION_NATIVE_OWNER_REQUIRED")));
#ifdef __linux__
    {
        struct aos_module_snapshot *snapshot = palloc0(sizeof(*snapshot));
        Datum *paths;
        ArrayType *result;
        unsigned i;
        int status = dl_iterate_phdr(collect_module, snapshot);
        if (status != 0 || snapshot->invalid || snapshot->count == 0)
            ereport(ERROR, (errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED), errmsg("SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_REQUIRED")));
        for (i = 0; i < snapshot->count; i++) {
            char resolved[PATH_MAX];
            char *name = snapshot->names[i];
            const char *input = name[0] ? name : "/proc/self/exe";
            if (strcmp(input, "linux-vdso.so.1") == 0) {
                strlcpy(name, "virtual:linux-vdso.so.1", AOS_MODULE_PATH_LIMIT);
                continue;
            }
            if (input[0] != '/' || realpath(input, resolved) == NULL ||
                strlen(resolved) >= AOS_MODULE_PATH_LIMIT)
                ereport(ERROR, (errcode(ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE), errmsg("SHARED_ADMISSION_NATIVE_MODULE_PATH_REQUIRED")));
            pg_verify_mbstr(GetDatabaseEncoding(), resolved, strlen(resolved), false);
            strlcpy(name, resolved, AOS_MODULE_PATH_LIMIT);
        }
        qsort(snapshot->names, snapshot->count, AOS_MODULE_PATH_LIMIT, compare_module_names);
        paths = palloc(sizeof(Datum) * snapshot->count);
        for (i = 0; i < snapshot->count; i++) {
            if (i > 0 && strcmp(snapshot->names[i - 1], snapshot->names[i]) == 0)
                ereport(ERROR, (errcode(ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE), errmsg("SHARED_ADMISSION_NATIVE_MODULE_ALIAS_REQUIRED")));
            paths[i] = CStringGetTextDatum(snapshot->names[i]);
        }
        result = construct_array(paths, (int) snapshot->count, TEXTOID, -1, false, 'i');
        pfree(paths);
        pfree(snapshot);
        PG_RETURN_ARRAYTYPE_P(result);
    }
#else
    ereport(ERROR, (errcode(ERRCODE_FEATURE_NOT_SUPPORTED), errmsg("SHARED_ADMISSION_NATIVE_LINUX_REQUIRED")));
    PG_RETURN_NULL();
#endif
}
