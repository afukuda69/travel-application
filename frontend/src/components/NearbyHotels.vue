<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import HotelChat from './HotelChat.vue'

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
const resultSource = ref('') // 'local' | 'api'

const savedHotelIds = ref(new Set())
const pendingActionHotelId = ref(null)
const actionFeedback = ref('')
const actionFeedbackKind = ref('success') // 'success' | 'error'

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

function formatCents(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

function isSaved(hotel) {
  return savedHotelIds.value.has(hotel.hotel_id)
}

function markerIcon(kind) {
  return L.divIcon({
    className: `map-marker map-marker-${kind}`,
    html: '<span class="map-marker-dot"></span>',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  })
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

function updateMarkerSelection() {
  hotelMarkers.forEach((marker, placeId) => {
    const el = marker.getElement()
    if (el) {
      el.classList.toggle('marker-selected', placeId === selectedPlaceId.value)
    }
  })
}

function renderMap() {
  ensureMap()
  map.invalidateSize()
  clearMapMarkers()

  const bounds = []

  // Defensive: local results always carry a center (real or a
  // hotel-centroid fallback computed by the backend), but guard anyway
  // so a missing coordinate can never reach Leaflet as undefined.
  const hasCenter = location.value.latitude != null && location.value.longitude != null
  if (hasCenter) {
    centerMarker = L.marker([location.value.latitude, location.value.longitude], {
      title: 'Search center',
      icon: markerIcon('center'),
    }).addTo(map)
    centerMarker.bindPopup(
      `ZIP ${location.value.postcode}${location.value.locality ? ` — ${location.value.locality}` : ''}`
    )
    bounds.push([location.value.latitude, location.value.longitude])
  }

  hotels.value.forEach((hotel) => {
    const marker = L.marker([hotel.latitude, hotel.longitude], { icon: markerIcon('hotel') }).addTo(map)
    marker.bindPopup(hotel.name || 'Unnamed hotel')
    marker.on('click', () => selectFromMarker(hotel.hotel_id))
    hotelMarkers.set(hotel.hotel_id, marker)
    bounds.push([hotel.latitude, hotel.longitude])
  })

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 })
  }
  updateMarkerSelection()
}

function selectFromList(placeId) {
  selectedPlaceId.value = placeId
  updateMarkerSelection()
  const marker = hotelMarkers.get(placeId)
  if (marker && map) {
    marker.openPopup()
    map.panTo(marker.getLatLng())
  }
}

async function selectFromMarker(placeId) {
  selectedPlaceId.value = placeId
  updateMarkerSelection()
  await nextTick()
  const el = listItemEls.get(placeId)
  if (el) {
    el.scrollIntoView({ block: 'nearest' })
  }
}

async function fetchLocalHotels(candidate) {
  const url = new URL('/api/saved-hotels', API_BASE)
  url.searchParams.set('zip', candidate)
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('Could not check your saved hotels right now. Please try again later.')
  }
  return response.json()
}

async function fetchApiHotels(candidate) {
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
  return response.json()
}

async function fetchSavedHotelIds() {
  try {
    const response = await fetch(new URL('/api/saved-hotels/ids', API_BASE))
    if (!response.ok) return new Set()
    return new Set(await response.json())
  } catch (_err) {
    return new Set()
  }
}

