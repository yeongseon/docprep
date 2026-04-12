# Contributing to docprep

Thank you for your interest in contributing to docprep! This guide covers everything you need to get started.

## Development Setup

### Prerequisites

- Python 3.11 or later
- Git
- Make (optional, but recommended)

### Clone and Install

```bash
git clone https://github.com/yeongseon/docprep.git
cd docprep
make install
```

This creates a virtual environment, installs [Hatch](https://hatch.pypa.io/) as the build tool, sets up the development environment with all dependencies, and installs pre-commit hooks.

If you don't have Make:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install hatch
hatch env create
```

### Verify Setup

```bash
make check-all
```

This runs linting (ruff), type checking (mypy --strict), tests (pytest), and security scanning (bandit).

## Development Workflow

### Running Commands

| Command | Description |
|---------|-------------|
| `make test` | Run pytest |
| `make lint` | Run ruff + mypy |
| `make format` | Auto-format with ruff |
| `make typecheck` | Run mypy strict |
| `make security` | Run bandit security scan |
| `make check` | Lint + typecheck |
| `make check-all` | Lint + typecheck + test + security |
| `make cov` | Generate coverage report |
| `make build` | Build wheel and sdist |

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:

- **ruff format** — code formatting
- **ruff check** — linting with auto-fix
- **mypy --strict** — type checking
- **bandit** — security scanning

If hooks fail, fix the issues and commit again. To run hooks manually:

```bash
make precommit
```

### Code Style

docprep follows these conventions:

- **Formatter**: ruff (line length 100)
- **Linter**: ruff with `E`, `F`, `I` rules
- **Type checker**: mypy strict mode — **all code must be fully typed**
- **Import order**: isort via ruff (standard library → third-party → first-party)

Key rules:
- No `# type: ignore` without explanation
- No `Any` types without justification
- All public functions and classes need docstrings
- Frozen dataclasses with `kw_only=True` and `slots=True` for domain types
- Protocol classes for component interfaces (Loader, Parser, Chunker, Sink)

### Project Structure

```
src/docprep/          # Main package
tests/                # Test suite (mirrors src/ structure)
docs/                 # Documentation
examples/             # Usage examples
```

Tests live in `tests/` and follow the naming convention `test_<module>.py`. Use `tests/conftest.py` for shared fixtures.

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature
```

### 2. Make Your Changes

- Write code following existing patterns
- Add or update tests
- Ensure type annotations are complete
- Update documentation if needed

### 3. Run Checks

```bash
make check-all
```

All of the following must pass:
- `ruff check` — no lint errors
- `ruff format --check` — properly formatted
- `mypy --strict` — no type errors
- `pytest` — all tests pass
- `bandit` — no security issues

### 4. Commit

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add support for RST table extraction
fix: handle empty frontmatter in markdown parser
docs: update CLI reference for export command
refactor: extract heading normalization to ids module
test: add edge cases for token chunker overlap
build: bump ruff to 0.8
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`

### 5. Open a Pull Request

- Write a clear description of what changed and why
- Reference any related issues
- Ensure CI passes

## Testing

### Running Tests

```bash
# All tests
make test

# Specific file
hatch run pytest tests/test_ingest.py -v

# Specific test
hatch run pytest tests/test_ingest.py::test_ingest_single_file -v

# With coverage
make cov
```

### Writing Tests

- Use `pytest` with fixtures from `conftest.py`
- Use `hypothesis` for property-based testing where appropriate
- Test both success and error paths
- Use frozen dataclasses for test data
- Keep tests focused — one assertion per test where practical

### Test Coverage

Coverage threshold is **90%**. Check coverage with:

```bash
make cov
# Open htmlcov/index.html for detailed report
```

## Architecture Guidelines

### Adding a New Component

1. **Define the protocol** in `<component>/protocol.py` if it doesn't exist
2. **Implement** the component following existing patterns
3. **Register** as a built-in in `registry.py` and `config.py`
4. **Add entry point** in `pyproject.toml`
5. **Write tests** covering normal operation, edge cases, and error handling
6. **Update documentation** in relevant docs/ files

### Adding a New CLI Command

1. Add the command function in `cli/main.py`
2. Register it with the argument parser
3. Add tests in `tests/test_cli.py`
4. Update `docs/cli-reference.md`

### Domain Types

All domain types live in `models/domain.py`:
- Use `@dataclass(frozen=True, kw_only=True, slots=True)`
- Use `tuple[...]` instead of `list[...]` for immutable collections
- Use `str` enums (via `StrEnum`) for categorical values

## Reporting Issues

Use [GitHub Issues](https://github.com/yeongseon/docprep/issues) to report bugs or request features.

For bugs, include:
- docprep version (`docprep --version` or `python -c "import docprep; print(docprep.__version__)"`)
- Python version
- Operating system
- Minimal reproduction steps
- Full error traceback

## License

By contributing to docprep, you agree that your contributions will be licensed under the [MIT License](../LICENSE).
