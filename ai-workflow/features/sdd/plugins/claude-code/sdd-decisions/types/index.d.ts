// What `sdd blockers --json` prints, kept as the session's state so a hot reload keeps the band.
export type Blocker = { slug: string; title: string; blocks: string[]; downstream: number; asked: string }
export type Summary = { open: number; blockers: Blocker[] }

export type Question = { slug: string; title: string }
// A running /sdd-answer-questions. `pending` is `null` until the first listing arrives, `dir` is
// the `--dir` the skill's commands use: its unshipped answers aren't on main yet.
export type Answering = { dir: string | null; current: string | null; pending: Question[] | null; touchedAt: number }

declare module 'claude-code' {
  interface PluginState {
    'sdd-decisions': { summary: Summary | null; answering: Answering | null }
  }
}
