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

"""RTL-derived capacities for the v5_full DASICS O3 model."""

from dasics_platform import run_model

# RTL shares 160 physical VF registers; O3 uses separate FP/vector files.
# L2 uses the integrated per-bank geometry; L3 selects the mini SoC platform.
PROFILE = {
    "name": "v5_full",
    "rtl": {
        "configuration": "CoreConfig.full",
        "soc_configuration": "SystemConfig.miniSoc",
        "FetchWidth_32bit_words": 8,
        "DecodeWidth": 4,
        "RenameWidth": 4,
        "CommitWidth": 8,
        "RobSize_entries": 96,
        "intPreg_entries": 128,
        "shared_vfPreg_entries": 160,
        "v0Preg_entries": 22,
        "vlPreg_entries": 32,
        "VLEN_bits": 128,
        "ELEN_bits": 64,
        "VirtualLoadQueueSize_entries": 56,
        "LoadQueueRAWSize_entries": 24,
        "LoadQueueReplaySize_entries": 32,
        "LoadUncacheBufferSize_entries": 8,
        "StoreQueueSize_entries": 32,
        "StoreBufferSize_entries": 8,
        "FtqSize_entries": 48,
        "IBufSize_instructions": 32,
        "IntDqSize_entries": 8,
        "FpDqSize_entries": 12,
        "LsDqSize_entries": 12,
        "IntDqDeqWidth": 8,
        "FpDqDeqWidth": 6,
        "VecDqDeqWidth": 6,
        "LsDqDeqWidth": 4,
        "RasSpecSize_entries": 32,
        "ICache_nFetchMshr": 4,
        "ICache_nPrefetchMshr": 10,
        "DCache_nSets": 256,
        "DCache_nWays": 4,
        "L2NBanks": 2,
        "L2_base_sets_per_bank": 512,
        "L2_effective_sets_per_bank": 1024,
        "L2_mshrs_per_bank": 16,
        "L3_hnxOutstanding_total": 32,
        "CacheLineSize_bytes": 64,
    },
    "cpu": {
        "fetchWidth": 16,
        "fetchBufferSize": 32,
        "decodeWidth": 4,
        "renameWidth": 4,
        "commitWidth": 8,
        "numROBEntries": 96,
        "numPhysIntRegs": 128,
        "numPhysFloatRegs": 160,
        "numPhysVecRegs": 160,
        "LQEntries": 56,
        "SQEntries": 32,
        "fetchQueueSize": 32,
        "numFTQEntries": 48,
    },
    "queues": [
        ("ALU0_BJU0", 18, "int_pair", 2),
        ("ALU1_BJU1", 18, "int_pair", 2),
        ("ALU2_BJU2", 18, "int_pair", 2),
        ("ALU3_BJU3", 18, "int_pair", 2),
        ("VFMA", 16, "fmac", 2),
        ("VFALU", 16, "simd", 2),
        ("VFDIV", 10, "fmisc", 1),
        ("STA0", 20, "store", 1),
        ("LDU0", 16, "load", 1),
        ("LDU1", 16, "load", 1),
        ("VLSU0", 16, "simd_mem", 1),
        ("STD0", 20, "store", 1),
    ],
    "branch": {
        "ubtb": 256,
        "ftb": 4096,
        "ftb_ways": 4,
        "ras": 16,
        "tage_rows": 2048,
        "tage_histories": [8, 13, 32, 119],
        "tage_tag": 8,
        "sc": False,
        "loop": False,
    },
    "caches": {
        "l1i": {
            "size": "64KiB",
            "assoc": 4,
            "mshrs": 4,
            "banks": 4,
            "prefetch": "tagged",
        },
        "l1d": {
            "size": "64KiB",
            "assoc": 4,
            "mshrs": 32,
            "banks": 1,
            "prefetch": "stream_stride",
        },
        "l2": {
            "size": "1MiB",
            "assoc": 8,
            "mshrs": 32,
            "banks": 2,
            "prefetch": "bop_sms",
        },
        "l3": {
            "size": "2MiB",
            "assoc": 16,
            "mshrs": 32,
            "banks": 2,
            "prefetch": "none",
        },
    },
    "vector": True,
}


if __name__ == "__m5_main__":
    run_model(PROFILE)
