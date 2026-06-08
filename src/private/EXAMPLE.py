"""Example custom section — copy this to a new module to add your own.

This is a deliberately generic template. Custom sections you create here (other
than this committed EXAMPLE) are gitignored, so they stay private to you.

To activate a section, add it in src/analyzer.py `_load_private_sections()`:

    from .private import example
    out.append((example.SECTION_ID, example.ORDER, example.INSTRUCTIONS))
"""

from __future__ import annotations

# Short slug. Also becomes the <!--SECTION:example--> marker the model emits,
# which lets the archive layer strip this section before publishing publicly.
SECTION_ID = "example"

# Where this section appears. Public sections are Pulse=10, Stack=30, Deep=40.
# Pick a number to slot it between them (e.g. 20 = right after the Pulse).
ORDER = 20

# The prompt block for this section. MUST begin with the marker line and an <h2>
# whose text ends with a "(N min read)" budget — matching the house style.
INSTRUCTIONS = """\
<!--SECTION:example-->
<h2>🧩 Example Section — Replace Me (2 min read)</h2>
Describe exactly what you want the model to produce here. Use bullets, name the
<h3> sub-blocks, and specify the format precisely. Every factual claim must carry
an <a href="..."> link, same as the rest of the briefing.

<h3>Sub-block A</h3>
A <ul> of 3–5 bullets doing X.

<h3>Sub-block B</h3>
A short <p> doing Y."""
