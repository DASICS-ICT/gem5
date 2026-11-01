import argparse

from m5.params import NULL

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_cache_hierarchy import (
    PrivateL1CacheHierarchy,
)
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator


class ConflictCacheHierarchy(PrivateL1CacheHierarchy):
    def __init__(self, l1d_assoc):
        super().__init__(l1i_size="32KiB", l1d_size="4KiB")
        # Apply this setting when the board creates its cache objects.
        self._l1d_assoc = l1d_assoc

    def incorporate_cache(self, board):
        super().incorporate_cache(board)

        for cache in self.l1icaches:
            cache.prefetcher = NULL

        for cache in self.l1dcaches:
            cache.assoc = self._l1d_assoc
            cache.prefetcher = NULL


parser = argparse.ArgumentParser()
parser.add_argument("--assoc", type=int, choices=[2, 8], required=True)
args = parser.parse_args()

processor = SimpleProcessor(
    cpu_type=CPUTypes.O3,
    isa=ISA.RISCV,
    num_cores=1,
    clk_freq="1GHz",
)

# Measure the effect of limiting commit bandwidth.
cpu = processor.get_cores()[0].get_simobject()
cpu.commitWidth = 4

cache_hierarchy = ConflictCacheHierarchy(l1d_assoc=args.assoc)

memory = SingleChannelDDR3_1600(size="8GiB")

board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

board.cache_line_size = 64

# Resolve the binary path relative to the repository working directory.
binary = BinaryResource(
    local_path="build/workloads/cache_conflict_roi",
    architecture=ISA.RISCV,
)
board.set_se_binary_workload(binary)

simulator = Simulator(board=board)
simulator.run()

print(f"Exit cause: {simulator.get_last_exit_event_cause()}")
print(f"Guest exit code: {simulator.get_last_exit_event_code()}")
