SRCS = $(shell find ./src -name "*.c")
CFLAGS += -DHAVE_CONFIG_H -I./src/include
LIBS = -lm
