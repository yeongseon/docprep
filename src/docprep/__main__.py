"""Allow running docprep as ``python -m docprep``."""

from docprep.cli.main import main

raise SystemExit(main())
