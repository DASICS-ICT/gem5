/* SPDX-License-Identifier: BSD-3-Clause */
#include <errno.h>
#include <qemu-plugin.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

/* The argument order determines the layout of each vCPU's counter array. */
static uint64_t *pcs;
static size_t num_pcs;
static struct qemu_plugin_scoreboard *counts;

static qemu_plugin_u64
counter(size_t i)
{
    return (qemu_plugin_u64){counts, i * sizeof(uint64_t)};
}

static void
translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    size_t insns = qemu_plugin_tb_n_insns(tb);
    for (size_t i = 0; i < insns; ++i) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint64_t pc = qemu_plugin_insn_vaddr(insn);
        for (size_t j = 0; j < num_pcs; ++j) {
            if (pc == pcs[j]) {
                qemu_plugin_register_vcpu_insn_exec_inline_per_vcpu(
                    insn, QEMU_PLUGIN_INLINE_ADD_U64, counter(j), 1);
                break;
            }
        }
    }
}

static void
report(qemu_plugin_id_t id, void *opaque)
{
    for (size_t i = 0; i < num_pcs; ++i) {
        char line[64];
        snprintf(line, sizeof(line), "0x%" PRIx64 " %" PRIu64 "\n", pcs[i],
                 qemu_plugin_u64_sum(counter(i)));
        qemu_plugin_outs(line);
    }
    qemu_plugin_scoreboard_free(counts);
    free(pcs);
}

QEMU_PLUGIN_EXPORT int
qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info, int argc,
                    char **argv)
{
    if (argc < 1) {
        return -1;
    }
    pcs = calloc(argc, sizeof(*pcs));
    if (!pcs) {
        return -1;
    }
    for (int i = 0; i < argc; ++i) {
        char *end;
        const char *value = strchr(argv[i], '=');
        if (!value || value == argv[i] || strncmp(value + 1, "0x", 2)) {
            free(pcs);
            return -1;
        }
        ++value;
        errno = 0;
        pcs[i] = strtoull(value, &end, 0);
        if (errno || end == value || *end || !pcs[i]) {
            free(pcs);
            return -1;
        }
    }
    num_pcs = argc;
    counts = qemu_plugin_scoreboard_new(num_pcs * sizeof(uint64_t));
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, report, NULL);
    return 0;
}
