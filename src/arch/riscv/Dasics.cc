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

// Use CSR addresses to distinguish aliases of shared register storage.
// SEDELEG controls user-trap delegation despite its S-mode access privilege.
bool
isUserTrapCsr(uint64_t csr)
{
    switch (csr) {
        case CSR_SEDELEG:
        case CSR_USTATUS:
        case CSR_UTVEC:
        case CSR_USCRATCH:
        case CSR_UEPC:
        case CSR_UCAUSE:
        case CSR_UTVAL:
            return true;
        default:
            return false;
    }
}

bool
isSupervisorTrapCsr(uint64_t csr)
{
    // These CSRs retain their ordinary VS aliases in virtualized execution.
    switch (csr) {
        case CSR_SSTATUS:
        case CSR_STVEC:
        case CSR_SSCRATCH:
        case CSR_SEPC:
        case CSR_SCAUSE:
        case CSR_STVAL:
            return true;
        default:
            return false;
    }
}

bool
isDasicsCsr(uint64_t csr)
{
    if (isUserTrapCsr(csr)) {
        return true;
    }

    switch (csr) {
        // Main-region and call state.
        case CSR_DASICS_U_MAIN_CFG:
        case CSR_DASICS_S_MAIN_CFG:
        case CSR_DASICS_MAIN_CALL_ENTRY:
        case CSR_DASICS_RETURN_PC:
        case CSR_DASICS_ACTIVE_ZONE_RETURN_PC:
        case CSR_DASICS_FREASON:
        case CSR_DASICS_U_MAIN_BOUND_LO:
        case CSR_DASICS_U_MAIN_BOUND_HI:
        case CSR_DASICS_S_MAIN_BOUND_LO:
        case CSR_DASICS_S_MAIN_BOUND_HI:

        // Data bounds.
        case CSR_DASICS_LIB_CFG:
        case CSR_DASICS_LIB_BOUND_LO0:
        case CSR_DASICS_LIB_BOUND_HI0:
        case CSR_DASICS_LIB_BOUND_LO1:
        case CSR_DASICS_LIB_BOUND_HI1:
        case CSR_DASICS_LIB_BOUND_LO2:
        case CSR_DASICS_LIB_BOUND_HI2:
        case CSR_DASICS_LIB_BOUND_LO3:
        case CSR_DASICS_LIB_BOUND_HI3:
        case CSR_DASICS_LIB_BOUND_LO4:
        case CSR_DASICS_LIB_BOUND_HI4:
        case CSR_DASICS_LIB_BOUND_LO5:
        case CSR_DASICS_LIB_BOUND_HI5:
        case CSR_DASICS_LIB_BOUND_LO6:
        case CSR_DASICS_LIB_BOUND_HI6:
        case CSR_DASICS_LIB_BOUND_LO7:
        case CSR_DASICS_LIB_BOUND_HI7:
        case CSR_DASICS_LIB_BOUND_LO8:
        case CSR_DASICS_LIB_BOUND_HI8:
        case CSR_DASICS_LIB_BOUND_LO9:
        case CSR_DASICS_LIB_BOUND_HI9:
        case CSR_DASICS_LIB_BOUND_LO10:
        case CSR_DASICS_LIB_BOUND_HI10:
        case CSR_DASICS_LIB_BOUND_LO11:
        case CSR_DASICS_LIB_BOUND_HI11:
        case CSR_DASICS_LIB_BOUND_LO12:
        case CSR_DASICS_LIB_BOUND_HI12:
        case CSR_DASICS_LIB_BOUND_LO13:
        case CSR_DASICS_LIB_BOUND_HI13:
        case CSR_DASICS_LIB_BOUND_LO14:
        case CSR_DASICS_LIB_BOUND_HI14:
        case CSR_DASICS_LIB_BOUND_LO15:
        case CSR_DASICS_LIB_BOUND_HI15:

        // Jump bounds.
        case CSR_DASICS_JUMP_CFG:
        case CSR_DASICS_JUMP_BOUND_LO0:
        case CSR_DASICS_JUMP_BOUND_HI0:
        case CSR_DASICS_JUMP_BOUND_LO1:
        case CSR_DASICS_JUMP_BOUND_HI1:
        case CSR_DASICS_JUMP_BOUND_LO2:
        case CSR_DASICS_JUMP_BOUND_HI2:
        case CSR_DASICS_JUMP_BOUND_LO3:
        case CSR_DASICS_JUMP_BOUND_HI3:
            return true;
        default:
            return false;
    }
}

