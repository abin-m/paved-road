"""Claude Code with the paved-road pack installed, for the "with" arm.

Harbor's built-in claude-code agent is the "without" arm. This class runs it
unchanged, except that before the task starts it copies this checkout's
marketplace into the container and installs the plugin the way a user does:

    claude plugin marketplace add /opt/paved-road
    claude plugin install paved-road-core@paved-road

The install goes into the trial's own CLAUDE_CONFIG_DIR, the one Harbor's
agent then runs with. The output is kept in the trial's agent logs.

    harbor run -p bench/harbor/tasks -a bench.harbor.agent:PavedRoadClaudeCode ...
"""

from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode

ROOT = Path(__file__).resolve().parents[2]
REMOTE = "/opt/paved-road"


class PavedRoadClaudeCode(ClaudeCode):
    async def run(self, instruction, environment, context) -> None:
        await environment.upload_dir(ROOT / ".claude-plugin", f"{REMOTE}/.claude-plugin")
        await environment.upload_dir(ROOT / "paved-road-core", f"{REMOTE}/paved-road-core")
        log = (self.environment_logs_dir / "paved-road-install.txt").as_posix()
        await self.exec_as_agent(
            environment,
            command=(
                'export PATH="$HOME/.local/bin:$PATH"; set -euo pipefail; '
                f"mkdir -p $CLAUDE_CONFIG_DIR; "
                f"{{ claude plugin marketplace add {REMOTE} && "
                "claude plugin install paved-road-core@paved-road && "
                f"claude plugin list; }} 2>&1 | tee {log}"
            ),
            env={
                "CLAUDE_CONFIG_DIR": (self.environment_logs_dir / "sessions").as_posix(),
                "IS_SANDBOX": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            },
        )
        await super().run(instruction, environment, context)
