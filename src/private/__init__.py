"""Private, user-specific digest sections.

Drop a module here that defines a custom briefing section and it will be merged
into the digest automatically — no edits to the core needed. A public clone of
this repo has no private modules beyond this scaffolding, so it produces the
briefing without them.

Contract — a section module must define three module-level names:

    SECTION_ID   : str   # short slug, also the <!--SECTION:id--> marker
    ORDER        : int   # position among sections (Pulse=10, Stack=30, Deep=40)
    INSTRUCTIONS : str   # the prompt block for this section (see EXAMPLE.py)

Then register it in src/analyzer.py `_load_private_sections()` with one line:

    from .private import your_module
    out.append((your_module.SECTION_ID, your_module.ORDER, your_module.INSTRUCTIONS))

See EXAMPLE.py for a working template.
"""
