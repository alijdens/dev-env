import { expect, mock, test } from 'claude-code/testing'
import type { Plugin, TestBody } from 'claude-code/testing'

type On = Parameters<TestBody>[1]

// Stands for the `secrets` CLI: `redact` swaps the secret for a marker, as the real one does.
function secretsCli(on: On, { exitCode = 0, isStdoutTruncated = false }: { exitCode?: number; isStdoutTruncated?: boolean } = {}) {
  const calls: { argv: readonly string[]; stdin?: string; timeoutMs?: number }[] = []
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, stdin: e.init?.stdin, timeoutMs: e.init?.timeoutMs })
    const stdout = (e.init?.stdin ?? '').replaceAll('hunter2hunter2', '[REDACTED:DB_PASSWORD]')
    return { value: { exitCode, stdout, stderr: exitCode ? 'boom' : '', isStdoutTruncated, isStderrTruncated: false } }
  })
  return calls
}

type Stored = { content: string | { type: string; text?: string }[] }

// The tool_result blocks of the first row the session kept.
const stored = (session: ReturnType<typeof mock.session>) => (session.appended()[0]?.message.content ?? []) as unknown as Stored[]

const toolResult = (content: unknown) => ({
  message: { type: 'user' as const, role: 'user' as const, content: [{ type: 'tool_result', tool_use_id: 't1', content }] },
  door: 'tool-result' as const,
  origin: { kind: 'tool' as const, tool: 'Bash' },
  uuid: 'u1',
})

test('a secret in a tool result is replaced, with a note on how to check one', async ($, on) => {
  const calls = secretsCli(on)
  const session = mock.session(on)

  await $.session.append(toolResult('DB_PASSWORD=hunter2hunter2\nPORT=3000'))

  const content = stored(session)[0]?.content as string
  expect(content).toContain('DB_PASSWORD=[REDACTED:DB_PASSWORD]\nPORT=3000')
  expect(content).toContain('`secrets has NAME`')
  expect(content).not.toContain('hunter2')
  expect(calls[0]?.argv).toEqual(['secrets', 'redact'])
  // A hung CLI would hold the row, and with it the session, forever.
  expect(calls[0]?.timeoutMs).toBeGreaterThan(0)
})

test('a result without secrets is stored as it came, with no note', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)

  await $.session.append(toolResult('all good'))

  expect(stored(session)[0]?.content).toBe('all good')
})

test('text blocks inside a tool result are redacted one by one, other blocks are left', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)
  const image = { type: 'image', source: { type: 'base64', data: 'hunter2hunter2' } }

  await $.session.append(toolResult([{ type: 'text', text: 'pw hunter2hunter2' }, image]))

  const content = stored(session)[0]?.content as { type: string; text?: string }[]
  expect(content[0]?.text).toContain('pw [REDACTED:DB_PASSWORD]')
  expect(content[1]).toEqual(image)
})

test('a result whose text blocks both held a secret gets one note, after the last of them', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)

  await $.session.append(toolResult([{ type: 'text', text: 'a hunter2hunter2' }, { type: 'text', text: 'b hunter2hunter2' }, { type: 'text', text: 'c' }]))

  const texts = (stored(session)[0]?.content as { text: string }[]).map(block => block.text)
  expect(texts[0]).toBe('a [REDACTED:DB_PASSWORD]')
  expect(texts[1]).toStartWith('b [REDACTED:DB_PASSWORD]')
  expect(texts[1]).toContain('`secrets has NAME`')
  expect(texts[2]).toBe('c')
})

test('a row whose own text blocks both held a secret gets one note, after the last of them', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)
  const blocks = [{ type: 'text' as const, text: 'a hunter2hunter2' }, { type: 'text' as const, text: 'b hunter2hunter2' }]

  await $.session.append({ message: { type: 'user', role: 'user', content: blocks }, door: 'prompt', origin: { kind: 'task-notification' } as never, uuid: 'u2' })

  const texts = (session.appended()[0]?.message.content as unknown as { text: string }[]).map(block => block.text)
  expect(texts[0]).toBe('a [REDACTED:DB_PASSWORD]')
  expect(texts[1]).toStartWith('b [REDACTED:DB_PASSWORD]')
  expect(texts[1]).toContain('`secrets has NAME`')
})

test('when the CLI fails the result is stored unredacted and the person is told once', async ($, on) => {
  secretsCli(on, { exitCode: 2 })
  const session = mock.session(on)
  const toasts: string[] = []
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))

  await $.session.append(toolResult('one'))
  await $.session.append(toolResult('two'))

  expect(session.appended()).toHaveLength(2)
  expect(toasts).toHaveLength(1)
  expect(toasts[0] ?? '').toContain('NOT being redacted')
})

test('a CLI that is missing or cuts its output off leaves the result stored, and each distinct reason is toasted once', async ($, on) => {
  // `b` is cut off; the others reach the kit's bottom, which rejects as a command that can't start does.
  on('process.run', (_, e, next) =>
    e.init?.stdin === 'b' ? { value: { exitCode: 0, stdout: 'b', stderr: '', isStdoutTruncated: true, isStderrTruncated: false } } : next(e))
  const session = mock.session(on)
  const toasts: string[] = []
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))

  for (const text of ['a', 'b', 'c']) await $.session.append(toolResult(text))

  expect(session.appended().map(row => (row.message.content[0] as unknown as Stored).content)).toEqual(['a', 'b', 'c'])
  expect(toasts).toHaveLength(2)
  expect(toasts[0]).toContain('no implementation for process.run')
  expect(toasts[1]).toContain('too large to redact')
})

