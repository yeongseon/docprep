# docprep Plugin Template

A minimal starting point for building a docprep plugin.

## What's Included

- `src/my_docprep_plugin/chunker.py` — A sentence-based chunker implementation
- `tests/test_chunker.py` — Protocol conformance and behavior tests
- `pyproject.toml` — Package config with entry-point registration

## Getting Started

1. Copy this template:

   ```bash
   cp -r examples/plugin-template my-docprep-plugin
   cd my-docprep-plugin
   ```

2. Rename `my_docprep_plugin` to your package name and update `pyproject.toml`.

3. Install in editable mode:

   ```bash
   pip install -e .
   ```

4. Verify discovery:

   ```python
   from docprep import get_all_chunkers
   print(get_all_chunkers())  # Should include "sentence"
   ```

5. Use in `docprep.toml`:

   ```toml
   [[chunkers]]
   type = "sentence"
   ```

## See Also

- [Plugin System docs](../../docs/plugins.md)
- [Full plugin example](../custom_plugin.py) — ParagraphChunker with demo script
