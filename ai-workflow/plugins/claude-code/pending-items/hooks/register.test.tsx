import { expect, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

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

function engine(on: Parameters<TestBody>[1]) {
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

test('the model is told when to add and resolve items', async ($, on) => {
  engine(on)
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'You are Claude.', scope: 'shared' as const }] }))
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const { sections } = await $.prompt.compose({ model: 'claude', promptModel: 'claude', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] })
  expect(sections.map(s => s.id)).toEqual(['intro', 'pending-items:instructions'])
  expect(sections[1]?.text).toContain('call the `add` tool')
})