test('output too large to redact is stored whole, not cut off, and says why', async ($, on) => {
  secretsCli(on, { isStdoutTruncated: true })
  const session = mock.session(on)
  const toasts: string[] = []
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))

  await $.session.append(toolResult('x'.repeat(100)))

  expect(stored(session)[0]?.content).toBe('x'.repeat(100))
  expect(toasts[0]).toContain('too large to redact')
})

test('rows beside a tool result are redacted too: plain text blocks, tool messages, attachments and hook context', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)
  const rows = [
    ['tool-message', 'user', { kind: 'tool', tool: 'Bash' }],
    ['attachment', 'attachment', { kind: 'engine' }],
    ['hook-context', 'user', { kind: 'hook', event: 'PostToolUse' }],
  ] as const

  for (const [door, type, origin] of rows) {
    await $.session.append({ message: { type, role: 'user', content: [{ type: 'text', text: 'pw hunter2hunter2' }] }, door, origin, uuid: `u-${door}` } as never)
  }

  const texts = session.appended().map(row => (row.message.content[0] as unknown as { text: string }).text)
  expect(texts).toHaveLength(rows.length)
  for (const text of texts) {
    expect(text).toContain('pw [REDACTED:DB_PASSWORD]')
    expect(text).not.toContain('hunter2')
  }
})

const prompt = (door: 'prompt' | 'delivery', kind: string) => ({
  message: { type: 'user' as const, role: 'user' as const, content: [{ type: 'text' as const, text: 'pw hunter2hunter2' }] },
  door,
  origin: { kind } as never,
  uuid: `u-${door}-${kind}`,
})

test('a notification, a message from another session and an SDK host\'s turn are redacted', async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)

  await $.session.append(prompt('prompt', 'task-notification'))
  await $.session.append(prompt('delivery', 'peer'))
  await $.session.append(prompt('prompt', 'sdk'))

  const texts = session.appended().map(row => (row.message.content[0] as unknown as { text: string }).text)
  expect(texts).toHaveLength(3)
  for (const text of texts) expect(text).toContain('pw [REDACTED:DB_PASSWORD]')
})

// Another plugin that appends a note for the model when it sees a Bash call.
const notifier: Plugin = {
  name: 'notifier',
  register: on => {
    on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
      await $.session.append({ message: { type: 'user', content: [{ type: 'text', text: 'pw hunter2hunter2' }] } })
      return next(e)
    })
  },
}

test('another plugin\'s note is redacted', { plugins: [notifier] }, async ($, on) => {
  secretsCli(on)
  const session = mock.session(on)
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({ tool: 'Bash', command: 'true' })

  const [row] = session.appended()
  expect(row?.door).toBe('note')
  expect((row?.message.content[0] as unknown as { text: string }).text).toStartWith('pw [REDACTED:DB_PASSWORD]')
})

test('what the person sends themselves is left as they wrote it', async ($, on) => {
  const calls = secretsCli(on)
  const session = mock.session(on)

  for (const kind of ['composer', 'bridge', 'slack-ping']) await $.session.append(prompt('prompt', kind))

  const texts = session.appended().map(row => (row.message.content[0] as unknown as { text: string }).text)
  expect(texts).toEqual(Array(3).fill('pw hunter2hunter2'))
  expect(calls).toHaveLength(0)
})

test('an attachment is redacted as a request carries it, but for a prompt delivered into a running turn', async ($, on) => {
  const calls = secretsCli(on)
  on('prompt.attachment', (_, e) => ({ text: e.text }))
  const attachment = (type: string) => $.prompt.attachment({ type, text: 'pw hunter2hunter2', origin: { kind: 'engine' } })

  const edited = await attachment('edited_text_file')
  expect(edited.text).toStartWith('pw [REDACTED:DB_PASSWORD]')
  expect(edited.text).toContain('`secrets has NAME`')
  expect((await attachment('queued_command')).text).toBe('pw hunter2hunter2')
  expect(calls).toHaveLength(1)
})

test('writing redacted text into an env file is refused, other writes are not', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  const redacted = 'DB_PASSWORD=[REDACTED:DB_PASSWORD]\n'

  for (const path of ['/repo/.env', '.env.local', '/repo/apps/api/.secrets']) {
    const write = await $.tool.call({ tool: 'Write', file_path: path, content: redacted })
    expect(write.deny).toContain('marker')
    const edit = await $.tool.call({ tool: 'Edit', file_path: path, old_string: 'A=1', new_string: redacted })
    expect(edit.deny).toContain('marker')
  }

  // Docs about the markers, and env files written without them, go through.
  expect((await $.tool.call({ tool: 'Write', file_path: '/repo/README.md', content: redacted })).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'Write', file_path: '/repo/.env', content: 'A=1\n' })).deny).toBeUndefined()
  expect((await $.tool.call({ tool: 'Write', file_path: '/repo/.environment', content: redacted })).deny).toBeUndefined()
})
