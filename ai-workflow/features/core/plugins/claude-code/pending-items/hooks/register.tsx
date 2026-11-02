import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Item, Pending, Stored } from '../types'

const PLUGIN = 'pending-items'
const ADD = `mcp__${PLUGIN}__add`
const RESOLVE = `mcp__${PLUGIN}__resolve`
const EMPTY: Pending = { items: [], nextId: 1 }
// Items outlive the process in $.store, one key per session, so `claude --resume` brings them back.
const KEY_PREFIX = 'session:'
// Claude Code's default transcript retention: past it the session can't be resumed anyway.
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000
const MAX_SESSIONS = 50

const pending = atom({ plugin: 'pending-items', key: 'pending' } as const, EMPTY)

// Read by the model with every prompt: when to call the tools, and when not to.
const INSTRUCTIONS = `# Pending items

The person follows long sessions and can miss something you need from them. When you ask them for a decision or an approval that work waits on, or that is hard to reverse (merge or publish this? delete that? which of these options? may I proceed with X?), call the \`add\` tool of ${PLUGIN} with a one-line description of what you need, in the same turn as the question. Ordinary clarifications you expect answered in the next message don't go there. Once the person has answered, or the item no longer applies, call \`resolve\` with its id in the same turn. The items are shown to the person above the prompt until resolved; they can also list them with /pending.`

function list(items: Item[]) {
  return items.length === 0 ? 'Nothing pending.' : items.map(i => `${i.id}. ${i.text}`).join('\n')
}

function isStored(value: unknown): value is Stored {
  const v = value as Stored | undefined
  return !!v && Array.isArray(v.items) && typeof v.nextId === 'number' && typeof v.updatedAt === 'number'
}

type $ = EngineInterface

// The atom belongs to one session; a resume or a /resume into another session swaps in that one's stored items.
async function sync($: $): Promise<Pending> {
  const sessionId = await $.session.id()
  const current = (await read($, pending)) ?? EMPTY
  if (current.sessionId === sessionId) return current
  let next: Pending
  if (current.sessionId === undefined && current.items.length > 0) {
    // MIGRATION(pending-items-persist): a value a hot reload kept from the version before items were persisted
    // has no session yet: it is this one's. Remove once no session from before that version is running.
    next = { ...current, sessionId }
    await persist($, next)
  } else {
    const stored = await $.store.get(KEY_PREFIX + sessionId)
    next = isStored(stored) ? { items: stored.items, nextId: stored.nextId, sessionId } : { ...EMPTY, sessionId }
  }
  await update($, pending, () => next)
  return next
}

async function persist($: $, p: Pending) {
  if (!p.sessionId) return
  const key = KEY_PREFIX + p.sessionId
  if (p.items.length === 0) await $.store.delete(key)
  else await $.store.set(key, { items: p.items, nextId: p.nextId, updatedAt: await $.clock.now() } satisfies Stored)
}

async function mutate($: $, fn: (p: Pending) => Pending): Promise<Pending> {
  await sync($)
  let result = EMPTY
  await update($, pending, p => (result = fn(p ?? EMPTY)))
  await persist($, result)
  return result
}

// Drops sessions untouched for longer than a transcript is kept, then all but the most recent ones.
async function collectGarbage($: $) {
  const now = await $.clock.now()
  const sessions: { key: string; updatedAt: number }[] = []
  for (const key of await $.store.keys()) {
    if (!key.startsWith(KEY_PREFIX)) continue
    const stored = await $.store.get(key)
    if (!isStored(stored) || now - stored.updatedAt > MAX_AGE_MS) await $.store.delete(key)
    else sessions.push({ key, updatedAt: stored.updatedAt })
  }
  sessions.sort((a, b) => b.updatedAt - a.updatedAt)
  for (const { key } of sessions.slice(MAX_SESSIONS)) await $.store.delete(key)
}

