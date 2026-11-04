SRCS = $(shell find ./src -name "*.c")
CFLAGS += -DSPEC_CPU_LINUX
LIBS = -lm
