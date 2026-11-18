import type { ApiContentBlock, EngineInterface, Register } from 'claude-code'

type $ = EngineInterface

// Appended once to each result that held a secret: the model reads it where it would have read the value.
const NOTE = '\n\n[Secret values were redacted from this output and shown as [REDACTED:NAME]. Never print, read or ask for secret values: check that one is set with `secrets has NAME` and list names with `secrets list` (see `secrets --help`). Never write redacted text back into a file: it would replace the real values with the markers.]'

// Rows a model or the person reads that can carry file contents: a tool's result and what the engine attaches
// beside it (a changed file, a hook's context, a notification delivered into a running turn), the prompts and
// deliveries that start a turn of their own (a background task's or a Monitor's notification, another
// session's message) and other plugins' notes. `session.append` raises them all, one door each. `command` is
// left alone: it is the output of a command the person ran themselves. This plugin appends no row, and a
// plugin's own append never runs its own hook, so a note can't loop back through here.
const DOORS = ['tool-result', 'tool-message', 'attachment', 'hook-context', 'prompt', 'delivery', 'note'] as const

// The origins the engine attests as the person, whose words reach the model as sent: a secret in them is one
// they chose to share. `composer` is their own Enter at the terminal, `bridge` their message through Remote
// Control, `slack-ping` the session's owner pinging it from Slack. `sdk` (`claude -p`, the Agent SDK) is a
// program's turn and is redacted, as is every other origin.
const PERSON = new Set(['composer', 'bridge', 'slack-ping'])

const ENV_FILE = /(^|\/)(\.env(\..*)?|\.secrets)$/
const MARKER = '[REDACTED:'
const TIMEOUT_MS = 10_000

// The `secrets` CLI does the matching, so the values stay in its process: this module only sees the result text.
async function redact($: $, text: string) {
  if (!text) return text
  const { exitCode, stdout, stderr, isStdoutTruncated } = await $.process.run(['secrets', 'redact'], { stdin: text, timeoutMs: TIMEOUT_MS })
  if (exitCode !== 0) throw new Error(stderr.trim() || `secrets redact exited ${exitCode}`)
  // A cut-off result would be stored with its tail missing, which is worse than storing it whole.
  if (isStdoutTruncated) throw new Error('the output was too large to redact')
  return stdout
}

const isText = (block: ApiContentBlock): block is ApiContentBlock & { type: 'text'; text: string } =>
  block.type === 'text' && typeof block.text === 'string'

// The text blocks among `blocks` redacted, with one note after the last that changed; other blocks are left.
async function redactTexts($: $, blocks: ApiContentBlock[]): Promise<ApiContentBlock[]> {
  const texts = await Promise.all(blocks.map(b => (isText(b) ? redact($, b.text) : undefined)))
  const changed = blocks.map((b, i) => isText(b) && texts[i] !== b.text)
  const last = changed.lastIndexOf(true)
  if (last === -1) return blocks
  return blocks.map((b, i) => (changed[i] ? { ...b, text: texts[i] + (i === last ? NOTE : '') } : b))
}

async function redactToolResult($: $, block: ApiContentBlock): Promise<ApiContentBlock> {
  if (block.type !== 'tool_result') return block
  if (typeof block.content === 'string') {
    const content = await redact($, block.content)
    return content === block.content ? block : { ...block, content: content + NOTE }
  }
  if (!Array.isArray(block.content)) return block
  const inner = block.content as ApiContentBlock[]
  const content = await redactTexts($, inner)
  return content === inner ? block : { ...block, content }
}

// Failing closed would make every tool unusable while `secrets` is missing; say so instead, once per distinct
// reason, so a second kind of failure isn't hidden behind the first.
function failOpen($: $, warned: Set<string>, error: unknown) {
  const reason = error instanceof Error ? error.message : String(error)
  if (warned.has(reason)) return
  warned.add(reason)
  $.ui.toast(`${$.plugin.name}: couldn't run \`secrets redact\`, so tool results are NOT being redacted (${reason}). Run ai-workflow/install.sh.`)
}

export const register: Register = on => {
  const warned = new Set<string>()

  for (const door of DOORS) {
    on('session.append', { door }, async ($, e, next) => {
      if (PERSON.has(e.origin.kind)) return next(e)
      let content: ApiContentBlock[]
      try {
        // A note per tool result (the model reads each on its own), one for the row's own text blocks.
        content = await redactTexts($, await Promise.all(e.message.content.map(block => redactToolResult($, block))))
      } catch (error) {
        failOpen($, warned, error)
        return next(e)
      }
      return next({ ...e, message: { ...e.message, content } })
    }).catch(($, e, next) => next(e))
  }

  // An attachment the engine renders for each request keeps the row as made whatever `session.append` answered,
  // and which kinds are rendered that way isn't documented, so every attachment is redacted again as a request
  // carries it (one already redacted comes back unchanged). Except `queued_command`: a prompt or notification
  // delivered into a running turn, whose sender, which decides, only `session.append` knows.
  on('prompt.attachment', async ($, e, next) => {
    const result = await next(e)
    if (e.type === 'queued_command' || !result.text) return result
    try {
      const text = await redact($, result.text)
      return text === result.text ? result : { text: text + NOTE }
    } catch (error) {
      failOpen($, warned, error)
      return result
    }
  }).catch(($, e, next) => next(e))

  // A model that read a redacted env file and writes it back would replace the real values, gitignored and so
  // unrecoverable, with markers. Edit's `old_string` can't match a marker, so only what is written needs guarding.
  const guard = (text: unknown, path: unknown) =>
    typeof text === 'string' && typeof path === 'string' && ENV_FILE.test(path) && text.includes(MARKER)
      ? { deny: `${path} would get a ${MARKER}NAME] marker where a secret value is: those are redactions of what you read, not the file's contents. Edit only the lines you mean to change, leaving the others as they are.` }
      : undefined

  on('tool.call', { tool: 'Write' }, ($, e, next) => guard(e.content, e.file_path) ?? next(e)).catch(($, e, next) => next(e))
  on('tool.call', { tool: 'Edit' }, ($, e, next) => guard(e.new_string, e.file_path) ?? next(e)).catch(($, e, next) => next(e))
}
