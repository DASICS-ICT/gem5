# Copyright (c) 2026 zengsy99
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""RTL-derived capacities for the V2_default DASICS O3 model."""

from dasics_platform import run_model

# RTL FetchWidth counts 32-bit words; O3 fetchWidth counts instructions.
# The maximum compressed-instruction count and fetch bytes are mapped below.
# Vector support is an experiment extension requested for all models.
# These 64 vector registers have no counterpart in the V2 reference RTL.
PROFILE = {
    "name": "V2_default",
    "rtl": {
        "configuration": "DefaultConfig",
        "FetchWidth_32bit_words": 8,
        "DecodeWidth": 6,
        "RenameWidth": 6,
        "CommitWidth": 6,
        "RobSize_entries": 256,
        "NRPhyRegs_entries_per_scalar_file": 192,
        "LoadQueueSize_entries": 80,
        "StoreQueueSize_entries": 64,
        "StoreBufferSize_entries": 16,
        "FtqSize_entries": 64,
        "IBufSize_instructions": 48,
        "IssQueSize_entries_per_dequeue_port": 16,
        "LoadPipelineWidth": 2,
        "StorePipelineWidth": 2,
        "IntDqSize_entries": 16,
        "FpDqSize_entries": 16,
        "LsDqSize_entries": 16,
        "IntDqDeqWidth": 4,
        "FpDqDeqWidth": 4,
        "LsDqDeqWidth": 4,
        "EnableBPD_config_field": True,
        "HCCache_mshrs_per_bank": 14,
        "HCCache_reserved_BC_mshrs_per_bank": 2,
        "CacheLineSize_bytes": 64,
    },
    "cpu": {
        "fetchWidth": 16,
        "fetchBufferSize": 32,
        "decodeWidth": 6,
        "renameWidth": 6,
        "commitWidth": 6,
        "numROBEntries": 256,
        "numPhysIntRegs": 192,
        "numPhysFloatRegs": 192,
        "numPhysVecRegs": 64,
        "LQEntries": 80,
        "SQEntries": 64,
        "fetchQueueSize": 48,
        "numFTQEntries": 64,
    },
    "queues": [
        ("ALU0", 32, "alu", 2),
        ("ALU1", 32, "alu", 2),
        ("MDU", 32, "mdu", 2),
        ("JUMP_CSR", 16, "system", 1),
        ("FMAC0", 32, "fmac", 2),
        ("FMAC1", 32, "fmac", 2),
        ("FMISC", 32, "fmisc", 2),
        ("LD", 32, "load", 2),
        ("STA", 32, "store", 2),
        ("STD", 32, "store", 2),
    ],
    "branch": {
        "ubtb": 256,
        "ftb": 2048,
        "ftb_ways": 4,
        "ras": 32,
        "tage_rows": 4096,
        "tage_histories": [8, 13, 32, 119],
        "tage_tag": 8,
        "sc": True,
        "loop": True,
    },
    "caches": {
        "l1i": {
            "size": "64KiB",
            "assoc": 4,
            "mshrs": 2,
            "banks": 1,
            "prefetch": "tagged",
        },
        "l1d": {
            "size": "64KiB",
            "assoc": 4,
            "mshrs": 16,
            "banks": 1,
            "prefetch": "none",
        },
        "l2": {
            "size": "1MiB",
            "assoc": 8,
            "mshrs": 56,
            "banks": 4,
            "prefetch": "sms",
        },
        "l3": {
            "size": "6MiB",
            "assoc": 6,
            "mshrs": 56,
            "banks": 4,
            "prefetch": "none",
        },
    },
    "vector": True,
}


if __name__ == "__m5_main__":
    run_model(PROFILE)
