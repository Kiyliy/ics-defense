import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({
  gfm: true,
  breaks: true,
})

/**
 * 将 Markdown 渲染为经过净化的 HTML，避免直接暴露 XSS 面。
 * 保留常规 Markdown 展示能力，但移除脚本、事件处理器、危险协议等内容。
 *
 * @param {string | null | undefined} text
 * @returns {string}
 */
export function renderMarkdownSafe(text) {
  const source = typeof text === 'string' ? text : ''

  try {
    const rawHtml = marked.parse(source)
    return DOMPurify.sanitize(rawHtml, {
      USE_PROFILES: { html: true },
    })
  } catch {
    return DOMPurify.sanitize(source, {
      USE_PROFILES: { html: true },
    })
  }
}
