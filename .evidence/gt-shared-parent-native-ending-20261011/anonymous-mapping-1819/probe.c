#define _GNU_SOURCE
#include <link.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct snapshot { unsigned n; uintptr_t addr[256]; };
static int collect(struct dl_phdr_info *i,size_t z,void *p) {
 struct snapshot *s=p;(void)z;if(s->n>=256)return 1;s->addr[s->n++]=i->dlpi_addr;return 0;
}
int main(void) {
 struct snapshot a={0},b={0};char line[1024],perms[5]={0};unsigned long lo,hi;int found=0;
 long size=sysconf(_SC_PAGESIZE);if(size<=0)return 2;
 if(dl_iterate_phdr(collect,&a))return 3;
 void *p=mmap(NULL,(size_t)size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(p==MAP_FAILED)return 4;memset(p,0,(size_t)size);
 if(mprotect(p,(size_t)size,PROT_READ|PROT_EXEC))return 5;
 if(dl_iterate_phdr(collect,&b))return 6;
 FILE *f=fopen("/proc/self/maps","r");if(!f)return 7;
 while(fgets(line,sizeof(line),f))if(sscanf(line,"%lx-%lx %4s",&lo,&hi,perms)==3 && (uintptr_t)p>=lo && (uintptr_t)p<hi){found=1;break;}
 fclose(f);int equal=memcmp(&a,&b,sizeof(a))==0;
 int rx=found && perms[0]=='r' && perms[1]=='-' && perms[2]=='x';
 printf("{\"loader_records\":%u,\"loader_unchanged\":%s,\"anonymous_rx_observed\":%s,\"page_executed\":false}\n",a.n,equal?"true":"false",rx?"true":"false");
 if(munmap(p,(size_t)size))return 8;return equal && rx ? 0:9;
}
