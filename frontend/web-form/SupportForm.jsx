/**
 * FlowForge Support Form — Embeddable React Component
 *
 * Usage:
 *   import SupportForm from './SupportForm';
 *   <SupportForm apiEndpoint="https://api.yourapp.com/channels/web-form/submit" />
 *
 * Features:
 *   - Client-side validation
 *   - Category + priority selection
 *   - Real-time character count
 *   - Ticket ID display on success
 *   - Ticket status polling
 *   - Accessible (ARIA labels, keyboard nav)
 *   - Tailwind CSS styling (or use SupportForm.css for standalone)
 */

import React, { useState, useEffect, useCallback } from 'react';

// ─── Constants ─────────────────────────────────────────────────────────────

const CATEGORIES = [
  { value: 'general',   label: 'General Question' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'billing',   label: 'Billing Inquiry' },
  { value: 'bug_report',label: 'Bug Report' },
  { value: 'feedback',  label: 'Feedback' },
];

const PRIORITIES = [
  { value: 'low',    label: '🟢 Low — Not urgent' },
  { value: 'medium', label: '🟡 Medium — Need help soon' },
  { value: 'high',   label: '🔴 High — Urgent issue' },
];

const INITIAL_FORM = {
  name:     '',
  email:    '',
  subject:  '',
  category: 'general',
  priority: 'medium',
  message:  '',
};

const MAX_MESSAGE_LENGTH = 1000;

// ─── Validation ────────────────────────────────────────────────────────────

function validateForm(data) {
  if (data.name.trim().length < 2)
    return 'Please enter your name (at least 2 characters).';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))
    return 'Please enter a valid email address.';
  if (data.subject.trim().length < 5)
    return 'Subject must be at least 5 characters.';
  if (data.message.trim().length < 10)
    return 'Please describe your issue in more detail (at least 10 characters).';
  if (data.message.length > MAX_MESSAGE_LENGTH)
    return `Message must be under ${MAX_MESSAGE_LENGTH} characters.`;
  return null;
}

// ─── Sub-components ────────────────────────────────────────────────────────

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
    >
      <span className="font-medium">⚠️ Error: </span>{message}
    </div>
  );
}

