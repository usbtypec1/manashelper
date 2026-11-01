import type { components } from './generated/api'
import messages from './generated/messages.json'

export type Schemas = components['schemas']
export type Document = Schemas['FlowDocument']
export type FlowNode = Document['nodes'][number]
export type Text = Schemas['InlineText'] | Schemas['CatalogText']
export type Value = Schemas['LiteralValue'] | Schemas['ReferenceValue']
export type Predicate = Schemas['Compare'] | Schemas['Exists'] | Schemas['ConditionGroup']
export type Button = Schemas['TransitionButton'] | Schemas['UrlButton']
export type Scalar = Schemas['LiteralValue']['value']
export type Locale = Schemas['PreviewUser']['locale']
export type Theme = Schemas['PreviewUser']['theme']
export type Issue = Schemas['ContractIssue']
export type Port = { id: string; label: string; target: string }
export const locales: Locale[] = ['en', 'ru', 'ky', 'tr', 'zh']
export const kinds: FlowNode['kind'][] = ['menu', 'input', 'condition', 'action', 'end']
export const identifier = /^[a-z][a-z0-9_]{0,31}$/

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

export function inline(text: string): Text {
  return { kind: 'inline', translations: { en: text }, parameters: {}, themes: {} }
}

export function ports(node: FlowNode): Port[] {
  const result: Port[] = []
  if (node.kind === 'menu' || node.kind === 'input') {
    for (const [r, row] of (node.buttons ?? []).entries()) {
      for (const [b, button] of row.entries()) {
        if (button.kind === 'transition')
          result.push({ id: `button:${r}:${b}`, label: button.id, target: button.target })
      }
    }
    if (node.kind === 'input') result.push({ id: 'next', label: 'next', target: node.next })
  } else if (node.kind === 'condition') {
    node.branches.forEach((branch, index) =>
      result.push({ id: `branch:${index}`, label: `#${index + 1}`, target: branch.target }),
    )
    result.push({ id: 'default', label: 'else', target: node.default })
  } else if (node.kind === 'action') {
    Object.entries(node.outcomes).forEach(([label, target]) =>
      result.push({ id: `outcome:${label}`, label, target }),
    )
  }
  return result
}

export function connect(node: FlowNode, port: string, target: string): void {
  if (port.startsWith('button:') && (node.kind === 'menu' || node.kind === 'input')) {
    const [, r, b] = port.split(':')
    const button = node.buttons?.[Number(r)]?.[Number(b)]
    if (button?.kind === 'transition') button.target = target
  } else if (node.kind === 'input' && port === 'next') node.next = target
  else if (node.kind === 'condition' && port === 'default') node.default = target
  else if (node.kind === 'condition' && port.startsWith('branch:'))
    node.branches[Number(port.split(':')[1])].target = target
  else if (node.kind === 'action' && port.startsWith('outcome:')) node.outcomes[port.slice(8)] = target
}

export function renameNode(document: Document, previous: string, next: string): boolean {
  if (!identifier.test(next) || document.nodes.some((node) => node.id === next)) return false
  const node = document.nodes.find((node) => node.id === previous)
  if (!node) return false
  node.id = next
  if (document.entry === previous) document.entry = next
  if (document.navigation_entries) {
    for (const name of Object.keys(document.navigation_entries)) {
      if (document.navigation_entries[name] === previous) document.navigation_entries[name] = next
    }
  }
  document.nodes.forEach((item) =>
    ports(item).forEach((port) => {
      if (port.target === previous) connect(item, port.id, next)
    }),
  )
  if (document.layout?.[previous]) {
    document.layout[next] = document.layout[previous]
    delete document.layout[previous]
  }
  return true
}

export function newDocument(id: string): Document {
  return {
    schema_version: 1,
    id,
    entry: 'menu',
    fields: {},
    initial_data: {},
    nodes: [
      {
        kind: 'menu',
        id: 'menu',
        text: [inline(messages.en.menu)],
        keyboard: 'inline',
        buttons: [
          [{ kind: 'transition', id: 'continue', label: inline(messages.en.continue), target: 'end' }],
        ],
      },
      { kind: 'end', id: 'end', status: 'completed', text: [inline(messages.en.completed)] },
    ],
    layout: { menu: { x: 100, y: 100 }, end: { x: 460, y: 100 } },
  }
}

export function uniqueId(base: string, used: string[]): string {
  let count = 1
  while (used.includes(`${base}_${count}`)) count++
  return `${base}_${count}`
}

export function newNode(document: Document, kind: FlowNode['kind']): FlowNode {
  const id = uniqueId(
    kind,
    document.nodes.map((node) => node.id),
  )
  const target = document.nodes.find((node) => node.kind === 'end')?.id ?? document.entry
  switch (kind) {
    case 'menu':
      return { kind, id, text: [inline(messages.en.menu)], keyboard: 'inline', buttons: [] }
    case 'input':
      document.fields ??= {}
      document.fields[id] = { type: 'text', nullable: false }
      return {
        kind,
        id,
        text: [inline(messages.en.newValue)],
        field: id,
        input_type: 'text',
        next: target,
        error: inline(messages.en.invalidValue),
        buttons: [],
        min_length: 1,
        max_length: 4000,
        choices: [],
      }
    case 'condition':
      return {
        kind,
        id,
        branches: [
          { when: { kind: 'exists', reference: { kind: 'ref', scope: 'user', field: 'id' } }, target },
        ],
        default: target,
      }
    case 'action':
      return {
        kind,
        id,
        delegate: 'student_questions.has_submitted',
        contract_version: 1,
        arguments: { user_id: { kind: 'ref', scope: 'user', field: 'id' } },
        results: {},
        outcomes: { success: target },
      }
    case 'end':
      return { kind, id, status: 'completed', text: [inline(messages.en.completed)] }
  }
}

export function issueNode(document: Document, issue: Issue): string | undefined {
  if (issue.node_id) return issue.node_id
  const match = issue.path.match(/\/nodes\/(\d+)/)
  return match ? document.nodes[Number(match[1])]?.id : undefined
}

export function textLabel(
  text: Text | undefined,
  locale: Locale = 'en',
  catalog?: Schemas['EditorCatalog'],
): string {
  if (!text) return ''
  const translations =
    text.kind === 'inline'
      ? text.translations
      : catalog?.texts.find((item) => item.key === text.key)?.translations
  return translations?.[locale] ?? translations?.en ?? (text.kind === 'catalog' ? text.key : '')
}
