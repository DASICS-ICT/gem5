from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

processor = SimpleProcessor(
    cpu_type=CPUTypes.ATOMIC,
    isa=ISA.RISCV,
    num_cores=1,
    clk_freq="3GHz",
)

cache_hierarchy = NoCache()
memory = SingleChannelDDR3_1600(size="8GiB")

board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hierarchy,
)

# Resolve the binary path relative to the repository working directory.
binary = BinaryResource(
    local_path="tests/test-progs/hello/bin/riscv/linux/hello",
    architecture=ISA.RISCV,
)
board.set_se_binary_workload(binary)

simulator = Simulator(board=board)
simulator.run()

print(f"Exit cause: {simulator.get_last_exit_event_cause()}")
print(f"Guest exit code: {simulator.get_last_exit_event_code()}")
