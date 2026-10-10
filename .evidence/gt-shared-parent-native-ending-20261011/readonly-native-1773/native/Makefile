EXTENSION = aos_admission_end
MODULE_big = aos_admission_end
OBJS = aos_admission_end.o
DATA = aos_admission_end--0.1.sql
PG_CFLAGS += -Wall -Wextra -Werror -Wno-unused-parameter
PG_CONFIG ?= pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
