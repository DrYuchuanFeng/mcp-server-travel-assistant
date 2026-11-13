<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import MarkdownIt from 'markdown-it'

const API_BASE = 'http://localhost:8000'

const md = new MarkdownIt({
  html: false, // 禁用 HTML 以防止 XSS
  linkify: true,
  breaks: true
})

// 回复中的链接在新标签页打开
const renderLinkOpen =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return renderLinkOpen(tokens, idx, options, env, self)
}

const suggestions = [
  '帮我规划东京 5 日游，预算适中，喜欢美食和街区散步',
  '从旧金山开车去优胜美地要多久？沿途有哪些值得停留的地方？',
  '巴黎卢浮宫附近有哪些评价好的餐厅？',
  '查一下京都今天的天气，并建议穿什么'
]

const newThreadId = () => `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

const messages = ref([])
const userInput = ref('')
const isLoading = ref(false)
const threadId = ref(newThreadId())
const backend = ref({ state: 'checking', model: '', servers: {} })
const chatContainer = ref(null)
const inputEl = ref(null)

const mapsConnected = computed(() => Boolean(backend.value.servers['google-maps']))
const canSend = computed(() => userInput.value.trim().length > 0 && !isLoading.value)

const loadStatus = async () => {
  try {
    const response = await fetch(`${API_BASE}/status`)
    if (!response.ok) throw new Error(String(response.status))
    const data = await response.json()
    backend.value = { state: 'online', model: data.model, servers: data.servers }
  } catch {
    backend.value = { state: 'offline', model: '', servers: {} }
  }
}

onMounted(() => {
  loadStatus()
  inputEl.value?.focus()
})

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const resizeInput = async () => {
  await nextTick()
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

const sendMessage = async (text) => {
  const content = (text ?? userInput.value).trim()
  if (!content || isLoading.value) return

  messages.value.push({ role: 'user', content })
  userInput.value = ''
  isLoading.value = true
  resizeInput()
  scrollToBottom()

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: content, thread_id: threadId.value })
    })
    const data = await response.json()

    if (!response.ok) {
      messages.value.push({ role: 'error', content: data.detail || `请求失败（${response.status}）` })
    } else if (data.status === 'success') {
      messages.value.push({ role: 'ai', content: data.content })
    } else if (data.status === 'empty') {
      messages.value.push({ role: 'error', content: '没有获取到回复，请重试。' })
    } else {
      messages.value.push({ role: 'error', content: data.error || '发生未知错误。' })
    }
  } catch {
    messages.value.push({ role: 'error', content: '无法连接后端服务，请确认 api_server.py 已启动。' })
    loadStatus()
  } finally {
    isLoading.value = false
    scrollToBottom()
    inputEl.value?.focus()
  }
}

const handleEnter = (event) => {
  // 中文输入法选词时的回车不发送
  if (event.isComposing) return
  event.preventDefault()
  sendMessage()
}

const startNewChat = () => {
  if (isLoading.value) return
  messages.value = []
  threadId.value = newThreadId()
  inputEl.value?.focus()
}

const renderMarkdown = (text) => md.render(text || '')
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
        </span>
        <h1>旅行规划助手</h1>
      </div>

      <div class="topbar-actions">
        <div class="status" role="status">
          <template v-if="backend.state === 'online'">
            <span class="status-item">{{ backend.model }}</span>
            <span class="status-item">
              <span :class="['dot', mapsConnected ? 'dot-ok' : 'dot-off']"></span>
              Google 地图{{ mapsConnected ? '已连接' : '未连接' }}
            </span>
          </template>
          <span v-else-if="backend.state === 'offline'" class="status-item">
            <span class="dot dot-off"></span>
            后端未连接
          </span>
        </div>
        <button class="ghost-btn" type="button" :disabled="isLoading || messages.length === 0" @click="startNewChat">
          新对话
        </button>
      </div>
    </header>

    <main ref="chatContainer" class="thread">
      <div class="thread-inner">
        <section v-if="messages.length === 0" class="welcome">
          <h2>这次想去哪儿？</h2>
          <p>告诉我目的地、天数和偏好，我会用 Google 地图查地点和路线，帮你排好行程。</p>
          <div class="suggestions">
            <button v-for="item in suggestions" :key="item" class="suggestion" type="button" @click="sendMessage(item)">
              {{ item }}
            </button>
          </div>
        </section>

        <template v-for="(msg, index) in messages" :key="index">
          <div v-if="msg.role === 'user'" class="msg-user">{{ msg.content }}</div>
          <div v-else-if="msg.role === 'error'" class="msg-error" role="alert">{{ msg.content }}</div>
          <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
        </template>

        <div v-if="isLoading" class="thinking" role="status">
          <span class="pulse"></span><span class="pulse"></span><span class="pulse"></span>
          正在查询并规划…
        </div>
      </div>
    </main>

    <footer class="composer">
      <form class="composer-box" @submit.prevent="sendMessage()">
        <textarea
          ref="inputEl"
          v-model="userInput"
          rows="1"
          aria-label="输入你的问题"
          placeholder="输入目的地或问题，Shift + Enter 换行"
          @input="resizeInput"
          @keydown.enter.exact="handleEnter"
        ></textarea>
        <button class="send-btn" type="submit" :disabled="!canSend" aria-label="发送">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>
        </button>
      </form>
    </footer>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100dvh;
}

/* 顶部栏 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--accent);
  color: var(--on-accent);
}

.brand h1 {
  font-size: 1.05rem;
  font-weight: 650;
  white-space: nowrap;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.status {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--ink-soft);
  font-size: 0.82rem;
}

.status-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot-ok {
  background: var(--ok);
}

.dot-off {
  background: var(--off);
}

.ghost-btn {
  padding: 7px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 0.85rem;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s ease;
}

.ghost-btn:hover:not(:disabled) {
  background: var(--surface-muted);
}

.ghost-btn:disabled {
  color: var(--ink-soft);
  opacity: 0.6;
  cursor: not-allowed;
}

/* 消息区 */
.thread {
  flex: 1;
  overflow-y: auto;
}

.thread-inner {
  display: flex;
  flex-direction: column;
  gap: 22px;
  width: 100%;
  max-width: 780px;
  min-height: 100%;
  margin: 0 auto;
  padding: 32px 24px;
  box-sizing: border-box;
}

.welcome {
  margin: auto 0;
  padding: 24px 0;
}

.welcome h2 {
  font-size: 1.9rem;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.welcome p {
  max-width: 34em;
  margin-top: 8px;
  color: var(--ink-soft);
  font-size: 1rem;
  line-height: 1.7;
}

.suggestions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 26px;
}

.suggestion {
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
  font: inherit;
  font-size: 0.92rem;
  line-height: 1.55;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.suggestion:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.msg-user {
  align-self: flex-end;
  max-width: 78%;
  padding: 10px 16px;
  border-radius: 16px 16px 4px 16px;
  background: var(--accent);
  color: var(--on-accent);
  font-size: 0.98rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-error {
  padding: 12px 16px;
  border-radius: 10px;
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 0.92rem;
  line-height: 1.6;
  word-break: break-word;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-soft);
  font-size: 0.88rem;
}

.pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.2s infinite ease-in-out both;
}

.pulse:nth-child(2) {
  animation-delay: 0.15s;
}

.pulse:nth-child(3) {
  margin-right: 6px;
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

/* 输入区 */
.composer {
  padding: 12px 24px 18px;
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  max-width: 732px;
  margin: 0 auto;
  padding: 8px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow);
  transition: border-color 0.15s ease;
}

.composer-box:focus-within {
  border-color: var(--accent);
}

textarea {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 1rem;
  line-height: 1.5;
}

textarea::placeholder {
  color: var(--ink-soft);
}

.send-btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: var(--on-accent);
  cursor: pointer;
  transition: background 0.15s ease;
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.send-btn:disabled {
  background: var(--surface-muted);
  color: var(--ink-soft);
  cursor: not-allowed;
}

button:focus-visible,
:deep(.markdown-body a:focus-visible) {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* AI 回复排版 */
.markdown-body {
  color: var(--ink);
  font-size: 1rem;
  line-height: 1.75;
  word-break: break-word;
}

:deep(.markdown-body > :first-child) {
  margin-top: 0;
}

:deep(.markdown-body > :last-child) {
  margin-bottom: 0;
}

:deep(.markdown-body p),
:deep(.markdown-body ul),
:deep(.markdown-body ol),
:deep(.markdown-body table),
:deep(.markdown-body pre),
:deep(.markdown-body blockquote) {
  margin: 0 0 0.85em;
}

:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3),
:deep(.markdown-body h4) {
  margin: 1.3em 0 0.5em;
  font-weight: 650;
  line-height: 1.35;
}

:deep(.markdown-body h1) {
  font-size: 1.35rem;
}

:deep(.markdown-body h2) {
  font-size: 1.2rem;
}

:deep(.markdown-body h3),
:deep(.markdown-body h4) {
  font-size: 1.05rem;
}

:deep(.markdown-body strong) {
  font-weight: 650;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  padding-left: 1.4em;
}

:deep(.markdown-body li) {
  margin: 0.25em 0;
}

:deep(.markdown-body a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

:deep(.markdown-body hr) {
  margin: 1.2em 0;
  border: none;
  border-top: 1px solid var(--line);
}

:deep(.markdown-body blockquote) {
  padding-left: 14px;
  border-left: 3px solid var(--line);
  color: var(--ink-soft);
}

:deep(.markdown-body table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  font-size: 0.93rem;
}

:deep(.markdown-body th),
:deep(.markdown-body td) {
  padding: 8px 12px;
  border: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}

:deep(.markdown-body th) {
  background: var(--surface-muted);
  font-weight: 650;
}

:deep(.markdown-body code) {
  padding: 2px 5px;
  border-radius: 5px;
  background: var(--surface-muted);
  font-family: Consolas, 'SF Mono', monospace;
  font-size: 0.88em;
}

:deep(.markdown-body pre) {
  padding: 16px;
  overflow-x: auto;
  border-radius: 10px;
  background: var(--code-bg);
}

:deep(.markdown-body pre code) {
  padding: 0;
  background: transparent;
  color: var(--code-ink);
}

@media (max-width: 640px) {
  .topbar {
    padding: 10px 16px;
  }

  .topbar-actions {
    gap: 10px;
  }

  .status-item:first-child:not(:last-child) {
    display: none;
  }

  .thread-inner {
    padding: 22px 16px;
  }

  .welcome h2 {
    font-size: 1.55rem;
  }

  .suggestions {
    grid-template-columns: minmax(0, 1fr);
  }

  .msg-user {
    max-width: 88%;
  }

  .composer {
    padding: 10px 16px 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .pulse {
    animation: none;
  }

  .suggestion:hover {
    transform: none;
  }
}
</style>
