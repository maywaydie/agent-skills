# agent-skills

Подобранный набор скилов для Claude Code, Codex, Cursor и OpenCode. Скилы взяты с GitHub, сами
обновляются и проверяются на конфликты. Формат стандартный: папка со `SKILL.md`, поэтому один и тот же
набор работает во всех агентах.

## Как это устроено

```
skills.toml            что брать и откуда: репозиторий, ветка, путь, домен (одна задача на скил)
skills.lock.json       точный коммит и хэш каждого скила (воспроизводимо, видно, что поменялось)
skills/<name>/         копии скилов + SOURCE.md (откуда, какой коммит, лицензия)
CHANGELOG.md           каждое обновление со ссылкой на diff в upstream
tools/skillsync.py     update | check | status | diff | install | uninstall | schedule
tools/auto_update.py   запуск по расписанию: update → commit → install, лог в .cache/auto-update.log
```

`~/.claude/skills/<name>` и `~/.agents/skills/<name>` — это junction-ссылки на `skills/<name>`. После
обновления репозитория агенты сразу видят новые версии, копировать ничего не нужно.

## Как скилы не мешают друг другу

`python tools/skillsync.py check` не пропускает набор, если:

- два скила имеют одно имя (в том числе с чужим скилом, уже лежащим в `~/.claude/skills`). Чтобы
  развести имена, в манифесте задаётся `as = "новое-имя"`;
- два скила заявлены на один `domain`. На каждую задачу должен быть один скил, иначе агент выбирает
  между ними случайно;
- у скила нет `description` (агент его никогда не выберет) или нет лицензии;
- скопированный скил правили руками (хэш не совпадает с lock). Свои правки нужно оформлять отдельным
  локальным скилом.

Если описания двух скилов совпадают по словам больше чем на 30%, `check` выдаёт предупреждение.

`install` трогает только свои ссылки. Если чужая папка мешает установке, `install` об этом сообщает и
оставляет её на месте.

## Как они остаются актуальными

- **Локально.** Задача Планировщика Windows `agent-skills-update` раз в 12 часов запускает
  `tools/auto_update.py`. Если upstream сдвинулся, файлы копируются, коммит пишется в lock и в
  `CHANGELOG.md`, изменение коммитится в git.
- **Проверка кода.** У источников с `trust = "review"` изменения в скриптах и конфигах (всё, кроме
  `.md` и картинок) не применяются автоматически. Скил остаётся на старом коммите со статусом `held`.
  Посмотреть изменения: `skillsync.py diff <name> --full`. Принять: `skillsync.py update --approve <name>`.
  Для проверки удобно использовать скил `skill-scanner`.
- **На GitHub.** Если опубликовать репозиторий, `.github/workflows/update-skills.yml` будет раз в день
  открывать PR с обновлениями. Ревью PR заменяет удержание `held`.

## Команды

```bash
python tools/skillsync.py status --remote   # что стоит и что отстало от upstream
python tools/skillsync.py update            # подтянуть всё (или: update <name> ...)
python tools/skillsync.py check             # валидация набора
python tools/skillsync.py install           # ссылки в ~/.claude/skills и ~/.agents/skills
python tools/skillsync.py schedule          # (пере)создать задачу автообновления; --remove чтобы убрать
```

Нужны только Python 3.11+ и git. Сторонние пакеты не требуются.

## Добавить скил

Добавьте блок `[[skill]]` (и при необходимости `[sources.*]`) в `skills.toml`, затем выполните
`update <name>`, `check` и `install`. Можно просто попросить агента: скил `skills-curator` знает
порядок действий.

Свои скилы кладите в `skills/<name>/` и отмечайте `local = true` в манифесте. Обновления их не трогают.

## Для других людей

- Через skills CLI: `npx skills add maywaydie/agent-skills -g` (находит `skills/*/SKILL.md`).
- Как плагин Claude Code: `/plugin marketplace add maywaydie/agent-skills`, затем
  `/plugin install agent-skills@agent-skills`. Файлы `.claude-plugin/` генерируются при `update`.
