# SPDX-License-Identifier: BSD-3-Clause
"""Run the v5_full register-pressure experiment with a 128-entry ROB."""

from dasics_platform import run_model
from riscv_dasics_o3_v5_full import PROFILE

if __name__ == "__m5_main__":
    run_model(PROFILE | {"cpu": PROFILE["cpu"] | {"numROBEntries": 128}})
