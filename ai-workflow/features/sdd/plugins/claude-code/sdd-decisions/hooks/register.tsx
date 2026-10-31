import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Answering, Question, Summary } from '../types'

// `null`: not a task-workflow project, or the CLI isn't reachable; the band stays hidden.
const summary = atom({ plugin: 'sdd-decisions', key: 'summary' } as const, null as Summary | null)
const answering = atom({ plugin: 'sdd-decisions', key: 'answering' } as const, null as Answering | null)

const REFRESH_MS = 60_000
// A user who says "stop" leaves no trace in the session, so the skill counts as over after this long without touching a question.
const IDLE_MS = 30 * 60_000
// Commands after which main, or the question files, may have changed.
const REFRESH_AFTER = /\bgh pr merge\b|\bgit (pull|merge|fetch|rebase|checkout|switch)\b/
const SDD_CHANGES = new Set(['ask', 'answer', 'defer', 'done', 'start', 'release', 'new', 'ship'])
const SDD_CALL = /\bsdd((?:\s+--(?:main|dir[= ]\S+))*)\s+([a-z]+)/g
// No sdd command says which question is being discussed: the skill reads its file to introduce it.
const QUESTION_FILE = /questions\/open\/([\w-]+)\.md/
const WRITES_FILE = /(?<![\d&])>|\bsed -i\b|\btee\b/

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

function parseQuestions(text: string): Question[] {
  return text
    .split('\n')
    .filter(Boolean)
    .map(line => {
      const [slug = '', , title = ''] = line.split('\t')
      return { slug, title }
    })
}

function sddCalls(command: string) {
  return [...command.matchAll(SDD_CALL)].map(([, flags = '', name = '']) => {
    const dir = /--dir[= ](\S+)/.exec(flags)?.[1]?.replace(/['"]/g, '')
    // A shell variable means nothing outside that shell.
    return { name, dir: dir?.includes('$') ? undefined : dir }
  })
}

// Goes by the skill's own `--dir`: main doesn't have its answers until they ship.
async function refreshPending($: EngineInterface) {
  const dir = (await read($, answering))?.dir
  if (dir === undefined) return
  let pending: Question[]
  try {
    const ran = await $.process.run(['sdd', ...(dir ? ['--dir', dir] : []), 'questions'], { timeoutMs: 120_000 })
    if (ran.exitCode !== 0) return
    pending = parseQuestions(ran.stdout)
  } catch {
    return
  }
  await update($, answering, a => {
    if (a === null || pending.length === 0) return null
    return { ...a, pending, current: pending.some(q => q.slug === a.current) ? a.current : null }
  })
}

async function touch($: EngineInterface, change: Partial<Answering>) {
  const touchedAt = await $.clock.now()
  await update($, answering, a => a && { ...a, ...change, touchedAt })
}

async function expireAnswering($: EngineInterface) {
  const now = await $.clock.now()
  await update($, answering, a => (a && now - a.touchedAt >= IDLE_MS ? null : a))
}

function questionIn(text: string) {
  return QUESTION_FILE.exec(text)?.[1]
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    if (e.isInteractive) {
      void refresh($, e.cwd)
      $.clock.every(REFRESH_MS, () => {
        void refresh($, e.cwd)
        void expireAnswering($).then(() => refreshPending($))
      })
    }
    return started
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    const command = 'command' in e ? String(e.command) : ''
    const calls = sddCalls(command)
    if (REFRESH_AFTER.test(command) || calls.some(c => SDD_CHANGES.has(c.name))) void refresh($)

    const dir = calls.findLast(c => c.dir)?.dir
    const slug = WRITES_FILE.test(command) ? undefined : questionIn(command)
    if (calls.length > 0 || slug) {
      await touch($, { ...(dir && { dir }), ...(slug && { current: slug }) })
      void refreshPending($)
    }
    return ran
  })

  on('tool.call', { tool: 'Read' }, async ($, e, next) => {
    const ran = await next(e)
    const slug = questionIn('file_path' in e ? String(e.file_path) : '')
    if (slug) await touch($, { current: slug })
    return ran
  })

  on('skill.prompt', { skill: 'sdd-answer-questions' }, async ($, e, next) => {
    const touchedAt = await $.clock.now()
    await update($, answering, () => ({ dir: null, current: null, pending: null, touchedAt }))
    void refreshPending($)
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    await update($, answering, () => null)
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, summary)
    const a = await read($, answering)
    if (e.props.hasSurvey) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    if (a?.pending) {
      const question = a.pending.find(q => q.slug === a.current)
      return (
        <Box>
          <Text wrap="truncate-end" color="cyan">
            {a.current
              ? `Answering question: ${question?.title ?? a.current}, ${a.pending.length - (question ? 1 : 0)} more pending`
              : `Answering open questions, ${a.pending.length} pending`}
          </Text>
        </Box>
      )
    }
    if (s === null || s.open === 0) return next(e)

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
