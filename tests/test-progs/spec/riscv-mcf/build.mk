SRCS = $(shell find ./src -name "*.c")
CFLAGS += -DWANT_STDC_PROTO
LIBS += -lm
