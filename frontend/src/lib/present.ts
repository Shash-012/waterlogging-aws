// ?present=1 is the video-recording mode: larger type, no dev controls, and the
// headline replay preloaded. ?event=<event_id> picks a different replay.
export const HEADLINE_EVENT = '2026-08-25'

export interface PresentMode {
  present: boolean
  eventId: string | null
}

export function readPresentMode(search: string): PresentMode {
  const params = new URLSearchParams(search)
  const present = params.get('present') === '1'
  return {
    present,
    eventId: params.get('event') ?? (present ? HEADLINE_EVENT : null),
  }
}
