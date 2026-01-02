/**
 * Billing API client for Stripe integration.
 */

import apiClient from './client';

export interface BillingStatus {
  plan_type: string;
  is_paid: boolean;
  paid_at: string | null;
  urls_limit: number | null;
  urls_viewed: number;
  urls_remaining: number | null;
  spots_remaining: number;
  can_upgrade: boolean;
}

export interface CheckoutSession {
  checkout_url: string;
  session_id: string;
}

export interface SpotsRemaining {
  spots_remaining: number;
  max_spots: number;
  spots_claimed: number;
}

/**
 * Get current user's billing status.
 */
export async function getBillingStatus(): Promise<BillingStatus> {
  const response = await apiClient.get<BillingStatus>('/api/v1/billing/status');
  return response.data;
}

/**
 * Create a Stripe checkout session for upgrade.
 */
export async function createCheckoutSession(
  successUrl: string,
  cancelUrl: string
): Promise<CheckoutSession> {
  const response = await apiClient.post<CheckoutSession>('/api/v1/billing/checkout', {
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  return response.data;
}

/**
 * Get remaining paid spots (public endpoint).
 */
export async function getSpotsRemaining(): Promise<SpotsRemaining> {
  const response = await apiClient.get<SpotsRemaining>('/api/v1/billing/spots-remaining');
  return response.data;
}
