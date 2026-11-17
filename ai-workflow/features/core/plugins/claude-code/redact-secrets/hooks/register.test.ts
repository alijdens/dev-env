import { expect, mock, test } from 'claude-code/testing'
import type { TestBody } from 'claude-code/testing'

type On = Parameters<TestBody>[1]

// Stands for the `secrets` CLI: `redact` swaps the secret for a marker, as the real one does.
function secretsCli(on: On, { exitCode = 0 }: { exitCode?: number } = {}) {
  const calls: { argv: readonly string[]; stdin?: string }[] = []
  on('process.run', (_, e) => {
    calls.push({ argv: e.argv, stdin: e.init?.stdin })
    const stdout = (e.init?.stdin ?? '').replaceAll('hunter2hunter2', '[REDACTED:DB_PASSWORD]')
    return { value: { exitCode, stdout, stderr: exitCode ? 'boom' : '', isStdoutTruncated: false, isStderrTruncated: false } }
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