async function searchHotels() {
  const candidate = zipInput.value.trim()
  zipInputError.value = ''
  statusError.value = ''
  actionFeedback.value = ''
  location.value = null
  hotels.value = []
  resultSource.value = ''
  savedHotelIds.value = new Set()
  selectedPlaceId.value = null
  clearMapMarkers()

  if (!ZIP_PATTERN.test(candidate)) {
    zipInputError.value = 'Enter a ZIP code with exactly 5 digits.'
    return
  }

  loading.value = true
  try {
    // Local-first: check our own saved hotels before calling the
    // Part 1 Geoapify-backed endpoint at all.
    const localBody = await fetchLocalHotels(candidate)

    if (localBody.hotels.length > 0) {
      location.value = {
        postcode: localBody.zip,
        locality: localBody.locality,
        latitude: localBody.latitude,
        longitude: localBody.longitude,
      }
      hotels.value = localBody.hotels.map((hotel) => ({ ...hotel, distance_m: null }))
      resultSource.value = 'local'
      radiusM.value = 0
      savedHotelIds.value = new Set(hotels.value.map((hotel) => hotel.hotel_id))
      loading.value = false
      await nextTick()
      renderMap()
      return
    }

    // No saved hotels for this ZIP — fall back to the live Part 1 search.
    const body = await fetchApiHotels(candidate)
    location.value = body.location
    hotels.value = body.hotels.map((hotel) => ({ ...hotel, hotel_id: hotel.place_id, nights: null }))
    resultSource.value = 'api'
    radiusM.value = body.radius_m
    savedHotelIds.value = await fetchSavedHotelIds()

    loading.value = false
    await nextTick()
    renderMap()
  } catch (err) {
    statusError.value = err.message
  } finally {
    loading.value = false
  }
}

async function addToLocal(hotel) {
  pendingActionHotelId.value = hotel.hotel_id
  actionFeedback.value = ''
  try {
    const response = await fetch(new URL('/api/saved-hotels', API_BASE), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hotel_id: hotel.hotel_id,
        name: hotel.name,
        address: hotel.address,
        latitude: hotel.latitude,
        longitude: hotel.longitude,
        zip: location.value?.postcode,
        locality: location.value?.locality || null,
        center_latitude: location.value?.latitude ?? null,
        center_longitude: location.value?.longitude ?? null,
      }),
    })
    if (!response.ok) {
      throw new Error('Could not save this hotel. Please try again.')
    }
    const saved = await response.json()

    const next = new Set(savedHotelIds.value)
    next.add(hotel.hotel_id)
    savedHotelIds.value = next

    const target = hotels.value.find((h) => h.hotel_id === hotel.hotel_id)
    if (target) target.nights = saved.nights

    actionFeedback.value = `Saved ${hotel.name || 'this hotel'} to local storage.`
    actionFeedbackKind.value = 'success'
  } catch (err) {
    actionFeedback.value = err.message
    actionFeedbackKind.value = 'error'
  } finally {
    pendingActionHotelId.value = null
  }
}

