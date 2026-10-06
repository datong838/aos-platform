EXTENSION = aos_ed25519
MODULE_big = aos_ed25519
OBJS = aos_ed25519.o
DATA = aos_ed25519--1.0.sql
PG_CFLAGS += -Wall -Wextra -Werror
SHLIB_LINK = -lcrypto
PG_CONFIG ?= pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
