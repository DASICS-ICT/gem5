SRCS = $(shell find ./src -name "*.cc")
CFLAGS += -I./src/include -DBOOST_DISABLE_THREADS -Ddeal_II_dimension=3
# ifneq ($(ARCH),riscv64)
# CFLAGS += -mlong-double-64
# endif
LD_CXX = 1