function workPrompt(items: Item[]) {
  return `Let's work through what you're waiting on from me, one item at a time, in this order:\n${list(items)}\n\nFor each: say in a few lines what you need from me and the context I need to decide, then wait for my answer. Act on it, resolve the item, and only then move to the next one.`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.tool.register({
      name: 'add',
      description: 'Records something you are waiting on from the person (a decision, an approval) so it stays visible to them until resolved. Returns its id.',
      inputSchema: { type: 'object', properties: { text: { type: 'string', description: 'One line: what you need from the person, and for what.' } }, required: ['text'] },
      isDeferred: false,
    })
    await $.tool.register({
      name: 'resolve',
      description: 'Removes a pending item once the person answered it or it no longer applies.',
      inputSchema: { type: 'object', properties: { id: { type: 'number', description: 'The id `add` returned.' } }, required: ['id'] },
      isDeferred: false,
    })
    if (e.isInteractive) {
      await $.command.register({ name: 'pending', description: 'What the model is waiting on from you; `/pending work` drafts a prompt to go through the items with it one by one, `/pending done <id>` drops one, `/pending clear` all.', argumentHint: '[work | done <id> | clear]' })
    }
    await sync($)
    await collectGarbage($)
    return started
  })

  // After /clear the agent no longer has the context the items were raised in, so they go; on an exit or a
  // /resume into another session they stay stored for a later resume of this one.
  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') await $.store.delete(KEY_PREFIX + e.sessionId)
    if (e.reason === 'clear' || e.reason === 'resume') await update($, pending, () => EMPTY)
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    await sync($)
    return next(e)
  })

  on('prompt.compose', async ($, e, next) => {
    const { sections } = await next(e)
    return { sections: [...sections, { id: `${PLUGIN}:instructions`, text: INSTRUCTIONS, scope: 'session' }] }
  })

  on('tool.call', { tool: ADD }, async ($, e) => {
    const text = typeof e.text === 'string' ? e.text.trim() : ''
    if (!text) return { deny: 'add needs a non-empty `text`' }
    const addedAt = new Date(await $.clock.now()).toISOString()
    let id = 0
    await mutate($, current => {
      id = current.nextId
      return { ...current, items: [...current.items, { id, text, addedAt }], nextId: id + 1 }
    })
    return { result: `pending item ${id} added: ${text}` }
  })

  on('tool.call', { tool: RESOLVE }, async ($, e) => {
    const id = typeof e.id === 'number' ? e.id : Number(e.id)
    const current = await sync($)
    if (!current.items.some(i => i.id === id)) return { deny: `no pending item ${id}; open: ${list(current.items)}` }
    await mutate($, p => ({ ...p, items: p.items.filter(i => i.id !== id) }))
    return { result: `pending item ${id} resolved` }
  })

  on('command.run', { command: 'pending' }, async ($, e) => {
    const [verb, arg] = (e.args ?? '').trim().split(/\s+/)
    const current = await sync($)
    if (verb === 'work') {
      if (current.items.length === 0) return { text: 'Nothing pending.' }
      // Into the input box rather than submitted: a command can't start a turn while it holds one, and this
      // way the person can edit the prompt before sending it.
      await $.prompt.fill({ text: workPrompt(current.items) })
      return { text: `The prompt to go through ${current.items.length} pending item${current.items.length === 1 ? '' : 's'} is in the input box; press Enter to start.` }
    }
    if (verb === 'clear') {
      await mutate($, p => ({ ...p, items: [] }))
      return { text: `Cleared ${current.items.length} pending item${current.items.length === 1 ? '' : 's'}.` }
    }
    if (verb === 'done') {
      const id = Number(arg)
      if (!current.items.some(i => i.id === id)) return { text: `No pending item ${arg ?? ''}.\n${list(current.items)}` }
      await mutate($, p => ({ ...p, items: p.items.filter(i => i.id !== id) }))
      return { text: `Resolved ${id}.` }
    }
    return { text: list(current.items) }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const current = (await read($, pending)) ?? EMPTY
    const [first, ...rest] = current.items
    if (e.props.hasSurvey || !first) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box>
        <Text wrap="truncate-end">
          <Text color="yellow">
            {'⚑ '}
            {current.items.length === 1 ? 'Waiting on you' : `${current.items.length} waiting on you`}: {first.text}
          </Text>
          {rest.length > 0 && <Text dimColor> +{rest.length} more</Text>}
          <Text dimColor> · /pending</Text>
        </Text>
      </Box>
    )
  })
}
