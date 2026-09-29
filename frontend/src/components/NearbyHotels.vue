<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const API_BASE = 'http://127.0.0.1:8123'
const ZIP_PATTERN = /^\d{5}$/

const zipInput = ref('')
const zipInputError = ref('')
const loading = ref(false)
const statusError = ref('')
const location = ref(null)
const hotels = ref([])
const radiusM = ref(0)
const selectedPlaceId = ref(null)

const mapContainer = ref(null)
let map = null
let centerMarker = null
const hotelMarkers = new Map()
const listItemEls = new Map()

function setListItemRef(placeId, el) {
  if (el) {
    listItemEls.set(placeId, el)
  } else {
    listItemEls.delete(placeId)
  }
}

function formatDistance(meters) {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km away`
  }
  return `${Math.round(meters)} m away`
}

function clearMapMarkers() {
  hotelMarkers.forEach((marker) => marker.remove())
  hotelMarkers.clear()
  if (centerMarker) {
    centerMarker.remove()
    centerMarker = null
  }
}

function ensureMap() {
  if (map) return
  map = L.map(mapContainer.value)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map)
}

function renderMap() {
  ensureMap()
  map.invalidateSize()
  clearMapMarkers()

  const bounds = []

  centerMarker = L.marker([location.value.latitude, location.value.longitude], {
    title: 'Search center',
  }).addTo(map)
  centerMarker.bindPopup(
    `ZIP ${location.value.postcode}${location.value.locality ? ` — ${location.value.locality}` : ''}`
  )
  bounds.push([location.value.latitude, location.value.longitude])

  hotels.value.forEach((hotel) => {
    const marker = L.marker([hotel.latitude, hotel.longitude]).addTo(map)
    marker.bindPopup(hotel.name || 'Unnamed hotel')
    marker.on('click', () => selectFromMarker(hotel.place_id))
    hotelMarkers.set(hotel.place_id, marker)
    bounds.push([hotel.latitude, hotel.longitude])
  })

  map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 })
}

function selectFromList(placeId) {
  selectedPlaceId.value = placeId
  const marker = hotelMarkers.get(placeId)
  if (marker && map) {
    marker.openPopup()
    map.panTo(marker.getLatLng())
  }
}

async function selectFromMarker(placeId) {
  selectedPlaceId.value = placeId
  await nextTick()
  const el = listItemEls.get(placeId)
  if (el) {
    el.scrollIntoView({ block: 'nearest' })
  }
}

async function searchHotels() {
  const candidate = zipInput.value.trim()
  zipInputError.value = ''
  statusError.value = ''
  location.value = null
  hotels.value = []
  selectedPlaceId.value = null
  clearMapMarkers()

  if (!ZIP_PATTERN.test(candidate)) {
    zipInputError.value = 'Enter a ZIP code with exactly 5 digits.'
    return
  }

  loading.value = true
  try {
    const url = new URL('/api/hotels/nearby', API_BASE)
    url.searchParams.set('zip', candidate)
    const response = await fetch(url)
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error("We couldn't find that ZIP code.")
      }
      if (response.status === 422) {
        throw new Error('That ZIP code is not valid. Enter exactly 5 digits.')
      }
      if (response.status === 429) {
        throw new Error('Too many requests right now. Please wait a moment and try again.')
      }
      if (response.status === 502 || response.status === 503) {
        throw new Error('The hotel search service is unavailable right now. Please try again later.')
      }
      throw new Error(`Request failed with status ${response.status}`)
    }
    const body = await response.json()
    location.value = body.location
    hotels.value = body.hotels
    radiusM.value = body.radius_m
    loading.value = false
    await nextTick()
    renderMap()
  } catch (err) {
    statusError.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  ensureMap()
})

onBeforeUnmount(() => {
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<template>
  <section class="card">
    <h2>Nearby Hotels</h2>

    <form class="zip-form" @submit.prevent="searchHotels">
      <div class="field field-zip">
        <span class="field-icon">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path
              d="M12 21s-7-6.5-7-11a7 7 0 0 1 14 0c0 4.5-7 11-7 11Z"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle cx="12" cy="10" r="2.5" />
          </svg>
        </span>
        <div class="field-body">
          <label for="zip-input">ZIP code</label>
          <input
            id="zip-input"
            v-model="zipInput"
            type="text"
            inputmode="numeric"
            maxlength="5"
            autocomplete="off"
            placeholder="e.g. 16802"
          />
        </div>
      </div>

      <button type="submit" class="btn-primary" :disabled="loading">
        {{ loading ? 'Searching…' : 'Search hotels' }}
      </button>
    </form>

    <p v-if="zipInputError" class="error status-message">{{ zipInputError }}</p>
    <p v-else-if="loading" class="loading-text">Loading…</p>
    <p v-else-if="statusError" class="error status-message">{{ statusError }}</p>

    <p v-else-if="location" class="search-summary">
      Showing hotels within {{ radiusM / 1000 }} km of
      <strong>{{ location.postcode }}</strong>
      <span v-if="location.locality">&nbsp;({{ location.locality }})</span>
      — {{ hotels.length }} found.
    </p>

    <!--
      This stays mounted (v-show, not v-if) so the map container element
      is never destroyed/recreated between searches — Leaflet's map
      instance is created once in onMounted and reused; recreating the
      container out from under it left `map` pointing at a detached div.
    -->
    <div class="nearby-layout" v-show="location">
      <div class="hotel-list-panel">
        <p v-if="hotels.length === 0" class="empty-state">No hotels found nearby.</p>
        <ul v-else class="hotel-list" role="list">
          <li v-for="hotel in hotels" :key="hotel.place_id">
            <button
              type="button"
              class="hotel-item"
              :class="{ 'hotel-item-selected': hotel.place_id === selectedPlaceId }"
              :ref="(el) => setListItemRef(hotel.place_id, el)"
              @click="selectFromList(hotel.place_id)"
            >
              <span class="hotel-item-name">{{ hotel.name || 'Unnamed hotel' }}</span>
              <span v-if="hotel.address" class="hotel-item-address">{{ hotel.address }}</span>
              <span v-if="hotel.distance_m != null" class="hotel-item-distance">
                {{ formatDistance(hotel.distance_m) }}
              </span>
            </button>
          </li>
        </ul>
      </div>

      <div ref="mapContainer" class="hotel-map" role="application" aria-label="Map of nearby hotels"></div>
    </div>

    <p v-if="location" class="data-note">
      Hotel data comes from Geoapify, may be incomplete, and is not live bookable availability.
    </p>
  </section>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 16px;
  border-left: 4px solid transparent;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 24px rgba(15, 23, 42, 0.06);
  padding: 1.75rem 2rem;
  margin-bottom: 1.75rem;
}

.card h2 {
  margin: 0 0 1.25rem;
  font-size: 1.15rem;
  font-weight: 700;
}

.icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.zip-form {
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

.field-zip {
  flex: 0 0 200px;
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

.field-body input {
  border: none;
  outline: none;
  font-size: 1rem;
  padding: 0;
  color: var(--color-text);
  background: transparent;
  width: 100%;
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
  font-size: 0.9rem;
}

.status-message {
  margin-top: 1rem;
  margin-bottom: 0;
}

.loading-text {
  color: var(--color-muted);
  padding: 0.25rem 0;
  margin-top: 1rem;
}

.empty-state {
  color: var(--color-muted);
  padding: 0.25rem 0;
}

.search-summary {
  margin-top: 1.25rem;
  margin-bottom: 1rem;
  color: var(--color-text);
}

.nearby-layout {
  display: flex;
  gap: 1.5rem;
  align-items: stretch;
}

.hotel-list-panel {
  flex: 1;
  min-width: 0;
}

.hotel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: 12px;
}

.hotel-item {
  width: 100%;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.75rem 1rem;
  border: none;
  border-bottom: 1px solid var(--color-border-light);
  background: #fff;
  cursor: pointer;
  font: inherit;
  color: var(--color-text);
  transition: background 0.15s ease;
}

.hotel-list li:last-child .hotel-item {
  border-bottom: none;
}

.hotel-item:hover {
  background: var(--color-row-hover);
}

.hotel-item:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.hotel-item-selected {
  background: var(--color-primary-wash);
}

.hotel-item-name {
  font-weight: 700;
}

.hotel-item-address,
.hotel-item-distance {
  font-size: 0.85rem;
  color: var(--color-muted);
}

.hotel-map {
  flex: 1;
  min-width: 0;
  height: 420px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.data-note {
  margin-top: 1.25rem;
  margin-bottom: 0;
  font-size: 0.82rem;
  color: var(--color-muted);
}

@media (max-width: 640px) {
  .zip-form {
    flex-direction: column;
  }

  .field-zip {
    flex: 1;
  }

  .card {
    padding: 1.25rem;
  }

  .nearby-layout {
    flex-direction: column;
  }

  .hotel-map {
    height: 300px;
  }
}
</style>