bool
csrHasWriteIntent(ExtMachInst machInst)
{
    switch (machInst.funct3) {
        case 0x1: // CSRRW
        case 0x5: // CSRRWI
            return true;
        case 0x2: // CSRRS
        case 0x3: // CSRRC
        case 0x6: // CSRRSI
        case 0x7: // CSRRCI
            // The field holds the rs1 index or zimm, never register data.
            return machInst.csrimm != 0;
        default:
            return false;
    }
}

} // anonymous namespace

bool
dasicsCsrNeedsSquash(ExtMachInst machInst)
{
    return isDasicsCsr(machInst.funct12) && csrHasWriteIntent(machInst);
}

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
dasicsJumpTargetIsAllowed(Addr target, RegVal jumpCfg,
                          const std::array<DasicsAddrRange, 4> &bounds,
                          Addr mainCallEntry, Addr returnPc,
                          Addr activeZoneReturnPc, unsigned vaddrBits)
{
    assert(vaddrBits >= 4 && vaddrBits <= 64);

    const DasicsJumpCfg config = jumpCfg;
    const std::array<bool, 4> valid = {
        static_cast<bool>(config.valid0), static_cast<bool>(config.valid1),
        static_cast<bool>(config.valid2), static_cast<bool>(config.valid3)};

    for (unsigned i = 0; i < bounds.size(); ++i) {
        // An invalid bound must not use the disabled-protection bypass.
        if (valid[i] && dasicsPcIsTrusted(target, true, bounds[i].lower,
                                          bounds[i].upper, vaddrBits)) {
            return true;
        }
    }

    const Addr targetAddress = bits(target, vaddrBits - 1, 0);
    return targetAddress == bits(mainCallEntry, vaddrBits - 1, 0) ||
           targetAddress == bits(returnPc, vaddrBits - 1, 0) ||
           targetAddress == bits(activeZoneReturnPc, vaddrBits - 1, 0);
}

bool
dasicsMemAccessIsAllowed(Addr address, unsigned size, bool isWrite,
                         RegVal libCfg,
                         const std::array<DasicsAddrRange, 16> &bounds)
{
    if (size != 1 && size != 2 && size != 4 && size != 8) {
        return false;
    }

    const Addr last = address + size - 1;
    if (last < address) {
        return false;
    }

    for (unsigned i = 0; i < bounds.size(); ++i) {
        // Move each V/U/R/W slot to slot 0 to use the named bitfields.
        const DasicsLibCfg slot = libCfg >> (4 * i);
        const bool permitted = isWrite ? static_cast<bool>(slot.write0)
                                       : static_cast<bool>(slot.read0);
        if (!slot.valid0 || !permitted) {
            continue;
        }

        const Addr lower = bounds[i].lower & DASICS_BOUND_MASK;
        const Addr upper = bounds[i].upper & DASICS_BOUND_MASK;
        if (lower <= address && last < upper) {
            return true;
        }
    }

    return false;
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
dasicsCsrAccessCheck(ExecContext *xc, ExtMachInst machInst, unsigned vaddrBits)
{
    const uint64_t csr = machInst.funct12;

    // User trap CSRs have no guest aliases; keep their host state private.
    if (isUserTrapCsr(csr) && virtualizationEnabled(xc)) {
        return std::make_shared<VirtualInstFault>(
            "User trap CSR is not accessible in virtualized mode", machInst);
    }

    // DASICS and supervisor trap CSRs require trust for reads and writes.
    const bool requires_trust = isDasicsCsr(csr) || isSupervisorTrapCsr(csr);
    if (requires_trust && !dasicsInstIsTrusted(xc, vaddrBits)) {
        return std::make_shared<IllegalInstFault>(
            "Untrusted access to protected CSR", machInst);
    }

    return NoFault;
}

Fault
dasicsCallAccessCheck(ExecContext *xc, ExtMachInst machInst,
                      unsigned vaddrBits)
{
    const auto mode = static_cast<PrivilegeMode>(xc->readMiscReg(MISCREG_PRV));

    // Calls require an enabled U/S domain before source-PC trust is checked.
    if ((mode == PRV_U || mode == PRV_S) && !virtualizationEnabled(xc)) {
        const DasicsMainCfg config = xc->readMiscReg(MISCREG_DASICS_MAIN_CFG);
        const bool enabled = mode == PRV_U ? static_cast<bool>(config.uena)
                                           : static_cast<bool>(config.sena);
        if (enabled && dasicsInstIsTrusted(xc, vaddrBits)) {
            return NoFault;
        }
    }

    return std::make_shared<IllegalInstFault>(
        "DASICS call requires enabled, trusted non-virtualized U/S execution",
        machInst);
}

Fault
dasicsJumpAccessCheck(ExecContext *xc, Addr target, bool taken,
                      unsigned vaddrBits)
{
    if (!taken || dasicsInstIsTrusted(xc, vaddrBits)) {
        return NoFault;
    }

    // An untrusted result implies enabled, non-virtualized U/S execution.
    const auto mode = static_cast<PrivilegeMode>(xc->readMiscReg(MISCREG_PRV));
    const DasicsMainCfg config = xc->readMiscReg(MISCREG_DASICS_MAIN_CFG);
    const bool checkDisabled = mode == PRV_U ? static_cast<bool>(config.cuft)
                                             : static_cast<bool>(config.csft);
    if (checkDisabled) {
        return NoFault;
    }

    const std::array<DasicsAddrRange, 4> bounds = {{
        {xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_LO0),
         xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_HI0)},
        {xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_LO1),
         xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_HI1)},
        {xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_LO2),
         xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_HI2)},
        {xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_LO3),
         xc->readMiscReg(MISCREG_DASICS_JUMP_BOUND_HI3)},
    }};
    if (dasicsJumpTargetIsAllowed(
            target, xc->readMiscReg(MISCREG_DASICS_JUMP_CFG), bounds,
            xc->readMiscReg(MISCREG_DASICS_MAIN_CALL_ENTRY),
            xc->readMiscReg(MISCREG_DASICS_RETURN_PC),
            xc->readMiscReg(MISCREG_DASICS_ACTIVE_ZONE_RETURN_PC),
            vaddrBits)) {
        return NoFault;
    }

    return std::make_shared<DasicsFault>(mode, DasicsFaultReason::Jump,
                                         target);
}

