/* SPDX-License-Identifier: BSD-3-Clause */

#include "arch/riscv/Dasics.hh"

#include <cassert>
#include <memory>

#include "arch/riscv/faults.hh"
#include "arch/riscv/isa.hh"
#include "base/bitfield.hh"
#include "base/logging.hh"
#include "cpu/exec_context.hh"

namespace gem5
{

namespace RiscvISA
{

#if USE_DASICS
namespace
{

bool
isDasicsMiscReg(RegIndex miscReg)
{
    switch (miscReg) {
        // Main-region and call state.
        case MISCREG_DASICS_MAIN_CFG:
        case MISCREG_DASICS_MAIN_CALL_ENTRY:
        case MISCREG_DASICS_RETURN_PC:
        case MISCREG_DASICS_ACTIVE_ZONE_RETURN_PC:
        case MISCREG_DASICS_FREASON:
        case MISCREG_DASICS_U_MAIN_BOUND_LO:
        case MISCREG_DASICS_U_MAIN_BOUND_HI:
        case MISCREG_DASICS_S_MAIN_BOUND_LO:
        case MISCREG_DASICS_S_MAIN_BOUND_HI:

        // Data bounds.
        case MISCREG_DASICS_LIB_CFG:
        case MISCREG_DASICS_LIB_BOUND_LO0:
        case MISCREG_DASICS_LIB_BOUND_HI0:
        case MISCREG_DASICS_LIB_BOUND_LO1:
        case MISCREG_DASICS_LIB_BOUND_HI1:
        case MISCREG_DASICS_LIB_BOUND_LO2:
        case MISCREG_DASICS_LIB_BOUND_HI2:
        case MISCREG_DASICS_LIB_BOUND_LO3:
        case MISCREG_DASICS_LIB_BOUND_HI3:
        case MISCREG_DASICS_LIB_BOUND_LO4:
        case MISCREG_DASICS_LIB_BOUND_HI4:
        case MISCREG_DASICS_LIB_BOUND_LO5:
        case MISCREG_DASICS_LIB_BOUND_HI5:
        case MISCREG_DASICS_LIB_BOUND_LO6:
        case MISCREG_DASICS_LIB_BOUND_HI6:
        case MISCREG_DASICS_LIB_BOUND_LO7:
        case MISCREG_DASICS_LIB_BOUND_HI7:
        case MISCREG_DASICS_LIB_BOUND_LO8:
        case MISCREG_DASICS_LIB_BOUND_HI8:
        case MISCREG_DASICS_LIB_BOUND_LO9:
        case MISCREG_DASICS_LIB_BOUND_HI9:
        case MISCREG_DASICS_LIB_BOUND_LO10:
        case MISCREG_DASICS_LIB_BOUND_HI10:
        case MISCREG_DASICS_LIB_BOUND_LO11:
        case MISCREG_DASICS_LIB_BOUND_HI11:
        case MISCREG_DASICS_LIB_BOUND_LO12:
        case MISCREG_DASICS_LIB_BOUND_HI12:
        case MISCREG_DASICS_LIB_BOUND_LO13:
        case MISCREG_DASICS_LIB_BOUND_HI13:
        case MISCREG_DASICS_LIB_BOUND_LO14:
        case MISCREG_DASICS_LIB_BOUND_HI14:
        case MISCREG_DASICS_LIB_BOUND_LO15:
        case MISCREG_DASICS_LIB_BOUND_HI15:

        // Jump bounds.
        case MISCREG_DASICS_JUMP_CFG:
        case MISCREG_DASICS_JUMP_BOUND_LO0:
        case MISCREG_DASICS_JUMP_BOUND_HI0:
        case MISCREG_DASICS_JUMP_BOUND_LO1:
        case MISCREG_DASICS_JUMP_BOUND_HI1:
        case MISCREG_DASICS_JUMP_BOUND_LO2:
        case MISCREG_DASICS_JUMP_BOUND_HI2:
        case MISCREG_DASICS_JUMP_BOUND_LO3:
        case MISCREG_DASICS_JUMP_BOUND_HI3:
            return true;
        default:
            return false;
    }
}

} // anonymous namespace

bool
dasicsPcIsTrusted(Addr pc, bool enabled, Addr lower, Addr upper,
                  unsigned vaddrBits)
{
    if (!enabled) {
        return true;
    }

    // The implemented comparator must include at least address bit 3.
    assert(vaddrBits >= 4 && vaddrBits <= 64);

    const Addr pcBlock = bits(pc, vaddrBits - 1, 3);
    const Addr lowerBlock = bits(lower, vaddrBits - 1, 3);
    const Addr upperBlock = bits(upper, vaddrBits - 1, 3);

    return lowerBlock <= pcBlock && pcBlock < upperBlock;
}

bool
dasicsInstIsTrusted(ExecContext *xc, unsigned vaddrBits)
{
    const auto mode = static_cast<PrivilegeMode>(xc->readMiscReg(MISCREG_PRV));

    // FDI checks apply only to non-virtualized S/U execution.
    if (mode == PRV_M || virtualizationEnabled(xc)) {
        return true;
    }

    const DasicsMainCfg config = xc->readMiscReg(MISCREG_DASICS_MAIN_CFG);
    const Addr pc = xc->pcState().instAddr();

    switch (mode) {
        case PRV_S:
            return dasicsPcIsTrusted(
                pc, config.sena,
                xc->readMiscReg(MISCREG_DASICS_S_MAIN_BOUND_LO),
                xc->readMiscReg(MISCREG_DASICS_S_MAIN_BOUND_HI), vaddrBits);
        case PRV_U:
            return dasicsPcIsTrusted(
                pc, config.uena,
                xc->readMiscReg(MISCREG_DASICS_U_MAIN_BOUND_LO),
                xc->readMiscReg(MISCREG_DASICS_U_MAIN_BOUND_HI), vaddrBits);
        default:
            panic("Invalid DASICS privilege mode %u",
                  static_cast<unsigned>(mode));
    }
}

Fault
dasicsCsrAccessCheck(ExecContext *xc, RegIndex miscReg, ExtMachInst machInst,
                     unsigned vaddrBits)
{
    if (!isDasicsMiscReg(miscReg)) {
        return NoFault;
    }

    if (dasicsInstIsTrusted(xc, vaddrBits)) {
        return NoFault;
    }

    return std::make_shared<IllegalInstFault>("Untrusted access to DASICS CSR",
                                              machInst);
}
#endif // USE_DASICS

} // namespace RiscvISA
} // namespace gem5
