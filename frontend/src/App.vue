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

    <p v-if="error" class="error">{{ error }}</p>

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
              <th>Nightly Rate (USD)</th>
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

      <p v-else class="empty-state">No results found.</p>
    </section>

    <section class="card card-bookings">
      <h2>My Bookings</h2>

      <p v-if="bookingsError" class="error">{{ bookingsError }}</p>

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

      <p v-else-if="!bookingsError" class="empty-state">No bookings yet.</p>
    </section>

    <NearbyHotels />
  </main>
</template>

<style scoped>
.page {
  --color-primary: #0d9488;
  --color-primary-dark: #0f766e;
  --color-primary-wash: #ecfdf5;
  --color-primary-border: #99f6e4;
  --color-accent: #d97706;
  --color-accent-dark: #b45309;
  --color-accent-wash: #fffbeb;
  --color-accent-border: #fde68a;
  --color-info: #2563eb;
  --color-info-dark: #1d4ed8;
  --color-info-wash: #eff6ff;
  --color-info-border: #bfdbfe;
  --color-text: #1e293b;
  --color-muted: #64748b;
  --color-border: #e2e8f0;
  --color-border-light: #eef2f6;
  --color-row-hover: #f8fafc;

  max-width: 1080px;
  margin: 3rem auto;
  padding: 0 1.5rem 3rem;
  font-family: system-ui, sans-serif;
  color: var(--color-text);
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-header h1 {
  font-size: 1.9rem;
  font-weight: 800;
  margin: 0 0 0.35rem;
}

.page-header .subtitle {
  margin: 0;
  color: var(--color-muted);
}

.search-card,
.card {
  background: #fff;
  border-radius: 16px;
  border-left: 4px solid transparent;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 24px rgba(15, 23, 42, 0.06);
  padding: 1.75rem 2rem;
  margin-bottom: 1.75rem;
}

.search-card {
  border-left-color: var(--color-primary);
  background: linear-gradient(180deg, rgba(13, 148, 136, 0.05), #fff 170px);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 16px 32px rgba(13, 148, 136, 0.12);
}

.card-results {
  border-left-color: var(--color-info);
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.04), #fff 170px);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 16px 32px rgba(37, 99, 235, 0.1);
}

.card-bookings {
  border-left-color: var(--color-accent);
  background: linear-gradient(180deg, rgba(217, 119, 6, 0.04), #fff 170px);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 16px 32px rgba(217, 119, 6, 0.1);
}

.card h2 {
  margin: 0 0 1.25rem;
  font-size: 1.15rem;
  font-weight: 700;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1.1rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.9rem;
}

.tab-active {
  background: var(--color-primary-wash);
  color: var(--color-primary-dark);
  border: 1px solid var(--color-primary-border);
}

.icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.search-form {
  display: flex;
  gap: 1rem;
  align-items: stretch;
}

.field {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 0.55rem 1rem;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.12);
}

.field-icon {
  color: var(--color-primary);
  display: flex;
}

.field-body {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.field-body label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-muted);
  font-weight: 700;
  margin-bottom: 0.1rem;
}

.field-body input,
.field-body select {
  border: none;
  outline: none;
  font-size: 1rem;
  padding: 0;
  color: var(--color-text);
  background: transparent;
  width: 100%;
}

.field-traveler {
  flex: 0 0 220px;
}

.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 0 1.75rem;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 6px 14px rgba(13, 148, 136, 0.25);
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(13, 148, 136, 0.32);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: default;
  box-shadow: none;
}

.error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
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
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-muted);
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.results-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 0.95rem;
}

.results-table tbody tr:last-child td {
  border-bottom: none;
}

.results-table tbody tr:hover {
  background: var(--color-row-hover);
}

.card-results .results-table tbody tr:hover {
  background: rgba(37, 99, 235, 0.045);
}

.card-bookings .results-table tbody tr:hover {
  background: rgba(217, 119, 6, 0.045);
}

.btn-pill {
  border-radius: 999px;
  padding: 0.4rem 1rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease,
    border-color 0.15s ease, color 0.15s ease;
}

.btn-pill.primary {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.btn-pill.primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
  border-color: var(--color-primary-dark);
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(13, 148, 136, 0.3);
}

.btn-pill.outline {
  background: #fff;
  color: var(--color-primary-dark);
  border-color: var(--color-primary-border);
}

.btn-pill.outline:hover:not(:disabled) {
  background: var(--color-primary-wash);
  border-color: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(13, 148, 136, 0.16);
}

.btn-pill.danger {
  background: #fff;
  color: #b91c1c;
  border-color: #fecaca;
}

.btn-pill.danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fca5a5;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(185, 28, 28, 0.14);
}

.btn-pill:disabled {
  opacity: 0.5;
  cursor: default;
  transform: none;
  box-shadow: none;
}

.booking-actions {
  display: flex;
  gap: 0.5rem;
}

.badge {
  display: inline-flex;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: capitalize;
}

.badge-active {
  background: #ecfdf5;
  color: #047857;
}

.badge-cancelled {
  background: #f1f5f9;
  color: #64748b;
}

.pill {
  display: inline-flex;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
}

.pill-city {
  background: var(--color-info-wash);
  color: var(--color-info-dark);
}

.pill-rate {
  background: var(--color-accent-wash);
  color: var(--color-accent-dark);
}

.empty-state {
  color: var(--color-muted);
  padding: 0.25rem 0;
}

.loading-text {
  color: var(--color-muted);
  padding: 0.25rem 0;
  margin-top: 1rem;
}

@media (max-width: 640px) {
  .search-form {
    flex-direction: column;
  }

  .field-traveler {
    flex: 1;
  }

  .btn-primary {
    padding: 0.75rem 1.5rem;
  }

  .search-card,
  .card {
    padding: 1.25rem;
  }
}
</style>

<style>
html {
  height: 100%;
}

body {
  margin: 0;
  min-height: 100%;
  background: linear-gradient(160deg, #eaf3ff 0%, #f7f8fc 42%, #fdf6ec 100%);
}

* {
  box-sizing: border-box;
}
</style>
