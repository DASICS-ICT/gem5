SRCS = $(shell find ./src -name "*.c") $(shell find ./src -name "*.f")
CFLAGS += -I./src/include -DCCODE
LD_FORTRAN = 1
