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

function fakeSdd(pending: { value: string }, dirs: (string | undefined)[] = []) {
  return (_: unknown, e: { argv: readonly string[] }) => {
    if (e.argv.includes('blockers')) return stdout(JSON.stringify(REPORT))
    const at = e.argv.indexOf('--dir')
    dirs.push(at === -1 ? undefined : e.argv[at + 1])
    return stdout(pending.value)
  }
}

const THREE = 'ttl\topen\tHow long?\t\t\t2026-10-29\nauth\topen\tWhich provider?\t\t\t2026-10-29\nlogs\topen\tKeep logs?\t\t\t2026-10-29\n'

async function bandText($: any, surface: 'terminal' | 'desktop' = 'terminal') {
  const ui = await $.ui.mount({ ...BAND, surface })
  const row = await ui.find({ type: 'Text', text: /question|pending/ })
  await ui.unmount()
  return row?.text
}

async function startAnswering($: any, on: any, pending: { value: string }, dirs?: (string | undefined)[]) {
  const clock = mock.clock(on)
  on('process.run', fakeSdd(pending, dirs))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: {} }))
  on('skill.prompt', (_: unknown, e: { text: string }) => ({ text: e.text }))
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.skill.prompt({ skill: 'sdd-answer-questions', text: 'walk' })
  await clock.settle()
  return clock
}

test('the skill swaps the band for its progress, following the question it reads', async ($, on) => {
  const clock = await startAnswering($, on, { value: THREE })
  expect(await bandText($)).toBe('Answering open questions, 3 pending')

  await $.tool.call({ tool: 'Read', file_path: '/w/tasks/questions/open/auth.md' })
  await clock.settle()
  expect(await bandText($)).toBe('Answering question: Which provider?, 2 more pending')

  await $.tool.call({ tool: 'Bash', command: 'sed -n 1,40p tasks/questions/open/logs.md 2>/dev/null' })
  await clock.settle()
  expect(await bandText($)).toBe('Answering question: Keep logs?, 2 more pending')
})

test('a question file being written is not the one under discussion', async ($, on) => {
  const clock = await startAnswering($, on, { value: THREE })
  await $.tool.call({ tool: 'Read', file_path: '/w/tasks/questions/open/auth.md' })
  await $.tool.call({ tool: 'Bash', command: 'cat > tasks/questions/open/logs.md <<EOF' })
  await clock.settle()
  expect(await bandText($)).toBe('Answering question: Which provider?, 2 more pending')
})

test('closing a question recounts in the directory the skill works in', async ($, on) => {
  const pending = { value: THREE }
  const dirs: (string | undefined)[] = []
  const clock = await startAnswering($, on, pending, dirs)
  await $.tool.call({ tool: 'Read', file_path: '/w/tasks/questions/open/ttl.md' })

  pending.value = THREE.split('\n').slice(1).join('\n')
  await $.tool.call({ tool: 'Bash', command: 'cd /w && sdd --dir /w/tasks answer ttl' })
  await clock.settle()
  expect(dirs.at(-1)).toBe('/w/tasks')
  expect(await bandText($)).toBe('Answering open questions, 2 pending')
})

test('the band returns when nothing is left to answer', async ($, on) => {
  const pending = { value: 'ttl\topen\tHow long?\t\t\t2026-10-29\n' }
  const clock = await startAnswering($, on, pending)
  pending.value = ''
  await $.tool.call({ tool: 'Bash', command: 'sdd answer ttl' })
  await clock.settle()
  expect(await bandText($)).toContain('3 open questions, /sdd-answer-questions to resolve')
})

test('the band returns after half an hour without touching a question', async ($, on) => {
  const clock = await startAnswering($, on, { value: THREE })
  await clock.advance(29 * 60_000)
  expect(await bandText($)).toBe('Answering open questions, 3 pending')
  await clock.advance(60_000)
  await clock.settle()
  expect(await bandText($)).toContain('3 open questions, /sdd-answer-questions to resolve')
})
