import axios from 'axios';
import { Event } from '../types';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export async function ingestEvent(event: Partial<Event>, token?: string): Promise<void> {
  await axios.post(`${baseURL}/events`, event, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}
