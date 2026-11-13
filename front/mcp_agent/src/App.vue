<script setup>
import ChatBox from './components/ChatBox.vue'
</script>

<template>
  <ChatBox />
</template>

<style>
:root {
  --bg: #f5f4ef;
  --surface: #ffffff;
  --surface-muted: #ecebe4;
  --ink: #1d2a2b;
  --ink-soft: #5b6868;
  --line: #dddbd1;
  --accent: #0f6f66;
  --accent-hover: #0b5a53;
  --on-accent: #ffffff;
  --ok: #1c9a6a;
  --off: #b0792a;
  --danger: #b3382c;
  --danger-bg: #fbeeec;
  --code-bg: #1f2a2b;
  --code-ink: #e6ecea;
  --shadow: 0 8px 28px rgba(29, 42, 43, 0.08);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141a1b;
    --surface: #1d2526;
    --surface-muted: #273133;
    --ink: #e7ecea;
    --ink-soft: #9aa7a6;
    --line: #313c3e;
    --accent: #3fb8a8;
    --accent-hover: #5dcbbc;
    --on-accent: #0e1b1a;
    --ok: #45c795;
    --off: #e0ac5f;
    --danger: #f0897d;
    --danger-bg: #3a2422;
    --code-bg: #0f1516;
    --code-ink: #e6ecea;
    --shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
  }
}

html,
body,
#app {
  height: 100%;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', Roboto, sans-serif;
}
</style>
