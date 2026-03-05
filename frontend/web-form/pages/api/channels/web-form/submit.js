export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  const { name, email, subject, category, priority, message } = req.body;

  if (!name || !email || !subject || !message) {
    return res.status(400).json({ detail: 'Missing required fields' });
  }

  // Generate a mock ticket ID
  const ticketId = 'TKT-' + Math.random().toString(36).substring(2, 8).toUpperCase();

  return res.status(200).json({
    ticket_id: ticketId,
    status: 'open',
    message: 'Your support request has been received.',
  });
}
