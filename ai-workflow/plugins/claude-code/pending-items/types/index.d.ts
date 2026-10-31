// What the model is waiting on from the person, kept as the session's state so a hot reload keeps the band.
export type Item = { id: number; text: string; addedAt: string }
export type Pending = { items: Item[]; nextId: number }

declare module 'claude-code' {
  interface PluginState {
    'pending-items': { pending: Pending }
  }
}
