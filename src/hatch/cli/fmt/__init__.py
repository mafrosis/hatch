from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from hatch.cli.application import Application


@click.command(short_help='Format and lint source code', context_settings={'ignore_unknown_options': True})
@click.argument('args', nargs=-1)
@click.option('--check', is_flag=True, help='Only check for errors rather than fixing them')
@click.option('--linter', '-l', is_flag=True, help='Only run the linter')
@click.option('--formatter', '-f', is_flag=True, help='Only run the formatter')
@click.option('--sync', is_flag=True, help='Sync the default config file with the current version of Hatch')
@click.pass_obj
def fmt(
    app: Application,
    *,
    args: tuple[str, ...],
    check: bool,
    linter: bool,
    formatter: bool,
    sync: bool,
):
    """Format and lint source code."""
    from hatch.cli.fmt.core import StaticAnalysisEnvironment

    if linter and formatter:
        app.abort('Cannot specify both --linter and --formatter')

    environment = app.get_environment('hatch-static-analysis')
    if not environment.exists():
        try:
            environment.check_compatibility()
        except Exception as e:  # noqa: BLE001
            app.abort(f'Environment is incompatible: {e}')

    sa_env = StaticAnalysisEnvironment(environment)

    # TODO: remove in a few minor releases, this is very new but we don't want to break users on the cutting edge
    if legacy_config_path := app.project.config.config.get('format', {}).get('config-path', ''):
        app.display_warning(
            'The `tool.hatch.format.config-path` option is deprecated and will be removed in a future release. '
            'Use `tool.hatch.envs.hatch-static-analysis.config-path` instead.'
        )
        sa_env.config_path = legacy_config_path

    if sync and not sa_env.config_path:
        app.abort('The --sync flag can only be used when the `tool.hatch.format.config-path` option is defined')

    scripts: list[str] = []
    if not formatter:
        scripts.append('lint-check' if check else 'lint-fix')

    if not linter:
        scripts.append('format-check' if check else 'format-fix')

    default_args = sa_env.get_default_args()
    arguments = list(args)
    try:
        arguments.remove('--preview')
    except ValueError:
        preview = False
    else:
        preview = True
        default_args.append('--preview')

    internal_args = environment.join_command_args(default_args)
    if internal_args:
        # Add an extra space if required
        internal_args = f' {internal_args}'

    with app.project.location.as_cwd({'HATCH_FMT_ARGS': internal_args}):
        if not sa_env.config_path or sync:
            sa_env.write_config_file(preview=preview)

        formatted_args = environment.join_command_args(arguments)
        app.prepare_environment(environment)
        app.run_shell_commands(
            environment,
            [f'{script} {formatted_args}' for script in scripts],
            show_code_on_error=False,
            hide_commands=True,
        )
