SRCS = $(shell find ./src -name "*.c") $(shell find ./src -name "*.f" | grep -v gauss.f)
FFLAGS += -I$(CASE_DIR)/src/SPOOLES
CFLAGS += -I$(CASE_DIR)/src/SPOOLES
LD_FORTRAN = 1
LIBS += -lm
