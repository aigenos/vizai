# Private sections

This folder is an extension point. Modules you add here define **custom briefing
sections** that get merged into the daily digest automatically.

Everything in this folder is **gitignored** except `__init__.py`, `EXAMPLE.py`,
and this README — so your custom section prompts stay on your machine and never
end up in the public repo or the published archive.

## Add a section

1. Copy `EXAMPLE.py` to a new file, e.g. `my_section.py`.
2. Edit `SECTION_ID`, `ORDER`, and `INSTRUCTIONS`.
3. Register it in [`../analyzer.py`](../analyzer.py) inside
   `_load_private_sections()`:
   ```python
   from .private import my_section
   out.append((my_section.SECTION_ID, my_section.ORDER, my_section.INSTRUCTIONS))
   ```

That's it. The section now appears in the digest at its `ORDER` position, and is
automatically **stripped from the public archive** (via its `<!--SECTION:id-->`
marker) so it stays private even when you publish the rest.

## Why it works this way

The digest's instruction prompt is composed from a list of section blocks. Public
sections live in `analyzer.py`; private ones load from here at runtime. A public
clone has no private modules, so it simply produces the briefing without them —
the prompt logic for your private sections is never in the public tree.
