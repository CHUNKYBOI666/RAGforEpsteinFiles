const STORAGE_KEY = 'archive_device_id';

function randomUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Returns a persistent device id (UUID) for anonymous session ownership.
 * Stored in localStorage under archive_device_id; created once per browser/device.
 */
export function getDeviceId(): string {
  if (typeof window === 'undefined') return randomUUID();
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
      id = randomUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return randomUUID();
  }
}
