import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

type On = Parameters<TestBody>[1]
type $ = Parameters<TestBody>[0]

const BAND = {
  plugin: 'pending-items',
  component: 'AbovePrompt',
  requestId: 'abovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 160,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

const DAY = 24 * 60 * 60 * 1000

// `session.id` is mutable so a test can move the process to another session, as /clear and /resume do.
function engine(on: On, { session = { id: 's1' }, store = {}, now = 100 * DAY, above }: { session?: { id: string }; store?: Record<string, unknown>; now?: number; above?: (on: On) => void } = {}) {
  // Hooks of the test's that must see calls before the mocks answer them.
  above?.(on)
  mock.store(on, store)
  mock.clock(on, { now })
  on('session.id', () => ({ value: session.id }))
  on('session.end', (_, e) => ({ sessionId: e.sessionId }))
  on('tool.register', (_, e) => ({ value: { tool: `mcp__pending-items__${e.name}` } }))
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
}

test('items the model adds show above the prompt until resolved', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })

  const added = await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Approve merging PR 214' })
  expect(added.result).toBe('pending item 1 added: Approve merging PR 214')
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Pick the storage option' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    const row = await ui.find({ type: 'Text', text: /waiting on you/ })
    expect(row?.text).toContain('2 waiting on you: Approve merging PR 214')
    expect(row?.text).toContain('+1 more')
    await ui.unmount()
  }

  const resolved = await $.tool.call({ tool: 'mcp__pending-items__resolve', id: 1 })
  expect(resolved.result).toBe('pending item 1 resolved')
  const missing = await $.tool.call({ tool: 'mcp__pending-items__resolve', id: 1 })
  expect(missing.deny).toContain('no pending item 1')

  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /Waiting on you/ }))?.text).toContain('Waiting on you: Pick the storage option')
  await ui.unmount()
})

test('with nothing pending the band is left to the engine', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
  await ui.unmount()
})

test('/pending lists, resolves and clears items', async ($, on) => {
  engine(on)
  const run = (args = '') => $.command.run({ command: 'pending', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  expect((await run()).text).toBe('Nothing pending.')

  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Approve merging PR 214' })
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Pick the storage option' })
  expect((await run()).text).toBe('1. Approve merging PR 214\n2. Pick the storage option')
  expect((await run('done 1')).text).toBe('Resolved 1.')
  expect((await run('done 9')).text).toContain('No pending item 9')
  expect((await run('clear')).text).toBe('Cleared 1 pending item.')
  expect((await run()).text).toBe('Nothing pending.')
})

function pendingCommand($: $) {
  return async (args = '') => (await $.command.run({ command: 'pending', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } })).text
}

async function endSession($: $, session: { id: string }, reason: 'clear' | 'resume', nextId: string) {
  await $.session.end({ reason, sessionId: session.id, resume: { id: session.id } })
  session.id = nextId
}

test('a resumed session gets its items back, and only its own', async ($, on) => {
  const session = { id: 'new' }
  engine(on, { session, store: { 'session:old': { items: [{ id: 3, text: 'Approve merging PR 214', addedAt: '' }], nextId: 4, updatedAt: 99 * DAY } } })
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  expect(await run()).toBe('Nothing pending.')
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Pick the storage option' })

  await endSession($, session, 'resume', 'old')
  expect(await run()).toBe('3. Approve merging PR 214')
  expect((await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Confirm the rename' })).result).toBe('pending item 4 added: Confirm the rename')

  await endSession($, session, 'resume', 'new')
  expect(await run()).toBe('1. Pick the storage option')
  // An emptied list stays empty on the next resume.
  await run('clear')
  await endSession($, session, 'resume', 'old')
  await endSession($, session, 'resume', 'new')
  expect(await run()).toBe('Nothing pending.')
})

test('/clear drops the items for good, since the agent loses their context', async ($, on) => {
  const session = { id: 's1' }
  engine(on, { session })
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Approve merging PR 214' })

  await endSession($, session, 'clear', 's2')
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
  await ui.unmount()
  expect(await run()).toBe('Nothing pending.')

  await endSession($, session, 'resume', 's1')
  expect(await run()).toBe('Nothing pending.')
})

const stored = (text: string, updatedAt: number) => ({ items: [{ id: 1, text, addedAt: '' }], nextId: 2, updatedAt })

test('stored sessions untouched for longer than a transcript is kept are dropped', async ($, on) => {
  const now = 100 * DAY
  const session = { id: 'fresh' }
  engine(on, { session, now, store: { 'session:stale': stored('stale', now - 31 * DAY), 'session:recent': stored('recent', now - 29 * DAY) } })
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })

  for (const [id, expected] of [['stale', 'Nothing pending.'], ['recent', '1. recent']]) {
    await endSession($, session, 'resume', id!)
    expect(await run()).toBe(expected)
  }
})

test('resuming a session counts as using it, so garbage collection keeps it', async ($, on) => {
  const now = 100 * DAY
  const session = { id: 'old' }
  engine(on, { session, now, store: { 'session:old': stored('old item', now - 31 * DAY) } })
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  expect(await run()).toBe('1. old item')

  await endSession($, session, 'resume', 'other')
  await endSession($, session, 'resume', 'old')
  expect(await run()).toBe('1. old item')
})

test('/resume into another session shows its items without waiting for a prompt', async ($, on) => {
  const session = { id: 'new' }
  engine(on, { session, store: { 'session:old': stored('old item', 99 * DAY) } })
  on('classic.SessionStart', () => ({}))
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })

  await endSession($, session, 'resume', 'old')
  await $.classic.SessionStart({ source: 'resume', session_id: 'old' })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /Waiting on you/ }))?.text).toContain('Waiting on you: old item')
  await ui.unmount()
})

