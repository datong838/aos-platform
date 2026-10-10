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

/* Program-header mapping identity only; this does not verify loaded image bytes. */
#ifdef __linux__
#include <sys/sysmacros.h>
static void append_header_mapping(StringInfo output, const char *path, uintptr_t header)
{
    FILE *volatile file = NULL;
    FILE *volatile maps = NULL;
    PG_TRY();
    {
        struct stat before, after, named;
        unsigned count = 0, matched = 0;
        unsigned long long found_start = 0, found_end = 0, found_offset = 0;
        char line[AOS_MODULE_PATH_LIMIT + 256];
        file = AllocateFile(path, "rb");
        if (file == NULL || fstat(fileno(file), &before) != 0 || !S_ISREG(before.st_mode) || header == 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_REQUIRED");
        maps = AllocateFile("/proc/self/maps", "r");
        if (maps == NULL)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_REQUIRED");
        while (fgets(line, sizeof(line), maps) != NULL) {
            unsigned long long start, end, offset, inode;
            unsigned device_major, device_minor;
            char permissions[5];
            CHECK_FOR_INTERRUPTS();
            if (++count > 8192 || strchr(line, '\n') == NULL ||
                sscanf(line, "%llx-%llx %4s %llx %x:%x %llu", &start, &end, permissions,
                    &offset, &device_major, &device_minor, &inode) != 7 || start >= end)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_REQUIRED");
            if ((unsigned long long) header < start || (unsigned long long) header >= end)
                continue;
            /* Locate the actual loader program header, never any matching pathname. */
            if (++matched != 1 || permissions[0] != 'r' || inode == 0 ||
                inode != (unsigned long long) before.st_ino ||
                device_major != (unsigned) major(before.st_dev) ||
                device_minor != (unsigned) minor(before.st_dev))
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_CHANGED");
            found_start = start;
            found_end = end;
            found_offset = offset;
        }
        if (ferror(maps) || matched != 1 || fstat(fileno(file), &after) != 0 ||
            stat(path, &named) != 0 || !same_file_stat(&before, &after) || !same_file_stat(&before, &named))
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_CHANGED");
        appendStringInfoString(output, "{\"path\":");
        escape_json(output, path);
        appendStringInfo(output, ",\"virtual\":false,\"headerAddress\":\"%llx\",\"mappingStart\":\"%llx\",\"mappingEnd\":\"%llx\",\"fileOffset\":\"%llx\",\"deviceMajor\":\"%u\",\"deviceMinor\":\"%u\",\"inode\":\"%llu\"}",
            (unsigned long long) header, found_start, found_end, found_offset,
            (unsigned) major(before.st_dev), (unsigned) minor(before.st_dev), (unsigned long long) before.st_ino);
        if (FreeFile(maps) != 0) {
            maps = NULL;
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_REQUIRED");
        }
        maps = NULL;
        if (FreeFile(file) != 0) {
            file = NULL;
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_MAPPING_REQUIRED");
        }
        file = NULL;
    }
    PG_CATCH();
    {
        if (maps != NULL)
            FreeFile(maps);
        if (file != NULL)
            FreeFile(file);
        PG_RE_THROW();
    }
    PG_END_TRY();
}
#endif
PG_FUNCTION_INFO_V1(aos_admission_loaded_module_mapping_facts);
Datum aos_admission_loaded_module_mapping_facts(PG_FUNCTION_ARGS)
{
    if (GetUserId() != get_role_oid("aos_physical_capacity_occupation_owner", false))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("SHARED_ADMISSION_NATIVE_OWNER_REQUIRED")));
