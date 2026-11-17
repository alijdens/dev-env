import type { ApiContentBlock, EngineInterface, Register } from 'claude-code'

type $ = EngineInterface

// Appended once to each result that held a secret: the model reads it where it would have read the value.
const NOTE = '\n\n[Secret values were redacted from this output and shown as [REDACTED:NAME]. Never print, read or ask for secret values: check that one is set with `secrets has NAME` and list names with `secrets list` (see `secrets --help`).]'

// The `secrets` CLI does the matching, so the values stay in its process: this module only sees the result text.
async function redact($: $, text: string) {
  if (!text) return text
  const { exitCode, stdout, stderr } = await $.process.run(['secrets', 'redact'], { stdin: text })
  if (exitCode !== 0) throw new Error(stderr.trim() || `secrets redact exited ${exitCode}`)
  return stdout === text ? text : stdout + NOTE
}

async function redactBlock($: $, block: ApiContentBlock): Promise<ApiContentBlock> {
  if (block.type === 'text' && typeof block.text === 'string') return { ...block, text: await redact($, block.text) }
  if (block.type !== 'tool_result') return block
  if (typeof block.content === 'string') return { ...block, content: await redact($, block.content) }
  if (Array.isArray(block.content)) return { ...block, content: await Promise.all(block.content.map(inner => redactBlock($, inner as ApiContentBlock))) }
  return block
}

export const register: Register = on => {
  let hasWarned = false

  on('session.append', { door: 'tool-result' }, async ($, e, next) => {
    let content: ApiContentBlock[]
    try {
      content = await Promise.all(e.message.content.map(block => redactBlock($, block)))
    } catch (error) {
      // Failing closed would make every tool unusable while `secrets` is missing; say so once instead.
      if (!hasWarned) {
        hasWarned = true
        $.ui.toast(`${$.plugin.name}: couldn't run \`secrets redact\`, so tool results are NOT being redacted (${error instanceof Error ? error.message : String(error)}). Run ai-workflow/install.sh.`)
      }
      return next(e)
    }
    return next({ ...e, message: { ...e.message, content } })
  }).catch(($, e, next) => next(e))
}
