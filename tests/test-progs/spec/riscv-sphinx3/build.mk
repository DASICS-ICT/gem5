SRCS = $(shell find ./src -name "*.c")
CFLAGS = -I$(CASE_DIR)/src -DHAVE_CONFIG_H \
         -I$(CASE_DIR)/src/libutil -fsigned-char
# Keep diagnostic source names independent of the checkout directory.
CFLAGS += -fmacro-prefix-map=$(CASE_DIR)/src/=
LIBS = -lm
