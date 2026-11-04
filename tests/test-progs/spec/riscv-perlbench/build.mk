SRCS = $(shell find ./src -name "*.c" | grep -vE "win32|hparser|parser-util")
CFLAGS += -DPERL_CORE -std=gnu89
ifeq ($(ARCH),i386)
CFLAGS  += -DSPEC_CPU_LINUX_IA32
LDFLAGS += -DSPEC_CPU_LINUX_IA32
else
CFLAGS  += -DSPEC_CPU_LINUX_X64
LDFLAGS += -DSPEC_CPU_LINUX_X64
endif
LIBS += -lm