function SuccessView({ ticketId, onReset }) {
  const [status, setStatus] = useState('processing');
  const [agentReply, setAgentReply] = useState(null);

  // Poll for agent response every 5 seconds
  useEffect(() => {
    if (!ticketId) return;
    let tries = 0;
    const maxTries = 24; // 2 minutes

    const interval = setInterval(async () => {
      tries++;
      try {
        const apiBase = window.__SUPPORT_API_ENDPOINT__ || '/channels/web-form';
        const res = await fetch(`${apiBase}/ticket/${ticketId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'resolved' || data.status === 'waiting_customer') {
            setStatus('replied');
            const messages = data.messages || [];
            const agentMsg = messages.find(m => !m.is_from_customer);
            if (agentMsg) setAgentReply(agentMsg.body);
            clearInterval(interval);
          } else if (data.status === 'escalated') {
            setStatus('escalated');
            clearInterval(interval);
          }
        }
      } catch {
        // Silent fail — keep polling
      }
      if (tries >= maxTries) clearInterval(interval);
    }, 5000);

    return () => clearInterval(interval);
  }, [ticketId]);

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-md text-center">
      {/* Success icon */}
      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-2">Request Submitted!</h2>
      <p className="text-gray-600 mb-4">
        Your support request has been received. Our AI assistant is working on it now.
      </p>

      {/* Ticket ID */}
      <div className="bg-gray-50 rounded-lg p-4 mb-4 inline-block min-w-48">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Your Ticket ID</p>
        <p className="text-lg font-mono font-bold text-gray-900">{ticketId}</p>
      </div>

      {/* Status indicator */}
      <div className="mb-6">
        {status === 'processing' && (
          <div className="flex items-center justify-center text-blue-600 text-sm">
            <svg className="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            AI assistant is reviewing your request...
          </div>
        )}
        {status === 'replied' && agentReply && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-left">
            <p className="text-xs text-blue-600 font-medium uppercase tracking-wide mb-2">
              FlowForge AI Support
            </p>
            <p className="text-gray-700 text-sm whitespace-pre-wrap">{agentReply}</p>
          </div>
        )}
        {status === 'escalated' && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
            🔔 Your request has been escalated to our human support team.
            They will follow up via email shortly.
          </div>
        )}
      </div>

      <button
        onClick={onReset}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
      >
        Submit Another Request
      </button>
    </div>
  );
}

// ─── Main Form Component ───────────────────────────────────────────────────

export default function SupportForm({
  apiEndpoint = '/channels/web-form/submit',
  companyName = 'FlowForge',
  primaryColor = '#2563eb',
}) {
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [status, setStatus] = useState('idle');  // idle | submitting | success | error
  const [ticketId, setTicketId] = useState(null);
  const [error, setError] = useState(null);

  // Store API endpoint globally for status polling
  useEffect(() => {
    const base = apiEndpoint.replace('/submit', '');
    window.__SUPPORT_API_ENDPOINT__ = base;
  }, [apiEndpoint]);

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (error) setError(null);
  }, [error]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const validationError = validateForm(formData);
    if (validationError) {
      setError(validationError);
      return;
    }

    setStatus('submitting');

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setTicketId(data.ticket_id);
      setStatus('success');
    } catch (err) {
      setError(err.message || 'Submission failed. Please try again.');
      setStatus('error');
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setFormData(INITIAL_FORM);
    setTicketId(null);
    setError(null);
  };

  if (status === 'success') {
    return <SuccessView ticketId={ticketId} onReset={handleReset} />;
  }

  const isSubmitting = status === 'submitting';
  const msgLength = formData.message.length;
  const msgLengthColor = msgLength > MAX_MESSAGE_LENGTH * 0.9
    ? 'text-red-500'
    : msgLength > MAX_MESSAGE_LENGTH * 0.7
    ? 'text-yellow-600'
    : 'text-gray-400';

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-md">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Contact Support</h2>
        <p className="text-gray-500 mt-1 text-sm">
          Fill out the form below. Our AI-powered assistant responds within 5 minutes.
        </p>
      </div>

      <ErrorBanner message={error} />

      <form onSubmit={handleSubmit} noValidate className="space-y-5">

        {/* Name + Email row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              Your Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              disabled={isSubmitting}
              placeholder="Jane Doe"
              autoComplete="name"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email Address <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              disabled={isSubmitting}
              placeholder="jane@company.com"
              autoComplete="email"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>
        </div>

        {/* Subject */}
        <div>
          <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">
            Subject <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="subject"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            disabled={isSubmitting}
            placeholder="Brief description of your issue"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
          />
        </div>

        {/* Category + Priority row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
              Category <span className="text-red-500">*</span>
            </label>
            <select
              id="category"
              name="category"
              value={formData.category}
              onChange={handleChange}
              disabled={isSubmitting}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 bg-white"
            >
              {CATEGORIES.map(cat => (
                <option key={cat.value} value={cat.value}>{cat.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">
              Priority
            </label>
            <select
              id="priority"
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              disabled={isSubmitting}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 bg-white"
            >
              {PRIORITIES.map(pri => (
                <option key={pri.value} value={pri.value}>{pri.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Message */}
        <div>
          <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
            How can we help? <span className="text-red-500">*</span>
          </label>
          <textarea
            id="message"
            name="message"
            value={formData.message}
            onChange={handleChange}
            disabled={isSubmitting}
            rows={6}
            maxLength={MAX_MESSAGE_LENGTH}
            placeholder="Please describe your issue or question in detail. Include any error messages or steps to reproduce the problem."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 resize-none"
          />
          <div className={`mt-1 text-xs text-right ${msgLengthColor}`}>
            {msgLength}/{MAX_MESSAGE_LENGTH}
          </div>
        </div>

        {/* Info note */}
        <div className="flex items-start p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
          <svg className="w-4 h-4 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span>Our AI assistant typically responds within <strong>5 minutes</strong>. For urgent issues, select High priority.</span>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className={`w-full py-3 px-4 rounded-lg font-medium text-white text-sm transition-all ${
            isSubmitting
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-sm hover:shadow-md'
          }`}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Submitting...
            </span>
          ) : (
            'Submit Support Request'
          )}
        </button>

        <p className="text-center text-xs text-gray-400">
          By submitting, you agree to our{' '}
          <a href="/privacy" className="text-blue-500 hover:underline">Privacy Policy</a>.
          {' '}Your information is used only to resolve your support request.
        </p>
      </form>
    </div>
  );
}
