SRCS = $(shell find src -name "*.f")
FFLAGS_EXTRA = -std=legacy -funconstrained-commons
LD_FORTRAN = 1
