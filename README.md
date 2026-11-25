# agent-skills

Мой набор скилов для ИИ-агентов: Claude Code, Codex, Cursor, OpenCode. Я собрал его под то, чем
занимаюсь сам: реверс, отладка ядра Windows и гипервизоров, аудит кода, Python и Node, иногда фронтенд.
В набор вошли скилы из процесса разработки, которые помогают агенту не наломать дров: сначала план,
потом код, тесты и проверка, а не «готово!» на ровном месте.

Скилов в интернете много, но если поставить всё подряд, начинаются две беды. Скилы устаревают, а
похожие скилы перебивают друг друга, и агент выбирает между ними наугад. Этот репозиторий решает обе:
скилы обновляются сами, и на каждую задачу отвечает ровно один скил.

## Установка

Проще всего через [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add maywaydie/agent-skills -g
```

Или как плагин Claude Code:

```
/plugin marketplace add maywaydie/agent-skills
/plugin install agent-skills@agent-skills
```

Если хочется, чтобы скилы обновлялись сами, склонируйте репозиторий и поставьте ссылки:

```bash
git clone https://github.com/maywaydie/agent-skills
cd agent-skills
python tools/skillsync.py install    # ссылки в ~/.claude/skills и ~/.agents/skills
python tools/skillsync.py schedule   # git pull раз в 12 часов (Планировщик Windows)
```

Нужны только Python 3.11+ и git.

## Что внутри

- **Процесс работы**, из [superpowers](https://github.com/obra/superpowers): обсудить задачу → написать
  план → выполнить его самому или через субагентов → TDD → отладка по шагам → проверка перед словом
  «готово» → аккуратно закрыть ветку.
- **Реверс.** IDAPython, Ghidra без GUI, разбор антиотладки и VM-протекторов, REA.
- **Ядро Windows и гипервизоры.** Разбор крэш-дампов, живая отладка ядра через WinDbg, DbgPrint через
  DebugView, VT-x/AMD-V, EPT, VMEXIT.
- **Безопасность.** Semgrep, CodeQL, поиск других мест с тем же багом (всё от Trail of Bits), а также
  проверка самих скилов на вредные инструкции.
- **Python, Node, веб.** uv и ruff (официальные скилы Astral), Node.js с TypeScript, тесты веб-приложений
  через Playwright, [hallmark](https://github.com/Nutlope/hallmark) для лендингов без «ИИ-шного» вида.
- **Про самих агентов.** Как писать MCP-серверы и описания инструментов, как экономить контекст, как
  найти нужный скил.

Полный список с версиями — [ниже](#все-скилы).

Часть скилов — просто инструкции, а инструменты ставятся отдельно: WinDbg и
[mcp-windbg](https://github.com/svnscha/mcp-windbg), Ghidra, IDA Pro, Semgrep, CodeQL.

## Как это работает

Весь набор описан в одном файле, [skills.toml](skills.toml): какой скил брать, из какого репозитория и
для какой задачи. Скрипт [tools/skillsync.py](tools/skillsync.py) по этому списку копирует скилы в
`skills/`. Рядом с каждым он кладёт `SOURCE.md` (откуда взят, какой коммит, лицензия) и записывает
точную версию в `skills.lock.json`.

**Обновления.** Раз в день GitHub Action проверяет, не вышло ли нового в исходных репозиториях. Если
вышло, он забирает изменения и коммитит их сюда. Что поменялось, видно в [CHANGELOG.md](CHANGELOG.md)
со ссылками на diff. На компьютере, где установлен набор, остаётся только `git pull`. В папках агентов
лежат ссылки на этот репозиторий, а не копии, поэтому после pull агенты сразу видят новые версии.

**Новый код сначала смотрю сам.** Если в небольшом репозитории поменялись скрипты (не текст, а код,
который агент может выполнить), обновление ждёт, пока я его посмотрю:

```bash
python tools/skillsync.py diff <скил> --full      # что поменялось
python tools/skillsync.py update --approve <скил>  # принять
```

Скилы от крупных команд (Anthropic, Microsoft, Trail of Bits, Astral, Sentry, Vercel, superpowers)
обновляются без ожидания.

**Скилы не мешают друг другу.** Перед каждым обновлением `python tools/skillsync.py check` проверяет:
- у двух скилов не совпадают имена, в том числе с тем, что у вас уже было установлено;
- на одну задачу не претендуют два скила;
- у каждого скила есть описание, по которому агент его найдёт, и лицензия;
- скачанные скилы никто не правил руками.

Если описания двух скилов слишком похожи, `check` предупредит. `install` трогает только свои ссылки:
если на месте уже лежит чужая папка, он скажет об этом и не тронет её.

## Добавить или убрать скил

Проще всего попросить агента, например: «добавь скил для X» или «убери brainstorming». Скил
`skills-curator` знает, где что лежит. Вручную: поправить `skills.toml`, затем выполнить
`skillsync.py update`, `check` и `install`.

Свои скилы можно класть в `skills/<имя>/` с пометкой `local = true` в `skills.toml`. Обновления их не
трогают.

## Все скилы

Таблица обновляется автоматически.

<!-- skills:start -->
| Скил | Задача | Откуда | Версия |
| --- | --- | --- | --- |
| `tool-design` | agent-tool-design | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | [d9202c76](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/tree/d9202c76d6dc8351e648badb576a6e9b5aae1e7f/skills/tool-design) |
| `anti-reversing-techniques` | anti-reversing | [wshobson/agents](https://github.com/wshobson/agents) | [c96b5f65](https://github.com/wshobson/agents/tree/c96b5f6552dba32e4492307493ee613581430715/plugins/reverse-engineering/skills/anti-reversing-techniques) |
| `context-optimization` | context-management | [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | [d9202c76](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/tree/d9202c76d6dc8351e648badb576a6e9b5aae1e7f/skills/context-optimization) |
| `analyze-dump` | crash-dump-analysis | [svnscha/mcp-windbg](https://github.com/svnscha/mcp-windbg) | [cf308c23](https://github.com/svnscha/mcp-windbg/tree/cf308c236e497ffaa613c54fc38babfa7da59409/plugins/mcp-windbg-skills/skills/analyze-dump) |
| `systematic-debugging` | debugging | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging) |
| `hallmark` | frontend-design | [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | [04977e15](https://github.com/Nutlope/hallmark/tree/04977e15f3dfd6ee4b74c887dac3eb52665d6c92/skills/hallmark) |
| `ghidra` | ghidra-headless | [mitsuhiko/agent-stuff](https://github.com/mitsuhiko/agent-stuff) | [0865c849](https://github.com/mitsuhiko/agent-stuff/tree/0865c849befd2021490679f96a8dee58c84ac857/skills/ghidra) |
| `finishing-a-development-branch` | git-branch-finish | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/finishing-a-development-branch) |
| `using-git-worktrees` | git-worktrees | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/using-git-worktrees) |
| `hypervisor-internals` | hypervisor | [mohitmishra786/low-level-dev-skills](https://github.com/mohitmishra786/low-level-dev-skills) | [18f29518](https://github.com/mohitmishra786/low-level-dev-skills/tree/18f29518a47fda070e6ec1268cb577692fae9a10/skills/virtualization/hypervisor-internals) |
| `idapython` | ida-scripting | [mrexodia/ida-pro-mcp](https://github.com/mrexodia/ida-pro-mcp) | [13e480cb](https://github.com/mrexodia/ida-pro-mcp/tree/13e480cb1198f923154b63669e8cb2faee5deaea/skills/idapython) |
| `brainstorming` | ideation | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming) |
| `debugview` | kernel-debug-output | [microsoft/skills](https://github.com/microsoft/skills) | [47eb3888](https://github.com/microsoft/skills/tree/47eb3888eb42aef074fcb617931bf6e5934e45d9/.github/skills/debugview) |
| `kernel-debug` | kernel-debugging | [svnscha/mcp-windbg](https://github.com/svnscha/mcp-windbg) | [cf308c23](https://github.com/svnscha/mcp-windbg/tree/cf308c236e497ffaa613c54fc38babfa7da59409/plugins/mcp-windbg-skills/skills/kernel-debug) |
| `mcp-builder` | mcp-servers | [anthropics/skills](https://github.com/anthropics/skills) | [e4bb5d96](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/mcp-builder) |
| `node-best-practices` | nodejs | [mcollina/skills](https://github.com/mcollina/skills) | [c75d70db](https://github.com/mcollina/skills/tree/c75d70dbfbe991d8cec42aeda0b64ff14fbb9ac7/skills/node) |
| `dispatching-parallel-agents` | parallel-agents | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/dispatching-parallel-agents) |
| `executing-plans` | plan-execution | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/executing-plans) |
| `writing-plans` | planning | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/writing-plans) |
| `uv` | python-env | [astral-sh/claude-code-plugins](https://github.com/astral-sh/claude-code-plugins) | [855418fb](https://github.com/astral-sh/claude-code-plugins/tree/855418fb9ebfada49a8345a5c3ada9db2cdc2419/plugins/astral/skills/uv) |
| `ruff` | python-lint | [astral-sh/claude-code-plugins](https://github.com/astral-sh/claude-code-plugins) | [855418fb](https://github.com/astral-sh/claude-code-plugins/tree/855418fb9ebfada49a8345a5c3ada9db2cdc2419/plugins/astral/skills/ruff) |
| `reverse-engineer-anything` | reverse-engineering | [morluto/rea](https://github.com/morluto/rea) | [ff2f1c2f](https://github.com/morluto/rea/tree/ff2f1c2f72a5cbe696086d64a28d450dcd7dc4b5/.agents/skills/reverse-engineer-anything) |
| `receiving-code-review` | review-feedback | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/receiving-code-review) |
| `codeql` | sast-codeql | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/static-analysis/skills/codeql) |
| `semgrep` | sast-semgrep | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/static-analysis/skills/semgrep) |
| `skills-curator` | skill-collection | свой | - |
| `find-skills` | skill-discovery | [vercel-labs/skills](https://github.com/vercel-labs/skills) | [57217cf8](https://github.com/vercel-labs/skills/tree/57217cf86ba38148a57af9e90d14a4c049558330/skills/find-skills) |
| `skill-scanner` | skill-security-scan | [getsentry/skills](https://github.com/getsentry/skills) | [a582c51e](https://github.com/getsentry/skills/tree/a582c51ee29d0f35e6ac321340796f77d43da733/skills/skill-scanner) |
| `subagent-driven-development` | subagent-execution | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development) |
| `test-driven-development` | tdd | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development) |
| `variant-analysis` | variant-analysis | [trailofbits/skills](https://github.com/trailofbits/skills) | [149d7b21](https://github.com/trailofbits/skills/tree/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/variant-analysis/skills/variant-analysis) |
| `verification-before-completion` | verification | [obra/superpowers](https://github.com/obra/superpowers) | [22f0b463](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion) |
| `webapp-testing` | web-e2e-testing | [anthropics/skills](https://github.com/anthropics/skills) | [e4bb5d96](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/webapp-testing) |
<!-- skills:end -->

## Что я не взял и почему

| Кандидат | Почему нет |
| --- | --- |
| [impeccable](https://github.com/pbakaus/impeccable) | Хороший скил, но тоже берётся за «сделай лендинг» и спорил бы с hallmark |
| [powershell-master](https://github.com/josiahsiegel/claude-plugin-marketplace) | Хочет включаться на любую строчку PowerShell и навязывает агенту свои правила про пути к файлам. Давно не обновлялся |
| [planning-with-files](https://github.com/OthmanAdi/planning-with-files) | Вешает хуки на каждое действие агента. Планы и так пишет `writing-plans` |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), [mattpocock/skills](https://github.com/mattpocock/skills) | Целые наборы для того же процесса, что и superpowers, с теми же именами скилов |
| superpowers: `requesting-code-review`, `writing-skills` | В Claude Code уже есть встроенные `code-review` и `skill-creator` |
| Trail of Bits: `c-review`, `fp-check`, `modern-python` | Первый не подходит для драйверов и требует весь плагин, второй ставит хуки, третий заменили скилы самой Astral |
| [windiff](https://github.com/ergrelet/windiff) | Работает только внутри своего репозитория, лицензия GPL |
| [VMware-AIops](https://github.com/vmware-skills/VMware-AIops) | Просит отдать стороннему пакету доступ к vCenter |
| Anthropic: docx, pdf, pptx, xlsx | Уже встроены в Claude и не под открытой лицензией |

## Лицензии

Каждый скил остаётся под лицензией своих авторов: файл `LICENSE` лежит в папке скила, ссылка на
оригинал — в `SOURCE.md`. Скилы Trail of Bits распространяются по CC-BY-SA-4.0: изменённые версии нужно
выпускать под той же лицензией и с указанием авторов.
