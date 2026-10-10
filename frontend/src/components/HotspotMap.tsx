import L from 'leaflet'
import { MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Hotspot, SnapshotHotspot } from '../types/contract'
import { markerSvg, type Level } from './levels'

const DELHI_CENTER: [number, number] = [28.62, 77.2]

const icons = new Map<Level, L.DivIcon>()
function iconFor(level: Level): L.DivIcon {
  let icon = icons.get(level)
  if (!icon) {
    icon = L.divIcon({
      html: markerSvg(level),
      className: `wl-marker wl-marker-${level.toLowerCase()}`,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    })
    icons.set(level, icon)
  }
  return icon
}

interface Props {
  hotspots: Hotspot[]
  scores: Map<string, SnapshotHotspot>
}

export function HotspotMap({ hotspots, scores }: Props) {
  return (
    <MapContainer center={DELHI_CENTER} zoom={11} className="wl-map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {hotspots.map((h) => {
        const level = scores.get(h.hotspot_id)?.level ?? 'LOW'
        return (
          <Marker
            key={h.hotspot_id}
            position={[h.lat, h.lon]}
            icon={iconFor(level)}
            title={`${h.name_en}: ${level}`}
          >
            <Tooltip>
              {h.name_en} · {level}
            </Tooltip>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
