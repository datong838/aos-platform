#include "postgres.h"
#include "fmgr.h"
#include "miscadmin.h"
#include <sys/mman.h>
#include <unistd.h>
PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(test_mapping);
static void *page=NULL;
static size_t length=0;
Datum test_mapping(PG_FUNCTION_ARGS) {
    bool allocate=PG_GETARG_BOOL(0);
    if (!superuser()) elog(ERROR,"TEST_SUPERUSER_REQUIRED");
    if (allocate) {
        long size;
        if(page!=NULL) elog(ERROR,"TEST_ALREADY_ALLOCATED");
        size=sysconf(_SC_PAGESIZE);
        if(size<=0) elog(ERROR,"TEST_PAGE_SIZE");
        length=(size_t)size;
        page=mmap(NULL,length,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
        if(page==MAP_FAILED){page=NULL;elog(ERROR,"TEST_MMAP");}
        if(mprotect(page,length,PROT_READ|PROT_EXEC)!=0){munmap(page,length);page=NULL;elog(ERROR,"TEST_MPROTECT");}
        PG_RETURN_INT64((int64)(uintptr_t)page);
    }
    if(page!=NULL){if(munmap(page,length)!=0)elog(ERROR,"TEST_MUNMAP");page=NULL;}
    PG_RETURN_INT64(0);
}
