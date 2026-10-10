import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Hotspot, SnapshotHotspot } from '../types/contract'
import { markerSvg, type Level } from './levels'

const DELHI_CENTER: [number, number] = [28.62, 77.2]

const icons = new Map<string, L.DivIcon>()
function iconFor(level: Level, selected: boolean, pumped: boolean): L.DivIcon {
  const key = `${level}|${selected}|${pumped}`
  let icon = icons.get(key)
  if (!icon) {
    const size = selected ? 30 : 22
    const classes = ['wl-marker', `wl-marker-${level.toLowerCase()}`]
    if (selected) classes.push('wl-marker-selected')
    if (pumped) classes.push('wl-marker-pumped')
    icon = L.divIcon({
      html: markerSvg(level, size),
      className: classes.join(' '),
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    })
    icons.set(key, icon)
  }
  return icon
}

export interface ReportPin {
  hotspot_id: string
  label: string
}

interface Props {
  hotspots: Hotspot[]
  scores: Map<string, SnapshotHotspot>
  selectedId?: string | null
  onSelect?: (id: string) => void
  pumpsById?: Map<string, number>
  reports?: ReportPin[]
}

export function HotspotMap({ hotspots, scores, selectedId, onSelect, pumpsById, reports }: Props) {
  const byId = new Map(hotspots.map((h) => [h.hotspot_id, h]))
  return (
    <MapContainer center={DELHI_CENTER} zoom={11} className="wl-map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {reports?.map((r) => {
        const h = byId.get(r.hotspot_id)
        if (!h) return null
        return (
          <CircleMarker
            key={`report-${r.hotspot_id}`}
            center={[h.lat, h.lon]}
            radius={18}
            pathOptions={{ className: 'wl-report-ring', color: '#1f5fbf', weight: 3, dashArray: '4 4', fill: false }}
          >
            <Tooltip>{r.label}</Tooltip>
          </CircleMarker>
        )
      })}
      {hotspots.map((h) => {
        const level = scores.get(h.hotspot_id)?.level ?? 'LOW'
        const pumps = pumpsById?.get(h.hotspot_id) ?? 0
        const selected = selectedId === h.hotspot_id
        return (
          <Marker
            key={h.hotspot_id}
            position={[h.lat, h.lon]}
            icon={iconFor(level, selected, pumps > 0)}
            title={`${h.name_en}: ${level}`}
            zIndexOffset={selected ? 1000 : 0}
            eventHandlers={{ click: () => onSelect?.(h.hotspot_id) }}
          >
            <Tooltip>
              {h.name_en} · {level}
              {pumps > 0 ? ` · ${pumps} pump${pumps > 1 ? 's' : ''}` : ''}
            </Tooltip>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
