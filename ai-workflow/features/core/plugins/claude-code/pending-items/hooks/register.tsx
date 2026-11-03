import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Item, Pending, Stored } from '../types'

const PLUGIN = 'pending-items'
const ADD = `mcp__${PLUGIN}__add`
const RESOLVE = `mcp__${PLUGIN}__resolve`
const LIST = `mcp__${PLUGIN}__list`
const EMPTY: Pending = { items: [], nextId: 1 }
const PICKER = 'pending'
// Items outlive the process in $.store, one key per session, so `claude --resume` brings them back.
const KEY_PREFIX = 'session:'
// Claude Code's default transcript retention: past it the session can't be resumed anyway.
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000
const MAX_SESSIONS = 50

const pending = atom({ plugin: 'pending-items', key: 'pending' } as const, EMPTY)

// Read by the model with every prompt: when to call the tools, and when not to.
const INSTRUCTIONS = `# Pending items

The person follows long sessions and can miss something you need from them. When you ask them for a decision or an approval that work waits on, or that is hard to reverse (merge or publish this? delete that? which of these options? may I proceed with X?), call the \`add\` tool of ${PLUGIN} with a one-line description of what you need, in the same turn as the question; when the decision depends on details you could lose by the time it is answered (the options, what each implies, the PR or file at stake), put them in its \`context\`. Ordinary clarifications you expect answered in the next message don't go there. Once the person has answered, or the item no longer applies, call \`resolve\` with its id in the same turn. The items are shown to the person above the prompt until resolved; they can also list them with /pending. The \`list\` tool returns them with their context.`

function list(items: Item[]) {
  return items.length === 0 ? 'Nothing pending.' : items.map(i => `${i.id}. ${i.text}`).join('\n')
}

function age(ms: number) {
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 60) return `${minutes}m`
  return minutes < 24 * 60 ? `${Math.floor(minutes / 60)}h` : `${Math.floor(minutes / (24 * 60))}d`
}

function describe(items: Item[], now: number) {
  if (items.length === 0) return 'Nothing pending.'
  return items
    .map(i => {
      const head = `${i.id}. ${i.text} (added ${age(now - Date.parse(i.addedAt))} ago)`
      return i.context ? `${head}\n${i.context.replace(/^/gm, '   ')}` : head
    })
    .join('\n')
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
    // A resume counts as use: garbage collection, which runs right after, measures age from it.
    if (next.items.length > 0) await persist($, next)
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

const WORK_ALL_PROMPT = `Let's work through what you're waiting on from me (the \`list\` tool of ${PLUGIN}), one item at a time, oldest first. For each: say in a few lines what you need from me and the context I need to decide, then wait for my answer. Act on it, resolve the item, and only then move to the next one.`

function workOnePrompt(item: Item) {
  const context = item.context ? ` Its context is in the \`list\` tool of ${PLUGIN}.` : ''
  return `Let's work on pending item ${item.id}: ${item.text}\n\nSay in a few lines what you need from me and the context I need to decide, then wait for my answer. Act on it and resolve the item.${context}`
}

const ALL = 'all'

// Not awaited: the prompt starts a turn of its own once the session is idle.
function work($: $, items: Item[], choice: string) {
  const item = items.find(i => String(i.id) === choice)
  const text = choice === ALL ? WORK_ALL_PROMPT : item && workOnePrompt(item)
  if (text) void $.prompt.submit({ text })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.tool.register({
      name: 'add',
      description: 'Records something you are waiting on from the person (a decision, an approval) so it stays visible to them until resolved. Returns its id.',
      inputSchema: {
        type: 'object',
        properties: {
          text: { type: 'string', description: 'One line: what you need from the person, and for what.' },
          context: { type: 'string', description: 'Optional, a few lines: what you need to take the item up again once the conversation no longer holds it (the options and what each implies, the PR, file or decision at stake).' },
        },
        required: ['text'],
      },
      isDeferred: false,
    })
    await $.tool.register({
      name: 'resolve',
      description: 'Removes a pending item once the person answered it or it no longer applies.',
      inputSchema: { type: 'object', properties: { id: { type: 'number', description: 'The id `add` returned.' } }, required: ['id'] },
      isDeferred: false,
    })
    await $.tool.register({
      name: 'list',
      description: 'Lists what you are waiting on from the person, oldest first: each item\'s id, text, age and context.',
      inputSchema: { type: 'object', properties: {} },
      isDeferred: false,
    })
    if (e.isInteractive) {
      await $.command.register({ name: 'pending', description: 'Pick a pending item to work on with the model, or all one at a time; `/pending all` starts on all directly, `/pending done <id>` drops one, `/pending clear` all.', argumentHint: '[all | done <id> | clear]' })
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

  // A /resume inside the running process starts the other session with no `session.start`, but with this
  // one: load its items now, so the band shows them before the next prompt.
  on('classic.SessionStart', async ($, e, next) => {
    await sync($)
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
    const context = typeof e.context === 'string' ? e.context.trim() : ''
    const addedAt = new Date(await $.clock.now()).toISOString()
    let id = 0
    await mutate($, current => {
      id = current.nextId
      const item: Item = context ? { id, text, addedAt, context } : { id, text, addedAt }
      return { ...current, items: [...current.items, item], nextId: id + 1 }
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

  on('tool.call', { tool: LIST }, async $ => {
    const current = await sync($)
    return { result: describe(current.items, await $.clock.now()) }
  })

  on('command.run', { command: 'pending' }, async ($, e) => {
    const [verb, arg] = (e.args ?? '').trim().split(/\s+/)
    const current = await sync($)
    if (verb === ALL) {
      if (current.items.length === 0) return { text: 'Nothing pending.' }
      // The engine refuses a submit from a command.run hook, which holds the turn the prompt would wait on.
      void $.clock.sleep(0).then(() => work($, current.items, ALL))
      return {}
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
    if (current.items.length === 0) return { text: 'Nothing pending.' }
    const opened = await $.ui.open({ id: PICKER, title: 'Pending items', focus: true, closeOnEscape: true, holdToasts: true, rows: 4 })
    if (opened.isPlaced) return {}
    // An unplaced pane stays open to show up later; a picker that pops up unasked would be stale by then.
    await $.ui.close({ id: PICKER })
    return { text: list(current.items) }
  })

  on('ui.render', { component: 'Pane', requestId: PICKER }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Button, Text } = elements
    // The mobile app's table has a Select it draws as an empty box.
    const Select = e.surface !== 'mobile' && 'Select' in elements ? elements.Select : undefined
    const { items } = (await read($, pending)) ?? EMPTY
    if (items.length === 0) return <Text dimColor>Nothing pending.</Text>
    const options = [{ value: ALL, label: 'All, one at a time' }, ...items.map(i => ({ value: String(i.id), label: `${i.id}. ${i.text}` }))]
    const pick = async (choice: string) => {
      await $.ui.close({ id: PICKER })
      work($, items, choice)
    }
    return (
      <Box flexDirection="column">
        <Text bold>Select which pending item you want to chat about</Text>
        {Select ? (
          <Select key="item" options={options} autoFocus onSelect={(value: string) => void pick(value)} />
        ) : (
          options.map((o, n) => <Button key={o.value} label={o.label} plain autoFocus={n === 0 || undefined} onPress={() => void pick(o.value)} />)
        )}
      </Box>
    )
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
            {current.items.length === 1 ? 'Waiting on you' : `${current.items.length} items waiting on you`}: {first.text}
          </Text>
          {rest.length > 0 && <Text dimColor> +{rest.length} more</Text>}
          <Text dimColor> · /pending</Text>
        </Text>
      </Box>
    )
  })
}
