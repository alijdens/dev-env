import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Summary } from '../types'

// `null`: not a task-workflow project, or the CLI isn't reachable; the band stays hidden.
const summary = atom({ plugin: 'sdd-decisions', key: 'summary' } as const, null as Summary | null)

const REFRESH_MS = 60_000
// Commands after which main, or the question files, may have changed.
const REFRESH_AFTER = /\bgh pr merge\b|\bgit (pull|merge|fetch|rebase|checkout|switch)\b|\bsdd (ask|answer|defer|done|start|release|new)\b/

function parse(text: string): Summary | null {
  try {
    const value = JSON.parse(text) as Partial<Summary>
    if (typeof value.open !== 'number' || !Array.isArray(value.blockers)) return null
    return { open: value.open, blockers: value.blockers }
  } catch {
    return null
  }
}

async function refresh($: EngineInterface, cwd?: string) {
  let next: Summary | null = null
  try {
    const ran = await $.process.run(['sdd', 'blockers', '--json', '--main'], { cwd, timeoutMs: 120_000 })
    if (ran.exitCode === 0) next = parse(ran.stdout)
  } catch {
    next = null
  }
  await update($, summary, () => next)
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    if (e.isInteractive) {
      void refresh($, e.cwd)
      $.clock.every(REFRESH_MS, () => void refresh($, e.cwd))
    }
    return started
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    const command = 'command' in e ? String(e.command) : ''
    if (REFRESH_AFTER.test(command)) void refresh($)
    return ran
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, summary)
    if (e.props.hasSurvey || s === null || s.open === 0) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    const [first, ...rest] = s.blockers

    return (
      <Box>
        <Text wrap="truncate-end">
          <Text dimColor>{plural(s.open, 'open question')}, /sdd-answer-questions to resolve</Text>
          {first && (
            <Text color="yellow">
              {' · ⚠ '}
              {s.blockers.length === 1 ? '1 blocks' : `${s.blockers.length} block`} {plural(first.downstream, 'task')}
              {s.blockers.length === 1 ? '' : ' or more'}: {first.title} ({first.blocks.join(', ')})
              {rest.length > 0 && <Text dimColor> +{rest.length} more</Text>}
            </Text>
          )}
        </Text>
      </Box>
    )
  })
}
