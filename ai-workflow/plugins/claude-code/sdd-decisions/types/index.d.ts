// What `sdd blockers --json` prints, kept as the session's state so a hot reload keeps the band.
export type Blocker = { slug: string; title: string; blocks: string[]; downstream: number; asked: string }
export type Summary = { open: number; blockers: Blocker[] }

declare module 'claude-code' {
  interface PluginState {
    'sdd-decisions': { summary: Summary | null }
  }
}
