# Repository Guidelines

## Project Structure & Module Organization

This repository is an AstrBot RSSHub plugin. `main.py` is the plugin entry point, `metadata.yaml` defines plugin metadata, and `requirements.txt` lists Python dependencies.

- `src/domain/`: entities, value objects, repository protocols, and pure business services.
- `src/application/`: commands, queries, DTOs, and orchestration services.
- `src/infrastructure/`: config, persistence, RSS fetching, messaging, scheduling, translation, media, and utilities.
- `src/interfaces/`: chat command handlers and Web API adapters.
- `pages/`: AstrBot plugin page frontend assets.
- `tests/`: unit tests, integration tests, fixtures, and mocks.
- `assets/`, `docs/`, `skills/`: images, project notes, and local workflow resources.

## Build, Test, and Development Commands

Run these from the plugin directory unless noted:

```bash
python tests/run_tests.py -v
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
pytest tests/ -v
```

When working from the AstrBot project root, format and lint this plugin with:

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

Pre-commit runs YAML checks, whitespace cleanup, `ruff --fix`, and `ruff-format`.

## Coding Style & Naming Conventions

Use Python 3.10+ conventions, 4-space indentation, and type hints for public functions. Keep `main.py` limited to lifecycle, registration, and dependency wiring. Put business rules in `src/domain/` or `src/application/`; put framework, storage, network, and platform details in `src/infrastructure/` or `src/interfaces/`.

Use `snake_case` for files, functions, and variables; `PascalCase` for classes. Command/query classes should read like actions, for example `SubscribeFeedCommand` or `GetSubscriptionsQuery`.

## Testing Guidelines

Tests use the custom runner in `tests/run_tests.py` and pytest-compatible files under `tests/unit/` and `tests/integration/`. Name test files `test_*.py`. Prefer focused unit tests for domain and application behavior. Use integration tests for database, scheduler, fetcher, Web API, and plugin wiring changes. Reuse fixtures from `tests/fixtures/` and mocks from `tests/mocks/`.

## Commit & Pull Request Guidelines

Follow the existing Conventional Commits style: `feat: ...`, `fix: ...`, or scoped forms like `feat(rss): ...`. Keep commits focused and describe user-visible behavior when relevant.

Pull requests should include a concise summary, test commands run, linked issues if applicable, and screenshots or recordings for WebUI changes.

## Agent-Specific Instructions

Treat current code, tests, README, and `CONTRIBUTE.md` as the source of truth when details conflict. Before editing, inspect the relevant modules and preserve existing user changes in the working tree. Keep edits scoped to the requested task, and update tests or documentation when behavior, commands, configuration, or WebUI surfaces change.
