import { getServerBackendUrl } from '../../../../lib/serverBackendUrl';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  const { name, email, subject, category, priority, message } = req.body;

  if (!name || !email || !subject || !message) {
    return res.status(400).json({ detail: 'Missing required fields' });
  }

  const backendUrl = getServerBackendUrl();
  
  try {
    const response = await fetch(`${backendUrl}/channels/web-form/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, email, subject, category, priority, message }),
    });

    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Backend error:', error);
    // Fallback mock response if backend is unavailable
    const ticketId = 'TKT-' + Math.random().toString(36).substring(2, 8).toUpperCase();
    return res.status(200).json({
      ticket_id: ticketId,
      status: 'open',
      message: 'Your support request has been received (using mock).',
    });
  }
}
