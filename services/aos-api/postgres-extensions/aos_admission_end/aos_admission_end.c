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

/* Disk observations are deliberately not evidence of mapped-image provenance. */
#include "common/cryptohash.h"
#include "common/sha2.h"
#include "storage/fd.h"
#include "utils/builtins.h"
#include "utils/json.h"
#include <sys/stat.h>
#ifdef __linux__
static bool same_file_stat(const struct stat *a, const struct stat *b)
{
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
        a->st_mode == b->st_mode && a->st_size == b->st_size &&
        a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
        a->st_ctim.tv_sec == b->st_ctim.tv_sec && a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}
static void append_file_fact(StringInfo output, const char *path)
{
    FILE *volatile stream = NULL;
    pg_cryptohash_ctx *volatile hash = NULL;
    struct stat before, after, named;
    uint8 digest[PG_SHA256_DIGEST_LENGTH];
    char hex[PG_SHA256_DIGEST_LENGTH * 2 + 1];
    char buffer[65536];
    volatile uint64 total = 0;
    unsigned i;
    appendStringInfoString(output, "{\"path\":");
    escape_json(output, path);
    if (strcmp(path, "virtual:linux-vdso.so.1") == 0) {
        appendStringInfoString(output, ",\"virtual\":true,\"sha256\":null}");
        return;
    }
    PG_TRY();
    {
        size_t n;
        stream = AllocateFile(path, "rb");
        if (stream == NULL || fstat(fileno(stream), &before) != 0 ||
            !S_ISREG(before.st_mode) || before.st_size < 0 || before.st_size > 256 * 1024 * 1024)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_FILE_REQUIRED");
        hash = pg_cryptohash_create(PG_SHA256);
        if (hash == NULL || pg_cryptohash_init(hash) < 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
        while ((n = fread(buffer, 1, sizeof(buffer), stream)) > 0) {
            CHECK_FOR_INTERRUPTS();
            total += n;
            if (total > 256 * 1024 * 1024 || pg_cryptohash_update(hash, (uint8 *) buffer, n) < 0)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
        }
        if (ferror(stream) || fstat(fileno(stream), &after) != 0 || stat(path, &named) != 0 ||
            total != (uint64) before.st_size || !same_file_stat(&before, &after) ||
            !same_file_stat(&before, &named))
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_FILE_CHANGED");
        if (pg_cryptohash_final(hash, digest, sizeof(digest)) < 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
        pg_cryptohash_free(hash);
        hash = NULL;
        if (FreeFile(stream) != 0) {
            stream = NULL;
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_FILE_REQUIRED");
        }
        stream = NULL;
    }
    PG_CATCH();
    {
        if (hash != NULL)
            pg_cryptohash_free(hash);
        if (stream != NULL)
            FreeFile(stream);
        PG_RE_THROW();
    }
    PG_END_TRY();
    for (i = 0; i < sizeof(digest); i++)
        snprintf(hex + i * 2, 3, "%02x", digest[i]);
    appendStringInfo(output, ",\"virtual\":false,\"sha256\":\"%s\",\"bytes\":%llu,\"device\":\"%llu\",\"inode\":\"%llu\"}",
        hex, (unsigned long long) total, (unsigned long long) before.st_dev, (unsigned long long) before.st_ino);
}
#endif

/* Public Linux loader observation only; paths are not package authority. */
#ifdef __linux__
#include <link.h>
#include <limits.h>
#include <stdlib.h>
#include <stdint.h>
#include <sys/auxv.h>
#include "utils/builtins.h"
#include "mb/pg_wchar.h"
#define AOS_MODULE_LIMIT 256
#define AOS_MODULE_PATH_LIMIT 4096
struct aos_module_snapshot {
    unsigned count;
    bool invalid;
    uintptr_t addresses[AOS_MODULE_LIMIT];
    uintptr_t headers[AOS_MODULE_LIMIT];
    char names[AOS_MODULE_LIMIT][AOS_MODULE_PATH_LIMIT];
};
static int collect_module(struct dl_phdr_info *info, size_t size, void *data)
{
    struct aos_module_snapshot *snapshot = data;
    const char *name;
    size_t length;
    /* No PostgreSQL ERROR/allocation while the loader holds its locks. */
    if (size < offsetof(struct dl_phdr_info, dlpi_phnum) + sizeof(info->dlpi_phnum) ||
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
    snapshot->addresses[snapshot->count] = (uintptr_t) info->dlpi_addr;
    snapshot->headers[snapshot->count] = (uintptr_t) info->dlpi_phdr;
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
        uintptr_t vdso = (uintptr_t) getauxval(AT_SYSINFO_EHDR);
        uintptr_t main_headers = (uintptr_t) getauxval(AT_PHDR);
        int status = dl_iterate_phdr(collect_module, snapshot);
        if (status != 0 || snapshot->invalid || snapshot->count == 0)
            ereport(ERROR, (errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED), errmsg("SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_REQUIRED")));
        for (i = 0; i < snapshot->count; i++) {
            char resolved[PATH_MAX];
            char *name = snapshot->names[i];
            const char *input = name;
            /* musl may expose the vDSO with an empty loader name. */
            if (vdso != 0 && snapshot->addresses[i] == vdso) {
                strlcpy(name, "virtual:linux-vdso.so.1", AOS_MODULE_PATH_LIMIT);
                continue;
            }
            if (!name[0]) {
                if (main_headers == 0 || snapshot->headers[i] != main_headers)
                    ereport(ERROR, (errcode(ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE), errmsg("SHARED_ADMISSION_NATIVE_UNNAMED_MODULE_REQUIRED")));
                input = "/proc/self/exe";
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

PG_FUNCTION_INFO_V1(aos_admission_loaded_module_file_facts);
Datum aos_admission_loaded_module_file_facts(PG_FUNCTION_ARGS)
{
    if (GetUserId() != get_role_oid("aos_physical_capacity_occupation_owner", false))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("SHARED_ADMISSION_NATIVE_OWNER_REQUIRED")));
#ifdef __linux__
    {
        ArrayType *first = DatumGetArrayTypeP(aos_admission_loaded_module_paths(fcinfo));
        ArrayType *last;
        Datum *paths, *check;
        bool *nulls, *check_nulls;
        int count, check_count, i;
        StringInfoData output;
        deconstruct_array(first, TEXTOID, -1, false, 'i', &paths, &nulls, &count);
        initStringInfo(&output);
        appendStringInfoString(&output, "{\"schemaVersion\":\"aos.native-module-file-observation/v1\",\"mappedImageProvenance\":false,\"executionAllowed\":false,\"files\":[");
        for (i = 0; i < count; i++) {
            CHECK_FOR_INTERRUPTS();
            if (nulls[i])
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_REQUIRED");
            if (i)
                appendStringInfoChar(&output, ',');
            append_file_fact(&output, TextDatumGetCString(paths[i]));
        }
        last = DatumGetArrayTypeP(aos_admission_loaded_module_paths(fcinfo));
        deconstruct_array(last, TEXTOID, -1, false, 'i', &check, &check_nulls, &check_count);
        if (count != check_count)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_CHANGED");
        for (i = 0; i < count; i++)
            if (check_nulls[i] || strcmp(TextDatumGetCString(paths[i]), TextDatumGetCString(check[i])) != 0)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_CHANGED");
        appendStringInfoString(&output, "]}");
        PG_RETURN_DATUM(DirectFunctionCall1(jsonb_in, CStringGetDatum(output.data)));
    }
#else
    ereport(ERROR, (errcode(ERRCODE_FEATURE_NOT_SUPPORTED), errmsg("SHARED_ADMISSION_NATIVE_LINUX_REQUIRED")));
    PG_RETURN_NULL();
#endif
}
