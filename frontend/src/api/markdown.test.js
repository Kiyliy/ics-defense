// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { renderMarkdownSafe } from './markdown.js'

describe('renderMarkdownSafe', () => {
  it('keeps regular markdown formatting', () => {
    const html = renderMarkdownSafe('## 标题\n\n**bold** and `code`')

    expect(html).toContain('<h2>标题</h2>')
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('<code>code</code>')
  })

  it('strips dangerous html and event handlers', () => {
    const html = renderMarkdownSafe('<img src=x onerror="alert(1)"><script>alert(1)</script><div onclick="evil()">safe</div>')

    expect(html).not.toContain('<script')
    expect(html).not.toContain('onerror=')
    expect(html).not.toContain('onclick=')
    expect(html).toContain('<img src="x">')
    expect(html).toContain('<div>safe</div>')
  })

  it('removes dangerous javascript links while preserving safe links', () => {
    const html = renderMarkdownSafe('[bad](javascript:alert(1)) [good](https://example.com)')

    expect(html).not.toContain('javascript:alert(1)')
    expect(html).toContain('https://example.com')
  })
})