- Или клонировать и выполнить `python tools/skillsync.py install`.

## Скилы

Таблица ниже генерируется при `update`.

<!-- skills:start -->
| Skill | Domain | Source | Commit |
| --- | --- | --- | --- |
| `tool-design` | agent-tool-design | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | [9ff0c991](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/tree/9ff0c99108b36d3b886defd825d8ac1f47dba374/skills/tool-design) |
| `anti-reversing-techniques` | anti-reversing | [wshobson/agents](https://github.com/wshobson/agents) | [9c61ab24](https://github.com/wshobson/agents/tree/9c61ab243def98f72da12abd41cfcf5bcd91af9d/plugins/reverse-engineering/skills/anti-reversing-techniques) |
| `context-optimization` | context-management | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | [9ff0c991](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/tree/9ff0c99108b36d3b886defd825d8ac1f47dba374/skills/context-optimization) |
| `analyze-dump` | crash-dump-analysis | [svnscha/mcp-windbg](https://github.com/svnscha/mcp-windbg) | [cf308c23](https://github.com/svnscha/mcp-windbg/tree/cf308c236e497ffaa613c54fc38babfa7da59409/plugins/mcp-windbg-skills/skills/analyze-dump) |
| `systematic-debugging` | debugging | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging) |
| `hallmark` | frontend-design | [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | [04977e15](https://github.com/Nutlope/hallmark/tree/04977e15f3dfd6ee4b74c887dac3eb52665d6c92/skills/hallmark) |
| `ghidra` | ghidra-headless | [mitsuhiko/agent-stuff](https://github.com/mitsuhiko/agent-stuff) | [0865c849](https://github.com/mitsuhiko/agent-stuff/tree/0865c849befd2021490679f96a8dee58c84ac857/skills/ghidra) |
| `finishing-a-development-branch` | git-branch-finish | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/finishing-a-development-branch) |
| `using-git-worktrees` | git-worktrees | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/using-git-worktrees) |
| `hypervisor-internals` | hypervisor | [mohitmishra786/low-level-dev-skills](https://github.com/mohitmishra786/low-level-dev-skills) | [d0d0a13d](https://github.com/mohitmishra786/low-level-dev-skills/tree/d0d0a13d4e3caec7afb2d647a1fffdb7cb1ee058/skills/virtualization/hypervisor-internals) |
| `idapython` | ida-scripting | [mrexodia/ida-pro-mcp](https://github.com/mrexodia/ida-pro-mcp) | [13e480cb](https://github.com/mrexodia/ida-pro-mcp/tree/13e480cb1198f923154b63669e8cb2faee5deaea/skills/idapython) |
| `brainstorming` | ideation | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming) |
| `debugview` | kernel-debug-output | [microsoft/skills](https://github.com/microsoft/skills) | [b35d2c60](https://github.com/microsoft/skills/tree/b35d2c60fac796bfd2cfd14ad3f550c73e92d9bb/.github/skills/debugview) |
| `kernel-debug` | kernel-debugging | [svnscha/mcp-windbg](https://github.com/svnscha/mcp-windbg) | [cf308c23](https://github.com/svnscha/mcp-windbg/tree/cf308c236e497ffaa613c54fc38babfa7da59409/plugins/mcp-windbg-skills/skills/kernel-debug) |
| `mcp-builder` | mcp-servers | [anthropics/skills](https://github.com/anthropics/skills) | [e4bb5d96](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/mcp-builder) |
| `node-best-practices` | nodejs | [mcollina/skills](https://github.com/mcollina/skills) | [c75d70db](https://github.com/mcollina/skills/tree/c75d70dbfbe991d8cec42aeda0b64ff14fbb9ac7/skills/node) |
| `dispatching-parallel-agents` | parallel-agents | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/dispatching-parallel-agents) |
| `executing-plans` | plan-execution | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/executing-plans) |
| `writing-plans` | planning | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/writing-plans) |
| `uv` | python-env | [astral-sh/claude-code-plugins](https://github.com/astral-sh/claude-code-plugins) | [855418fb](https://github.com/astral-sh/claude-code-plugins/tree/855418fb9ebfada49a8345a5c3ada9db2cdc2419/plugins/astral/skills/uv) |
| `ruff` | python-lint | [astral-sh/claude-code-plugins](https://github.com/astral-sh/claude-code-plugins) | [855418fb](https://github.com/astral-sh/claude-code-plugins/tree/855418fb9ebfada49a8345a5c3ada9db2cdc2419/plugins/astral/skills/ruff) |
| `reverse-engineer-anything` | reverse-engineering | [morluto/rea](https://github.com/morluto/rea) | [b7461b7b](https://github.com/morluto/rea/tree/b7461b7b14dcc3ec47798b60ce06d63ae6324e06/.agents/skills/reverse-engineer-anything) |
| `receiving-code-review` | review-feedback | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/receiving-code-review) |
| `codeql` | sast-codeql | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/static-analysis/skills/codeql) |
| `semgrep` | sast-semgrep | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/static-analysis/skills/semgrep) |
| `skills-curator` | skill-collection | local | - |
| `find-skills` | skill-discovery | [vercel-labs/skills](https://github.com/vercel-labs/skills) | [57217cf8](https://github.com/vercel-labs/skills/tree/57217cf86ba38148a57af9e90d14a4c049558330/skills/find-skills) |
| `skill-scanner` | skill-security-scan | [getsentry/skills](https://github.com/getsentry/skills) | [a582c51e](https://github.com/getsentry/skills/tree/a582c51ee29d0f35e6ac321340796f77d43da733/skills/skill-scanner) |
| `subagent-driven-development` | subagent-execution | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development) |
| `test-driven-development` | tdd | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development) |
| `variant-analysis` | variant-analysis | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/variant-analysis/skills/variant-analysis) |
| `verification-before-completion` | verification | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion) |
| `webapp-testing` | web-e2e-testing | [anthropics/skills](https://github.com/anthropics/skills) | [e4bb5d96](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/webapp-testing) |
<!-- skills:end -->

## Что сознательно не взято

| Кандидат | Почему |
| --- | --- |
| `pbakaus/impeccable` | В описании заявлено «design, redesign … landing pages», это пересекается с hallmark на новых страницах |
| `josiahsiegel/powershell-master` | Требует включаться на любую задачу с PowerShell и навязывает правило про пути в Edit/Write; последнее обновление было 5 месяцев назад |
| `OthmanAdi/planning-with-files` | Регистрирует хуки на каждый Write/Edit/Bash; пересекается с `writing-plans` |
| `addyosmani/agent-skills`, `mattpocock/skills` | Полные наборы для workflow: пересекаются с superpowers и совпадают с ним по именам |
| `superpowers: requesting-code-review`, `writing-skills` | Дублируют встроенные `code-review` и `skill-creator` |
| `trailofbits: c-review`, `fp-check`, `modern-python` | `c-review` не предназначен для драйверов и зависит от плагина, `fp-check` ставит хуки Stop, `modern-python` вытеснен официальными скилами Astral |
| `ergrelet/windiff` | Работает только внутри checkout WinDiff, лицензия GPL-3.0 |
| `vmware-skills/VMware-AIops` | Нужен PyPI-пакет с учётными данными vCenter, один мейнтейнер |
| `anthropics: docx/pdf/pptx/xlsx`, `skill-creator` | Уже встроены и распространяются по проприетарной лицензии |

Лицензии остаются у авторов (файлы `LICENSE*` в каждой папке). Скилы trailofbits распространяются по
CC-BY-SA-4.0: изменённые копии должны выходить под той же лицензией и с указанием авторства.
