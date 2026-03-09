import nox

nox.options.sessions = ["lint", "typecheck", "test"]
nox.options.stop_on_first_error = False


@nox.session
def lint(session: nox.Session) -> None:
    """Check code with ruff."""
    session.run("uv", "run", "ruff", "check", "src", "tests", external=True)
    session.run("uv", "run", "ruff", "format", "--check", "src", "tests", external=True)


@nox.session
def format(session: nox.Session) -> None:
    """Format code with ruff."""
    session.run("uv", "run", "ruff", "format", "src", "tests", external=True)


@nox.session
def typecheck(session: nox.Session) -> None:
    """Type check with pyright."""
    session.run("uv", "run", "pyright", external=True)


@nox.session
def fix(session: nox.Session) -> None:
    """Auto-fix lint issues and format code."""
    session.run("uv", "run", "ruff", "check", "--fix", "src", "tests", external=True)
    session.run("uv", "run", "ruff", "format", "src", "tests", external=True)


@nox.session
def test(session: nox.Session) -> None:
    """Run tests."""
    session.run("uv", "run", "pytest", "-v", external=True)


@nox.session
def coverage(session: nox.Session) -> None:
    """Run tests with coverage."""
    session.run("uv", "run", "pytest", "--cov=src", "--cov-report=term", "-v", external=True)


@nox.session
def ci(session: nox.Session) -> None:
    """Run the full CI pipeline."""
    session.run("uv", "run", "ruff", "check", "src", "tests", external=True)
    session.run("uv", "run", "ruff", "format", "--check", "src", "tests", external=True)
    session.run("uv", "run", "pyright", external=True)
    session.run("uv", "run", "pytest", "--cov=src", "-v", external=True)