async function removeFromLocal(hotel) {
  pendingActionHotelId.value = hotel.hotel_id
  actionFeedback.value = ''
  try {
    const response = await fetch(new URL(`/api/saved-hotels/${encodeURIComponent(hotel.hotel_id)}`, API_BASE), {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error('Could not remove this hotel. Please try again.')
    }

    const next = new Set(savedHotelIds.value)
    next.delete(hotel.hotel_id)
    savedHotelIds.value = next

    if (selectedPlaceId.value === hotel.hotel_id) {
      selectedPlaceId.value = null
    }

    if (resultSource.value === 'local') {
      hotels.value = hotels.value.filter((h) => h.hotel_id !== hotel.hotel_id)
    } else {
      const target = hotels.value.find((h) => h.hotel_id === hotel.hotel_id)
      if (target) target.nights = null
    }

    actionFeedback.value = `Removed ${hotel.name || 'this hotel'} from local storage.`
    actionFeedbackKind.value = 'success'
    await nextTick()
    renderMap()
  } catch (err) {
    actionFeedback.value = err.message
    actionFeedbackKind.value = 'error'
  } finally {
    pendingActionHotelId.value = null
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

    <div class="zip-row">
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

      <p v-if="zipInputError" class="status-message status-error">
        <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
          <line x1="12" y1="9" x2="12" y2="14" />
          <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
        </svg>
        {{ zipInputError }}
      </p>
      <p v-else-if="loading" class="status-message status-loading">
        <svg class="status-icon spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="9" stroke-opacity="0.3" />
          <path d="M21 12a9 9 0 0 0-9-9" stroke-linecap="round" />
        </svg>
        Loading…
      </p>
      <p v-else-if="statusError" class="status-message status-error">
        <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 3l10 18H2L12 3z" stroke-linejoin="round" />
          <line x1="12" y1="9" x2="12" y2="14" />
          <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
        </svg>
        {{ statusError }}
      </p>
      <p v-else-if="location" class="status-message status-summary">
        <span class="source-badge" :class="resultSource === 'local' ? 'source-local' : 'source-api'">
          {{ resultSource === 'local' ? 'Saved locally' : 'API results' }}
        </span>
        <span v-if="resultSource === 'api'">
          Within {{ radiusM / 1000 }} km of
          <strong>{{ location.postcode }}</strong>
          <span v-if="location.locality">&nbsp;({{ location.locality }})</span>
          — {{ hotels.length }} found.
        </span>
        <span v-else>
          <strong>{{ location.postcode }}</strong>
          <span v-if="location.locality">&nbsp;({{ location.locality }})</span>
          — {{ hotels.length }} hotel(s) you've saved here (not a complete list of hotels in this area).
        </span>
      </p>
    </div>

    <HotelChat />

    <p
      v-if="actionFeedback"
      class="status-message"
      :class="actionFeedbackKind === 'error' ? 'status-error' : 'status-success'"
    >
      {{ actionFeedback }}
    </p>

    <!--
      This stays mounted (v-show, not v-if) so the map container element
      is never destroyed/recreated between searches — Leaflet's map
      instance is created once in onMounted and reused; recreating the
      container out from under it left `map` pointing at a detached div.
    -->
    <div class="nearby-layout" v-show="location">
      <div class="hotel-list-panel">
        <p v-if="hotels.length === 0" class="status-message status-empty">
          <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <line x1="12" y1="11" x2="12" y2="16" />
            <circle cx="12" cy="7.5" r="0.9" fill="currentColor" stroke="none" />
          </svg>
          No hotels found nearby.
        </p>
        <ul v-else class="hotel-list" role="list">
          <li v-for="hotel in hotels" :key="hotel.hotel_id">
            <div class="hotel-item" :class="{ 'hotel-item-selected': hotel.hotel_id === selectedPlaceId }">
              <button
                type="button"
                class="hotel-item-select"
                :ref="(el) => setListItemRef(hotel.hotel_id, el)"
                @click="selectFromList(hotel.hotel_id)"
              >
                <span class="hotel-item-row1">
                  <span class="hotel-item-name">{{ hotel.name || 'Unnamed hotel' }}</span>
                  <span v-if="hotel.distance_m != null" class="hotel-item-distance">
                    {{ formatDistance(hotel.distance_m) }}
                  </span>
                </span>
                <span v-if="hotel.address" class="hotel-item-address">{{ hotel.address }}</span>

                <div v-if="hotel.nights && hotel.nights.length" class="hotel-item-nights">
                  <span class="nights-label">Simulated classroom rates — not from the hotel API</span>
                  <span v-for="night in hotel.nights" :key="night.stay_date" class="night-chip">
                    {{ night.stay_date }}: {{ formatCents(night.nightly_rate_cents) }}/night
                    · {{ night.rooms_available }} rooms
                  </span>
                </div>
              </button>

              <div class="hotel-item-actions">
                <button
                  v-if="!isSaved(hotel)"
                  type="button"
                  class="btn-pill primary"
                  :disabled="pendingActionHotelId === hotel.hotel_id"
                  @click="addToLocal(hotel)"
                >
                  {{ pendingActionHotelId === hotel.hotel_id ? 'Saving…' : 'Add to Local' }}
                </button>
                <button
                  v-else
                  type="button"
                  class="btn-pill danger"
                  :disabled="pendingActionHotelId === hotel.hotel_id"
                  @click="removeFromLocal(hotel)"
                >
                  {{ pendingActionHotelId === hotel.hotel_id ? 'Removing…' : 'Remove from Local' }}
                </button>
              </div>
            </div>
          </li>
        </ul>
      </div>

      <div ref="mapContainer" class="hotel-map" role="application" aria-label="Map of nearby hotels"></div>
    </div>

    <p v-if="location && resultSource === 'api'" class="data-note">
      Hotel data comes from Geoapify, may be incomplete, and is not live bookable availability.
    </p>
    <p v-else-if="location && resultSource === 'local'" class="data-note">
      Showing hotels you've saved for this ZIP. Rates and availability are simulated classroom data, not live
      bookable information.
    </p>
  </section>
</template>

<style scoped>
.card {
  background: var(--bg-panel-translucent);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  box-shadow: var(--card-shadow);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.card h2 {
  margin: 0 0 var(--space-3);
  font-size: 0.98rem;
  font-weight: 600;
  color: var(--text-primary);
}

.icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.zip-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.zip-form {
  display: flex;
  gap: var(--space-3);
  align-items: stretch;
  flex-shrink: 0;
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

.field-zip {
  flex: 0 0 180px;
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

.field-body input {
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

.btn-primary {
  /* 1.2rem (≈19.2px) + font-weight 700 qualifies as WCAG "large text",
     which only needs 3:1 contrast — the gradient's lighter end (#9d5cff)
     clears that but not the stricter 4.5:1 normal-text threshold. */
  background: linear-gradient(135deg, var(--accent-button-start), var(--accent-button-end));
  color: #ffffff;
  border: 1px solid transparent;
  border-radius: var(--radius);
  min-height: var(--min-target);
  padding: 0 var(--space-4);
  font-size: 1.2rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.btn-primary:hover:not(:disabled),
.btn-primary:focus-visible:not(:disabled) {
  box-shadow: var(--button-glow);
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: default;
}

.status-message {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius);
  margin: 0 auto;
  font-size: 0.85rem;
  font-weight: 500;
  max-width: 480px;
}

.status-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.status-icon.spin {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.status-error {
  color: var(--color-danger);
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.status-loading {
  color: var(--text-secondary);
  background: var(--bg-raised);
  border: 1px solid var(--border);
}

.status-empty {
  color: var(--text-secondary);
  background: var(--bg-raised);
  border: 1px solid var(--border);
}

.status-summary {
  color: var(--text-primary);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  flex-wrap: wrap;
}

.status-summary strong {
  color: var(--accent-text);
}

.status-success {
  color: var(--color-success);
  background: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.source-badge {
  display: inline-flex;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.source-local {
  background: rgba(74, 222, 128, 0.14);
  color: var(--color-success);
  border: 1px solid rgba(74, 222, 128, 0.35);
}

.source-api {
  background: rgba(96, 165, 250, 0.14);
  color: var(--accent-secondary);
  border: 1px solid rgba(96, 165, 250, 0.35);
}

.nearby-layout {
  display: flex;
  gap: var(--space-4);
  align-items: stretch;
}

.hotel-list-panel {
  flex: 0 0 38%;
  min-width: 0;
}

.hotel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  height: clamp(360px, 70vh, 640px);
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-raised);
}

.hotel-item {
  width: 100%;
  display: flex;
  align-items: stretch;
  gap: var(--space-2);
  border-left: 3px solid transparent;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.hotel-list li:last-child .hotel-item {
  border-bottom: none;
}

.hotel-item:hover {
  background: var(--bg-panel);
}

.hotel-item-selected {
  background: rgba(139, 92, 246, 0.1);
  border-left-color: var(--accent);
}

.hotel-item-select {
  flex: 1;
  min-width: 0;
  min-height: var(--min-target);
  text-align: left;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: var(--text-primary);
}

.hotel-item-row1 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.hotel-item-name {
  font-weight: 600;
  font-size: 0.92rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotel-item-address {
  font-size: 0.78rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotel-item-distance {
  font-size: 0.76rem;
  color: var(--accent-text);
  white-space: nowrap;
  flex-shrink: 0;
}

.hotel-item-nights {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: var(--space-1);
  padding-top: var(--space-1);
  border-top: 1px dashed var(--border);
}

.nights-label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-warning);
  font-weight: 700;
}

.night-chip {
  font-size: 0.76rem;
  color: var(--text-secondary);
}

.hotel-item-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: var(--space-2);
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
  white-space: nowrap;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.btn-pill.primary {
  color: var(--accent-text);
  border-color: rgba(139, 92, 246, 0.4);
}

.btn-pill.primary:hover:not(:disabled) {
  background: rgba(139, 92, 246, 0.12);
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

.hotel-map {
  flex: 1;
  min-width: 0;
  height: clamp(360px, 70vh, 640px);
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
}

.data-note {
  margin-top: var(--space-3);
  margin-bottom: 0;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

/* Darken only the raster tile layer — markers, popups, and the
   attribution control live in separate Leaflet panes and are untouched. */
.hotel-map :deep(.leaflet-tile-pane) {
  filter: invert(0.88) hue-rotate(180deg) brightness(0.95) saturate(0.6) contrast(0.92);
}

.hotel-map :deep(.leaflet-container) {
  background: var(--bg-raised);
  font-family: var(--font-body);
}

.hotel-map :deep(.map-marker-dot) {
  display: block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  background: var(--accent);
}

.hotel-map :deep(.map-marker-center .map-marker-dot) {
  width: 14px;
  height: 14px;
  border: 2px solid var(--text-primary);
  background: transparent;
}

.hotel-map :deep(.map-marker-hotel.marker-selected .map-marker-dot) {
  width: 15px;
  height: 15px;
  border: 2px solid var(--text-primary);
  background: var(--accent);
}

.hotel-map :deep(.leaflet-popup-content-wrapper) {
  background: var(--bg-panel);
  color: var(--text-primary);
  border: 1px solid var(--border);
  box-shadow: var(--card-shadow);
  border-radius: var(--radius);
}

.hotel-map :deep(.leaflet-popup-tip) {
  background: var(--bg-panel);
  border: 1px solid var(--border);
}

.hotel-map :deep(.leaflet-popup-content) {
  font-family: var(--font-body);
  font-weight: 500;
  margin: var(--space-2) var(--space-3);
}

.hotel-map :deep(.leaflet-popup-close-button) {
  color: var(--text-secondary);
}

.hotel-map :deep(.leaflet-popup-close-button:hover) {
  color: var(--text-primary);
}

.hotel-map :deep(.leaflet-control-attribution) {
  background: rgba(11, 11, 16, 0.8);
  color: var(--text-secondary);
}

.hotel-map :deep(.leaflet-control-attribution a) {
  color: var(--accent-text);
}

.hotel-map :deep(.leaflet-control-zoom a) {
  background: var(--bg-panel);
  color: var(--text-primary);
  border-color: var(--border);
}

.hotel-map :deep(.leaflet-control-zoom a:hover) {
  background: var(--bg-raised);
}

.hotel-map :deep(.leaflet-control-zoom a:focus-visible) {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

@media (max-width: 900px) {
  .nearby-layout {
    flex-direction: column;
  }

  /* flex: 1 expands to flex-basis: 0%, which wins over an explicit
     height on the main axis in a column flex container — that left the
     map rendering at ~2px tall. flex: none makes both panels size from
     their own explicit height instead. */
  .hotel-list-panel,
  .hotel-map {
    flex: none;
  }

  .hotel-list,
  .hotel-map {
    height: 45vh;
  }
}

@media (max-width: 640px) {
  .zip-form {
    flex-direction: column;
  }

  .field-zip {
    flex: 1;
  }

  .card {
    padding: var(--space-3);
  }

  .status-message {
    min-width: 100%;
  }
}
</style>
