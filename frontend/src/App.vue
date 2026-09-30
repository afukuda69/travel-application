<script setup>
import { onMounted, ref } from 'vue'
import NearbyHotels from './components/NearbyHotels.vue'

const API_BASE = 'http://127.0.0.1:8123'

const hotelName = ref('')
const results = ref([])
const hasSearched = ref(false)
const error = ref('')
const loading = ref(false)
const bookingTripId = ref(null)

const bookings = ref([])
const bookingsError = ref('')
const bookingActionId = ref(null)

const users = ref([])
const selectedUserId = ref(null)

async function loadUsers() {
  try {
    const response = await fetch(new URL('/users', API_BASE))
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    users.value = await response.json()
    if (users.value.length > 0) {
      selectedUserId.value = users.value[0].user_id
    }
  } catch (err) {
    bookingsError.value = `Could not load travelers: ${err.message}`
  }
}

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

async function loadBookings() {
  bookingsError.value = ''
  try {
    const response = await fetch(new URL('/bookings', API_BASE))
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    bookings.value = await response.json()
  } catch (err) {
    bookingsError.value = `Could not load bookings: ${err.message}`
  }
}

async function bookTrip(tripId) {
  bookingTripId.value = tripId
  try {
    const response = await fetch(new URL('/bookings', API_BASE), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trip_id: tripId, user_id: selectedUserId.value }),
    })
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    await loadBookings()
  } catch (err) {
    error.value = `Could not book this trip: ${err.message}`
  } finally {
    bookingTripId.value = null
  }
}

async function cancelBooking(bookingId) {
  bookingActionId.value = bookingId
  try {
    const response = await fetch(new URL(`/bookings/${bookingId}/cancel`, API_BASE), {
      method: 'PATCH',
    })
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    await loadBookings()
  } catch (err) {
    bookingsError.value = `Could not cancel booking: ${err.message}`
  } finally {
    bookingActionId.value = null
  }
}

async function deleteBooking(bookingId) {
  bookingActionId.value = bookingId
  try {
    const response = await fetch(new URL(`/bookings/${bookingId}`, API_BASE), {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    await loadBookings()
  } catch (err) {
    bookingsError.value = `Could not delete booking: ${err.message}`
  } finally {
    bookingActionId.value = null
  }
}

onMounted(() => {
  loadBookings()
  loadUsers()
})
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>Hotel Trip Search</h1>
      <p class="subtitle">Find your next stay and manage your bookings.</p>
    </header>

    <section class="search-card">
      <div class="tabs">
        <span class="tab tab-active">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M4 21V9.5L12 4l8 5.5V21" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M9 21v-6h6v6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          Hotels
        </span>
      </div>

      <form class="search-form" @submit.prevent="search">
        <div class="field">
          <span class="field-icon">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4.35-4.35" stroke-linecap="round" />
            </svg>
          </span>
          <div class="field-body">
            <label for="hotel-name">Where to?</label>
            <input
              id="hotel-name"
              v-model="hotelName"
              type="text"
              placeholder="Search by hotel name..."
            />
          </div>
        </div>

        <div class="field field-traveler">
          <span class="field-icon">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="12" cy="8" r="3.5" />
              <path d="M5 20c0-3.87 3.13-7 7-7s7 3.13 7 7" stroke-linecap="round" />
            </svg>
          </span>
          <div class="field-body">
            <label for="traveler">Booking As</label>
            <select id="traveler" v-model="selectedUserId">
              <option v-for="user in users" :key="user.user_id" :value="user.user_id">
                {{ user.name }}
              </option>
            </select>
          </div>
        </div>

        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? 'Searching…' : 'Find Your Hotel' }}
        </button>
      </form>
    </section>

    <p v-if="error" class="status-message status-error">
      <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
        <line x1="12" y1="9" x2="12" y2="14" />
        <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      {{ error }}
    </p>

    <div class="results-bookings-grid">
      <section v-if="hasSearched" class="card card-results">
        <h2>Search Results</h2>

        <div v-if="results.length > 0" class="table-scroll">
          <table class="results-table">
            <thead>
              <tr>
                <th>Hotel Name</th>
                <th>City</th>
                <th>Trip Name</th>
                <th>Check In</th>
                <th>Check Out</th>
                <th>Rate</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in results" :key="`${row.hotel_id}-${row.trip_id}`">
                <td>{{ row.hotel_name }}</td>
                <td><span class="pill pill-city">{{ row.city }}</span></td>
                <td>{{ row.trip_name }}</td>
                <td>{{ row.check_in }}</td>
                <td>{{ row.check_out }}</td>
                <td><span class="pill pill-rate">{{ row.nightly_rate_usd }}</span></td>
                <td>
                  <button
                    type="button"
                    class="btn-pill primary"
                    :disabled="!selectedUserId || bookingTripId === row.trip_id"
                    @click="bookTrip(row.trip_id)"
                  >
                    {{ bookingTripId === row.trip_id ? 'Booking…' : 'Book' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-else class="status-message status-empty">
          <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <line x1="12" y1="11" x2="12" y2="16" />
            <circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none" />
          </svg>
          No results found.
        </p>
      </section>

      <section class="card card-bookings">
        <h2>My Bookings</h2>

        <p v-if="bookingsError" class="status-message status-error">
          <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
            <line x1="12" y1="9" x2="12" y2="14" />
            <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
          </svg>
          {{ bookingsError }}
        </p>

        <div v-if="bookings.length > 0" class="table-scroll">
          <table class="results-table">
            <thead>
              <tr>
                <th>Hotel Name</th>
                <th>Trip Name</th>
                <th>Check In</th>
                <th>Check Out</th>
                <th>Traveler</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="booking in bookings" :key="booking.booking_id">
                <td>{{ booking.hotel_name }}</td>
                <td>{{ booking.trip_name }}</td>
                <td>{{ booking.check_in }}</td>
                <td>{{ booking.check_out }}</td>
                <td>{{ booking.user_name }}</td>
                <td>
                  <span class="badge" :class="`badge-${booking.status}`">{{ booking.status }}</span>
                </td>
                <td class="booking-actions">
                  <button
                    type="button"
                    class="btn-pill outline"
                    :disabled="booking.status === 'cancelled' || bookingActionId === booking.booking_id"
                    @click="cancelBooking(booking.booking_id)"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    class="btn-pill danger"
                    :disabled="bookingActionId === booking.booking_id"
                    @click="deleteBooking(booking.booking_id)"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-else-if="!bookingsError" class="status-message status-empty">
          <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <line x1="12" y1="11" x2="12" y2="16" />
            <circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none" />
          </svg>
          No bookings yet.
        </p>
      </section>
    </div>

    <NearbyHotels />
  </main>
</template>

<style scoped>
.page {
  max-width: var(--page-max-width);
  margin: 0 auto;
  padding: var(--space-5) var(--space-5) var(--space-6);
  font-family: var(--font-body);
  color: var(--text-primary);
}

.page-header {
  margin-bottom: var(--space-4);
}

.page-header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  margin: 0 0 var(--space-1);
  color: var(--text-primary);
}

.page-header .subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.92rem;
}

