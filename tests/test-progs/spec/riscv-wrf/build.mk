SRCS = $(shell find src -name "*.c") $(shell find src -name "*.f90" | grep -v "include/")
CFLAGS = -I./src -I./src/netcdf/include -DSPEC_CPU_CASE_FLAG -DSPEC_CPU_LINUX
FFLAGS = -I./ -I./netcdf/include -I./include -std=legacy
LD_FORTRAN = 1
