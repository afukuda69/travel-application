<script setup>
import { computed, ref } from 'vue'

const API_BASE = 'http://127.0.0.1:8123'

const LABEL_ORDER = ['Hotel', 'Location', 'Stay dates', 'Nightly rate', 'Total cost', 'Availability', 'Reason']
const SUGGESTIONS = [
  { label: 'Cheapest stay', question: "What's the cheapest stay among my saved hotels?" },
  { label: 'Rooms on Oct 10', question: 'How many rooms are available on 2026-10-10?' },
  { label: 'Compare hotels', question: 'Compare my saved hotels by price.' },
]

const question = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')

function fillSuggestion(suggestion) {
  question.value = suggestion.question
}

// The backend asks the LLM to format its row-grounded answer as labeled
// lines (see chat.py:_build_answer_prompt) so we can show a clean
// labeled-field layout without the frontend ever re-interpreting/
// guessing structured values itself. Any line that doesn't match a known
// label is kept, never dropped, and shown as plain text below the fields.
function parseLabeledAnswer(text) {
  const fields = []
  const leftover = []
  for (const rawLine of (text || '').split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const match = LABEL_ORDER.map((label) => ({ label, re: new RegExp(`^${label}\\s*:\\s*(.*)$`, 'i') })).find(
      ({ re }) => re.test(line)
    )
    if (match) {
      fields.push({ label: match.label, value: line.match(match.re)[1].trim() })
    } else {
      leftover.push(line)
    }
  }
  return { fields, leftover: leftover.join(' ') }
}

const parsedAnswer = computed(() => parseLabeledAnswer(result.value?.answer))

const recordColumns = computed(() => (result.value?.rows?.length ? Object.keys(result.value.rows[0]) : []))

