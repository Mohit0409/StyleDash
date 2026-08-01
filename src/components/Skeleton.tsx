import React from 'react'

const SkeletonCard: React.FC = () => (
  <div className="bg-white dark:bg-gray-800 rounded-2xl overflow-hidden shadow-sm border border-gray-100 dark:border-gray-700 animate-pulse">
    <div className="h-36 bg-gray-200 dark:bg-gray-700" />
    <div className="p-3 space-y-2">
      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/5" />
      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
      <div className="flex justify-between mt-3">
        <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
        <div className="h-7 bg-gray-200 dark:bg-gray-700 rounded-xl w-16" />
      </div>
    </div>
  </div>
)

export const SkeletonGrid: React.FC<{ count?: number }> = ({ count = 8 }) => (
  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
    {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
  </div>
)

export default SkeletonCard
