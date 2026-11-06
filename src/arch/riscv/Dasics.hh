/* SPDX-License-Identifier: BSD-3-Clause */

#ifndef __ARCH_RISCV_DASICS_HH__
#define __ARCH_RISCV_DASICS_HH__

#include <array>

#include "arch/riscv/types.hh"
#include "base/types.hh"
#include "config/use_dasics.hh"

namespace gem5
{

class ExecContext;

namespace RiscvISA
{

#if USE_DASICS
/**
 * Classify decoded CSR instructions for a squash after successful commit.
 * Uses architectural write intent, including writes of an unchanged value.
 * CSRRS/CSRRC with rs1=x0 and their zero-immediate forms are read-only.
 */
bool dasicsCsrNeedsSquash(ExtMachInst machInst);

/**
 * Check the PC against one domain's half-open main bound.
 * Disabled protection treats every PC as trusted. Comparisons use address
 * bits [vaddrBits - 1:3]; vaddrBits is the implemented comparator width,
 * independent of the active address translation mode.
 */
bool dasicsPcIsTrusted(Addr pc, bool enabled, Addr lower, Addr upper,
                       unsigned vaddrBits);

/** Raw CSR values for one half-open jump bound. */
struct DasicsJumpBound
{
    Addr lower = 0;
    Addr upper = 0;
};

/**
 * Match a target against four jump bounds or three special addresses.
 * JumpCfg bits 0, 16, 32, and 48 enable the corresponding bounds, whose
 * comparisons use bits [vaddrBits - 1:3]. Special addresses match exactly
 * in bits [vaddrBits - 1:0]; a zero special address remains matchable.
 * The caller handles privilege, source trust, enables, and branch outcome.
 */
bool dasicsJumpTargetIsAllowed(Addr target, RegVal jumpCfg,
                               const std::array<DasicsJumpBound, 4> &bounds,
                               Addr mainCallEntry, Addr returnPc,
                               Addr activeZoneReturnPc, unsigned vaddrBits);

/**
 * Check the current instruction using the non-virtualized S/U domain state.
 * The execution context supplies its PC, privilege, and architectural CSRs.
 */
bool dasicsInstIsTrusted(ExecContext *xc, unsigned vaddrBits);

/**
 * Check DASICS CSR access after ordinary CSR permission checks.
 * miscReg is the internal MISCREG index, not the architectural CSR address.
 * A rejected access returns an illegal-instruction fault without updating
 * FReason or any other architectural state.
 */
Fault dasicsCsrAccessCheck(ExecContext *xc, RegIndex miscReg,
                           ExtMachInst machInst, unsigned vaddrBits);
#endif // USE_DASICS

} // namespace RiscvISA
} // namespace gem5

#endif // __ARCH_RISCV_DASICS_HH__
