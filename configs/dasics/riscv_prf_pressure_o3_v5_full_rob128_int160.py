# SPDX-License-Identifier: BSD-3-Clause
"""Run v5_full with 128 ROB entries and 160 integer physical registers."""

from dasics_platform import run_model
from riscv_dasics_o3_v5_full import PROFILE

if __name__ == "__m5_main__":
    cpu = PROFILE["cpu"] | {"numROBEntries": 128, "numPhysIntRegs": 160}
    run_model(PROFILE | {"cpu": cpu})
