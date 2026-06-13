# Custom Agents — Duke3D: Neon Noir

Repository-level [custom agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/create-custom-agents) for working on this codebase. Each agent is a Markdown file with YAML frontmatter at `.github/agents/<name>.agent.md`.

These agents are auto-discovered by GitHub Copilot CLI / cloud agent and selectable via:
- `/agent` slash command in the CLI
- `copilot --agent=<name> --prompt "..."`
- Inline reference in a prompt: *"Use the engine-surgeon agent to ..."*

## When to use which agent

The agent set is partitioned by **code area** — pick the agent whose scope contains the files you're touching. Agents include explicit out-of-scope handoffs to keep tasks routed correctly.

| Agent | Scope | Use for |
|---|---|---|
| **`engine-surgeon`** | `SRC/*.C`, `source/*.C` and their headers | Bug fixes / surgical edits to the 1996 K&R BUILD engine and Duke3D game logic. **Never reformats or modernizes.** |
| **`compat-engineer`** | `compat/*.{c,h}` | Modern C11 work in the compat layer — SDL2 driver, audio/MACT stubs, MSVC↔GCC mappings, headless render hooks. |
| **`build-doctor`** | `Makefile`, `build.mk`, `CMakeLists.txt`, `build_windows.bat`, `tools/win_build.ps1` | Anything build-system. Owns the **three-way mirror** (`build.mk` is source of truth — `CMakeLists.txt` and `build_windows.bat` must mirror it). |
| **`asset-pipeline`** | `tools/*.py`, `requirements.txt`, asset format tests | Texture/audio/map generators, GRP packing, FLUX/Azure GPT Audio integration, file-format encoders. |
| **`playtest-runner`** | Built `duke3d`/`duke3d.exe` binary + `captures/` | Headless game runs (`DUKE3D_HEADLESS`/`DUKE3D_SKIP_LOGO`/`DUKE3D_FRAME_LIMIT`/`DUKE3D_CAPTURE_INTERVAL`), frame analysis, render-bug triage. **Diagnoses; does not fix.** |
| **`release-bundler`** | `tools/bundle_windows.sh`, `tools/get_sdl2_mingw.sh`, `duke3d_launcher.bat` | Windows release packaging + `objdump` DLL audit. Owns the invariant that every non-system DLL ships in the release zip. |

## Quick decision tree

```
Touching .C or .H in SRC/ or source/?               → engine-surgeon
Touching .c or .h in compat/?                       → compat-engineer
Touching .py in tools/ (asset/audio/format/tests)?  → asset-pipeline
Touching Makefile / CMakeLists / build.mk / win_build.ps1?  → build-doctor
Touching .github/workflows/build.yml?               → build-doctor
Touching .github/workflows/release.yml / bundle_windows.sh? → release-bundler
Building, no source change?                         → build-doctor
Running the binary headless to verify rendering?    → playtest-runner
Cutting a Windows release / DLL audit?              → release-bundler

# Areas without a dedicated custom agent — use built-ins:
Docs (README.md, CONTRIBUTING.md, docs/*, SECURITY.md)?  → doc-scribe
Specs / planning (.smith/specs/*, .smith/project.yaml)?  → general-purpose or doc-scribe
Dependency bumps / CVE patches?                          → dependency-auditor or security-auditor (then route fix to the owning area)
Reference / unused dirs (audiolib/, extras/, UTIL/, kenbuild_data/)?  → general-purpose unless promoting code into SRC/, source/, or compat/
Cross-cutting refactor?                                  → general-purpose
Just exploring?                                          → explore
Unknown / unlisted area?                                 → general-purpose first; delegate by file ownership after discovery
```

## Design principles (for adding new agents)

- **Partition by area, not by verb.** Don't create `bug-fixer` or `feature-adder` — the existing agents already know how to do those *within their area*.
- **Keep `description:` tight** — the model uses it to auto-route tasks. Lead with the file glob/scope, then the use-case.
- **Always include "Out of scope (delegate)"** so chained tasks land on the right agent.
- **Hard-code the codebase facts** (env vars, constants, file paths, `SDL2_VERSION` source) so the agent doesn't have to rediscover them every invocation.
- **Constrain `tools:`** to the minimum needed. The default set is `read, edit, search, execute`. Diagnostic-only agents like `playtest-runner` omit `edit`.
