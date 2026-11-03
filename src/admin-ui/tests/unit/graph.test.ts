import { describe, expect, test } from 'bun:test'
import { clone, connect, issueNode, newDocument, newNode, ports, renameNode } from '../../src/types'

describe('graph contract', () => {
  test('rewiring a button changes its target and preserves other behavior', () => {
    const document = newDocument('test_flow')
    const before = clone(document)
    connect(document.nodes[0], 'button:0:0', 'input_1')
    expect(ports(document.nodes[0])[0].target).toBe('input_1')
    expect(document.nodes[1]).toEqual(before.nodes[1])
  })
  test('all connector types round-trip to executable fields', () => {
    const document = newDocument('test_flow')
    for (const kind of ['input', 'condition', 'action', 'call'] as const) {
      const node = newNode(document, kind)
      const before = ports(node)
      for (const port of before) connect(node, port.id, 'menu')
      expect(ports(node).map((port) => port.target)).toEqual(before.map(() => 'menu'))
    }
  })
  test('renaming updates entry, every incoming reference and coordinates', () => {
    const document = newDocument('test_flow')
    document.navigation_entries = { study: 'menu' }
    const condition = newNode(document, 'condition')
    document.nodes.push(condition)
    expect(renameNode(document, 'end', 'finished')).toBe(true)
    expect(ports(document.nodes[0])[0].target).toBe('finished')
    expect(ports(condition).every((port) => port.target === 'finished')).toBe(true)
    expect(document.layout?.finished).toEqual({ x: 460, y: 100 })
    expect(document.layout?.end).toBeUndefined()
    expect(renameNode(document, 'menu', 'root')).toBe(true)
    expect(document.entry).toBe('root')
    expect(document.navigation_entries?.study).toBe('root')
  })
  test('invalid and duplicate renames preserve the complete document', () => {
    const document = newDocument('test_flow'),
      before = clone(document)
    expect(renameNode(document, 'menu', 'end')).toBe(false)
    expect(renameNode(document, 'menu', 'Bad name')).toBe(false)
    expect(document).toEqual(before)
  })
  test('Call continuation edits preserve scenario identity and explicit argument/result bindings', () => {
    const document = newDocument('parent')
    document.schema_version = 2
    document.fields = { end: { type: 'text' } }
    const call = newNode(document, 'call')
    if (call.kind !== 'call') throw new Error('Expected a Call node')
    call.flow = 'end'
    call.arguments = { selection: { kind: 'ref', scope: 'data', field: 'end' } }
    call.results = { selected: 'end' }
    call.outcomes = { completed: 'end', cancelled: 'menu' }
    document.nodes.push(call)
    const before = clone(call)
    connect(call, 'outcome:cancelled', 'end')
    expect(ports(call)).toEqual([
      { id: 'outcome:completed', label: 'completed', target: 'end' },
      { id: 'outcome:cancelled', label: 'cancelled', target: 'end' },
    ])
    expect(renameNode(document, 'end', 'finished')).toBe(true)
    expect(call.outcomes).toEqual({ completed: 'finished', cancelled: 'finished' })
    expect(call.flow).toBe(before.flow)
    expect(call.arguments).toEqual(before.arguments!)
    expect(call.results).toEqual(before.results!)
    expect(document.fields).toEqual({ end: { type: 'text' } })
  })
  test('Return and Replace have no fabricated local graph edges', () => {
    const document = newDocument('parent')
    document.schema_version = 2
    document.outcomes = ['selected', 'cancelled']
    const returned = newNode(document, 'return')
    const replaced = newNode(document, 'replace')
    if (returned.kind !== 'return' || replaced.kind !== 'replace')
      throw new Error('Expected composition terminal nodes')
    returned.values = { selected: { kind: 'literal', value: 'menu' } }
    replaced.flow = 'menu'
    replaced.arguments = { choice: { kind: 'literal', value: 'menu' } }
    document.nodes.push(returned, replaced)
    const before = clone([returned, replaced])
    expect(returned.outcome).toBe('selected')
    expect(ports(returned)).toEqual([])
    expect(ports(replaced)).toEqual([])
    connect(replaced, 'outcome:completed', 'end')
    expect(renameNode(document, 'menu', 'root')).toBe(true)
    expect([returned, replaced]).toEqual(before)
  })
  test('layout edits leave executable nodes intact', () => {
    const document = newDocument('test_flow'),
      before = clone(document)
    document.layout!.menu = { x: 123, y: 456 }
    expect(document.nodes).toEqual(before.nodes)
    expect(document.entry).toBe(before.entry)
  })
  test('validation paths select the responsible node', () => {
    const document = newDocument('test_flow')
    expect(
      issueNode(document, { code: 'invalid', path: '/body/document/nodes/1/end/text', message: '' }),
    ).toBe('end')
    expect(issueNode(document, { code: 'invalid', path: '/nodes/1', message: '', node_id: 'menu' })).toBe(
      'menu',
    )
  })
})
