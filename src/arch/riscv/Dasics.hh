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

/** Raw lower/upper CSR values; each checker supplies its comparison rules. */
struct DasicsAddrRange
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
                               const std::array<DasicsAddrRange, 4> &bounds,
                               Addr mainCallEntry, Addr returnPc,
                               Addr activeZoneReturnPc, unsigned vaddrBits);

/**
 * Authorize a complete scalar access using one of the 16 data bounds.
 * size is a byte count of 1, 2, 4, or 8; other sizes and address wraparound
 * are rejected. Compare full 64-bit virtual addresses without discarding
 * access-address low bits; bound CSR values have bits [2:0] cleared.
 * A single valid entry must cover the entire access and permit the read or
 * write. The reserved U bit does not affect permission. The caller handles
 * privilege, source trust, check enables, alignment, and exception delivery.
 */
bool dasicsMemAccessIsAllowed(Addr address, unsigned size, bool isWrite,
                              RegVal libCfg,
                              const std::array<DasicsAddrRange, 16> &bounds);

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

/**
 * Authorize DASICSCALL in an enabled, non-virtualized U/S domain.
 * The source PC must be trusted. M mode and disabled protection do not
 * authorize this instruction.
 * The caller handles decoding; machInst supplies the original encoding for
 * an ordinary illegal-instruction fault. This check does not change the PC,
 * link register, ReturnPC, FReason, or any other architectural state.
 */
Fault dasicsCallAccessCheck(ExecContext *xc, ExtMachInst machInst,
                            unsigned vaddrBits);

/**
 * Check a resolved control transfer while xc still holds the source PC.
 * taken is the actual branch outcome, even when target is the next PC.
 * The caller supplies the ISA-resolved target, including JALR bit 0 clearing.
 * A rejected transfer returns a fault carrying the full target address;
 * this check does not change architectural state.
 */
Fault dasicsJumpAccessCheck(ExecContext *xc, Addr target, bool taken,
                            unsigned vaddrBits);

/**
 * Check an ordinary scalar access against the current S/U data permissions.
 * address is the original effective virtual address; size is a byte count.
 * vaddrBits applies only to source-PC trust, not the data-address comparison.
 * Privilege, source trust, and the matching load/store close bit can bypass
 * the check. A rejection carries the original address in a DasicsFault;
 * this function does not access memory or change architectural state.
 */
Fault dasicsMemAccessCheck(ExecContext *xc, Addr address, unsigned size,
                           bool isWrite, unsigned vaddrBits);

/**
 * Check ECALL from an enabled, untrusted, non-virtualized U/S domain.
 * CUET/CSET close bits bypass the check for the corresponding domain.
 * NoFault leaves ordinary ECALL handling to the caller. A rejection carries
 * the Ecall reason and a zero trap value; only fault delivery writes FReason.
 * This check does not change architectural state.
 */
Fault dasicsEcallAccessCheck(ExecContext *xc, unsigned vaddrBits);
#endif // USE_DASICS

} // namespace RiscvISA
} // namespace gem5

#endif // __ARCH_RISCV_DASICS_HH__
