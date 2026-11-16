/**
 * Client Authentication Helper for AI Clipper Pro
 * Retrieves or registers a valid JWT bearer token with the backend.
 */

export async function getValidAuthToken(): Promise<string> {
  if (typeof window === 'undefined') {
    return '';
  }

  // 1. Check existing stored token
  const existingToken = localStorage.getItem('access_token');
  if (existingToken && existingToken !== 'local_dev_token') {
    return existingToken;
  }

  // 2. Obtain fresh token from backend /api/v1/auth
  try {
    const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'demo@aiclipper.pro',
        password: 'Password123!',
      }),
    });

    if (loginRes.ok) {
      const data = await loginRes.json();
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        return data.access_token;
      }
    }

    // Register if account doesn't exist
    const regRes = await fetch('http://localhost:8000/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'demo@aiclipper.pro',
        password: 'Password123!',
        full_name: 'Demo Creator',
      }),
    });

    if (regRes.ok) {
      const data = await regRes.json();
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        return data.access_token;
      }
    }
  } catch (err) {
    console.warn('Backend authentication unreachable, falling back to local simulation mode.');
  }

  return 'local_dev_token';
}
