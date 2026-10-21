import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { FilterSidebar } from '../components/FilterSidebar';

const renderFilters = (isOpenMobile: boolean) => renderToStaticMarkup(
  <FilterSidebar
    department="all" setDepartment={() => undefined}
    category="all" setCategory={() => undefined} categories={[]}
    brand="all" setBrand={() => undefined} brands={[]}
    size="all" setSize={() => undefined} sizes={[]}
    maxPrice={1500} setMaxPrice={() => undefined}
    sortBy="default" setSortBy={() => undefined}
    onClearAll={() => undefined}
    isOpenMobile={isOpenMobile}
    onCloseMobile={() => undefined}
  />
);

describe('mobile product filters', () => {
  it('keeps the Apply Filters button outside the scrollable drawer content', () => {
    const html = renderFilters(true);
    expect(html).toContain('data-testid="mobile-filter-backdrop"');
    expect(html).toContain('role="dialog"');
    expect(html).toContain('h-[100dvh]');
    expect(html).toContain('min-h-0 flex-1 overflow-y-auto');
    expect(html).toContain('shrink-0');
    expect(html).toContain('safe-area-inset-bottom');
    expect(html).toContain('Apply Filters');
  });

  it('renders no dialog while closed', () => {
    expect(renderFilters(false)).not.toContain('role="dialog"');
  });
});
