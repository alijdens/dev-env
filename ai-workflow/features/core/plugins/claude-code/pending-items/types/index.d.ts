// What the model is waiting on from the person, kept as the session's state so a hot reload keeps the band.
// `context` is what the model needs to pick the item up after the conversation lost it (a compaction, a resume).
export type Item = { id: number; text: string; addedAt: string; context?: string }
// `sessionId` is the session the items belong to; absent only in a value from before they were persisted.
export type Pending = { items: Item[]; nextId: number; sessionId?: string }
// A session's items in $.store, under `session:<id>`.
export type Stored = { items: Item[]; nextId: number; updatedAt: number }

declare module 'claude-code' {
  interface PluginState {
    'pending-items': { pending: Pending }
  }
}
