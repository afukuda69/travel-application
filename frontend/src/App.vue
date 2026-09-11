<script setup>
import { ref } from 'vue'

const API_BASE = 'http://127.0.0.1:8123'

const hotelName = ref('')
const results = ref([])
const hasSearched = ref(false)
const error = ref('')
const loading = ref(false)

async function search() {
  loading.value = true
  error.value = ''
  try {
    const url = new URL('/search', API_BASE)
    url.searchParams.set('hotel_name', hotelName.value)
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    results.value = await response.json()
  } catch (err) {
    error.value = `Could not reach the search API: ${err.message}`
    results.value = []
  } finally {
    hasSearched.value = true
    loading.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>Hotel Trip Search</h1>

    <form class="search-bar" @submit.prevent="search">
      <input
        v-model="hotelName"
        type="text"
        placeholder="Search by hotel name..."
        aria-label="Hotel name"
      />
      <button type="submit" :disabled="loading">
        {{ loading ? 'Searching…' : 'Search' }}
      </button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>

    <table v-if="results.length > 0" class="results">
      <thead>
        <tr>
          <th>Hotel Name</th>
          <th>City</th>
          <th>Trip Name</th>
          <th>Check In</th>
          <th>Check Out</th>
          <th>Nightly Rate (USD)</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in results" :key="`${row.hotel_id}-${row.trip_id}`">
          <td>{{ row.hotel_name }}</td>
          <td>{{ row.city }}</td>
          <td>{{ row.trip_name }}</td>
          <td>{{ row.check_in }}</td>
          <td>{{ row.check_out }}</td>
          <td>{{ row.nightly_rate_usd }}</td>
        </tr>
      </tbody>
    </table>

    <p v-else-if="hasSearched && !error" class="no-results">No results found.</p>
  </main>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
  font-family: system-ui, sans-serif;
}

.search-bar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.search-bar input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  font-size: 1rem;
}

.search-bar button {
  padding: 0.5rem 1.25rem;
  font-size: 1rem;
  cursor: pointer;
}

.search-bar button:disabled {
  cursor: default;
  opacity: 0.6;
}

.results {
  width: 100%;
  border-collapse: collapse;
}

.results th,
.results td {
  border: 1px solid #ddd;
  padding: 0.5rem 0.75rem;
  text-align: left;
}

.results th {
  background: #f5f5f5;
}

.no-results {
  color: #666;
  font-style: italic;
}

.error {
  color: #b00020;
}
</style>