.search-card,
.card {
  background: var(--bg-panel);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.results-bookings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.results-bookings-grid .card {
  margin-bottom: 0;
}

.card h2 {
  margin: 0 0 var(--space-3);
  font-size: 0.98rem;
  font-weight: 600;
  color: var(--text-primary);
}

.tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  font-weight: 600;
  font-size: 0.82rem;
}

.tab-active {
  background: rgba(139, 92, 246, 0.14);
  color: var(--accent-text);
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.search-form {
  display: flex;
  gap: var(--space-3);
  align-items: stretch;
}

.field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-height: var(--min-target);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--space-2) var(--space-3);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field:focus-within {
  border-color: var(--accent);
  box-shadow: var(--focus-ring);
}

.field-icon {
  color: var(--text-secondary);
  display: flex;
}

.field-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.field-body label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
}

.field-body input,
.field-body select {
  border: none;
  outline: none;
  font-family: var(--font-body);
  font-size: 0.95rem;
  font-weight: 500;
  padding: 0;
  color: var(--text-primary);
  background: transparent;
  width: 100%;
}

.field-body select option {
  background: var(--bg-panel);
  color: var(--text-primary);
}

.field-traveler {
  flex: 0 0 200px;
}

.btn-primary {
  background: var(--accent-button);
  color: var(--text-primary);
  border: 1px solid transparent;
  border-radius: var(--radius);
  min-height: var(--min-target);
  padding: 0 var(--space-4);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  transition: background 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-button-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: default;
}

.status-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  margin: 0 0 var(--space-3);
  font-size: 0.86rem;
  font-weight: 500;
}

.status-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.status-error {
  color: var(--color-danger);
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.status-empty {
  color: var(--text-secondary);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  margin: 0;
}

.table-scroll {
  overflow-x: auto;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
}

.results-table th {
  text-align: left;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  font-weight: 600;
  padding: var(--space-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.results-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border);
  font-size: 0.87rem;
  color: var(--text-primary);
}

.results-table tbody tr:last-child td {
  border-bottom: none;
}

.results-table tbody tr:hover {
  background: var(--bg-raised);
}

.btn-pill {
  border-radius: var(--radius-sm);
  min-height: 34px;
  padding: 0 var(--space-3);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  background: transparent;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.btn-pill.primary {
  color: var(--accent-text);
  border-color: rgba(139, 92, 246, 0.4);
}

.btn-pill.primary:hover:not(:disabled) {
  background: rgba(139, 92, 246, 0.12);
}

.btn-pill.outline {
  color: var(--text-secondary);
  border-color: var(--border);
}

.btn-pill.outline:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--border-strong);
  background: var(--bg-raised);
}

.btn-pill.danger {
  color: var(--color-danger);
  border-color: rgba(248, 113, 113, 0.35);
}

.btn-pill.danger:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.6);
}

.btn-pill:disabled {
  opacity: 0.45;
  cursor: default;
}

.booking-actions {
  display: flex;
  gap: var(--space-2);
}

.badge {
  display: inline-flex;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: capitalize;
  border: 1px solid transparent;
}

.badge-active {
  background: rgba(74, 222, 128, 0.12);
  color: var(--color-success);
  border-color: rgba(74, 222, 128, 0.3);
}

.badge-cancelled {
  background: var(--bg-raised);
  color: var(--text-secondary);
  border-color: var(--border);
}

.pill {
  display: inline-flex;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid transparent;
}

.pill-city {
  background: rgba(96, 165, 250, 0.1);
  color: var(--accent-secondary);
  border-color: rgba(96, 165, 250, 0.3);
}

.pill-rate {
  background: var(--bg-raised);
  color: var(--text-primary);
  border-color: var(--border);
}

@media (max-width: 720px) {
  .page {
    padding: var(--space-3) var(--space-3) var(--space-5);
  }

  .search-form {
    flex-direction: column;
  }

  .field-traveler {
    flex: 1;
  }

  .results-bookings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
