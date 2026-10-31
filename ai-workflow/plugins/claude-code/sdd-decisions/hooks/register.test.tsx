import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  plugin: 'sdd-decisions',
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

const REPORT = {
  open: 3,
  blockers: [
    { slug: 'rate-limit', title: 'Rate limit behind a proxy?', blocks: ['bookings-api'], downstream: 10, asked: '2026-10-29' },
    { slug: 'ttl', title: 'How long?', blocks: ['cache'], downstream: 1, asked: '2026-10-29' },
  ],
}

function stdout(text: string) {
  return { value: { exitCode: 0, stdout: text, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
}

test('the band counts open questions and names the decision holding up the most work', async ($, on) => {
  const clock = mock.clock(on)
  on('process.run', () => stdout(JSON.stringify(REPORT)))
  on('session.start', (_, e) => ({ cwd: e.cwd }))

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await clock.settle()

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    const row = await ui.find({ type: 'Text', text: /open question/ })
    expect(row?.text).toContain('3 open questions, /sdd-answer-questions to resolve')
    expect(row?.text).toContain('2 block 10 tasks or more: Rate limit behind a proxy? (bookings-api)')
    expect(row?.text).toContain('+1 more')
    await ui.unmount()
  }
})

test('without a task workflow the band is left to the engine', async ($, on) => {
  const clock = mock.clock(on)
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'sdd: project not initialized', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await clock.settle()

  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
  await ui.unmount()
})

test('a merge in the session refreshes the band', async ($, on) => {
  const clock = mock.clock(on)
  let calls = 0
  on('process.run', () => stdout(JSON.stringify(calls++ === 0 ? { open: 1, blockers: [] } : { open: 0, blockers: [] })))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await clock.settle()
  let ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /open question/ }))?.text).toBe('1 open question, /sdd-answer-questions to resolve')
  await ui.unmount()

  await $.tool.call({ tool: 'Bash', command: 'gh pr merge 12 --squash' })
  await clock.settle()
  ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /engine/ }))?.text).toBe('engine')
  await ui.unmount()
})