Fault
dasicsMemAccessCheck(ExecContext *xc, Addr address, unsigned size,
                     bool isWrite, unsigned vaddrBits)
{
    if (dasicsInstIsTrusted(xc, vaddrBits)) {
        return NoFault;
    }

    // An untrusted result implies enabled, non-virtualized U/S execution.
    const auto mode = static_cast<PrivilegeMode>(xc->readMiscReg(MISCREG_PRV));
    const DasicsMainCfg config = xc->readMiscReg(MISCREG_DASICS_MAIN_CFG);
    bool checkDisabled;
    if (mode == PRV_U) {
        checkDisabled = isWrite ? static_cast<bool>(config.cust)
                                : static_cast<bool>(config.cult);
    } else {
        checkDisabled = isWrite ? static_cast<bool>(config.csst)
                                : static_cast<bool>(config.cslt);
    }
    if (checkDisabled) {
        return NoFault;
    }

    const std::array<DasicsAddrRange, 16> bounds = {{
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO0),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI0)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO1),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI1)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO2),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI2)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO3),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI3)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO4),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI4)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO5),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI5)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO6),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI6)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO7),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI7)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO8),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI8)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO9),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI9)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO10),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI10)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO11),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI11)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO12),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI12)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO13),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI13)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO14),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI14)},
        {xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_LO15),
         xc->readMiscReg(MISCREG_DASICS_LIB_BOUND_HI15)},
    }};
    if (dasicsMemAccessIsAllowed(address, size, isWrite,
                                 xc->readMiscReg(MISCREG_DASICS_LIB_CFG),
                                 bounds)) {
        return NoFault;
    }

    const auto reason =
        isWrite ? DasicsFaultReason::Store : DasicsFaultReason::Load;
    return std::make_shared<DasicsFault>(mode, reason, address);
}

Fault
dasicsEcallAccessCheck(ExecContext *xc, unsigned vaddrBits)
{
    if (dasicsInstIsTrusted(xc, vaddrBits)) {
        return NoFault;
    }

    // An untrusted result implies enabled, non-virtualized U/S execution.
    const auto mode = static_cast<PrivilegeMode>(xc->readMiscReg(MISCREG_PRV));
    const DasicsMainCfg config = xc->readMiscReg(MISCREG_DASICS_MAIN_CFG);
    const bool checkDisabled = mode == PRV_U ? static_cast<bool>(config.cuet)
                                             : static_cast<bool>(config.cset);
    if (checkDisabled) {
        return NoFault;
    }

    return std::make_shared<DasicsFault>(mode, DasicsFaultReason::Ecall, 0);
}
#endif // USE_DASICS

} // namespace RiscvISA
} // namespace gem5
