#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Prepare the protected SoPlex sources outside the ordinary build."""

import sys
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one source match for {old!r}")
    return text.replace(old, new)


def prepare(case, overlay, layout_names):
    sources = case / "src"
    if not (sources / "mpsinput.h").is_file():
        raise ValueError(f"missing SoPlex sources in {sources}")

    # Every translation unit that saw the original class layout must be rebuilt.
    consumers = set()
    for source in sources.glob("*.cc"):
        deps = case / "build" / "objects" / "src" / (source.stem + ".d")
        if any(
            Path(dep).name == "mpsinput.h" for dep in deps.read_text().split()
        ):
            consumers.add(source.stem)
    if consumers != set(layout_names):
        raise ValueError(f"MPSInput layout is used by {sorted(consumers)}")

    header = (sources / "mpsinput.h").read_text()
    header = replace_once(
        header, "char            m_buf[", "alignas(8) char m_buf["
    )
    source = (sources / "mpsinput.cc").read_text()
    source = replace_once(
        source,
        '#include "mpsinput.h"',
        '#include "mpsinput.h"\n\n'
        'extern "C" char* SOPLEX_DATA_STRTOK(char*, const char*, char*);',
    )
    for field in range(1, 6):
        arg = "s" if field == 1 else "0"
        source = replace_once(
            source,
            f'(m_f{field} = strtok({arg}, " "))',
            f'(m_f{field} = SOPLEX_DATA_STRTOK({arg}, " ", m_buf))',
        )

    overlay.mkdir(parents=True, exist_ok=True)
    (overlay / "mpsinput.h").write_text(header)
    for name in layout_names:
        file = name + ".cc"
        content = (
            source if name == "mpsinput" else (sources / file).read_text()
        )
        (overlay / file).write_text(content)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
