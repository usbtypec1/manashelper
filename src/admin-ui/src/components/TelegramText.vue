<script lang="ts">
import { defineComponent, h, type VNodeChild } from 'vue'

// Parse only presentation tags. No HTML injection, DOMParser, URLs or event attributes.
function decode(text: string): string {
  return text.replace(/&(lt|gt|amp|quot|apos|#\d+|#x[0-9a-f]+);/gi, (all, entity: string) => {
    const named: Record<string, string> = { lt: '<', gt: '>', amp: '&', quot: '"', apos: "'" }
    if (named[entity]) return named[entity]
    const value = entity.startsWith('#x') ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
    return value >= 0 && value <= 0x10ffff ? String.fromCodePoint(value) : all
  })
}
export default defineComponent({
  props: { text: { type: String, required: true } },
  setup(props) {
    return () => {
      const tags: Record<string, string> = {
        b: 'strong',
        strong: 'strong',
        i: 'em',
        em: 'em',
        u: 'u',
        ins: 'u',
        s: 's',
        strike: 's',
        del: 's',
        code: 'code',
        pre: 'pre',
        a: 'u',
        'tg-spoiler': 'span',
        span: 'span',
      }
      const root: VNodeChild[] = []
      const stack = [{ tag: 'div', children: root }]
      for (const token of props.text.split(/(<[^>]*>)/g)) {
        const match = token.match(/^<(\/?)([a-z-]+)(?:\s[^>]*)?>$/i)
        const tag = match && tags[match[2].toLowerCase()]
        if (!tag) stack.at(-1)!.children.push(decode(token))
        else if (!match![1]) stack.push({ tag, children: [] })
        else if (stack.length > 1) {
          const child = stack.pop()!
          stack.at(-1)!.children.push(h(child.tag, child.children))
        }
      }
      while (stack.length > 1) {
        const child = stack.pop()!
        stack.at(-1)!.children.push(h(child.tag, child.children))
      }
      return h('div', { class: 'telegram-text' }, root)
    }
  },
})
</script>