test('only the 50 most recently updated sessions are kept', async ($, on) => {
  const now = 100 * DAY
  const store: Record<string, unknown> = {}
  for (let i = 1; i <= 51; i++) store[`session:s${i}`] = stored(`s${i}`, now - i * 60_000)
  const session = { id: 'fresh' }
  engine(on, { session, store, now })
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })

  for (const [id, expected] of [['s51', 'Nothing pending.'], ['s50', '1. s50'], ['s1', '1. s1']]) {
    await endSession($, session, 'resume', id!)
    expect(await run()).toBe(expected)
  }
})

test('a session whose items are all resolved leaves nothing stored', async ($, on) => {
  const writes: string[] = []
  engine(on, {
    above: on => {
      on('store.set', { key: 'session:s1' }, (_, e, next) => (writes.push('set'), next(e)))
      on('store.delete', { key: 'session:s1' }, (_, e, next) => (writes.push('delete'), next(e)))
    },
  })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Approve merging PR 214' })
  await $.tool.call({ tool: 'mcp__pending-items__resolve', id: 1 })
  expect(writes).toEqual(['set', 'delete'])
})

// MIGRATION(pending-items-persist): remove with the migration code in register.tsx.
test('items a hot reload kept from before they were persisted stay, and get stored', async ($, on) => {
  const writes: string[] = []
  engine(on, { above: on => void on('store.set', { key: 'session:s1' }, (_, e, next) => (writes.push('set'), next(e))) })
  // The first read finds what the earlier version left; the kit's own state answers after that.
  let seeded = false
  on('state.get', (_, e, next) => {
    if (seeded) return next(e)
    seeded = true
    return { value: { value: { items: [{ id: 1, text: 'Approve merging PR 214', addedAt: '' }], nextId: 2 }, version: 1 } }
  })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  expect(await pendingCommand($)()).toBe('1. Approve merging PR 214')
  expect(writes).toEqual(['set'])
})

test('/pending work drafts a prompt to go through the items one by one', async ($, on) => {
  engine(on)
  const filled: string[] = []
  on('prompt.fill', (_, e) => (filled.push(e.text), { isFilled: true }))
  const run = pendingCommand($)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  expect(await run('work')).toBe('Nothing pending.')

  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Approve merging PR 214' })
  await $.tool.call({ tool: 'mcp__pending-items__add', text: 'Pick the storage option' })
  expect(await run('work')).toContain('is in the input box')
  expect(filled).toHaveLength(1)
  expect(filled[0]).toContain('one item at a time, in this order:\n1. Approve merging PR 214\n2. Pick the storage option')
  // Working on them doesn't resolve them: the model does, once each is answered.
  expect(await run()).toBe('1. Approve merging PR 214\n2. Pick the storage option')
})

test('the model is told when to add and resolve items', async ($, on) => {
  engine(on)
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'You are Claude.', scope: 'shared' as const }] }))
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const { sections } = await $.prompt.compose({ model: 'claude', promptModel: 'claude', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] })
  expect(sections.map(s => s.id)).toEqual(['intro', 'pending-items:instructions'])
  expect(sections[1]?.text).toContain('call the `add` tool')
})
