SRCS = $(shell find ./src -name "*.c") $(shell find ./src -name "*.f")
CFLAGS += -I./src -DHAVE_CONFIG_H
LD_FORTRAN = 1
