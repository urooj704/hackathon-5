import { getServerBackendUrl } from '../../../../../lib/serverBackendUrl';

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  const { id } = req.query;

  if (!id) {
    return res.status(400).json({ detail: 'Missing ticket ID' });
  }

  const backendUrl = getServerBackendUrl();
  
  try {
    const response = await fetch(`${backendUrl}/channels/web-form/ticket/${id}`);
    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Backend error:', error);
    // Fallback mock response
    return res.status(200).json({
      ticket_id: id,
      status: 'processing',
      message: 'Processing your request...',
      messages: [],
    });
  }
}
