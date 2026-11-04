SRCS = $(shell find ./src -name "*.c")
CFLAGS += -I./src -DFN -DFAST -DCONGRAD_TMP_VECTORS -DDSLASH_TMP_LINKS
LIBS += -lm
