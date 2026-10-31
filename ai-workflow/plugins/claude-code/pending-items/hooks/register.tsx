import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Item, Pending } from '../types'

const PLUGIN = 'pending-items'
const ADD = `mcp__${PLUGIN}__add`
const RESOLVE = `mcp__${PLUGIN}__resolve`
const EMPTY: Pending = { items: [], nextId: 1 }

const pending = atom({ plugin: 'pending-items', key: 'pending' } as const, EMPTY)

// Read by the model with every prompt: when to call the tools, and when not to.
const INSTRUCTIONS = `# Pending items

The person follows long sessions and can miss something you need from them. When you ask them for a decision or an approval that work waits on, or that is hard to reverse (merge or publish this? delete that? which of these options? may I proceed with X?), call the \`add\` tool of ${PLUGIN} with a one-line description of what you need, in the same turn as the question. Ordinary clarifications you expect answered in the next message don't go there. Once the person has answered, or the item no longer applies, call \`resolve\` with its id in the same turn. The items are shown to the person above the prompt until resolved; they can also list them with /pending.`

function list(items: Item[]) {
  return items.length === 0 ? 'Nothing pending.' : items.map(i => `${i.id}. ${i.text}`).join('\n')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.tool.register({
      name: 'add',
      description: 'Records something you are waiting on from the person (a decision, an approval) so it stays visible to them until resolved. Returns its id.',
      inputSchema: { type: 'object', properties: { text: { type: 'string', description: 'One line: what you need from the person, and for what.' } }, required: ['text'] },
      isDeferred: false,
    })
    await $.tool.register({
      name: 'resolve',
      description: 'Removes a pending item once the person answered it or it no longer applies.',
      inputSchema: { type: 'object', properties: { id: { type: 'number', description: 'The id `add` returned.' } }, required: ['id'] },
      isDeferred: false,
    })
    if (e.isInteractive) {
      await $.command.register({ name: 'pending', description: 'What the model is waiting on from you; `/pending clear` drops it all, `/pending done <id>` one item.', argumentHint: '[clear | done <id>]' })
    }
    return started
  })

  on('prompt.compose', async ($, e, next) => {
    const { sections } = await next(e)
    return { sections: [...sections, { id: `${PLUGIN}:instructions`, text: INSTRUCTIONS, scope: 'session' }] }
  })

  on('tool.call', { tool: ADD }, async ($, e) => {
    const text = typeof e.text === 'string' ? e.text.trim() : ''
    if (!text) return { deny: 'add needs a non-empty `text`' }
    let id = 0
    await update($, pending, p => {
      const current = p ?? EMPTY
      id = current.nextId
      return { items: [...current.items, { id, text, addedAt: new Date().toISOString() }], nextId: id + 1 }
    })
    return { result: `pending item ${id} added: ${text}` }
  })

  on('tool.call', { tool: RESOLVE }, async ($, e) => {
    const id = typeof e.id === 'number' ? e.id : Number(e.id)
    const current = (await read($, pending)) ?? EMPTY
    if (!current.items.some(i => i.id === id)) return { deny: `no pending item ${id}; open: ${list(current.items)}` }
    await update($, pending, p => ({ ...(p ?? EMPTY), items: (p ?? EMPTY).items.filter(i => i.id !== id) }))
    return { result: `pending item ${id} resolved` }
  })

  on('command.run', { command: 'pending' }, async ($, e) => {
    const [verb, arg] = (e.args ?? '').trim().split(/\s+/)
    const current = (await read($, pending)) ?? EMPTY
    if (verb === 'clear') {
      await update($, pending, p => ({ ...(p ?? EMPTY), items: [] }))
      return { text: `Cleared ${current.items.length} pending item${current.items.length === 1 ? '' : 's'}.` }
    }
    if (verb === 'done') {
      const id = Number(arg)
      if (!current.items.some(i => i.id === id)) return { text: `No pending item ${arg ?? ''}.\n${list(current.items)}` }
      await update($, pending, p => ({ ...(p ?? EMPTY), items: (p ?? EMPTY).items.filter(i => i.id !== id) }))
      return { text: `Resolved ${id}.` }
    }
    return { text: list(current.items) }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const current = (await read($, pending)) ?? EMPTY
    const [first, ...rest] = current.items
    if (e.props.hasSurvey || !first) return next(e)

    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box>
        <Text wrap="truncate-end">
          <Text color="yellow">
            {'⚑ '}
            {current.items.length === 1 ? 'Waiting on you' : `${current.items.length} waiting on you`}: {first.text}
          </Text>
          {rest.length > 0 && <Text dimColor> +{rest.length} more</Text>}
          <Text dimColor> · /pending</Text>
        </Text>
      </Box>
    )
  })
}
