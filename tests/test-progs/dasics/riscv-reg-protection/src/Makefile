# SPDX-License-Identifier: BSD-3-Clause

CROSS_COMPILE ?= riscv64-linux-gnu-
CC = $(CROSS_COMPILE)gcc
CPPFLAGS += -I../../../../../include
CFLAGS = -O2 -g -Wall -Wextra -Werror -march=rv64gc -mabi=lp64d \
	-fno-tree-vectorize
ASFLAGS = -g -march=rv64gcv -mabi=lp64d
LDFLAGS = -static -no-pie -Wl,--build-id=none
OUT = ../build/riscv-reg-protection.elf
OBJECTS = ../build/reg_protection.o ../build/reg_protection_asm.o
RESTORE_OUT = ../build/reg-restore.elf
RESTORE_OBJECTS = ../build/reg_restore.o ../build/reg_restore_asm.o
PRESSURE_OUT = ../build/reg-pressure.elf
PRESSURE_OBJECTS = ../build/reg_pressure.o ../build/reg_pressure_asm.o \
	../build/reg_protection_asm.o

.PHONY: all restore pressure clean

all: $(OUT)

$(OUT): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

../build/reg_protection.o: reg_protection.c reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

../build/reg_protection_asm.o: reg_protection.S reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(ASFLAGS) -c -o $@ $<

restore: $(RESTORE_OUT)

$(RESTORE_OUT): $(RESTORE_OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

../build/reg_restore.o: reg_restore.c reg_restore.h reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

../build/reg_restore_asm.o: reg_restore.S reg_restore.h reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(ASFLAGS) -c -o $@ $<

pressure: $(PRESSURE_OUT)

$(PRESSURE_OUT): $(PRESSURE_OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

../build/reg_pressure.o: reg_pressure.c reg_pressure.h reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

../build/reg_pressure_asm.o: reg_pressure.S reg_pressure.h reg_protection.h Makefile
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(ASFLAGS) -c -o $@ $<

# Measurement records remain available after software cleanup.
clean:
	rm -f $(OUT) $(OBJECTS) $(RESTORE_OUT) $(RESTORE_OBJECTS) \
		$(PRESSURE_OUT) $(PRESSURE_OBJECTS)
