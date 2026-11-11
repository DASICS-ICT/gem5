# The gem5 Simulator

This is the repository for the gem5 simulator. It contains the full source code
for the simulator and all tests and regressions.

The gem5 simulator is a modular platform for computer-system architecture
research, encompassing system-level architecture as well as processor
microarchitecture. It is primarily used to evaluate new hardware designs,
system software changes, and compile-time and run-time system optimizations.

The main website can be found at <http://www.gem5.org>.

## DASICS

| Configuration | Build command |
| --- | --- |
| RISC-V | `make riscv` |
| RISC-V with DASICS | `make riscv-dasics` |

[中文：编译、测试与清理](docs/dasics.md) |
[English: build, test, and cleanup](docs/dasics.en.md)

### User-mode exception support

The DASICS build provides RV64 user-mode synchronous exception handling in
non-virtualized M/S/U systems. The user handler executes in U mode and must
reside in the trusted U region when U-domain protection is enabled.

| Facility | Behavior |
| --- | --- |
| User exception CSRs | `USTATUS`, `UTVEC`, `USCRATCH`, `UEPC`, `UCAUSE`, and `UTVAL` |
| Shared status | `USTATUS` exposes `UIE` and `UPIE`, shared with host `SSTATUS` and `MSTATUS`; `VSSTATUS` retains its existing view |
| Delegation | S-level `SEDELEG` has independent storage and mask `0x0100B1FF`; writes are limited by the current `MEDELEG` |
| Exception entry | A U-origin exception selects U handling only when both delegation bits are set; otherwise it selects M or S handling |
| User return | `URET` (`0x00200073`) returns through `UEPC`, restores `UIE` from `UPIE`, and sets `UPIE` to one |

U entry saves `UCAUSE`, `UEPC`, and `UTVAL`, copies `UIE` to `UPIE`, clears
`UIE`, and transfers control to `UTVEC.BASE`. Synchronous exceptions use
BASE in both supported UTVEC modes. Writing reserved UTVEC modes preserves
the old mode while updating BASE. UEPC reads follow the C-extension
alignment rules. Delegation does not depend on `UIE` or the DASICS domain
enable bits; disabling protection does not disable user exception handling.

Explicit accesses to the user exception support CSRs require source trust
after the ordinary CSR privilege checks. Non-virtualized untrusted S code
also cannot read or write `SSTATUS`, `STVEC`, `SSCRATCH`, `SEPC`, `SCAUSE`, or
`STVAL`, or execute `SRET`. M mode remains trusted, and disabling a domain's
protection bypasses its trust check. URET follows the NanhuV5 restriction:
only non-virtualized trusted U code may execute it; M/S execution is illegal.
Guest accesses to the user exception support CSRs and guest URET execution
are rejected as virtual instructions.

Writes to the DASICS and user exception support CSRs retain the successful
commit squash policy. Pure reads do not request that extra squash. The six
supervisor exception CSRs retain ordinary CSR serialization; URET and SRET
use non-speculative execution and serialize younger instructions without an
additional squash-after flag. Trap entry and return do not automatically
save general-purpose, floating-point, or vector registers.

User-mode interrupt delivery, virtualized user exception handling, and
direct M-to-U delegation in M/U-only systems are outside this support.
The existing [CSR permission test](tests/test-progs/dasics/riscv-dasics-csr-permission/README.en.md)
checks SSCRATCH rejection and recovery; a dedicated U-handler/URET round-trip
test is not yet part of the functional test inventory.

## SPEC CPU2006

[29 项测试：构建、运行与校验](tests/test-progs/spec/README.md) |
[gem5 SE 配置](configs/spec/README.md)

```bash
make spec06-test TEST=riscv-calculix input=test \
  config="riscv_se_V2_default.py riscv_se_v5_full.py"
make spec06-test TEST=riscv-calculix input=test config=all
```

## Testing and code coverage status

**Note**: These regard tests run on the develop branch of gem5:
<https://github.com/gem5/gem5/tree/develop>.

[![Daily Tests](https://github.com/gem5/gem5/actions/workflows/daily-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/daily-tests.yaml)
[![Weekly Tests](https://github.com/gem5/gem5/actions/workflows/weekly-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/weekly-tests.yaml)
[![Compiler Tests](https://github.com/gem5/gem5/actions/workflows/compiler-tests.yaml/badge.svg?branch=develop)](https://github.com/gem5/gem5/actions/workflows/compiler-tests.yaml)
[![codecov](https://codecov.io/gh/gem5/gem5/branch/develop/graph/badge.svg)](https://app.codecov.io/gh/gem5/gem5/tree/develop)

## Getting started

A good starting point is <http://www.gem5.org/about>, and for
more information about building the simulator and getting started
please see <http://www.gem5.org/documentation> and
<http://www.gem5.org/documentation/learning_gem5/introduction>.

## Building gem5

To build gem5, you will need the following software: g++ or clang,
Python (gem5 links in the Python interpreter), SCons, zlib 1.2+, GNU m4
1.4+, and lastly protobuf if you want trace capture and playback support.
Please see
<http://www.gem5.org/documentation/general_docs/building> for more details
concerning the minimum versions of these tools.

Once you have all dependencies resolved, execute
`scons build/ALL/gem5.opt` to build an optimized version of the gem5 binary
(`gem5.opt`) containing all gem5 ISAs. If you only wish to compile gem5 to
include a single ISA, you can replace `ALL` with the name of the ISA. Valid
options include `ARM`, `NULL`, `MIPS`, `POWER`, `RISCV`, `SPARC`, and `X86`
The complete list of options can be found in the build_opts directory.

See https://www.gem5.org/documentation/general_docs/building for more
information on building gem5.

## The Source Tree

The main source tree includes these subdirectories:

* build_opts: pre-made default configurations for gem5
* build_tools: tools used internally by gem5's build process.
* configs: example simulation configuration scripts
* ext: less-common external packages needed to build gem5
* include: include files for use in other programs
* site_scons: modular components of the build system
* src: source code of the gem5 simulator. The C++ source, Python wrappers, and Python standard library are found in this directory.
* system: source for some optional system software for simulated systems
* tests: regression tests
* util: useful utility programs and files

## gem5 Resources

To run full-system simulations, you may need compiled system firmware, kernel
binaries and one or more disk images, depending on gem5's configuration and
what type of workload you're trying to run. Many of these resources can be
obtained from <https://resources.gem5.org>.

More information on gem5 Resources can be found at
<https://www.gem5.org/documentation/general_docs/gem5_resources/>.

## Getting Help, Reporting bugs, and Requesting Features

We provide a variety of channels for users and developers to get help, report
bugs, requests features, or engage in community discussions. Below
are a few of the most common we recommend using.

* **GitHub Discussions**: A GitHub Discussions page. This can be used to start
discussions or ask questions. Available at
<https://github.com/orgs/gem5/discussions>.
* **GitHub Issues**: A GitHub Issues page for reporting bugs or requesting
features. Available at <https://github.com/gem5/gem5/issues>.
* **gem5-users@gem5.org**: A mailing list for users of gem5 to ask questions
or start discussions. To join the mailing list please visit
<https://www.gem5.org/mailing_lists>.
* **gem5-dev@gem5.org**: A mailing list for developers of gem5 to ask questions
or start discussions. To join the mailing list please visit
<https://www.gem5.org/mailing_lists>.

## Contributing to gem5

We hope you enjoy using gem5. When appropriate we advise sharing your
contributions to the project. <https://www.gem5.org/contributing> can help you
get started. Additional information can be found in the CONTRIBUTING.md file.