async function askQuestion() {
  const trimmed = question.value.trim()
  if (!trimmed || loading.value) return

  loading.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const response = await fetch(new URL('/api/chat', API_BASE), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: trimmed }),
    })
    const body = await response.json()
    if (body && typeof body.status === 'string') {
      result.value = body
    } else {
      errorMessage.value = 'Something went wrong. Please try again.'
    }
  } catch (_err) {
    errorMessage.value = 'Could not reach the chatbot. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="chat-card">
    <h3>Ask about your saved hotels</h3>

    <form class="chat-form" @submit.prevent="askQuestion">
      <div class="chat-input-box">
        <textarea
          id="chat-question"
          v-model="question"
          rows="2"
          placeholder="Ask a question about your saved hotels…"
          :disabled="loading"
          @keydown.enter.exact.prevent="askQuestion"
        ></textarea>
        <button type="submit" class="chat-ask-button" :disabled="loading || !question.trim()">
          {{ loading ? 'Thinking…' : 'Ask' }}
        </button>
      </div>
    </form>

    <div class="chat-chips">
      <button
        v-for="suggestion in SUGGESTIONS"
        :key="suggestion.label"
        type="button"
        class="chip"
        @click="fillSuggestion(suggestion)"
      >
        {{ suggestion.label }}
      </button>
    </div>

    <p v-if="loading" class="status-message status-loading">
      <svg class="status-icon spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="9" stroke-opacity="0.3" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke-linecap="round" />
      </svg>
      Thinking…
    </p>

    <p v-else-if="errorMessage" class="status-message status-error">
      <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
        <line x1="12" y1="9" x2="12" y2="14" />
        <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      {{ errorMessage }}
    </p>

    <p v-else-if="result && (result.status === 'rejected' || result.status === 'error')" class="status-message status-error">
      <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
        <line x1="12" y1="9" x2="12" y2="14" />
        <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      {{ result.answer }}
    </p>

    <p v-else-if="result && result.status === 'no_match'" class="status-message status-empty">
      <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="11" x2="12" y2="16" />
        <circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      {{ result.answer }}
    </p>

    <div v-else-if="result && result.status === 'answer'" class="answer-card">
      <h4>Answer</h4>

      <div v-if="parsedAnswer.fields.length" class="answer-fields">
        <div v-for="field in parsedAnswer.fields" :key="field.label" class="answer-field">
          <span class="answer-field-label">{{ field.label }}</span>
          <span class="answer-field-value">{{ field.value }}</span>
        </div>
      </div>
      <p v-if="parsedAnswer.leftover" class="answer-leftover">{{ parsedAnswer.leftover }}</p>

      <p class="answer-disclaimer">Rates and availability are simulated course data.</p>

      <details class="answer-expand">
        <summary>View query</summary>
        <pre class="answer-sql">{{ result.proposed_sql }}</pre>
      </details>

      <details class="answer-expand">
        <summary>View source records</summary>
        <div v-if="result.rows.length" class="table-scroll">
          <table class="records-table">
            <thead>
              <tr>
                <th v-for="col in recordColumns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in result.rows" :key="index">
                <td v-for="col in recordColumns" :key="col">{{ row[col] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty-state">No records.</p>
      </details>
    </div>
  </section>
</template>

<style scoped>
.chat-card {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.chat-card h3 {
  margin: 0 0 var(--space-3);
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-form {
  margin-bottom: var(--space-3);
}

.chat-input-box {
  position: relative;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  padding-bottom: 48px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.chat-input-box:focus-within {
  border-color: var(--accent);
  box-shadow: var(--focus-ring);
}

.chat-input-box textarea {
  width: 100%;
  resize: vertical;
  min-height: 48px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: 0.95rem;
  line-height: 1.4;
}

.chat-ask-button {
  position: absolute;
  right: var(--space-3);
  bottom: var(--space-3);
  min-height: var(--min-target);
  padding: 0 var(--space-4);
  background: linear-gradient(135deg, var(--accent-button-start), var(--accent-button-end));
  color: #ffffff;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 1.05rem;
  font-weight: 700;
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.chat-ask-button:hover:not(:disabled),
.chat-ask-button:focus-visible:not(:disabled) {
  box-shadow: var(--button-glow);
  transform: translateY(-1px);
}

.chat-ask-button:disabled {
  opacity: 0.5;
  cursor: default;
}

.chat-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.chip {
  padding: var(--space-1) var(--space-3);
  min-height: 32px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-panel);
  color: var(--text-secondary);
  font-family: var(--font-body);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.chip:hover {
  color: var(--accent-text);
  border-color: rgba(139, 92, 246, 0.4);
  background: rgba(139, 92, 246, 0.08);
}

.status-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  margin: 0;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.status-icon.spin {
  animation: chat-spin 0.9s linear infinite;
}

@keyframes chat-spin {
  to {
    transform: rotate(360deg);
  }
}

.status-error {
  color: var(--color-danger);
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.status-loading,
.status-empty {
  color: var(--text-secondary);
  background: var(--bg-raised);
  border: 1px solid var(--border);
}

.answer-card {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
}

.answer-card h4 {
  margin: 0 0 var(--space-2);
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
}

.answer-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-2) var(--space-4);
  margin-bottom: var(--space-2);
}

.answer-field {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.answer-field-label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.answer-field-value {
  font-size: 0.92rem;
  color: var(--text-primary);
}

.answer-leftover {
  margin: 0 0 var(--space-2);
  font-size: 0.88rem;
  color: var(--text-primary);
}

.answer-disclaimer {
  margin: 0 0 var(--space-3);
  font-size: 0.74rem;
  color: var(--text-secondary);
  font-style: italic;
}

.answer-expand {
  margin-top: var(--space-2);
}

.answer-expand summary {
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--accent-text);
  padding: var(--space-1) 0;
}

.answer-expand summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.answer-sql {
  margin: var(--space-2) 0 0;
  padding: var(--space-2);
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.table-scroll {
  overflow-x: auto;
  margin-top: var(--space-2);
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.records-table th {
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.66rem;
  color: var(--text-secondary);
  padding: var(--space-1) var(--space-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.records-table td {
  padding: var(--space-1) var(--space-2);
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  white-space: nowrap;
}

.records-table tbody tr:last-child td {
  border-bottom: none;
}

.empty-state {
  color: var(--text-secondary);
  margin: var(--space-2) 0 0;
}
</style>
