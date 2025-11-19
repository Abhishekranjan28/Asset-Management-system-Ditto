export type ImageRow = {
  id: number
  camera_id: string
  image_url: string | null
  lat: number
  lon: number
  captured_at: string
  processed: boolean
  changed: boolean
  reason: string
  caption: string
}

export type RoadPoint = {
  id: string
  lat: number
  lng: number
  order?: number
  title?: string
  subtitle?: string
  time?: string
  iconText?: string
  meta?: Record<string, any>
}
