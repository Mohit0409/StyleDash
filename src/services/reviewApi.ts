import { Review } from '../types';
import { apiFetch, apiJson } from './apiClient';

export type ReviewSort = 'newest' | 'highest' | 'lowest';

export interface ReviewSummary {
  rating: number;
  reviewCount: number;
}

export interface ProductReviews extends ReviewSummary {
  productId: string;
  distribution: Record<string, number>;
  reviews: Review[];
}

export interface ReviewEligibility {
  eligible: boolean;
  orderId: string | null;
  existingReview: Review | null;
  reason: string | null;
}

export interface ReviewDraft {
  rating: number;
  title?: string;
  comment: string;
}

export const reviewApi = {
  async list(productId: string, sort: ReviewSort = 'newest'): Promise<ProductReviews> {
    const query = new URLSearchParams({ productId, sort });
    return apiFetch<{ success: true } & ProductReviews>(`/api/reviews?${query.toString()}`);
  },
  async summaries(productIds: string[]): Promise<Record<string, ReviewSummary>> {
    const query = new URLSearchParams();
    productIds.forEach(id => query.append('productId', id));
    return (await apiFetch<{ success: true; summaries: Record<string, ReviewSummary> }>(
      `/api/reviews/summaries?${query.toString()}`,
    )).summaries;
  },

  async eligibility(productId: string): Promise<ReviewEligibility> {
    const query = new URLSearchParams({ productId });
    return apiFetch<{ success: true } & ReviewEligibility>(`/api/reviews/eligibility?${query.toString()}`);
  },

  async create(productId: string, draft: ReviewDraft): Promise<Review> {
    return (await apiJson<{ success: true; review: Review }>('/api/reviews', 'POST', {
      productId,
      ...draft,
    })).review;
  },

  async edit(reviewId: string, draft: ReviewDraft): Promise<Review> {
    return (await apiJson<{ success: true; review: Review }>(
      `/api/reviews/${encodeURIComponent(reviewId)}/edit`, 'POST', draft,
    )).review;
  },

  async delete(reviewId: string): Promise<void> {
    await apiJson<{ success: true }>(
      `/api/reviews/${encodeURIComponent(reviewId)}/delete`, 'POST', {},
    );
  },
};