#ifdef __linux__
    {
        struct aos_module_snapshot *first = palloc0(sizeof(*first));
        struct aos_module_snapshot *last = palloc0(sizeof(*last));
        uintptr_t vdso = (uintptr_t) getauxval(AT_SYSINFO_EHDR);
        uintptr_t main_headers = (uintptr_t) getauxval(AT_PHDR);
        unsigned i;
        StringInfoData output;
        /* Preserve all existing canonical path/alias/unnamed-object checks. */
        (void) aos_admission_loaded_module_paths(fcinfo);
        if (dl_iterate_phdr(collect_module, first) != 0 || first->invalid || first->count == 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_REQUIRED");
        initStringInfo(&output);
        appendStringInfoString(&output, "{\"schemaVersion\":\"aos.native-module-header-mapping/v1\",\"programHeaderMappingIdentity\":true,\"imageBytesVerified\":false,\"executionAllowed\":false,\"files\":[");
        for (i = 0; i < first->count; i++) {
            const char *input = first->names[i];
            char resolved[PATH_MAX];
            CHECK_FOR_INTERRUPTS();
            if (i)
                appendStringInfoChar(&output, ',');
            if (vdso != 0 && first->addresses[i] == vdso) {
                appendStringInfoString(&output, "{\"path\":\"virtual:linux-vdso.so.1\",\"virtual\":true}");
                continue;
            }
            if (!input[0]) {
                if (main_headers == 0 || first->headers[i] != main_headers)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_UNNAMED_MODULE_REQUIRED");
                input = "/proc/self/exe";
            }
            if (input[0] != '/' || realpath(input, resolved) == NULL || strlen(resolved) >= AOS_MODULE_PATH_LIMIT)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_PATH_REQUIRED");
            pg_verify_mbstr(GetDatabaseEncoding(), resolved, strlen(resolved), false);
            append_header_mapping(&output, resolved, first->headers[i]);
        }
        if (dl_iterate_phdr(collect_module, last) != 0 || memcmp(first, last, sizeof(*first)) != 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_CHANGED");
        appendStringInfoString(&output, "]}");
        PG_RETURN_DATUM(DirectFunctionCall1(jsonb_in, CStringGetDatum(output.data)));
    }
#else
    ereport(ERROR, (errcode(ERRCODE_FEATURE_NOT_SUPPORTED), errmsg("SHARED_ADMISSION_NATIVE_LINUX_REQUIRED")));
    PG_RETURN_NULL();
#endif
}

/* Bounded readonly PT_LOAD parity, not trusted package provenance. */
#ifdef __linux__
#include <elf.h>
#include <unistd.h>
#include <limits.h>
struct aos_readonly_snapshot {
    struct aos_module_snapshot modules;
    Elf64_Half counts[AOS_MODULE_LIMIT];
};
static int collect_readonly_module(struct dl_phdr_info *info, size_t size, void *data)
{
    struct aos_readonly_snapshot *snapshot = data;
    unsigned index = snapshot->modules.count;
    int status = collect_module(info, size, &snapshot->modules);
    if (status != 0)
        return status;
    if (info->dlpi_phnum == 0 || info->dlpi_phnum > 256) {
        snapshot->modules.invalid = true;
        return 1;
    }
    snapshot->counts[index] = info->dlpi_phnum;
    return 0;
}
static void exact_pread(int fd, void *buffer, size_t size, uint64 offset)
{
    size_t done = 0;
    if (offset > INT64_MAX || size > (uint64) INT64_MAX - offset)
        elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_RANGE_REQUIRED");
    while (done < size) {
        ssize_t n;
        CHECK_FOR_INTERRUPTS();
        n = pread(fd, (char *) buffer + done, size - done, (off_t) (offset + done));
        if (n <= 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_READ_REQUIRED");
        done += (size_t) n;
    }
}
static void readonly_mapping_range(const struct stat *file, uint64 address, uint64 offset, uint64 size)
{
    FILE *volatile maps = NULL;
    PG_TRY();
    {
        char line[AOS_MODULE_PATH_LIMIT + 256];
        uint64 cursor = address;
        unsigned lines = 0;
        maps = AllocateFile("/proc/self/maps", "r");
        if (maps == NULL || size > UINT64_MAX - address || size > UINT64_MAX - offset)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_RANGE_REQUIRED");
        while (fgets(line, sizeof(line), maps) != NULL) {
            unsigned long long start, end, mapped_offset, inode;
            unsigned device_major, device_minor;
            char permissions[5];
            CHECK_FOR_INTERRUPTS();
            if (++lines > 8192 || strchr(line, '\n') == NULL ||
                sscanf(line, "%llx-%llx %4s %llx %x:%x %llu", &start, &end, permissions,
                    &mapped_offset, &device_major, &device_minor, &inode) != 7 || start >= end)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_MAPPING_REQUIRED");
            if (cursor == address + size || cursor < start || cursor >= end)
                continue;
            if (permissions[0] != 'r' || permissions[1] == 'w' ||
                inode != (unsigned long long) file->st_ino ||
                device_major != (unsigned) major(file->st_dev) || device_minor != (unsigned) minor(file->st_dev) ||
                mapped_offset > UINT64_MAX - (cursor - start) ||
                mapped_offset + cursor - start != offset + cursor - address)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_MAPPING_CHANGED");
            cursor = Min((uint64) end, address + size);
        }
        if (ferror(maps) || cursor != address + size)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_MAPPING_REQUIRED");
        if (FreeFile(maps) != 0) {
            maps = NULL;
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_MAPPING_REQUIRED");
        }
        maps = NULL;
    }
    PG_CATCH();
    {
        if (maps != NULL)
            FreeFile(maps);
        PG_RE_THROW();
    }
    PG_END_TRY();
}
static void append_readonly_image(StringInfo output, const char *path, uintptr_t bias, uintptr_t loader_header, Elf64_Half loader_count)
{
    FILE *volatile file = NULL;
    FILE *volatile memory = NULL;
    pg_cryptohash_ctx *volatile hash = NULL;
    PG_TRY();
    {
        struct stat before, after, named;
        Elf64_Ehdr header;
        Elf64_Phdr ph[256];
        unsigned i, segments = 0, header_matches = 0;
        char disk[65536], loaded[65536];
        file = AllocateFile(path, "rb");
        memory = AllocateFile("/proc/self/mem", "rb");
        if (file == NULL || memory == NULL || fstat(fileno(file), &before) != 0 ||
            !S_ISREG(before.st_mode) || before.st_size < (off_t) sizeof(header) || before.st_size > 256 * 1024 * 1024)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_FILE_REQUIRED");
        exact_pread(fileno(file), &header, sizeof(header), 0);
        if (memcmp(header.e_ident, ELFMAG, SELFMAG) != 0 || header.e_ident[EI_CLASS] != ELFCLASS64 ||
            header.e_ident[EI_DATA] != ELFDATA2LSB || header.e_ident[EI_VERSION] != EV_CURRENT ||
            header.e_version != EV_CURRENT || header.e_machine != EM_AARCH64 ||
            (header.e_type != ET_EXEC && header.e_type != ET_DYN) || header.e_ehsize != sizeof(header) ||
            header.e_phentsize != sizeof(Elf64_Phdr) || header.e_phnum == 0 || header.e_phnum > 256 || header.e_phnum != loader_count ||
            header.e_phoff < sizeof(header) || header.e_phoff > (uint64) before.st_size ||
            header.e_phnum * sizeof(Elf64_Phdr) > (uint64) before.st_size - header.e_phoff)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_LAYOUT_REQUIRED");
        exact_pread(fileno(file), ph, header.e_phnum * sizeof(Elf64_Phdr), header.e_phoff);
        for (i = 0; i < header.e_phnum; i++) {
            Elf64_Phdr *p = &ph[i];
            if (p->p_offset > (uint64) before.st_size || p->p_filesz > (uint64) before.st_size - p->p_offset ||
                p->p_filesz > p->p_memsz || p->p_vaddr > UINT64_MAX - p->p_memsz ||
                bias > UINT64_MAX - p->p_vaddr || p->p_memsz > UINT64_MAX - bias - p->p_vaddr ||
                ((p->p_flags & PF_W) && (p->p_flags & PF_X)))
                elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_RANGE_REQUIRED");
            if (p->p_type == PT_LOAD && ((p->p_flags & ~(PF_R | PF_W | PF_X)) ||
                (p->p_align > 1 && ((p->p_align & (p->p_align - 1)) || p->p_vaddr % p->p_align != p->p_offset % p->p_align))))
                elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_LAYOUT_REQUIRED");
            if (p->p_type == PT_LOAD && p->p_offset <= header.e_phoff &&
                p->p_filesz >= header.e_phoff - p->p_offset + header.e_phnum * sizeof(Elf64_Phdr)) {
                if (bias + p->p_vaddr + header.e_phoff - p->p_offset != loader_header)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_HEADER_REQUIRED");
                header_matches++;
            }
            if (p->p_type == PT_DYNAMIC) {
                uint64 at;
                bool ended = false;
                if (p->p_filesz % sizeof(Elf64_Dyn) != 0)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_DYNAMIC_REQUIRED");
                for (at = 0; at < p->p_filesz; at += sizeof(Elf64_Dyn)) {
                    Elf64_Dyn dynamic;
                    exact_pread(fileno(file), &dynamic, sizeof(dynamic), p->p_offset + at);
                    if (dynamic.d_tag == DT_NULL) { ended = true; break; }
                    if (dynamic.d_tag == DT_TEXTREL || (dynamic.d_tag == DT_FLAGS && (dynamic.d_un.d_val & DF_TEXTREL)))
                        elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_TEXTREL_REQUIRED");
                }
                if (!ended)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_DYNAMIC_REQUIRED");
            }
        }
        if (header_matches != 1)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_HEADER_REQUIRED");
        exact_pread(fileno(memory), loaded, header.e_phnum * sizeof(Elf64_Phdr), loader_header);
        if (memcmp(ph, loaded, header.e_phnum * sizeof(Elf64_Phdr)) != 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_BYTES_CHANGED");
        appendStringInfoString(output, "{\"path\":");
        escape_json(output, path);
        appendStringInfoString(output, ",\"virtual\":false,\"segments\":[");
        for (i = 0; i < header.e_phnum; i++) {
            Elf64_Phdr *p = &ph[i];
            uint64 at;
            uint8 digest[PG_SHA256_DIGEST_LENGTH];
            char hex[PG_SHA256_DIGEST_LENGTH * 2 + 1];
            unsigned j;
            if (p->p_type != PT_LOAD || !(p->p_flags & PF_R) || (p->p_flags & PF_W) || p->p_filesz == 0)
                continue;
            readonly_mapping_range(&before, bias + p->p_vaddr, p->p_offset, p->p_filesz);
            hash = pg_cryptohash_create(PG_SHA256);
            if (hash == NULL || pg_cryptohash_init(hash) < 0)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
            for (at = 0; at < p->p_filesz;) {
                size_t n = (size_t) Min((uint64) sizeof(disk), p->p_filesz - at);
                exact_pread(fileno(file), disk, n, p->p_offset + at);
                exact_pread(fileno(memory), loaded, n, bias + p->p_vaddr + at);
                if (memcmp(disk, loaded, n) != 0)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_BYTES_CHANGED");
                if (pg_cryptohash_update(hash, (uint8 *) loaded, n) < 0)
                    elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
                at += n;
            }
            readonly_mapping_range(&before, bias + p->p_vaddr, p->p_offset, p->p_filesz);
            if (pg_cryptohash_final(hash, digest, sizeof(digest)) < 0)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_HASH_REQUIRED");
            pg_cryptohash_free(hash); hash = NULL;
            for (j = 0; j < sizeof(digest); j++)
                snprintf(hex + j * 2, 3, "%02x", digest[j]);
            if (segments++) appendStringInfoChar(output, ',');
            appendStringInfo(output, "{\"memoryStart\":\"%llx\",\"fileOffset\":\"%llu\",\"fileBytes\":\"%llu\",\"sha256\":\"%s\"}",
                (unsigned long long) (bias + p->p_vaddr), (unsigned long long) p->p_offset, (unsigned long long) p->p_filesz, hex);
        }
        if (!segments || fstat(fileno(file), &after) != 0 || stat(path, &named) != 0 ||
            !same_file_stat(&before, &after) || !same_file_stat(&before, &named))
            elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_FILE_CHANGED");
        appendStringInfoString(output, "]}");
        if (FreeFile(file) != 0) { file = NULL; elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_FILE_REQUIRED"); }
        file = NULL;
        if (FreeFile(memory) != 0) { memory = NULL; elog(ERROR, "SHARED_ADMISSION_NATIVE_ELF_READ_REQUIRED"); }
        memory = NULL;
    }
    PG_CATCH();
    {
        if (hash != NULL) pg_cryptohash_free(hash);
        if (memory != NULL) FreeFile(memory);
        if (file != NULL) FreeFile(file);
        PG_RE_THROW();
    }
    PG_END_TRY();
}
#endif
PG_FUNCTION_INFO_V1(aos_admission_loaded_module_readonly_facts);
Datum aos_admission_loaded_module_readonly_facts(PG_FUNCTION_ARGS)
{
    if (GetUserId() != get_role_oid("aos_physical_capacity_occupation_owner", false))
        ereport(ERROR, (errcode(ERRCODE_INSUFFICIENT_PRIVILEGE), errmsg("SHARED_ADMISSION_NATIVE_OWNER_REQUIRED")));
#ifdef __linux__
    {
        struct aos_readonly_snapshot *first = palloc0(sizeof(*first)), *last = palloc0(sizeof(*last));
        uintptr_t vdso = (uintptr_t) getauxval(AT_SYSINFO_EHDR), main_headers = (uintptr_t) getauxval(AT_PHDR);
        StringInfoData output;
        unsigned i;
        (void) aos_admission_loaded_module_mapping_facts(fcinfo);
        if (dl_iterate_phdr(collect_readonly_module, first) != 0 || first->modules.invalid || first->modules.count == 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_REQUIRED");
        initStringInfo(&output);
        appendStringInfoString(&output, "{\"schemaVersion\":\"aos.native-module-readonly-bytes/v1\",\"readonlyLoadedBytesVerified\":true,\"writableBytesVerified\":false,\"mappedImageProvenance\":false,\"executionAllowed\":false,\"files\":[");
        for (i = 0; i < first->modules.count; i++) {
            const char *input = first->modules.names[i];
            char path[PATH_MAX];
            CHECK_FOR_INTERRUPTS();
            if (i) appendStringInfoChar(&output, ',');
            if (vdso != 0 && first->modules.addresses[i] == vdso) {
                appendStringInfoString(&output, "{\"path\":\"virtual:linux-vdso.so.1\",\"virtual\":true}");
                continue;
            }
            if (!input[0]) {
                if (first->modules.headers[i] != main_headers) elog(ERROR, "SHARED_ADMISSION_NATIVE_UNNAMED_MODULE_REQUIRED");
                input = "/proc/self/exe";
            }
            if (input[0] != '/' || realpath(input, path) == NULL || strlen(path) >= AOS_MODULE_PATH_LIMIT)
                elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_PATH_REQUIRED");
            append_readonly_image(&output, path, first->modules.addresses[i], first->modules.headers[i], first->counts[i]);
        }
        (void) aos_admission_loaded_module_mapping_facts(fcinfo);
        if (dl_iterate_phdr(collect_readonly_module, last) != 0 || memcmp(first, last, sizeof(*first)) != 0)
            elog(ERROR, "SHARED_ADMISSION_NATIVE_MODULE_SNAPSHOT_CHANGED");
        appendStringInfoString(&output, "]}");
        PG_RETURN_DATUM(DirectFunctionCall1(jsonb_in, CStringGetDatum(output.data)));
    }
#else
    ereport(ERROR, (errcode(ERRCODE_FEATURE_NOT_SUPPORTED), errmsg("SHARED_ADMISSION_NATIVE_LINUX_REQUIRED")));
    PG_RETURN_NULL();
#endif
}
