# Playbook: exactly what to do, in order

**Deadline:** Wed 18 Nov, 18:29 GMT. **Our target:** submitted by Wed 14:00, which leaves 4.5 hours of buffer.
**Fable window:** included until 16 Nov. Treat **Sunday night** as the safe cutoff, so both Fable sessions
(Phase 1 and Phase 3) must happen by then. If Fable still shows "included" on Monday, use it there too.

---

## Part A: one-time setup (Sat 14 Nov, about 30 min)

**A1. Put the kit somewhere.** Unzip `rr-superr-selector.zip`. You get a folder called `rr-superr-selector`.
Move it to wherever you keep projects, for example `C:\Users\<you>\code\rr-superr-selector`.

**A2. Add the data.** Open the data pack zip and go into its `Data Pack` folder. Copy these 6 files into
`rr-superr-selector\data\raw\`:
```
ball_by_ball.csv   matches.csv   competitions.csv   teams.csv
playing_eleven.csv   competition_team_player_mapping.csv
```
Also copy the problem-statement PDF into `data\raw\` for reference. Ignore `__MACOSX` and `.DS_Store`.
(`data\raw` is git-ignored, so none of this gets uploaded to GitHub.)

**A3. Open the folder in VS Code.** File → Open Folder → `rr-superr-selector`. Open a terminal
(Ctrl+`). It should be PowerShell, sitting in the repo folder.

**A4. Python environment.** Run these one at a time:
```
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If `Activate.ps1` gives an execution-policy error, run this once, then try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**A5. Run the cleaning script.**
```
python src/01_clean.py
```
You should see exactly:
```
matches.parquet      883 rows
balls.parquet    200,999 rows, 72 columns
players.parquet    1,217 rows
Wrote outputs/data_quality.md
```
If the numbers differ, stop and tell me (in the claude.ai chat) what you got.

**A6. Git and GitHub (private for now).**
```
git init
git add .
git commit -m "Project kit and cleaning pipeline"
```
Then create a **private** GitHub repo called `rr-superr-selector` and push to it, either on github.com or with
`gh repo create rr-superr-selector --private --source . --push`.
Make it public on Wednesday, just before you submit, so the report can link to it.

**A7. Check the Unstop dropdowns (5 min, important).** Open the Unstop submission page, click into the batter
and bowler dropdowns, and look at how names are written and whether the list looks limited, for example to IPL
2026 players only. If it's limited, tell me, because that changes eligibility. Don't submit anything yet.

---

## Part B: the phases

**Rules for every phase**
- Start Claude Code in the repo folder (type `claude` in the VS Code terminal, or use the Claude Code panel).
- **Before each phase, type `/clear`**, then `/model` and pick the model named at the top of the prompt file.
- Open the prompt file in `prompts\`, copy **everything below the `---` line**, and paste it into Claude Code.
- When Claude Code asks permission to run `python` or `git` in this folder, allow it.
- After each phase: `git add .` then `git commit -m "<phase name>"`.

| # | When | Model | Prompt file | You're done when |
|---|------|-------|-------------|------------------|
| 1 | **Sat evening** | **Fable** | `prompts/phase1_fable_design.md` | `docs/METHODOLOGY_SPEC.md` exists and DECISIONS.md has D6+ |
| — | Sat night | **You** | — | You've read the spec end to end (about 20 min). You must be able to defend it in person. Bring anything confusing back to me. |
| 2 | **Sun morning–afternoon** | Opus | `prompts/phase2_opus_build.md` | All scripts in spec section 7 pass their checks. Reply "next" between scripts, and commit after each. |
| 3 | **Sun evening (before midnight)** | **Fable** | `prompts/phase3_fable_review.md` | `docs/REVIEW_1.md` exists |
| 3b | Mon | Opus | `prompts/phase3b_opus_fixes.md` | `outputs/final_top10_*.csv` exist |
| — | Mon evening | **You** | — | Sanity-check both top 10s against your cricket knowledge. Anything odd → ask Opus "why is X ranked here? Show the evidence." |
| 4 | **Tue** | Opus | `prompts/phase4_opus_report.md` | `reports/report.html` looks right page by page |
| 5 | Tue evening | Fable (on credits) or Opus | `prompts/phase5_redteam.md` | `docs/REDTEAM.md`. Then ask Opus to apply the top fixes. |
| — | **Wed by 14:00** | **You** | — | See Part C |

**If you fall behind:** skip the steps marked CUTTABLE in spec section 7, and drop Phase 5 before you drop
anything else. Never skip Phase 3. A wrong ranking costs more than a plain report.

**If Fable isn't in `/model` in Claude Code:** use Fable in the claude.ai chat instead. Attach `CLAUDE.md`,
`DECISIONS.md` and `outputs/data_quality.md`, paste the Phase 1 prompt, then save its answer as
`docs/METHODOLOGY_SPEC.md` and add its decisions to `DECISIONS.md` yourself.

---

## Part C: submission (Wed, by 14:00)
1. Replace `{{REPO_URL}}` in `reports/report.html` with your GitHub link. Make the repo public.
2. Open `reports/report.html` in Chrome or Edge → Print → Save as PDF → A4, margins Default, background
   graphics ON. Check every page of the PDF.
3. On Unstop, select the 10 batters and 10 bowlers **in the exact order** of `outputs/final_top10_batters.csv`
   and `outputs/final_top10_bowlers.csv`. Check each name twice, and check there are no repeats.
4. Upload the PDF. Submit. Screenshot the confirmation.
5. Optional: the 30–60 second "journey" video. It isn't scored, so only do it if you have time.
